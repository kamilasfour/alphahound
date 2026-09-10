-- ============================================================
-- AlphaHound schema — chunk 7
-- Sprint 3: adds scoring_watermark table.
-- sentiment_scores and divergence_events already exist from Sprint 1.
-- Run AFTER chunk 6. Safe to re-run.
-- ============================================================

-- scoring_watermark: tracks the last scored timestamp per source class.
-- Used by orchestrator.py to avoid re-scanning raw_posts from scratch.
CREATE TABLE IF NOT EXISTS scoring_watermark (
    source_class        TEXT PRIMARY KEY,
    last_scored_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE scoring_watermark IS
    'Tracks the last raw_posts timestamp scored per source class. '
    'Maintained by engine/scoring/orchestrator.py.';
