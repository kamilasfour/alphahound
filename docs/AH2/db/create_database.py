"""One-off script: create the `alphahound2` database on the existing
PostgreSQL Flexible Server, without touching the existing `alphahound`
(AH1) database in any way, and without ever printing a password.

This is NOT an Alembic migration — Alembic operates within an existing
database; creating the database itself is a separate, one-time, manual
step (CREATE DATABASE cannot run inside a transaction/migration in
PostgreSQL in the general case, and doing it via a migration would also
require pointing Alembic at a database that doesn't exist yet).

Usage:
    python create_database.py

Reads DATABASE_URL from C:\\alphahound_project\\.env (AH1's existing
connection string — same server, same admin credentials). Connects to
the server's default 'postgres' maintenance database (never to
'alphahound' itself) to run CREATE DATABASE. Idempotent: does nothing if
alphahound2 already exists.

On success, appends AH2_DATABASE_URL to .env (same host/port/user/
password/sslmode as DATABASE_URL, with the database name swapped to
alphahound2) so Alembic's env.py can pick it up. The password is copied
byte-for-byte from the existing .env value — it is read, never displayed,
and never sent anywhere except back into the local .env file.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("Missing dependency: pip install -r requirements.txt (in docs/AH2/db/) first.")
    sys.exit(1)

try:
    from dotenv import dotenv_values
except ImportError:
    print("Missing dependency: pip install -r requirements.txt (in docs/AH2/db/) first.")
    sys.exit(1)

ENV_PATH = Path(r"C:\alphahound_project\.env")
NEW_DB_NAME = "alphahound2"


def _swap_database_name(url: str, new_db_name: str) -> str:
    """Return `url` with only the path component (database name) replaced."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{new_db_name}", parts.query, parts.fragment))


def main() -> None:
    if not ENV_PATH.exists():
        print(f"Expected .env at {ENV_PATH} — not found. Aborting.")
        sys.exit(1)

    env = dotenv_values(str(ENV_PATH))
    database_url = env.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found in .env. Aborting.")
        sys.exit(1)

    maintenance_url = _swap_database_name(database_url, "postgres")

    print("Connecting to the server's maintenance database to check/create "
          f"'{NEW_DB_NAME}' (never touching 'alphahound')...")
    conn = psycopg2.connect(maintenance_url)
    try:
        conn.autocommit = True  # CREATE DATABASE cannot run inside a transaction
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (NEW_DB_NAME,))
            exists = cur.fetchone() is not None
            if exists:
                print(f"Database '{NEW_DB_NAME}' already exists — nothing to do.")
            else:
                cur.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(NEW_DB_NAME))
                )
                print(f"Created database '{NEW_DB_NAME}'.")
    finally:
        conn.close()

    ah2_url = _swap_database_name(database_url, NEW_DB_NAME)
    existing_lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    if any(line.startswith("AH2_DATABASE_URL=") for line in existing_lines):
        print("AH2_DATABASE_URL already present in .env — leaving it as-is.")
    else:
        with ENV_PATH.open("a", encoding="utf-8") as f:
            f.write(f"\nAH2_DATABASE_URL={ah2_url}\n")
        print("Added AH2_DATABASE_URL to .env (derived from DATABASE_URL; "
              "password copied through, never displayed here).")

    print("Done. You can now run: alembic upgrade head")


if __name__ == "__main__":
    main()
