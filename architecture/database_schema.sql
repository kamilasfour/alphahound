-- ============================================================
-- AlphaHound database schema
-- Source: PRD v1.2 §A10.2 (Part A — Engine architecture)
-- Target: PostgreSQL 17 + TimescaleDB (Azure Flexible Server)
-- Idempotent: safe to re-run.
-- ============================================================
--
-- Design notes that diverge or clarify PRD §A10.2:
--   1. `raw_posts` stores BOTH `text` (needed for Tier 1 scoring)
--      AND `text_hash` (for dedup). PRD only shows text_hash; we
--      keep the raw text because FinBERT and Claude need it.
--   2. `raw_posts` denormalizes `source_class` and `tier` from
--      `source_adapters` for query speed. Trade-off: drift if an
--      adapter is retiered. Acceptable — tier changes trigger an
--      audit (PRD §A8.2) so we can backfill.
--   3. Posts that mention N entities are written as N rows (one
--      row per (post, entity)). Simpler than a junction table for
--      now; revisit if posts commonly mention many entities.
--   4. Entity IDs are UUIDs, not symbols. Aliases live in
--      `entity_aliases` with validity windows (PRD §A9.3).
-- ============================================================

-- Extensions -------------------------------------------------
CREATE EXTENSION IF NOT EXISTS timescaledb;
-- pgcrypto is pre-installed on Azure PG 17; gen_random_uuid() is core in PG 13+.

-- ============================================================
-- Engine-level tables (standard Postgres)
-- ============================================================

