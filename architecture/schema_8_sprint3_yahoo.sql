-- ============================================================
-- AlphaHound schema — chunk 8
-- Sprint 3 mid-sprint: register Yahoo Finance RSS adapter.
-- Adds news_wire source class to enable divergence math.
-- Run AFTER chunk 7. Safe to re-run.
-- ============================================================

INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.yahoo_finance',
    'stocks',
    'news_wire',
    'C',
    'Yahoo Finance RSS public feed — https://feeds.finance.yahoo.com/rss/2.0/headline (public syndication, personal sentiment research use, Stage 1 only)',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier         = EXCLUDED.tier,
        tos_basis    = EXCLUDED.tos_basis,
        enabled      = true;

-- Also retire Reddit reference from source_adapters if it was ever added.
-- (It wasn't seeded, but this is a clean no-op if run multiple times.)

-- Verify state after applying:
-- SELECT adapter_id, source_class, tier, enabled FROM source_adapters ORDER BY adapter_id;
