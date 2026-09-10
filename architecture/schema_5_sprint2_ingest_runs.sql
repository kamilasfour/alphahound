-- ============================================================
-- AlphaHound schema — chunk 5
-- Adds the ingest_runs table for ingestion health tracking (Sprint 2).
-- Run once against the alphahound DB. Safe to re-run.
-- ============================================================

-- One row per invocation of an adapter's pull().
-- Used for:
--   - Health checks: "latest run in the last 30 min?"
--   - SLO tracking: ingestion latency, error rates
--   - Debugging: who failed and why, when
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    adapter_id      TEXT NOT NULL REFERENCES source_adapters(adapter_id),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    posts_fetched   INTEGER NOT NULL DEFAULT 0,
    posts_written   INTEGER NOT NULL DEFAULT 0,
    error           TEXT,
    host            TEXT,                              -- which machine ran it
    details         JSONB                              -- freeform: watchlist size, api status, etc.
);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_adapter_started
    ON ingest_runs (adapter_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingest_runs_errors
    ON ingest_runs (started_at DESC) WHERE error IS NOT NULL;

-- Seed the StockTwits adapter registration (Sprint 2 addition).
INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.stocktwits',
    'stocks',
    'retail_social',
    'C',
    'StockTwits Public API — https://api.stocktwits.com/developers/docs (200 calls/hour on free tier, attribution required, non-commercial dev use)',
    true
)
ON CONFLICT (adapter_id) DO NOTHING;
