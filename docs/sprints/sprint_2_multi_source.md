# Sprint 2 — Multi-source + scheduled ingest 🎯

**Dates:** TBD (estimate: 2–3 days of work)
**Status:** Planning — awaiting green light
**Goal:** Data flows into the database continuously, from more than one source, and produces the first observable signal.

---

## Why this sprint

After Sprint 1, the engine can pull ApeWisdom once, on demand, when Kamil types a command. That's a static snapshot. Two problems:

1. **One source is not enough.** Divergence (the core differentiator) is literally "retail vs institutions disagree." We need at least one more source class wired in to have anything to diverge.
2. **Manual triggers die on contact with reality.** Kamil isn't going to type `alphahound ingest` every 15 minutes for 90 days. Without scheduling, the data ages instantly and is useless for anything time-series.

This sprint closes both gaps and produces the **first output that looks like a signal** — mention velocity — so we can sanity-check the pipeline against eyeball intuition.

---

## Definition of done

- [ ] Second adapter added (StockTwits retail_social) and tested end-to-end
- [ ] Windows Task Scheduler job runs `alphahound ingest` every 15 min for both adapters
- [ ] Task is idempotent — dedup prevents duplicate rows on retries
- [ ] A `signals` subcommand exists: `alphahound signals velocity --ticker STNG --window 24h` returns a number
- [ ] `signal_scores` table has its first rows (simple mention-velocity score, not the full 9-component signal yet)
- [ ] A README-style runbook exists in `docs/runbooks/` explaining how to check ingestion health and what to do if it stops
- [ ] First basic test: `tests/test_apewisdom_adapter.py` uses a recorded fixture so we don't hit the live API in CI

---

## In scope

### 1. StockTwits adapter

**Source class:** retail_social (same as ApeWisdom, complementary data)
**Tier:** C
**Cost:** Free tier — 200 calls/hour
**Endpoint:** `https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json`

Why StockTwits: gives us *actual post text* (not just aggregates), with bull/bear annotations, usernames (to hash), and timestamps. Unlike ApeWisdom synthetic rows, these are real posts that FinBERT can score in Sprint 3.

Implementation notes:
- Unlike ApeWisdom (pull all tickers), StockTwits is symbol-scoped — we pull N posts per symbol.
- We need a **watchlist** of symbols to pull. First draft: top 50 ApeWisdom mentions from the last 24h, refreshed daily.
- Author usernames get hashed with `ALPHAHOUND_AUTHOR_SALT_STOCKS` per PRD §A9.2.
- ToS basis: StockTwits API public docs — must cite properly in `source_adapters`.

**New file:** `src/alphahound/modules/stocks/adapters/stocktwits.py`
**New seed row:** `stocks.stocktwits` in `source_adapters`

### 2. Scheduled ingest

**Mechanism:** Windows Task Scheduler (not cron — we're on Windows Server 2022). Running as `SYSTEM` so the task survives logout and reboots.
**Frequency:** Every 15 minutes
**Action:** runs a PowerShell wrapper that activates the venv and calls `alphahound ingest --source apewisdom` then `alphahound ingest --source stocktwits`

> **Why not Azure Functions?** We considered it. Functions is the better long-term pick (built-in alerting, Key Vault secrets, runs even when VM is off). But Task Scheduler ships in 15 min vs 60+ min for Functions, and the load on the VM is negligible (<0.1% CPU). We'll revisit Functions when real reliability matters — likely around paid-tier launch. **No scheduled migration sprint.**

**New files:**
- `scripts/ingest_all.ps1` — the wrapper script
- `scripts/register_scheduled_task.ps1` — one-time command to register the task (documented, not auto-run)
- `docs/runbooks/ingestion.md` — runbook: how to check the task is running, where the logs go, how to pause it

**Logging:** stdout/stderr → `C:\alphahound_project\logs\ingest_YYYY-MM-DD.log` (rotated daily). Last 50 runs also summarized in a `ingest_runs` table — we add it to the schema this sprint.

**New table:** `ingest_runs(run_id, adapter_id, started_at, finished_at, posts_fetched, posts_written, error)`. Added as a small chunk-5 SQL file.

### 3. Mention velocity signal (crude but real)

**What it computes:** for each ticker, the ratio of posts in the last hour vs posts in the last 24h (normalized per adapter).

Formula:
```
v(ticker) = (posts_last_1h / adapter_baseline_1h) - 1
```

Where `adapter_baseline_1h` is the rolling 7-day average posts/hour for that ticker on that adapter.

- `v > 0` means the ticker is posting faster than its 7-day baseline
- `v > 2.0` means it's posting 3x faster — interesting
- Writes to `signal_scores` with a **placeholder 1–10 score** just to exercise the table. Real scoring comes in Sprint 3.

**New file:** `src/alphahound/engine/signals/velocity.py`
**New CLI command:** `alphahound signals velocity --ticker X [--window 1h|24h|7d]`
**New CLI command:** `alphahound signals compute-all --window 1h` (runs against every ticker with recent activity)

### 4. Minimal test scaffold

- `tests/conftest.py` with a pytest fixture that loads `.env`
- `tests/test_apewisdom_adapter.py` — uses a recorded JSON fixture (real API response saved to `tests/fixtures/apewisdom_all_stocks_page1.json`), asserts the adapter emits the expected number of posts with expected fields
- `tests/test_velocity.py` — synthetic data in, expected velocity out

No DB-level integration tests yet — those need a throwaway DB, which is Sprint 4 territory.

---

## Out of scope (explicit)

- SEC EDGAR adapter — originally considered for Sprint 2 but institutional_flow adds complexity (XBRL parsing) that distracts from the sprint goal. **Moved to Sprint 3.**
- FinBERT sentiment scoring (Sprint 3)
- Any UI or Grafana (Sprint 4)
- Unusual Whales / Kalshi (Sprint 5)
- Rhyme Engine (Sprint 6)

---

## Risks

| Risk | Mitigation |
|---|---|
| EDGAR User-Agent enforcement | SEC requires an identifying UA string; adapter sends `AlphaHound/0.1 (contact: kamil@...)` |
| EDGAR rate limiting (10 req/s) | Backoff in adapter; one run at 15-min cadence is nowhere near the limit |
| EDGAR filing schema drift | SEC is stable but filings are XBRL — adapter parses JSON submissions feed, not raw XBRL, so schema changes are minimal |
| Task Scheduler task dies silently | Health check query in runbook; alert path in Sprint 4 |
| Duplicate data on retries | Already handled — `raw_posts` dedup on `(adapter_id, external_id, entity_id, time)` |
| ApeWisdom schema changes | Adapter test with fixture catches shape drift; fails fast in CI |
| Cost creep | Both adapters are free; no cost risk this sprint |
| StockTwits code rot | Retained for reference only; will be audited in Sprint 5 when we revisit multi-source retail |

---

## Exit criteria

- [ ] `alphahound db tables` shows `ingest_runs` table exists
- [ ] `alphahound ingest --source stocktwits` pulls real posts and writes them
- [ ] Scheduled task runs for 24 hours continuously, at least 80 successful invocations
- [ ] `alphahound signals velocity --ticker NVDA` returns a sensible number
- [ ] `tests/` passes `pytest -q`
- [ ] A tick-by-tick line chart in DBeaver (even just SQL output) shows `raw_posts` growing over time per adapter

---

## Handoff to Sprint 3

Two adapters streaming, basic velocity signal running — but no *sentiment* yet. Sprint 3 plugs in FinBERT and the first real divergence math.
