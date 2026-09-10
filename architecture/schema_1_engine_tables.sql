-- ============================================================
-- AlphaHound schema — chunk 1 of 4
-- Extensions + engine-level tables (standard Postgres, no hypertables)
-- Run this first. Safe to re-run.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- modules: one row per industry module registered with the engine.
CREATE TABLE IF NOT EXISTS modules (
    module_id       TEXT PRIMARY KEY,
    version         TEXT NOT NULL,
    config_hash     TEXT,
    enabled_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- entities: canonical record for every tradable / trackable thing.
CREATE TABLE IF NOT EXISTS entities (
    entity_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id           TEXT NOT NULL REFERENCES modules(module_id),
    canonical_symbol    TEXT NOT NULL,
    kind                TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (module_id, canonical_symbol, kind)
);
CREATE INDEX IF NOT EXISTS idx_entities_symbol ON entities (module_id, canonical_symbol);

-- entity_aliases: symbol changes, rebrands, redraws.
CREATE TABLE IF NOT EXISTS entity_aliases (
    alias_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    alias           TEXT NOT NULL,
    valid_from      TIMESTAMPTZ NOT NULL,
    valid_to        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_aliases_lookup ON entity_aliases (alias, valid_from);

-- source_adapters: one row per data-source adapter declared by a module.
CREATE TABLE IF NOT EXISTS source_adapters (
    adapter_id      TEXT PRIMARY KEY,
    module_id       TEXT NOT NULL REFERENCES modules(module_id),
    source_class    TEXT NOT NULL,
    tier            TEXT NOT NULL CHECK (tier IN ('A','B','C','D')),
    tos_basis       TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
