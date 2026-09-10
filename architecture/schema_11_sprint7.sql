-- ============================================================
-- AlphaHound schema — chunk 11
-- Sprint 7: substack_feeds registry table + adapter seed
-- Run AFTER chunks 1–10. Safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- 1. substack_feeds
--    Registry of Substack newsletters we ingest.
--    One row per feed. The adapter reads this table to know
--    which RSS URLs to pull, rather than hardcoding in Python.
--    Add new feeds by inserting rows here — no code changes needed.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS substack_feeds (
    feed_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,       -- e.g. 'doomberg', 'kuppy'
    display_name    TEXT NOT NULL,              -- e.g. 'Doomberg'
    rss_url         TEXT NOT NULL,              -- full RSS URL
    author          TEXT,                       -- author name if known
    focus           TEXT,                       -- 'energy', 'macro', 'tech', etc.
    tier            TEXT NOT NULL DEFAULT 'B'
                    CHECK (tier IN ('A','B','C','D')),
    enabled         BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- 2. earnings_calendar
--    Upcoming earnings dates per ticker.
--    Updated by the earnings_calendar adapter on each run.
--    Used by trade_advisor and kalshi_watcher for context.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS earnings_calendar (
    entity_id           UUID NOT NULL REFERENCES entities(entity_id),
    earnings_date       DATE NOT NULL,
    fiscal_quarter      TEXT,                   -- e.g. 'Q1 2026'
    estimate_eps        DOUBLE PRECISION,       -- consensus EPS estimate
    actual_eps          DOUBLE PRECISION,       -- filled in after report
    beat                BOOLEAN,                -- true=beat, false=miss, null=pending
    data_source         TEXT NOT NULL DEFAULT 'yahoo_finance',
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, earnings_date)
);

CREATE INDEX IF NOT EXISTS idx_earnings_date
    ON earnings_calendar (earnings_date ASC);

CREATE INDEX IF NOT EXISTS idx_earnings_entity
    ON earnings_calendar (entity_id, earnings_date DESC);

-- ------------------------------------------------------------
-- 3. Seed substack_feeds — initial newsletter roster
--    All are free RSS feeds, no auth required.
--    Tier B = analyst_curated weight in divergence math.
-- ------------------------------------------------------------

INSERT INTO substack_feeds (slug, display_name, rss_url, author, focus, tier, enabled)
VALUES
    ('doomberg',
     'Doomberg',
     'https://doomberg.substack.com/feed',
     'Doomberg',
     'energy,commodities,macro',
     'B', true),

    ('kuppy',
     'Adventures in Capitalism',
     'https://adventuresinfinance.substack.com/feed',
     'Harris Kupperman',
     'macro,emerging_markets,commodities',
     'B', true),

    ('grant-williams',
     'Things That Make You Go Hmmm',
     'https://ttmygh.substack.com/feed',
     'Grant Williams',
     'macro,gold,credit',
     'B', true),

    ('larry-macdonald',
     'The Bear Traps Report',
     'https://beartrapsreport.substack.com/feed',
     'Larry McDonald',
     'macro,credit,rates',
     'B', true),

    ('genevieve-roch-decter',
     'GRIT Capital',
     'https://gritcapital.substack.com/feed',
     'Genevieve Roch-Decter',
     'equities,tech,growth',
     'B', true),

    ('bill-brewster',
     'Brew''s Biz Briefs',
     'https://billbrewster.substack.com/feed',
     'Bill Brewster',
     'equities,value',
     'B', true),

    ('kyla-scanlon',
     'Kyla''s Newsletter',
     'https://kylascanlon.substack.com/feed',
     'Kyla Scanlon',
     'macro,economy,fed',
     'C', true),

    ('net-interest',
     'Net Interest',
     'https://www.netinterest.co/feed',
     'Marc Rubinstein',
     'financials,banks,fintech',
     'B', true)

ON CONFLICT (slug) DO UPDATE
    SET display_name = EXCLUDED.display_name,
        rss_url      = EXCLUDED.rss_url,
        author       = EXCLUDED.author,
        focus        = EXCLUDED.focus,
        tier         = EXCLUDED.tier,
        enabled      = EXCLUDED.enabled;

-- ------------------------------------------------------------
-- 4. Seed source_adapters for Sprint 7
-- ------------------------------------------------------------

INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.substack',
    'stocks',
    'analyst_curated',
    'B',
    'Substack public RSS feeds — free, personal research use, no redistribution',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier         = EXCLUDED.tier,
        tos_basis    = EXCLUDED.tos_basis,
        enabled      = true;

INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.earnings_calendar',
    'stocks',
    'price_data',
    'A',
    'Yahoo Finance earnings calendar — public data, personal research use',
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
-- SELECT slug, display_name, focus, tier, enabled FROM substack_feeds ORDER BY slug;
-- SELECT * FROM earnings_calendar ORDER BY earnings_date LIMIT 10;
-- SELECT adapter_id, source_class, enabled FROM source_adapters ORDER BY adapter_id;
