"""AH2 Step 6: initial PostgreSQL schema foundation for alphahound2.

Creates all 18 foundation tables (covering the 16 domain areas requested
for STEP 6) on the alphahound2 database. Pure additive DDL — no AH1
tables/databases are touched or referenced.

See docs/AH2/docs/DATA_ARCHITECTURE.md for the full design rationale,
index/access-pattern documentation, and the provenance/idempotency
strategy per table.

Revision ID: ah2_0001
Revises:
Create Date: 2026-09-12
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "ah2_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- 1. raw_source_events ----------------------------------------
    op.execute("""
        CREATE TABLE raw_source_events (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_id            UUID NOT NULL UNIQUE,
            correlation_id      UUID NOT NULL,
            data_source         TEXT NOT NULL,
            source_record_id    TEXT NOT NULL,
            raw_data_ref        TEXT NOT NULL,
            received_at         TIMESTAMPTZ NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (data_source, source_record_id)
        );
    """)
    op.execute("CREATE INDEX ix_raw_source_events_correlation_id ON raw_source_events (correlation_id);")
    op.execute("CREATE INDEX ix_raw_source_events_received_at ON raw_source_events (received_at);")

    # ---- 2. evidence ---------------------------------------------------
    op.execute("""
        CREATE TABLE evidence (
            id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_id               UUID NOT NULL UNIQUE,
            correlation_id         UUID NOT NULL,
            raw_source_event_id    BIGINT NOT NULL REFERENCES raw_source_events (id),
            evidence_type          TEXT NOT NULL,
            ticker                 TEXT NOT NULL,
            structured_fields      JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_evidence_correlation_id ON evidence (correlation_id);")
    op.execute("CREATE INDEX ix_evidence_raw_source_event_id ON evidence (raw_source_event_id);")
    op.execute("CREATE INDEX ix_evidence_ticker ON evidence (ticker);")
    op.execute("CREATE INDEX ix_evidence_evidence_type ON evidence (evidence_type);")
    op.execute("CREATE INDEX ix_evidence_structured_fields_gin ON evidence USING gin (structured_fields);")

    # ---- 3. features -----------------------------------------------------
    op.execute("""
        CREATE TABLE features (
            id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            correlation_id         UUID NOT NULL,
            ticker                 TEXT NOT NULL,
            feature_name           TEXT NOT NULL,
            feature_value          JSONB NOT NULL,
            source_evidence_ids    BIGINT[] NOT NULL DEFAULT '{}',
            computed_at            TIMESTAMPTZ NOT NULL,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (ticker, feature_name, computed_at)
        );
    """)
    op.execute("CREATE INDEX ix_features_ticker_name ON features (ticker, feature_name);")
    op.execute("CREATE INDEX ix_features_computed_at ON features (computed_at);")

    # ---- 4. models / model_versions (model registry) ----------------
    op.execute("""
        CREATE TABLE models (
            id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            model_name     TEXT NOT NULL UNIQUE,
            description    TEXT,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE TABLE model_versions (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            model_id            BIGINT NOT NULL REFERENCES models (id),
            version_label       TEXT NOT NULL,
            artifact_ref        TEXT,
            training_metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active           BOOLEAN NOT NULL DEFAULT false,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (model_id, version_label)
        );
    """)
    op.execute("CREATE INDEX ix_model_versions_model_active ON model_versions (model_id, is_active);")

    # ---- 5. predictions -------------------------------------------------
    op.execute("""
        CREATE TABLE predictions (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            correlation_id      UUID NOT NULL,
            model_version_id    BIGINT NOT NULL REFERENCES model_versions (id),
            ticker              TEXT NOT NULL,
            feature_ids         BIGINT[] NOT NULL DEFAULT '{}',
            raw_output          JSONB NOT NULL,
            predicted_at        TIMESTAMPTZ NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_predictions_ticker_predicted_at ON predictions (ticker, predicted_at);")
    op.execute("CREATE INDEX ix_predictions_model_version_id ON predictions (model_version_id);")

    # ---- 6. probabilities (maps to PROBABILITY_UPDATED) -----------
    op.execute("""
        CREATE TABLE probabilities (
            id                             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_id                       UUID NOT NULL UNIQUE,
            correlation_id                 UUID NOT NULL,
            ticker                         TEXT NOT NULL,
            probability_score              DOUBLE PRECISION NOT NULL
                                           CHECK (probability_score >= 0 AND probability_score <= 1),
            previous_score                 DOUBLE PRECISION,
            contributing_signal_event_ids  UUID[] NOT NULL DEFAULT '{}',
            created_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_probabilities_ticker_created_at ON probabilities (ticker, created_at);")

    # ---- 7. market_states -------------------------------------------
    op.execute("""
        CREATE TABLE market_states (
            id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            correlation_id  UUID,
            state_type      TEXT NOT NULL,
            ticker          TEXT,
            state_value     TEXT NOT NULL,
            state_details   JSONB NOT NULL DEFAULT '{}'::jsonb,
            observed_at     TIMESTAMPTZ NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_market_states_type_observed_at ON market_states (state_type, observed_at);")
    op.execute("""
        CREATE INDEX ix_market_states_ticker_observed_at ON market_states (ticker, observed_at)
        WHERE ticker IS NOT NULL;
    """)

    # ---- 8. opportunities (maps to OPPORTUNITY_DETECTED) -----------
    op.execute("""
        CREATE TABLE opportunities (
            id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            opportunity_id        UUID NOT NULL UNIQUE,
            event_id              UUID NOT NULL UNIQUE,
            correlation_id        UUID NOT NULL,
            ticker                TEXT NOT NULL,
            strategy_type         TEXT NOT NULL,
            probability_id        BIGINT REFERENCES probabilities (id),
            proposed_structure    JSONB NOT NULL,
            status                TEXT NOT NULL DEFAULT 'detected',
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_opportunities_ticker ON opportunities (ticker);")
    op.execute("CREATE INDEX ix_opportunities_status ON opportunities (status);")
    op.execute("CREATE INDEX ix_opportunities_correlation_id ON opportunities (correlation_id);")

    # ---- 9. risk_decisions (maps to RISK_APPROVED / RISK_REJECTED) --
    # NOT BLINDLY REPLAYABLE (Program Manager decision) — see
    # docs/AH2/docs/DATA_ARCHITECTURE.md and EVENT_CONTRACT.md §13.
    op.execute("""
        CREATE TABLE risk_decisions (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_id            UUID NOT NULL UNIQUE,
            correlation_id      UUID NOT NULL,
            opportunity_id      UUID NOT NULL REFERENCES opportunities (opportunity_id),
            decision            TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
            checks_evaluated    JSONB NOT NULL DEFAULT '[]'::jsonb,
            approver            TEXT NOT NULL,
            decided_at          TIMESTAMPTZ NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_risk_decisions_opportunity_id ON risk_decisions (opportunity_id);")
    op.execute("CREATE INDEX ix_risk_decisions_decision_decided_at ON risk_decisions (decision, decided_at);")

    # ---- 10. compliance_decisions -----------------------------------
    # NOT BLINDLY REPLAYABLE (Program Manager decision) — same caution as risk_decisions.
    op.execute("""
        CREATE TABLE compliance_decisions (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_id            UUID NOT NULL UNIQUE,
            correlation_id      UUID NOT NULL,
            opportunity_id      UUID NOT NULL REFERENCES opportunities (opportunity_id),
            decision            TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
            checks_evaluated    JSONB NOT NULL DEFAULT '[]'::jsonb,
            decided_at          TIMESTAMPTZ NOT NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_compliance_decisions_opportunity_id ON compliance_decisions (opportunity_id);")
    op.execute("CREATE INDEX ix_compliance_decisions_decision_decided_at ON compliance_decisions (decision, decided_at);")

    # ---- 11. orders (maps to ORDER_REQUESTED / ORDER_SUBMITTED) -----
    # NOT BLINDLY REPLAYABLE (Program Manager decision) — replay of
    # anything touching this table must never re-trigger a broker call.
    op.execute("""
        CREATE TABLE orders (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_request_id    UUID NOT NULL UNIQUE,
            opportunity_id      UUID NOT NULL REFERENCES opportunities (opportunity_id),
            correlation_id      UUID NOT NULL,
            ticker              TEXT NOT NULL,
            order_legs          JSONB NOT NULL,
            max_contracts       INTEGER NOT NULL,
            broker_order_id     TEXT UNIQUE,
            status              TEXT NOT NULL DEFAULT 'requested'
                                CHECK (status IN ('requested','submitted','filled','partially_filled','cancelled','rejected')),
            requested_at        TIMESTAMPTZ NOT NULL,
            submitted_at        TIMESTAMPTZ,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_orders_opportunity_id ON orders (opportunity_id);")
    op.execute("CREATE INDEX ix_orders_status ON orders (status);")

    # ---- 12. fills (maps to ORDER_FILLED) ----------------------------
    op.execute("""
        CREATE TABLE fills (
            id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            order_id          BIGINT NOT NULL REFERENCES orders (id),
            broker_fill_id    TEXT NOT NULL,
            correlation_id    UUID NOT NULL,
            fill_price        NUMERIC(18,4) NOT NULL,
            fill_quantity     INTEGER NOT NULL,
            filled_at         TIMESTAMPTZ NOT NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (order_id, broker_fill_id)
        );
    """)
    op.execute("CREATE INDEX ix_fills_order_id_filled_at ON fills (order_id, filled_at);")

    # ---- 13. positions (maps to POSITION_CHANGED, append-only history) --
    op.execute("""
        CREATE TABLE positions (
            id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            position_id       UUID NOT NULL,
            version           INTEGER NOT NULL,
            ticker            TEXT NOT NULL,
            change_type       TEXT NOT NULL CHECK (change_type IN ('opened','adjusted','closed')),
            new_quantity      INTEGER NOT NULL,
            correlation_id    UUID NOT NULL,
            changed_at        TIMESTAMPTZ NOT NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (position_id, version)
        );
    """)
    op.execute("CREATE INDEX ix_positions_position_id ON positions (position_id);")
    op.execute("CREATE INDEX ix_positions_ticker_changed_at ON positions (ticker, changed_at);")

    # ---- 14. outcomes (maps to MARKET_RESOLVED / realized results) --
    op.execute("""
        CREATE TABLE outcomes (
            id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_id              UUID UNIQUE,
            correlation_id        UUID,
            market_id             TEXT,
            ticker                TEXT,
            resolution_outcome    JSONB NOT NULL,
            resolved_at           TIMESTAMPTZ NOT NULL,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE UNIQUE INDEX ux_outcomes_market_id ON outcomes (market_id) WHERE market_id IS NOT NULL;")
    op.execute("CREATE INDEX ix_outcomes_ticker_resolved_at ON outcomes (ticker, resolved_at);")

    # ---- 15. audit_events (immutable/append-only, authoritative store) --
    # Application Insights remains observability-only; THIS table is the
    # durable audit record per Program Manager decision. Enforced
    # append-only at the database level via trigger below, not just by
    # application convention.
    op.execute("""
        CREATE TABLE audit_events (
            id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            event_id           UUID NOT NULL UNIQUE,
            correlation_id     UUID NOT NULL,
            event_type         TEXT NOT NULL,
            schema_version     TEXT NOT NULL,
            source             TEXT NOT NULL,
            event_created_at   TIMESTAMPTZ NOT NULL,
            payload            JSONB NOT NULL,
            reference_ids      JSONB NOT NULL DEFAULT '{}'::jsonb,
            recorded_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_audit_events_event_type ON audit_events (event_type);")
    op.execute("CREATE INDEX ix_audit_events_correlation_id ON audit_events (correlation_id);")
    op.execute("CREATE INDEX ix_audit_events_event_created_at ON audit_events (event_created_at);")
    op.execute("CREATE INDEX ix_audit_events_payload_gin ON audit_events USING gin (payload);")
    op.execute("CREATE INDEX ix_audit_events_reference_ids_gin ON audit_events USING gin (reference_ids);")
    op.execute("""
        CREATE FUNCTION audit_events_block_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only: % is not permitted', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_events_no_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_block_update_delete();
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_events_no_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_block_update_delete();
    """)

    # ---- 16. replay_requests / replay_history ------------------------
    # Replay is tracked out-of-band per Program Manager decision — the
    # AH2Event envelope itself gains no is_replay/replay_count field.
    op.execute("""
        CREATE TABLE replay_requests (
            id                                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            replay_request_id                      UUID NOT NULL UNIQUE,
            original_event_id                       UUID NOT NULL REFERENCES audit_events (event_id),
            reason                                  TEXT NOT NULL,
            requested_by                            TEXT NOT NULL,
            requested_at                            TIMESTAMPTZ NOT NULL DEFAULT now(),
            target_workflow                         TEXT NOT NULL,
            target_version                          TEXT,
            status                                  TEXT NOT NULL DEFAULT 'pending'
                                                     CHECK (status IN ('pending','in_progress','completed','failed','blocked')),
            involves_financial_side_effect_types    BOOLEAN NOT NULL DEFAULT false,
            created_at                              TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_replay_requests_original_event_id ON replay_requests (original_event_id);")
    op.execute("CREATE INDEX ix_replay_requests_status ON replay_requests (status);")

    op.execute("""
        CREATE TABLE replay_history (
            id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            replay_request_id      UUID NOT NULL REFERENCES replay_requests (replay_request_id),
            attempt_number         INTEGER NOT NULL,
            outcome                TEXT NOT NULL CHECK (outcome IN ('success','failure','skipped_side_effect_guard')),
            details                JSONB NOT NULL DEFAULT '{}'::jsonb,
            executed_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (replay_request_id, attempt_number)
        );
    """)
    op.execute("CREATE INDEX ix_replay_history_replay_request_id ON replay_history (replay_request_id, executed_at);")


def downgrade() -> None:
    # Reverse dependency order: children before parents.
    op.execute("DROP TABLE IF EXISTS replay_history;")
    op.execute("DROP TABLE IF EXISTS replay_requests;")

    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_delete ON audit_events;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_no_update ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS audit_events_block_update_delete();")
    op.execute("DROP TABLE IF EXISTS audit_events;")

    op.execute("DROP TABLE IF EXISTS outcomes;")
    op.execute("DROP TABLE IF EXISTS positions;")
    op.execute("DROP TABLE IF EXISTS fills;")
    op.execute("DROP TABLE IF EXISTS orders;")
    op.execute("DROP TABLE IF EXISTS compliance_decisions;")
    op.execute("DROP TABLE IF EXISTS risk_decisions;")
    op.execute("DROP TABLE IF EXISTS opportunities;")
    op.execute("DROP TABLE IF EXISTS market_states;")
    op.execute("DROP TABLE IF EXISTS probabilities;")
    op.execute("DROP TABLE IF EXISTS predictions;")
    op.execute("DROP TABLE IF EXISTS model_versions;")
    op.execute("DROP TABLE IF EXISTS models;")
    op.execute("DROP TABLE IF EXISTS features;")
    op.execute("DROP TABLE IF EXISTS evidence;")
    op.execute("DROP TABLE IF EXISTS raw_source_events;")
