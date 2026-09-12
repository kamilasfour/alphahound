"""Yahoo Finance ingestion orchestration — the business logic behind the
AH2 Yahoo Finance timer trigger.

Pipeline per article: normalize (already done by the client) -> persist
raw_source_events (idempotency boundary) -> persist evidence -> persist
audit_events -> build a DATA_RECEIVED AH2Event for the trigger to publish
to Service Bus. A duplicate article (same data_source + source_record_id)
stops at the first step — no evidence, audit_events, or Service Bus
message is created for it, so re-running the same fetch never produces
duplicate downstream records anywhere in the pipeline.

Kept free of any azure.functions trigger/binding types so it is fully
unit-testable without the Functions runtime (matches the STEP 4B
architecture pattern).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

from domain.events import SCHEMA_VERSION, AH2Event
from infrastructure.db import audit_events_repo, evidence_repo, raw_source_events_repo
from infrastructure.db.connection import get_connection
from infrastructure.sources.yahoo_finance_client import NormalizedYahooArticle, fetch_all
from infrastructure.configuration.settings import AH2_SOURCE_NAME
from shared.ids import new_id

log = logging.getLogger(__name__)

EVENT_TYPE = "DATA_RECEIVED"
DATA_SOURCE = "yahoo_finance"
EVIDENCE_TYPE = "news_headline"


@dataclass(frozen=True)
class IngestionRunResult:
    events_to_publish: List[AH2Event] = field(default_factory=list)
    new_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0


def run_yahoo_ingestion() -> IngestionRunResult:
    """Fetch, normalize, and idempotently persist Yahoo Finance headlines.

    Returns the DATA_RECEIVED events for genuinely-new articles, ready
    for the caller to publish to Service Bus, plus run statistics.
    """
    events: List[AH2Event] = []
    new_count = 0
    duplicate_count = 0
    error_count = 0

    conn = get_connection()
    try:
        for article in fetch_all():
            try:
                result = _ingest_one_article(conn, article)
            except Exception:
                conn.rollback()
                error_count += 1
                log.exception(
                    "Yahoo ingestion: unexpected error persisting %s:%s",
                    article.ticker, article.guid,
                )
                continue

            if result is None:
                duplicate_count += 1
                continue

            events.append(result)
            new_count += 1
    finally:
        conn.close()

    log.info(
        "Yahoo ingestion run complete: %d new, %d duplicate, %d error",
        new_count, duplicate_count, error_count,
    )
    return IngestionRunResult(
        events_to_publish=events,
        new_count=new_count,
        duplicate_count=duplicate_count,
        error_count=error_count,
    )


def _ingest_one_article(conn, article: NormalizedYahooArticle) -> AH2Event | None:
    """Persist one article idempotently. Returns the DATA_RECEIVED event
    if this article was genuinely new, or None if it was a duplicate
    (in which case nothing was written and the caller must not publish
    anything for it)."""
    event_id = new_id()
    correlation_id = new_id()

    raw_source_event_id = raw_source_events_repo.insert_if_new(
        conn,
        event_id=event_id,
        correlation_id=correlation_id,
        data_source=DATA_SOURCE,
        source_record_id=article.source_record_id,
        raw_data_ref=f"yahoo_rss:{article.source_record_id}",
        received_at=article.published_at,
    )

    if raw_source_event_id is None:
        # Duplicate — (data_source, source_record_id) already exists.
        # Stop here: no evidence, no audit_events, no DATA_RECEIVED
        # message for this article.
        conn.rollback()
        return None

    structured_fields = {
        "title": article.title,
        "description": article.description,
        "text": article.text,
        "link": article.link,
        "guid": article.guid,
        "source": DATA_SOURCE,
    }
    evidence_id = evidence_repo.insert(
        conn,
        event_id=new_id(),
        correlation_id=correlation_id,
        raw_source_event_id=raw_source_event_id,
        evidence_type=EVIDENCE_TYPE,
        ticker=article.ticker,
        structured_fields=structured_fields,
    )

    source = f"{AH2_SOURCE_NAME}:yahoo_finance_timer"
    reference_ids = {
        "raw_source_event_id": raw_source_event_id,
        "evidence_id": evidence_id,
    }
    # Per STEP 6A Program Manager decision: audit payload holds only
    # structured, decision-reconstruction-relevant fields — the full
    # article text lives in evidence.structured_fields, not duplicated
    # here.
    audit_payload = {
        "data_source": DATA_SOURCE,
        "ticker": article.ticker,
        "guid": article.guid,
        "title": article.title,
    }
    audit_events_repo.insert(
        conn,
        event_id=event_id,
        correlation_id=correlation_id,
        event_type=EVENT_TYPE,
        schema_version=SCHEMA_VERSION,
        source=source,
        event_created_at=article.observed_at,
        payload=audit_payload,
        reference_ids=reference_ids,
    )

    conn.commit()

    event_payload = dict(audit_payload)
    event_payload["reference_ids"] = reference_ids
    return AH2Event(
        event_id=event_id,
        event_type=EVENT_TYPE,
        correlation_id=correlation_id,
        source=source,
        created_at=article.observed_at.isoformat(),
        schema_version=SCHEMA_VERSION,
        payload=event_payload,
    )
