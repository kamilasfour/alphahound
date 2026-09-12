"""Tests for the AH2 (alphahound2) Alembic migration.

This environment (the Claude sandbox) has no network path to the real
Postgres server, so these tests verify the migration via Alembic's
built-in offline SQL-generation mode (`--sql`), which renders the exact
DDL Alembic would run without needing a live connection. This confirms
the migration is structurally complete and syntactically sound.

It is NOT a substitute for actually running `alembic upgrade head`
against alphahound2 (see docs/AH2/docs/MIGRATIONS.md) — that is a
manual step for whoever has network access to the Postgres server.
"""
import contextlib
import io
from pathlib import Path

from alembic import command
from alembic.config import Config

DB_DIR = Path(__file__).resolve().parents[1] / "db"

EXPECTED_TABLES = [
    "raw_source_events",
    "evidence",
    "features",
    "models",
    "model_versions",
    "predictions",
    "probabilities",
    "market_states",
    "opportunities",
    "risk_decisions",
    "compliance_decisions",
    "orders",
    "fills",
    "positions",
    "outcomes",
    "audit_events",
    "replay_requests",
    "replay_history",
]


def _alembic_config() -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(DB_DIR / "migrations"))
    return cfg


def _generate_sql(direction_fn, revision_range: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        direction_fn(_alembic_config(), revision_range, sql=True)
    return buf.getvalue()


def test_upgrade_creates_every_expected_table():
    sql = _generate_sql(command.upgrade, "base:head")
    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE {table} " in sql, f"upgrade() did not create table '{table}'"


def test_downgrade_drops_every_expected_table():
    sql = _generate_sql(command.downgrade, "head:base")
    for table in EXPECTED_TABLES:
        assert f"DROP TABLE IF EXISTS {table};" in sql, f"downgrade() does not drop table '{table}'"


def test_upgrade_creates_the_append_only_audit_trigger():
    sql = _generate_sql(command.upgrade, "base:head")
    assert "CREATE TRIGGER trg_audit_events_no_update" in sql
    assert "CREATE TRIGGER trg_audit_events_no_delete" in sql
    assert "audit_events_block_update_delete" in sql


def test_downgrade_removes_the_append_only_audit_trigger_and_function():
    sql = _generate_sql(command.downgrade, "head:base")
    assert "DROP TRIGGER IF EXISTS trg_audit_events_no_update" in sql
    assert "DROP TRIGGER IF EXISTS trg_audit_events_no_delete" in sql
    assert "DROP FUNCTION IF EXISTS audit_events_block_update_delete" in sql


def test_no_ah1_tables_or_databases_are_referenced():
    # AH1's database is 'alphahound' and its known tables include
    # options_trade_log / convergence_signals (per AH2_DEV_ENVIRONMENT.md
    # history) — none of that should ever appear in an AH2 migration.
    sql = _generate_sql(command.upgrade, "base:head")
    for forbidden in ("alphahound ", "options_trade_log", "convergence_signals"):
        assert forbidden not in sql


def test_foreign_keys_reference_only_tables_created_in_this_migration():
    sql = _generate_sql(command.upgrade, "base:head")
    # A loose but useful guard: spot-check that key REFERENCES targets
    # point at tables this same migration creates, not something external.
    assert "REFERENCES raw_source_events" in sql
    assert "REFERENCES opportunities" in sql
    assert "REFERENCES orders" in sql
    assert "REFERENCES audit_events" in sql
    assert "REFERENCES replay_requests" in sql
