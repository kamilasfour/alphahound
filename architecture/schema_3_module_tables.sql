-- ============================================================
-- AlphaHound schema — chunk 3 of 4
-- Trade log, prediction markets, stock-module tables
-- Run AFTER chunk 2. Safe to re-run.
-- ============================================================

-- trade_log: the legal-evidence artifact for the proof campaign.
CREATE TABLE IF NOT EXISTS trade_log (
    time        TIMESTAMPTZ NOT NULL,
    trade_id    UUID NOT NULL DEFAULT gen_random_uuid(),
    module_id   TEXT NOT NULL REFERENCES modules(module_id),
    signal_id   UUID,
    entity_id   UUID NOT NULL REFERENCES entities(entity_id),
    side        TEXT NOT NULL CHECK (side IN ('buy','sell','short','cover','bet_yes','bet_no')),
    size        DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION,
    venue       TEXT NOT NULL,
    pnl         DOUBLE PRECISION,
    notes       TEXT,
    PRIMARY KEY (trade_id, time)
);
SELECT create_hypertable(
    'trade_log', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- prediction_market_prices: Kalshi / Polymarket probabilities.
CREATE TABLE IF NOT EXISTS prediction_market_prices (
    time                TIMESTAMPTZ NOT NULL,
    market_id           TEXT NOT NULL,
    venue               TEXT NOT NULL,
    probability         DOUBLE PRECISION NOT NULL CHECK (probability BETWEEN 0 AND 1),
    tickers_linked      TEXT[],
    PRIMARY KEY (venue, market_id, time)
);
SELECT create_hypertable(
    'prediction_market_prices', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- options_flow: stock-module-specific.
CREATE TABLE IF NOT EXISTS options_flow (
    time            TIMESTAMPTZ NOT NULL,
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    strike          DOUBLE PRECISION NOT NULL,
    expiry          DATE NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('call','put')),
    premium         DOUBLE PRECISION NOT NULL,
    sweep_flag      BOOLEAN NOT NULL DEFAULT false,
    raw             JSONB,
    PRIMARY KEY (entity_id, time, strike, expiry, side)
);
SELECT create_hypertable(
    'options_flow', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- institutional_positions: SEC filings (13F, 13D, 13G, Form 4).
CREATE TABLE IF NOT EXISTS institutional_positions (
    filing_id       TEXT PRIMARY KEY,
    filer           TEXT NOT NULL,
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    shares          BIGINT NOT NULL,
    filed_at        TIMESTAMPTZ NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('13F','13D','13G','Form4'))
);
CREATE INDEX IF NOT EXISTS idx_inst_entity_filed
    ON institutional_positions (entity_id, filed_at DESC);

-- historical_events: Rhyme Engine corpus.
CREATE TABLE IF NOT EXISTS historical_events (
    event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   TEXT NOT NULL REFERENCES modules(module_id),
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    start_time  TIMESTAMPTZ NOT NULL,
    phases      JSONB NOT NULL,
    series      JSONB
);
CREATE INDEX IF NOT EXISTS idx_hist_module_kind
    ON historical_events (module_id, kind);
