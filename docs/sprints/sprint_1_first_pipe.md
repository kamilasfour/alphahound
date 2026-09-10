# Sprint 1 — First pipe ✅

**Dates:** April 18, 2026 (single session)
**Status:** Complete
**Goal:** Prove the architecture works end-to-end with one adapter, one DB write, one CLI command.

---

## Why this sprint existed

The PRD describes an engine. Before writing any scoring math, divergence metrics, or Rhyme Engine, we needed to prove the *plumbing* works: can we pull live data, normalize it into the `Post` model, resolve an entity, and write a row? If the plumbing doesn't work, nothing downstream matters. This is the "smoke test" sprint.

---

## Definition of done

- [x] Database schema applied (all PRD A10.2 tables + stock-module tables)
- [x] Timescale hypertables confirmed working
- [x] One adapter implemented and conforming to `BaseAdapter` contract
- [x] Storage layer writes deduped rows to `raw_posts`
- [x] Entity resolver creates canonical IDs for new symbols
- [x] CLI command runs end-to-end with live data
- [x] `raw_posts` contains real data queryable via SQL

---

## What was built

### Files created

| File | Purpose |
|---|---|
| `architecture/schema_1_engine_tables.sql` | Extensions + engine tables (modules, entities, aliases, adapters) |
| `architecture/schema_2_core_hypertables.sql` | 5 core hypertables (raw_posts, sentiment, signals, divergence, rhyme) |
| `architecture/schema_3_module_tables.sql` | trade_log, PM prices, options_flow, institutional, historical_events |
| `architecture/schema_4_seed_data.sql` | Seeds the `stocks` module and `stocks.apewisdom` adapter |
| `src/alphahound/engine/storage.py` | Connection pool, `EntityResolver`, `write_posts()`, adapter metadata loader |
| `src/alphahound/modules/stocks/adapters/apewisdom.py` | First concrete adapter (Reddit mention aggregator) |
| `src/alphahound/cli.py` | Typer CLI: `db check`, `db tables`, `ingest` |
| `pyproject.toml` (updated) | Added `psycopg[binary,pool]`, `python-dotenv` |
| `.env.example` | Template for DB connection string + module salt |

Note: `architecture/database_schema.sql` still exists as the monolithic source of truth, kept in sync with the 4 chunks. Future sprints edit the monolith; 4 chunks are only for manual re-apply if needed.

### Database shape after Sprint 1

- 14 tables total
- 8 hypertables (7-day chunks for `raw_posts`, 30-day for the rest per PRD §A10.2)
- 1 module registered: `stocks` v0.1.0
- 1 adapter registered: `stocks.apewisdom` (tier C, retail_social)
- 100 rows in `raw_posts` from one live ApeWisdom pull

### CLI commands working

```powershell
alphahound db check             # verifies DB connection + reports version
alphahound db tables            # lists tables, marks hypertables
alphahound ingest --source apewisdom --dry-run   # fetch only
alphahound ingest --source apewisdom             # fetch + write
```

---

## First real data (verified in DBeaver)

Top mentions from the 14:37 UTC snapshot on April 18:
- SPY, NVDA, MSFT, QQQ, TSLA, AMD, BB, VNQ, NKE, SMCI

Sample row:
```
SPY (SPDR S&P 500 ETF Trust) mentions=277 (24h_ago=...) upvotes=... rank=... source=ApeWisdom:all-stocks
tier=C  source_class=retail_social
```

---

## Things that went sideways

1. **PGAdmin v9.0 dropped connections mid-script.** Spent time debugging what turned out to be a UI bug, not a real issue. **Fix:** switched to DBeaver Community for SQL work.
2. **TimescaleDB required two settings to enable.** Adding it to `azure.extensions` is necessary but not sufficient — also needed to add it to `shared_preload_libraries` and restart the server. First schema apply failed with a clear "must be preloaded" error.
3. **Password authentication confusion in `.env`.** URL-encoding special characters in the Postgres DSN is error-prone. **Fix:** used the keyword/value libpq format (`host=... user=... password=...`) instead of the URL format to skip encoding.
4. **Connection pool cleanup warnings.** Pool threads didn't shut down cleanly on process exit. **Fix:** added `atexit.register(close_pool)` in the CLI bootstrap.

---

## Design decisions locked in

1. **One row per `(post, entity)` pair** — posts mentioning 3 tickers become 3 rows. Junction table deferred.
2. **Denormalized `source_class` and `tier` in `raw_posts`** — faster queries, trade-off is drift if an adapter is retiered.
3. **Kept `text` column in `raw_posts`** — PRD only specified `text_hash`, but FinBERT and Claude need the actual text. Both are stored.
4. **UUID entity IDs, not symbols** — symbols change (rebrands, tickers), UUIDs don't. Aliases live in `entity_aliases` with validity windows per PRD §A9.3.
5. **Synthetic posts from aggregators** — ApeWisdom returns ranked mention counts, not posts. We synthesize a deterministic text row per (ticker, snapshot) so the `Post` contract stays uniform. When we add direct Reddit ingestion later, real posts flow through the same pipe.

---

## What was explicitly NOT done (out of scope, deferred)

- FinBERT or any sentiment scoring (Sprint 3)
- Claude / Tier 2 LLM calls (Sprint 7)
- Divergence metric, Rhyme Engine, regime-weighted scoring (Sprints 3, 6)
- More than one adapter (Sprint 2+)
- YAML module config loader — adapters are registered in SQL seed rows for now (Sprint 3)
- Scheduled runs — user types the command manually (Sprint 2)
- Dashboard, visuals (Sprint 4)
- Tests (Sprint 2 — start small with a `test_apewisdom.py` fixture)

---

## Exit criteria — all green

- [x] `alphahound db check` succeeds
- [x] `alphahound db tables` shows 14 tables and 8 hypertables
- [x] `alphahound ingest --source apewisdom` writes 100 rows
- [x] DBeaver query confirms entities resolved and posts stored
- [x] No Python errors, no SQL errors, pool closes cleanly

---

## Handoff to Sprint 2

The engine can now receive data. Sprint 2 turns a single manual pull into a continuous stream from multiple sources and produces the first observable "signal" (mention velocity). See `sprint_2_multi_source.md`.
