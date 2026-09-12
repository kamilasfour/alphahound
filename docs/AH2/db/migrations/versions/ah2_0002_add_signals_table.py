"""AH2 Step 6A: first-class signals table + FK-backed references.

Additive follow-up to ah2_0001. Adds:
- signals — a proper table for SIGNAL_DETECTED, previously unmodeled
  (STEP 6's table list didn't include one; probabilities only stored a
  bare UUID array of contributing signal event IDs with no table to
  reference).
- probability_signals — junction table giving `probabilities` a real,
  FK-enforced many-to-many link to `signals`.
- opportunity_signals — same, for `opportunities`.

Nothing existing is altered or dropped. `probabilities.contributing_signal_event_ids`
is left in place unchanged as a legacy/fallback column for any signal
that predates having a real `signals` row — see
docs/AH2/docs/DATA_ARCHITECTURE.md.

Revision ID: ah2_0002
Revises: ah2_0001
Create Date: 2026-09-12
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "ah2_0002"
down_revision = "ah2_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- signals (maps to SIGNAL_DETECTED) ----------------------------
    op.execute("""
        CREATE TABLE signals (
            id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            signal_id               UUID NOT NULL UNIQUE,
            event_id                UUID NOT NULL UNIQUE,
            correlation_id          UUID NOT NULL,
            signal_type             TEXT NOT NULL,
            ticker                  TEXT,
            direction               TEXT,
            score                   DOUBLE PRECISION,
            pillars                 TEXT[] NOT NULL DEFAULT '{}',
            convergence_metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
            source_evidence_ids     BIGINT[] NOT NULL DEFAULT '{}',
            source_feature_ids      BIGINT[] NOT NULL DEFAULT '{}',
            catalyst_ref            TEXT,
            catalyst_details        JSONB NOT NULL DEFAULT '{}'::jsonb,
            schema_version          TEXT NOT NULL DEFAULT '1.0',
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at              TIMESTAMPTZ
        );
    """)
    op.execute("CREATE INDEX ix_signals_ticker ON signals (ticker);")
    op.execute("CREATE INDEX ix_signals_signal_type ON signals (signal_type);")
    op.execute("CREATE INDEX ix_signals_correlation_id ON signals (correlation_id);")
    op.execute("CREATE INDEX ix_signals_created_at ON signals (created_at);")
    op.execute("CREATE INDEX ix_signals_expires_at ON signals (expires_at) WHERE expires_at IS NOT NULL;")
    op.execute("CREATE INDEX ix_signals_convergence_metadata_gin ON signals USING gin (convergence_metadata);")
    op.execute("CREATE INDEX ix_signals_catalyst_details_gin ON signals USING gin (catalyst_details);")

    # ---- probability_signals (junction: probabilities <-> signals) --
    op.execute("""
        CREATE TABLE probability_signals (
            probability_id    BIGINT NOT NULL REFERENCES probabilities (id),
            signal_id         BIGINT NOT NULL REFERENCES signals (id),
            PRIMARY KEY (probability_id, signal_id)
        );
    """)
    op.execute("CREATE INDEX ix_probability_signals_signal_id ON probability_signals (signal_id);")

    # ---- opportunity_signals (junction: opportunities <-> signals) --
    # References opportunities(opportunity_id) — the UUID business key —
    # matching how risk_decisions/compliance_decisions/orders already
    # reference opportunities, for consistency.
    op.execute("""
        CREATE TABLE opportunity_signals (
            opportunity_id    UUID NOT NULL REFERENCES opportunities (opportunity_id),
            signal_id         BIGINT NOT NULL REFERENCES signals (id),
            PRIMARY KEY (opportunity_id, signal_id)
        );
    """)
    op.execute("CREATE INDEX ix_opportunity_signals_signal_id ON opportunity_signals (signal_id);")


def downgrade() -> None:
    # Reverse order: junction tables (they reference signals) before signals itself.
    op.execute("DROP TABLE IF EXISTS opportunity_signals;")
    op.execute("DROP TABLE IF EXISTS probability_signals;")
    op.execute("DROP TABLE IF EXISTS signals;")
