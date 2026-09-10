-- ============================================================
-- AlphaHound schema — chunk 13
-- Sprint 9: Alpaca paper trading
-- Run AFTER chunks 1–12. Safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Add Alpaca execution columns to trade_log
--    alpaca_order_id — UUID returned by Alpaca on order submission
--    alpaca_status   — Alpaca order lifecycle status
--    filled_price    — actual fill price from Alpaca (vs signal price)
--    closed_at       — when position was closed
--    close_order_id  — Alpaca order ID of the closing trade
-- ------------------------------------------------------------
ALTER TABLE trade_log
    ADD COLUMN IF NOT EXISTS alpaca_order_id  TEXT,
    ADD COLUMN IF NOT EXISTS alpaca_status    TEXT,
    ADD COLUMN IF NOT EXISTS filled_price     DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS closed_at        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS close_order_id   TEXT;

-- Index for fast lookup by alpaca_order_id (used by close-positions)
CREATE INDEX IF NOT EXISTS idx_trade_log_alpaca_order
    ON trade_log (alpaca_order_id)
    WHERE alpaca_order_id IS NOT NULL;

-- Index for finding open positions (no close_order_id yet)
CREATE INDEX IF NOT EXISTS idx_trade_log_open_positions
    ON trade_log (time DESC)
    WHERE alpaca_order_id IS NOT NULL
      AND closed_at IS NULL;

-- ------------------------------------------------------------
-- Verification queries
-- ------------------------------------------------------------
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'trade_log' ORDER BY ordinal_position;
-- SELECT COUNT(*) FROM trade_log WHERE alpaca_order_id IS NOT NULL;
