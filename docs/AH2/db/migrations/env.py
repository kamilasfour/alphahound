"""Alembic environment for the AH2 (alphahound2) database.

Connection info comes from AH2_DATABASE_URL in C:\\alphahound_project\\.env
(created by ../create_database.py) — never hard-coded here, and never
committed anywhere (.env is gitignored).

Supports both:
- Offline mode (`alembic upgrade head --sql`): generates SQL without a
  live connection. Used by tests/test_db_migrations.py, which has no
  network path to the real Postgres server.
- Online mode (`alembic upgrade head`): applies migrations for real.
"""
from __future__ import annotations

import os
from pathlib import Path

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import engine_from_config, pool

config = context.config
target_metadata = None  # Raw SQL migrations (op.execute) — no ORM models to autogenerate from.

ENV_PATH = Path(r"C:\alphahound_project\.env")


def _get_database_url() -> str:
    # Explicit env var (e.g. set by a test or CI) wins; otherwise read .env.
    url = os.environ.get("AH2_DATABASE_URL")
    if url:
        return url
    if ENV_PATH.exists():
        url = dotenv_values(str(ENV_PATH)).get("AH2_DATABASE_URL")
        if url:
            return url
    # Offline SQL generation (used by tests) doesn't need a real,
    # reachable database — a syntactically valid placeholder URL is
    # enough for Alembic to render the SQL without connecting.
    if context.is_offline_mode():
        return "postgresql://placeholder:placeholder@localhost/alphahound2"
    raise RuntimeError(
        "AH2_DATABASE_URL not found in the environment or in "
        f"{ENV_PATH}. Run create_database.py first."
    )


def run_migrations_offline() -> None:
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
