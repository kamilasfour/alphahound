"""Repository for evidence — normalized data derived from a raw_source_events row.

Only called after raw_source_events_repo.insert_if_new() confirms the
source row is genuinely new (see that module's docstring for the
idempotency boundary this depends on).
"""
from __future__ import annotations

from typing import Any, Dict

import psycopg2
from psycopg2.extras import Json


def insert(
    conn: "psycopg2.extensions.connection",
    *,
    event_id: str,
    correlation_id: str,
    raw_source_event_id: int,
    evidence_type: str,
    ticker: str,
    structured_fields: Dict[str, Any],
) -> int:
    """Insert an evidence row. Returns the new row's id.

    ON CONFLICT (event_id) DO NOTHING is defense-in-depth only — under
    normal operation this is called exactly once per new
    raw_source_events row, since the caller already checked for a
    duplicate before reaching here.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO evidence
                (event_id, correlation_id, raw_source_event_id, evidence_type,
                 ticker, structured_fields)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            RETURNING id;
            """,
            (event_id, correlation_id, raw_source_event_id, evidence_type, ticker, Json(structured_fields)),
        )
        row = cur.fetchone()
    assert row is not None, "evidence insert unexpectedly conflicted on a fresh event_id"
    return row[0]
