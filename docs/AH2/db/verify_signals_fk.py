"""Verifies the STEP 6A junction table foreign keys actually enforce
referential integrity — attempts an insert into probability_signals
referencing a signal_id that does not exist, and confirms Postgres
rejects it.

Usage (from docs/AH2/db/):
    python verify_signals_fk.py
"""
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ENV_PATH = Path(r"C:\alphahound_project\.env")


def main() -> None:
    env = dotenv_values(str(ENV_PATH))
    url = env["AH2_DATABASE_URL"]
    conn = psycopg2.connect(url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            # A probability row must exist to attempt the FK violation
            # against a real target table (probability_signals.probability_id
            # also has its own FK, so we need a genuine probability row).
            cur.execute(
                """
                INSERT INTO probabilities
                    (event_id, correlation_id, ticker, probability_score, created_at)
                VALUES (gen_random_uuid(), gen_random_uuid(), 'FKTEST', 0.5, now())
                RETURNING id
                """
            )
            probability_id = cur.fetchone()[0]
            print(f"Inserted a throwaway probability row (id={probability_id}) to test against.")

            try:
                cur.execute(
                    "INSERT INTO probability_signals (probability_id, signal_id) VALUES (%s, 999999999)",
                    (probability_id,),
                )
                print("INSERT with a non-existent signal_id SUCCEEDED — THIS IS WRONG, the FK did not block it.")
                conn.rollback()
            except psycopg2.errors.ForeignKeyViolation as exc:
                print(f"INSERT correctly blocked by FK constraint: {exc.pgerror.strip()}")
                conn.rollback()  # undo the throwaway probability insert too
                print("Rolled back — no rows left behind.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
