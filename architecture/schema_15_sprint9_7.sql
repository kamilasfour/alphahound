-- ============================================================
-- AlphaHound schema — chunk 15
-- Sprint 9.7: Entity relationships + sector rollup sentiment
-- Run AFTER chunks 1–14. Safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- 1. entity_relationships
--    Maps constituent stocks to their parent sector/thematic ETFs.
--    relationship_type: 'constituent_of' | 'proxy_for'
--    weight: 0.0–1.0, represents the constituent's weight in the ETF
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entity_relationships (
    child_entity_id   UUID NOT NULL REFERENCES entities(entity_id),
    parent_entity_id  UUID NOT NULL REFERENCES entities(entity_id),
    relationship_type TEXT NOT NULL DEFAULT 'constituent_of',
    weight            DOUBLE PRECISION DEFAULT NULL,  -- ETF constituent weight
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (child_entity_id, parent_entity_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_entity_rel_parent
    ON entity_relationships (parent_entity_id);

CREATE INDEX IF NOT EXISTS idx_entity_rel_child
    ON entity_relationships (child_entity_id);

-- ------------------------------------------------------------
-- 2. sector_sentiment
--    Aggregated sector-level sentiment rolled up from constituents.
--    Written by sector_rollup_scorer.py after each scoring cycle.
--    Read by divergence.py alongside options_flow for sector divergence.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sector_sentiment (
    time              TIMESTAMPTZ NOT NULL,
    entity_id         UUID NOT NULL REFERENCES entities(entity_id),
    source_class      TEXT NOT NULL DEFAULT 'sector_rollup',
    polarity          DOUBLE PRECISION NOT NULL,
    confidence        DOUBLE PRECISION NOT NULL,
    constituent_count INTEGER,      -- how many stocks contributed
    coverage_pct      DOUBLE PRECISION,  -- % of ETF weight covered by constituents with data
    PRIMARY KEY (entity_id, time)
);

CREATE INDEX IF NOT EXISTS idx_sector_sentiment_entity_time
    ON sector_sentiment (entity_id, time DESC);

-- ------------------------------------------------------------
-- Verification
-- ------------------------------------------------------------
-- SELECT COUNT(*) FROM entity_relationships;
-- SELECT COUNT(*) FROM sector_sentiment;
