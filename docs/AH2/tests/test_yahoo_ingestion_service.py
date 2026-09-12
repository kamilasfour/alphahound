"""Tests for application.yahoo_ingestion_service — idempotency,
duplicate-ingestion handling, correlation-ID propagation, audit_events
creation discipline, DATA_RECEIVED event construction, timestamp/
provenance preservation, and DB persistence service call sequencing.

All PostgreSQL and HTTP access is mocked here — this environment has no
network path to the real database or to Yahoo Finance. Live end-to-end
verification (real DB rows, real Service Bus delivery) happens
separately against the deployed Function App — see
docs/AH2/docs/AH2_DEV_ENVIRONMENT.md STEP 7B.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import application.yahoo_ingestion_service as svc
from domain.events import AH2Event
from infrastructure.sources.yahoo_finance_client import NormalizedYahooArticle


def _article(
    ticker="AAPL",
    guid="g1",
    title="Headline",
    description="Desc",
    published_at=None,
    observed_at=None,
) -> NormalizedYahooArticle:
    default_time = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    return NormalizedYahooArticle(
        ticker=ticker,
        guid=guid,
        title=title,
        description=description,
        text=f"{title}. {description}" if description else title,
        link=f"https://finance.yahoo.com/{ticker}",
        published_at=published_at or default_time,
        observed_at=observed_at or default_time,
    )


def test_new_article_creates_raw_source_event_evidence_audit_and_returns_event():
    article = _article()
    mock_conn = MagicMock()

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", return_value=42) as mock_raw, \
         patch.object(svc.evidence_repo, "insert", return_value=99) as mock_evidence, \
         patch.object(svc.audit_events_repo, "insert") as mock_audit:
        result = svc.run_yahoo_ingestion()

    assert result.new_count == 1
    assert result.duplicate_count == 0
    assert result.error_count == 0
    assert len(result.events_to_publish) == 1

    event = result.events_to_publish[0]
    assert event.event_type == "DATA_RECEIVED"
    assert event.payload["ticker"] == "AAPL"

    mock_raw.assert_called_once()
    mock_evidence.assert_called_once()
    mock_audit.assert_called_once()
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()


def test_duplicate_article_creates_no_evidence_no_audit_no_event():
    article = _article()
    mock_conn = MagicMock()

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", return_value=None), \
         patch.object(svc.evidence_repo, "insert") as mock_evidence, \
         patch.object(svc.audit_events_repo, "insert") as mock_audit:
        result = svc.run_yahoo_ingestion()

    assert result.new_count == 0
    assert result.duplicate_count == 1
    assert result.events_to_publish == []
    mock_evidence.assert_not_called()
    mock_audit.assert_not_called()
    mock_conn.rollback.assert_called()


def test_second_run_of_the_same_article_reports_duplicate_not_a_new_event():
    """Simulates re-running ingestion twice with the same article — the
    second run's raw_source_events insert reports a conflict (as the
    real UNIQUE(data_source, source_record_id) + ON CONFLICT DO NOTHING
    would), and must not create a duplicate evidence/audit_events/
    DATA_RECEIVED anywhere."""
    article = _article()

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=MagicMock()), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", return_value=1), \
         patch.object(svc.evidence_repo, "insert", return_value=1), \
         patch.object(svc.audit_events_repo, "insert"):
        first_result = svc.run_yahoo_ingestion()

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=MagicMock()), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", return_value=None), \
         patch.object(svc.evidence_repo, "insert") as mock_evidence_2, \
         patch.object(svc.audit_events_repo, "insert") as mock_audit_2:
        second_result = svc.run_yahoo_ingestion()

    assert first_result.new_count == 1
    assert second_result.new_count == 0
    assert second_result.duplicate_count == 1
    mock_evidence_2.assert_not_called()
    mock_audit_2.assert_not_called()


def test_correlation_id_is_identical_across_raw_source_event_evidence_and_audit():
    article = _article()
    mock_conn = MagicMock()
    captured = {}

    def fake_raw_insert(conn, **kwargs):
        captured["raw_correlation_id"] = kwargs["correlation_id"]
        captured["event_id"] = kwargs["event_id"]
        return 1

    def fake_evidence_insert(conn, **kwargs):
        captured["evidence_correlation_id"] = kwargs["correlation_id"]
        return 1

    def fake_audit_insert(conn, **kwargs):
        captured["audit_correlation_id"] = kwargs["correlation_id"]
        captured["audit_event_id"] = kwargs["event_id"]

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", side_effect=fake_raw_insert), \
         patch.object(svc.evidence_repo, "insert", side_effect=fake_evidence_insert), \
         patch.object(svc.audit_events_repo, "insert", side_effect=fake_audit_insert):
        result = svc.run_yahoo_ingestion()

    event = result.events_to_publish[0]
    assert captured["raw_correlation_id"] == captured["evidence_correlation_id"] == captured["audit_correlation_id"]
    assert captured["raw_correlation_id"] == event.correlation_id
    assert captured["event_id"] == captured["audit_event_id"] == event.event_id


def test_published_at_timestamp_is_preserved_through_to_raw_source_event():
    published = datetime(2025, 3, 4, 8, 30, 0, tzinfo=timezone.utc)
    observed = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    article = _article(published_at=published, observed_at=observed)
    mock_conn = MagicMock()
    captured = {}

    def fake_raw_insert(conn, **kwargs):
        captured["received_at"] = kwargs["received_at"]
        return 1

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", side_effect=fake_raw_insert), \
         patch.object(svc.evidence_repo, "insert", return_value=1), \
         patch.object(svc.audit_events_repo, "insert"):
        result = svc.run_yahoo_ingestion()

    # raw_source_events.received_at must be the article's original
    # source-provided published_at, not the fetch/observation time.
    assert captured["received_at"] == published
    event = result.events_to_publish[0]
    assert event.created_at == observed.isoformat()


def test_audit_event_payload_contains_only_structured_reconstruction_fields():
    long_description = "A long description that should not be duplicated into the audit log. " * 5
    article = _article(description=long_description)
    mock_conn = MagicMock()
    captured = {}

    def fake_audit_insert(conn, **kwargs):
        captured["payload"] = kwargs["payload"]
        captured["reference_ids"] = kwargs["reference_ids"]
        captured["event_type"] = kwargs["event_type"]

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", return_value=1), \
         patch.object(svc.evidence_repo, "insert", return_value=7), \
         patch.object(svc.audit_events_repo, "insert", side_effect=fake_audit_insert):
        svc.run_yahoo_ingestion()

    assert captured["event_type"] == "DATA_RECEIVED"
    # STEP 6A Program Manager decision: audit payload holds structured
    # decision-reconstruction fields only — the full article body lives
    # in evidence.structured_fields, not duplicated into audit_events.
    assert "description" not in captured["payload"]
    assert captured["payload"]["ticker"] == "AAPL"
    assert captured["payload"]["guid"] == "g1"
    assert captured["reference_ids"] == {"raw_source_event_id": 1, "evidence_id": 7}


def test_data_received_event_is_a_well_formed_ah2_event():
    article = _article()
    mock_conn = MagicMock()

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", return_value=1), \
         patch.object(svc.evidence_repo, "insert", return_value=1), \
         patch.object(svc.audit_events_repo, "insert"):
        result = svc.run_yahoo_ingestion()

    event = result.events_to_publish[0]
    restored = AH2Event.from_json(event.to_json())
    assert restored == event
    assert event.event_type == "DATA_RECEIVED"
    assert event.source.endswith(":yahoo_finance_timer")


def test_unexpected_persistence_error_is_counted_and_does_not_raise():
    article = _article()
    mock_conn = MagicMock()

    with patch.object(svc, "fetch_all", return_value=[article]), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", side_effect=RuntimeError("db exploded")):
        result = svc.run_yahoo_ingestion()

    assert result.error_count == 1
    assert result.new_count == 0
    assert result.events_to_publish == []
    mock_conn.rollback.assert_called()
    mock_conn.close.assert_called_once()


def test_multiple_articles_each_get_independent_correlation_ids():
    articles = [_article(ticker="AAPL", guid="a1"), _article(ticker="TSLA", guid="t1")]
    mock_conn = MagicMock()

    with patch.object(svc, "fetch_all", return_value=articles), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", side_effect=[1, 2]), \
         patch.object(svc.evidence_repo, "insert", side_effect=[1, 2]), \
         patch.object(svc.audit_events_repo, "insert"):
        result = svc.run_yahoo_ingestion()

    assert len(result.events_to_publish) == 2
    correlation_ids = {e.correlation_id for e in result.events_to_publish}
    assert len(correlation_ids) == 2  # each article starts its own correlation chain


def test_connection_is_always_closed_even_when_all_articles_are_duplicates():
    articles = [_article(ticker="AAPL", guid="a1"), _article(ticker="TSLA", guid="t1")]
    mock_conn = MagicMock()

    with patch.object(svc, "fetch_all", return_value=articles), \
         patch.object(svc, "get_connection", return_value=mock_conn), \
         patch.object(svc.raw_source_events_repo, "insert_if_new", return_value=None), \
         patch.object(svc.evidence_repo, "insert") as mock_evidence, \
         patch.object(svc.audit_events_repo, "insert") as mock_audit:
        result = svc.run_yahoo_ingestion()

    assert result.duplicate_count == 2
    assert result.events_to_publish == []
    mock_evidence.assert_not_called()
    mock_audit.assert_not_called()
    mock_conn.close.assert_called_once()
