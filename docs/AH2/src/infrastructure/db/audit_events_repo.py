"""Repository for audit_events — the durable, append-only authoritative
audit record (Program Manager decision, STEP 6 / STEP 6A).

Per STEP 6A's Program Manager decisions: payload here holds only
structured decision-reconstruction data (identifying fields), not large
raw content — the full article text lives in `evidence.structured_fields`,
not duplicated here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import psycopg2
from psycopg2.extras import Json


def insert(
    conn: "psycopg2.extensions.connection",
    *,
    event_id: str,
    correlation_id: str,
    event_type: str,
    schema_version: str,
    source: str,
    event_created_at: datetime,
    payload: Dict[str, Any],
    reference_ids: Dict[str, Any],
) -> None:
    """Insert an audit_events row. ON CONFLICT (event_id) DO NOTHING is
    defense-in-depth only, matching the pattern in evidence_repo — under
    normal operation this is called exactly once per new event_id.

    Note: audit_events is append-only at the database level (a trigger
    rejects UPDATE/DELETE — see docs/AH2/docs/DATA_ARCHITECTURE.md §3.1).
    This function only ever INSERTs.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_events
                (event_id, correlation_id, event_type, schema_version,
                 source, event_created_at, payload, reference_ids)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING;
            """,
            (
                event_id, correlation_id, event_type, schema_version,
                source, event_created_at, Json(payload), Json(reference_ids),
            ),
        )
