"""Quick verification script: lists all tables in the alphahound2
database, confirming the STEP 6 migration was actually applied.

Usage (from docs/AH2/db/):
    python verify_schema.py
"""
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ENV_PATH = Path(r"C:\alphahound_project\.env")


def main() -> None:
    env = dotenv_values(str(ENV_PATH))
    url = env.get("AH2_DATABASE_URL")
    if not url:
        print("AH2_DATABASE_URL not found in .env — run create_database.py first.")
        return

    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
            )
            tables = [row[0] for row in cur.fetchall()]
            print(f"{len(tables)} table(s) in alphahound2:")
            for t in tables:
                print(f"  - {t}")

            cur.execute("SELECT version_num FROM alembic_version;")
            version = cur.fetchone()
            print(f"\nAlembic version stamp: {version[0] if version else '(none)'}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
