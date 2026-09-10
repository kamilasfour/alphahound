-- ============================================================
-- AlphaHound schema — chunk 14
-- Sprint 9.5: Daily price history for technical analysis
-- Run AFTER chunks 1–13. Safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- 1. price_daily
--    One row per ticker per trading day.
--    Source: Massive /v2/aggs/ticker/{ticker}/range/1/day
--    Used by: TechnicalGate (MACD, RSI, EMA, volume, momentum)
--    Backfilled 60 days on first run, then daily top-up.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_daily (
    date            DATE            NOT NULL,
    entity_id       UUID            NOT NULL REFERENCES entities(entity_id),
    open            DOUBLE PRECISION NOT NULL,
    high            DOUBLE PRECISION NOT NULL,
    low             DOUBLE PRECISION NOT NULL,
    close           DOUBLE PRECISION NOT NULL,
    volume          BIGINT,
    vwap            DOUBLE PRECISION,
    transactions    INTEGER,
    PRIMARY KEY (entity_id, date)
);

CREATE INDEX IF NOT EXISTS idx_price_daily_entity_date
    ON price_daily (entity_id, date DESC);

-- ------------------------------------------------------------
-- Verification queries
-- ------------------------------------------------------------
-- SELECT COUNT(*) FROM price_daily;
-- SELECT e.canonical_symbol, COUNT(*), MIN(pd.date), MAX(pd.date)
--   FROM price_daily pd JOIN entities e ON e.entity_id = pd.entity_id
--   GROUP BY e.canonical_symbol ORDER BY COUNT(*) DESC LIMIT 10;
