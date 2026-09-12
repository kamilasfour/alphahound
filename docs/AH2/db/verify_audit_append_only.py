"""Verifies the audit_events append-only trigger actually blocks UPDATE
and DELETE, by inserting a throwaway row and attempting both — each
should raise, and the row should still be there afterward unchanged.

Usage (from docs/AH2/db/):
    python verify_audit_append_only.py
"""
import uuid
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ENV_PATH = Path(r"C:\alphahound_project\.env")


def main() -> None:
    env = dotenv_values(str(ENV_PATH))
    url = env["AH2_DATABASE_URL"]
    conn = psycopg2.connect(url)
    conn.autocommit = True
    test_event_id = str(uuid.uuid4())

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_events
                    (event_id, correlation_id, event_type, schema_version,
                     source, event_created_at, payload)
                VALUES (%s, %s, 'TEST_APPEND_ONLY_CHECK', '1.0',
                        'verify_audit_append_only.py', now(), '{}'::jsonb)
                """,
                (test_event_id, str(uuid.uuid4())),
            )
            print("Inserted a throwaway test row — OK (insert should always work).")

            try:
                cur.execute(
                    "UPDATE audit_events SET event_type = 'CHANGED' WHERE event_id = %s",
                    (test_event_id,),
                )
                print("UPDATE succeeded — THIS IS WRONG, the trigger did not block it.")
            except psycopg2.Error as exc:
                print(f"UPDATE correctly blocked: {exc.pgerror.strip()}")

            try:
                cur.execute("DELETE FROM audit_events WHERE event_id = %s", (test_event_id,))
                print("DELETE succeeded — THIS IS WRONG, the trigger did not block it.")
            except psycopg2.Error as exc:
                print(f"DELETE correctly blocked: {exc.pgerror.strip()}")

            cur.execute(
                "SELECT event_type FROM audit_events WHERE event_id = %s", (test_event_id,)
            )
            row = cur.fetchone()
            print(f"\nRow still present with original event_type: {row[0] if row else '(MISSING!)'}")
            print(
                "\nNote: this test row (event_type=TEST_APPEND_ONLY_CHECK) is now "
                "permanently in audit_events, by design — it cannot be deleted. "
                "This is expected and fine for a dev-stage verification."
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
