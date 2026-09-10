-- ============================================================
-- AlphaHound schema — chunk 10
-- Sprint 6: options_flow table, kalshi_contracts table,
--           Unusual Whales + Kalshi adapter seeds
-- Run AFTER chunks 1–9. Safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- 1. options_flow
--    Stores unusual options activity per ticker per event.
--    Separate from raw_posts — options data has structured fields
--    (strike, expiry, call/put, premium) that don't fit text-sentiment.
--    Rule-based scorer maps each row to a polarity score directly.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS options_flow (
    time            TIMESTAMPTZ     NOT NULL,
    entity_id       UUID            NOT NULL REFERENCES entities(entity_id),
    adapter_id      TEXT            NOT NULL REFERENCES source_adapters(adapter_id),
    external_id     TEXT            NOT NULL,               -- stable dedup key from UW
    ticker          TEXT            NOT NULL,
    expiry          DATE,                                   -- option expiration date
    strike          DOUBLE PRECISION,                       -- strike price
    contract_type   TEXT            NOT NULL                -- 'call' or 'put'
                    CHECK (contract_type IN ('call', 'put')),
    sentiment       TEXT            NOT NULL                -- 'bullish', 'bearish', 'neutral'
                    CHECK (sentiment IN ('bullish', 'bearish', 'neutral')),
    premium         DOUBLE PRECISION,                       -- total premium ($)
    volume          BIGINT,                                 -- contract volume
    open_interest   BIGINT,                                 -- open interest
    volume_oi_ratio DOUBLE PRECISION,                       -- volume / open_interest
    unusual_score   DOUBLE PRECISION,                       -- UW's own unusualness score 0-100
    raw             JSONB,                                  -- full UW response
    observed_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, time, external_id)
);

SELECT create_hypertable(
    'options_flow', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_options_flow_dedup
    ON options_flow (adapter_id, external_id, entity_id, time);

CREATE INDEX IF NOT EXISTS idx_options_flow_entity_time
    ON options_flow (entity_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_options_flow_ticker_time
    ON options_flow (ticker, time DESC);

-- ------------------------------------------------------------
-- 2. kalshi_contracts
--    Stores prediction market contract state per ticker per run.
--    yes_price = implied probability of YES resolution (0-100).
--    We map yes_price to polarity: (yes_price - 50) / 50 → [-1, 1].
--    Contracts are resolved_at when the market closes.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kalshi_contracts (
    time            TIMESTAMPTZ     NOT NULL,
    entity_id       UUID            NOT NULL REFERENCES entities(entity_id),
    contract_id     TEXT            NOT NULL,               -- Kalshi market ticker (e.g. KXNVDA-25DEC31-T500)
    title           TEXT            NOT NULL,               -- human-readable description
    yes_price       DOUBLE PRECISION NOT NULL               -- cents (0-100), implied probability
                    CHECK (yes_price BETWEEN 0 AND 100),
    no_price        DOUBLE PRECISION                        -- cents (0-100)
                    CHECK (no_price BETWEEN 0 AND 100),
    volume_24h      BIGINT,                                 -- 24h contract volume
    open_interest   BIGINT,
    close_time      TIMESTAMPTZ,                            -- when the market resolves
    resolved        BOOLEAN         NOT NULL DEFAULT false,
    resolution      TEXT,                                   -- 'yes', 'no', null if open
    raw             JSONB,
    observed_at     TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, contract_id, time)
);

SELECT create_hypertable(
    'kalshi_contracts', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_kalshi_entity_time
    ON kalshi_contracts (entity_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_kalshi_contract_time
    ON kalshi_contracts (contract_id, time DESC);

-- ------------------------------------------------------------
-- 3. Seed new source_adapters (Sprint 6)
-- ------------------------------------------------------------

-- Unusual Whales (options flow — writes to options_flow table)
INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.unusual_whales',
    'stocks',
    'options_flow',
    'A',
    'Unusual Whales API Basic plan — $125/mo, personal research use, https://unusualwhales.com/terms',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier         = EXCLUDED.tier,
        tos_basis    = EXCLUDED.tos_basis,
        enabled      = true;

-- Kalshi (prediction markets — writes to kalshi_contracts table)
INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.kalshi',
    'stocks',
    'prediction_market',
    'B',
    'Kalshi public API — free, personal research use, https://kalshi.com/terms',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier         = EXCLUDED.tier,
        tos_basis    = EXCLUDED.tos_basis,
        enabled      = true;

-- ------------------------------------------------------------
-- Verification queries
-- ------------------------------------------------------------
-- SELECT hypertable_name FROM timescaledb_information.hypertables ORDER BY 1;
-- SELECT adapter_id, source_class, tier, enabled FROM source_adapters ORDER BY adapter_id;
-- \d options_flow
-- \d kalshi_contracts
