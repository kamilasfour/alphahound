"""Live verification for STEP 7B: counts rows in raw_source_events,
evidence, and audit_events, and spot-checks one row for correlation-ID
tracing across all three tables plus timestamp/provenance preservation.

Usage (from docs/AH2/db/):
    python verify_yahoo_ingestion.py
"""
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ENV_PATH = Path(r"C:\alphahound_project\.env")


def main() -> None:
    env = dotenv_values(str(ENV_PATH))
    url = env["AH2_DATABASE_URL"]
    conn = psycopg2.connect(url)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM raw_source_events WHERE data_source = 'yahoo_finance';")
            raw_count = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM evidence WHERE evidence_type = 'news_headline';")
            evidence_count = cur.fetchone()[0]

            cur.execute(
                "SELECT count(*) FROM audit_events WHERE event_type = 'DATA_RECEIVED' "
                "AND payload->>'data_source' = 'yahoo_finance';"
            )
            audit_count = cur.fetchone()[0]

            print(f"raw_source_events (yahoo_finance): {raw_count}")
            print(f"evidence (news_headline):          {evidence_count}")
            print(f"audit_events (DATA_RECEIVED):       {audit_count}")

            print("\n--- Spot-check: one full row, tracing correlation_id/event_id ---")
            cur.execute(
                """
                SELECT r.id, r.event_id, r.correlation_id, r.data_source,
                       r.source_record_id, r.received_at, r.created_at
                FROM raw_source_events r
                WHERE r.data_source = 'yahoo_finance'
                ORDER BY r.id DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
            if row is None:
                print("No rows found.")
                return
            raw_id, event_id, correlation_id, data_source, source_record_id, received_at, row_created_at = row
            print(f"raw_source_events.id={raw_id} event_id={event_id} correlation_id={correlation_id}")
            print(f"  data_source={data_source} source_record_id={source_record_id}")
            print(f"  received_at (source timestamp)={received_at}")
            print(f"  created_at (row insert time)={row_created_at}")

            cur.execute(
                "SELECT id, event_id, correlation_id, ticker, structured_fields->>'title' "
                "FROM evidence WHERE raw_source_event_id = %s;",
                (raw_id,),
            )
            evidence_row = cur.fetchone()
            print(f"\nMatching evidence row: {evidence_row}")
            if evidence_row and evidence_row[2] != correlation_id:
                print("  *** CORRELATION ID MISMATCH between raw_source_events and evidence! ***")
            elif evidence_row:
                print("  correlation_id matches raw_source_events: OK")

            cur.execute(
                "SELECT event_id, correlation_id, event_type, payload, reference_ids "
                "FROM audit_events WHERE event_id = %s;",
                (event_id,),
            )
            audit_row = cur.fetchone()
            print(f"\nMatching audit_events row: {audit_row}")
            if audit_row and audit_row[1] != correlation_id:
                print("  *** CORRELATION ID MISMATCH between raw_source_events and audit_events! ***")
            elif audit_row:
                print("  correlation_id matches raw_source_events: OK")
                print("  event_id matches raw_source_events: OK" if audit_row[0] == event_id else "  *** EVENT ID MISMATCH ***")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
