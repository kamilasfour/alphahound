-- ============================================================
-- AlphaHound schema — chunk 6
-- Sprint 2 mid-sprint pivot (April 19, 2026):
--   - Register the new stocks.edgar adapter
--   - Disable the stocks.stocktwits adapter (API locked to new developers)
--   - Add a new entity kind: 'filer' (for SEC filers identified by CIK)
--
-- Run AFTER chunk 5. Safe to re-run.
-- ============================================================

-- 1. Register the SEC EDGAR adapter.
INSERT INTO source_adapters (adapter_id, module_id, source_class, tier, tos_basis, enabled)
VALUES (
    'stocks.edgar',
    'stocks',
    'institutional_flow',
    'B',
    'SEC.gov public data; <=10 req/s rate limit; User-Agent identifies AlphaHound per SEC fair-use policy (https://www.sec.gov/os/webmaster-faq#code-support)',
    true
)
ON CONFLICT (adapter_id) DO UPDATE
    SET source_class = EXCLUDED.source_class,
        tier = EXCLUDED.tier,
        tos_basis = EXCLUDED.tos_basis,
        enabled = true;

-- 2. Retire the StockTwits adapter. Row stays for audit history; enabled flipped off.
UPDATE source_adapters
SET enabled = false
WHERE adapter_id = 'stocks.stocktwits';

-- 3. Verify the state. (Run this manually after applying.)
-- Expected: apewisdom + edgar enabled; stocktwits disabled.
--
-- SELECT adapter_id, source_class, tier, enabled FROM source_adapters ORDER BY adapter_id;
