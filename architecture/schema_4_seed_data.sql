-- ============================================================
-- AlphaHound schema — chunk 4 of 4
-- Seed rows (stocks module + first adapter)
-- Run AFTER chunks 1–3. Safe to re-run.
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

-- Verification queries (optional — run to confirm everything is in place)
-- SELECT * FROM modules;
-- SELECT * FROM source_adapters;
-- SELECT hypertable_name FROM timescaledb_information.hypertables ORDER BY 1;
