-- ============================================================
-- AlphaHound schema — chunk 9
-- Sprint 5: price context + 4 new adapters + Congress kind
-- Run AFTER chunks 1–8. Safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- 1. price_snapshots
--    Stores OHLCV + computed change metrics per ticker per run.
--    NOT a raw_posts replacement — price is context, not content.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_snapshots (
    time            TIMESTAMPTZ     NOT NULL,
    entity_id       UUID            NOT NULL REFERENCES entities(entity_id),
    price           DOUBLE PRECISION NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    volume          BIGINT,
    change_1d_pct   DOUBLE PRECISION,
    change_5d_pct   DOUBLE PRECISION,
    change_vs_spy   DOUBLE PRECISION,
    PRIMARY KEY (entity_id, time)
);

SELECT create_hypertable(
    'price_snapshots', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_price_entity_time
    ON price_snapshots (entity_id, time DESC);

-- ------------------------------------------------------------
-- 2. institutional_positions — add 'Congress' to kind CHECK
--    Drop the old constraint by name, re-add with Congress included.
--    The constraint name follows Postgres auto-naming convention.
-- ------------------------------------------------------------
ALTER TABLE institutional_positions
    DROP CONSTRAINT IF EXISTS institutional_positions_kind_check;

ALTER TABLE institutional_positions
    ADD CONSTRAINT institutional_positions_kind_check
    CHECK (kind IN ('13F', '13D', '13G', 'Form4', 'Congress'));

-- ------------------------------------------------------------
-- 3. Seed new source_adapters (Sprint 5)
-- ------------------------------------------------------------

-- Massive (price snapshots — does not write to raw_posts)
INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.massive',
    'stocks',
    'price_data',
    'A',
    'Massive (formerly Polygon.io) Stocks Starter plan — $29/mo, personal research use, https://massive.com/terms',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier         = EXCLUDED.tier,
        tos_basis    = EXCLUDED.tos_basis,
        enabled      = true;

-- Finnhub (social sentiment + news headlines)
INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.finnhub',
    'stocks',
    'retail_social',
    'C',
    'Finnhub free tier — https://finnhub.io/terms (personal/non-commercial, attribution required)',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier         = EXCLUDED.tier,
        tos_basis    = EXCLUDED.tos_basis,
        enabled      = true;

-- Alpha Vantage (news sentiment + earnings transcripts)
INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.alpha_vantage',
    'stocks',
    'analyst_curated',
    'B',
    'Alpha Vantage free tier — https://www.alphavantage.co/terms_of_service/ (personal research use, Stage 1 only)',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier         = EXCLUDED.tier,
        tos_basis    = EXCLUDED.tos_basis,
        enabled      = true;

-- Quiver (congressional trades)
INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.quiver',
    'stocks',
    'institutional_flow',
    'B',
    'Quiver Quantitative Hobbyist plan — $30/mo, personal research use, https://api.quiverquant.com/terms',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier         = EXCLUDED.tier,
        tos_basis    = EXCLUDED.tos_basis,
        enabled      = true;

-- ------------------------------------------------------------
-- Verification queries (run after applying to confirm state)
-- ------------------------------------------------------------
-- SELECT table_name FROM timescaledb_information.hypertables ORDER BY 1;
-- SELECT adapter_id, source_class, tier, enabled FROM source_adapters ORDER BY adapter_id;
-- \d institutional_positions
-- SELECT COUNT(*) FROM price_snapshots;
