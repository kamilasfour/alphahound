-- ============================================================
-- AlphaHound schema — chunk 12
-- Sprint 8: Rhyme Engine + hit rate tracking
-- Run AFTER chunks 1–11. Safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- 1. historical_events
--    Stores named market events for Rhyme Engine pattern matching.
--    Each event is a labeled period (e.g. "NVDA earnings beat Q4 2025")
--    with a start/end window. The Rhyme Engine finds current divergence
--    patterns that look like past events and uses the outcome to predict
--    what happens next.
--
--    Seeded automatically from:
--      - divergence_events (past alerts with known outcomes)
--      - price_snapshots (price series context)
--      - trade_log (outcome = did the signal work?)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historical_events (
    event_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    label           TEXT NOT NULL,          -- e.g. "NVDA Q4 2025 earnings beat"
    event_type      TEXT NOT NULL           -- 'earnings', 'divergence', 'congress_trade', 'macro'
                    CHECK (event_type IN ('earnings','divergence','congress_trade','macro','other')),
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    d_value         DOUBLE PRECISION,       -- divergence at time of event
    direction       TEXT                    -- 'long' or 'short' signal at time
                    CHECK (direction IN ('long','short', NULL)),
    outcome_pct     DOUBLE PRECISION,       -- price change % over next 5 trading days
    outcome_correct BOOLEAN,               -- did the signal direction match price move?
    components      JSONB,                  -- snapshot of source class polarities
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_historical_events_entity
    ON historical_events (entity_id, window_start DESC);

CREATE INDEX IF NOT EXISTS idx_historical_events_type
    ON historical_events (event_type, outcome_correct);

-- ------------------------------------------------------------
-- 2. rhyme_matches — already exists from schema_2 but may need
--    the narrative column added for display purposes.
-- ------------------------------------------------------------
ALTER TABLE rhyme_matches
    ADD COLUMN IF NOT EXISTS narrative TEXT,
    ADD COLUMN IF NOT EXISTS outcome_prediction TEXT,   -- 'bullish' | 'bearish'
    ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION;

-- ------------------------------------------------------------
-- 3. hit_rate
--    Rolling hit rate tracker. Updated by hit_rate.py after
--    each trade_log entry is closed (pnl filled in).
--    Also updated by the Rhyme Engine when outcomes are resolved.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hit_rate (
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    window_days     INTEGER NOT NULL,       -- rolling window (7, 30, 90)
    total_signals   INTEGER NOT NULL,
    correct_signals INTEGER NOT NULL,
    hit_rate_pct    DOUBLE PRECISION NOT NULL,
    avg_gain_pct    DOUBLE PRECISION,       -- avg gain on winning trades
    avg_loss_pct    DOUBLE PRECISION,       -- avg loss on losing trades
    expectancy      DOUBLE PRECISION,       -- (hit_rate * avg_gain) - (miss_rate * avg_loss)
    by_source_class JSONB,                  -- {retail_social: 0.62, institutional_flow: 0.71}
    by_ticker       JSONB,                  -- {PLTR: 0.80, AAPL: 0.55}
    PRIMARY KEY (computed_at, window_days)
);

SELECT create_hypertable(
    'hit_rate', 'computed_at',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- ------------------------------------------------------------
-- 4. Seed historical_events from existing divergence_events.
--    Every past divergence alert becomes a historical event.
--    outcome_pct and outcome_correct filled in by hit_rate.py
--    when price data confirms the move.
-- ------------------------------------------------------------
INSERT INTO historical_events (
    entity_id, label, event_type,
    window_start, window_end,
    d_value, direction, components
)
SELECT
    de.entity_id,
    'Divergence alert: ' || e.canonical_symbol || ' D=' || ROUND(de.d_value::numeric, 2),
    'divergence',
    de.time,
    de.time + INTERVAL '5 days',
    de.d_value,
    CASE
        WHEN (de.components->>'institutional_flow')::float < -0.1 THEN 'short'
        WHEN (de.components->>'institutional_flow')::float > 0.1  THEN 'long'
        WHEN (de.components->>'news_wire')::float > 0.2           THEN 'long'
        WHEN (de.components->>'news_wire')::float < -0.2          THEN 'short'
        ELSE NULL
    END,
    de.components
FROM divergence_events de
JOIN entities e ON e.entity_id = de.entity_id
ON CONFLICT DO NOTHING;

-- Seed from trade_log — every signal recommendation becomes a historical event.
INSERT INTO historical_events (
    entity_id, label, event_type,
    window_start, window_end,
    direction, components
)
SELECT
    tl.entity_id,
    'Signal: ' || e.canonical_symbol || ' ' || UPPER(tl.side) || ' $' || ROUND(tl.size::numeric, 0),
    'divergence',
    tl.time,
    tl.time + INTERVAL '5 days',
    CASE tl.side WHEN 'buy' THEN 'long' WHEN 'short' THEN 'short' ELSE NULL END,
    tl.notes::jsonb
FROM trade_log tl
JOIN entities e ON e.entity_id = tl.entity_id
WHERE tl.venue = 'signal'
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- Verification queries
-- ------------------------------------------------------------
-- SELECT COUNT(*) FROM historical_events;
-- SELECT event_type, COUNT(*) FROM historical_events GROUP BY event_type;
-- SELECT COUNT(*) FROM hit_rate;
