"""Repository for raw_source_events — the DATA_RECEIVED durable record.

The idempotency boundary for the whole ingestion pipeline lives here:
`insert_if_new` returns None when the (data_source, source_record_id)
pair already exists, and the caller (application/yahoo_ingestion_service.py)
is expected to skip creating evidence/audit_events/the DATA_RECEIVED
Service Bus message entirely when that happens — duplicate ingestion of
the same article must not create duplicate downstream records anywhere.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import psycopg2


def insert_if_new(
    conn: "psycopg2.extensions.connection",
    *,
    event_id: str,
    correlation_id: str,
    data_source: str,
    source_record_id: str,
    raw_data_ref: str,
    received_at: datetime,
) -> Optional[int]:
    """Insert a raw_source_events row. Returns the new row's id, or None
    if (data_source, source_record_id) already exists (duplicate —
    caller must not proceed to create evidence/audit/DATA_RECEIVED)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_source_events
                (event_id, correlation_id, data_source, source_record_id,
                 raw_data_ref, received_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (data_source, source_record_id) DO NOTHING
            RETURNING id;
            """,
            (event_id, correlation_id, data_source, source_record_id, raw_data_ref, received_at),
        )
        row = cur.fetchone()
    return row[0] if row else None