-- modules: one row per industry module registered with the engine.
CREATE TABLE IF NOT EXISTS modules (
    module_id       TEXT PRIMARY KEY,
    version         TEXT NOT NULL,
    config_hash     TEXT,
    enabled_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- entities: canonical record for every tradable / trackable thing.
CREATE TABLE IF NOT EXISTS entities (
    entity_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id           TEXT NOT NULL REFERENCES modules(module_id),
    canonical_symbol    TEXT NOT NULL,
    kind                TEXT NOT NULL,          -- 'ticker', 'sector', 'etf', 'neighborhood', ...
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (module_id, canonical_symbol, kind)
);
CREATE INDEX IF NOT EXISTS idx_entities_symbol ON entities (module_id, canonical_symbol);

-- entity_aliases: symbol changes, rebrands, redraws.
CREATE TABLE IF NOT EXISTS entity_aliases (
    alias_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    alias           TEXT NOT NULL,
    valid_from      TIMESTAMPTZ NOT NULL,
    valid_to        TIMESTAMPTZ                       -- NULL = currently valid
);
CREATE INDEX IF NOT EXISTS idx_aliases_lookup ON entity_aliases (alias, valid_from);

-- source_adapters: one row per data-source adapter declared by a module.
CREATE TABLE IF NOT EXISTS source_adapters (
    adapter_id      TEXT PRIMARY KEY,                  -- e.g. 'stocks.apewisdom'
    module_id       TEXT NOT NULL REFERENCES modules(module_id),
    source_class    TEXT NOT NULL,                     -- retail_social | institutional_flow | options | prediction_market | analyst_curated | news_wire
    tier            TEXT NOT NULL CHECK (tier IN ('A','B','C','D')),
    tos_basis       TEXT NOT NULL,                     -- cite; PRD §A9.4 requires non-empty
    enabled         BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Event-shaped tables (Timescale hypertables)
-- Partition interval per PRD §A10.2: 7 days on raw_posts, 30 days elsewhere.
-- ============================================================

-- raw_posts: every ingested post, one row per (post, entity).
CREATE TABLE IF NOT EXISTS raw_posts (
    time            TIMESTAMPTZ NOT NULL,
    post_id         UUID NOT NULL DEFAULT gen_random_uuid(),
    adapter_id      TEXT NOT NULL REFERENCES source_adapters(adapter_id),
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    source_class    TEXT NOT NULL,
    tier            TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    author_hash     TEXT,
    text            TEXT NOT NULL,
    text_hash       TEXT NOT NULL,
    raw             JSONB,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, time)
);
-- Dedup: same adapter shouldn't ingest the same external_id twice for the same entity.
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_posts_dedup
    ON raw_posts (adapter_id, external_id, entity_id, time);
CREATE INDEX IF NOT EXISTS idx_raw_posts_entity_time
    ON raw_posts (entity_id, time DESC);

-- Convert to hypertable (idempotent).
SELECT create_hypertable(
    'raw_posts', 'time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- sentiment_scores: FinBERT polarity per (entity, source_class) per tick.
CREATE TABLE IF NOT EXISTS sentiment_scores (
    time            TIMESTAMPTZ NOT NULL,
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    source_class    TEXT NOT NULL,
    polarity        DOUBLE PRECISION NOT NULL,          -- [-1, 1]
    confidence      DOUBLE PRECISION NOT NULL,          -- [0, 1]
    tier            TEXT NOT NULL,
    post_count      INTEGER NOT NULL,
    PRIMARY KEY (entity_id, source_class, time)
);
CREATE INDEX IF NOT EXISTS idx_sentiment_entity_time
    ON sentiment_scores (entity_id, time DESC);
SELECT create_hypertable(
    'sentiment_scores', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- signal_scores: final 1–10 signal with confidence and the weight snapshot used.
CREATE TABLE IF NOT EXISTS signal_scores (
    time                TIMESTAMPTZ NOT NULL,
    entity_id           UUID NOT NULL REFERENCES entities(entity_id),
    signal_1to10        DOUBLE PRECISION NOT NULL CHECK (signal_1to10 BETWEEN 0 AND 10),
    confidence_1to10    DOUBLE PRECISION NOT NULL CHECK (confidence_1to10 BETWEEN 0 AND 10),
    regime              TEXT,
    weights_snapshot    JSONB NOT NULL,
    PRIMARY KEY (entity_id, time)
);
SELECT create_hypertable(
    'signal_scores', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- divergence_events: PRD §A7.1.
CREATE TABLE IF NOT EXISTS divergence_events (
    time            TIMESTAMPTZ NOT NULL,
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    d_value         DOUBLE PRECISION NOT NULL,
    p_value         DOUBLE PRECISION NOT NULL,
    components      JSONB NOT NULL,                     -- class -> sentiment mean used
    PRIMARY KEY (entity_id, time)
);
SELECT create_hypertable(
    'divergence_events', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- rhyme_matches: PRD §A7.3.
CREATE TABLE IF NOT EXISTS rhyme_matches (
    time                TIMESTAMPTZ NOT NULL,
    entity_id           UUID NOT NULL REFERENCES entities(entity_id),
    current_event_id    UUID NOT NULL,
    corpus_event_id     UUID NOT NULL,
    dtw_distance        DOUBLE PRECISION NOT NULL,
    p_value             DOUBLE PRECISION NOT NULL,
    phase_position      JSONB,
    PRIMARY KEY (entity_id, current_event_id, corpus_event_id, time)
);
SELECT create_hypertable(
    'rhyme_matches', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- trade_log: the legal-evidence artifact for the proof campaign.
-- Indefinite retention (PRD §A9.1).
CREATE TABLE IF NOT EXISTS trade_log (
    time        TIMESTAMPTZ NOT NULL,
    trade_id    UUID NOT NULL DEFAULT gen_random_uuid(),
    module_id   TEXT NOT NULL REFERENCES modules(module_id),
    signal_id   UUID,                                   -- nullable: pre-AlphaHound baseline trades
    entity_id   UUID NOT NULL REFERENCES entities(entity_id),
    side        TEXT NOT NULL CHECK (side IN ('buy','sell','short','cover','bet_yes','bet_no')),
    size        DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION,
    venue       TEXT NOT NULL,                          -- 'schwab','merrill','kalshi','polymarket',...
    pnl         DOUBLE PRECISION,                       -- null until closed
    notes       TEXT,
    PRIMARY KEY (trade_id, time)
);
SELECT create_hypertable(
    'trade_log', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- prediction_market_prices: Kalshi / Polymarket probabilities over time.
CREATE TABLE IF NOT EXISTS prediction_market_prices (
    time                TIMESTAMPTZ NOT NULL,
    market_id           TEXT NOT NULL,
    venue               TEXT NOT NULL,                  -- 'kalshi' | 'polymarket'
    probability         DOUBLE PRECISION NOT NULL CHECK (probability BETWEEN 0 AND 1),
    tickers_linked      TEXT[],
    PRIMARY KEY (venue, market_id, time)
);
SELECT create_hypertable(
    'prediction_market_prices', 'time',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- ============================================================
-- Stock-module-specific tables
-- (Other modules will add their own; engine doesn't enforce this.)
-- ============================================================

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

CREATE TABLE IF NOT EXISTS historical_events (
    event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   TEXT NOT NULL REFERENCES modules(module_id),
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    start_time  TIMESTAMPTZ NOT NULL,
    phases      JSONB NOT NULL,                         -- [{"label","day"}, ...]
    series      JSONB                                   -- normalized variable paths
);
CREATE INDEX IF NOT EXISTS idx_hist_module_kind
    ON historical_events (module_id, kind);

-- ============================================================
-- Seed rows: the stocks module and its first adapter
-- ============================================================
INSERT INTO modules (module_id, version)
VALUES ('stocks', '0.1.0')
ON CONFLICT (module_id) DO NOTHING;

INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.apewisdom',
    'stocks',
    'retail_social',
    'C',
    'ApeWisdom free API — https://apewisdom.io/api/ (public, no auth, attribution on use)',
    true
)
ON CONFLICT (adapter_id) DO NOTHING;
