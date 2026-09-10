# AlphaHound Handoff — June 12, 2026

## CRITICAL — READ FIRST

**New Alpaca paper account being created by Kamil — awaiting new API credentials.**
**Old account PA32DU6RYVJJ has ~$7,500 in unrealized losses across 13 positions — DO NOT trade on it.**
**When new credentials arrive: update .env, clear options_trade_log, clear convergence_signals, restart uvicorn.**

---

## System State

- **Stack:** Python 3.11, FastAPI/uvicorn port 8080, Azure PostgreSQL/TimescaleDB
- **Server:** Windows Server 2022 (repsportalvm), PST timezone
- **Project root:** C:\alphahound_project
- **Dashboard:** localhost:8080
- **Alpaca:** Paper trading — NEW ACCOUNT PENDING (old: PA32DU6RYVJJ — ABANDON)

---

## What Happened This Session (June 2-12)

### The Problem
1. **Timestamp rounding bug** — convergence_scorer.py was rounding signal timestamps to the hour. The 20-minute freshness check in the executor never passed → zero trades for days.
2. **Fixed June 2** — changed `_write_result()` to use actual `computed_at` timestamp.
3. **First trade placed June 2** — ORCL bull call spread $824.
4. **Overnight June 2-3** — catalyst window widened (7-60 days, was 14-45) + no-catalyst high-conviction signals unlocked (score ≥ 5.0). Scheduler fired multiple times → 13 positions placed instead of intended 2-3.
5. **Duplicate prevention failed** — executor wrote to DB after placing, but scheduler fired again before DB write completed.
6. **Stop loss never fired** — close endpoint was wrong (`POST /v2/orders` instead of `DELETE /v2/positions/{symbol}`). All -80% positions sat bleeding for 10 days.
7. **Macro gate too loose** — NEUTRAL allowed trading at 75% size. Market was in sustained selloff. Every LONG position lost.
8. **Result: ~$7,500 unrealized losses across 13 open positions.**

---

## All Fixes Applied This Session

### Execution
- `options_executor.py`: Max 3 open spreads hard limit (was unlimited)
- `options_executor.py`: Max 2 contracts per spread (was 5)
- `options_executor.py`: Portfolio health gate — halts if 2+ positions >50% down
- `options_executor.py`: Cross-checks live Alpaca positions before placing (duplicate prevention)
- `options_executor.py`: Timestamp rounding removed from convergence_scorer.py

### Stop Loss
- `options_monitor.py`: Close uses `DELETE /v2/positions/{symbol}` (was broken POST)
- `options_monitor.py`: Time-based exits added:
  - Catalyst trades: close 3 days after earnings fires
  - No-catalyst trades: max 14 days hold
- `options_monitor.py`: Days held shown in monitor output

### Macro Gate
- `macro_context.py`: NEUTRAL now BLOCKS new entries (was 75% size — still traded)
- `macro_context.py`: RISK_OFF threshold lowered to -0.10 (was -0.15, trips faster)
- `macro_context.py`: RISK_ON threshold raised to +0.20 (was +0.15, needs clearer signal)
- `macro_context.py`: SPY 5-day trend override — if SPY 5d < -2%, forces RISK_OFF
- `options_executor.py`: Both NEUTRAL and RISK_OFF now block new LONG entries

### Health Monitor
- `health_monitor.py`: Portfolio loss alert added — shows RED when positions at stop loss
- Shows count of positions at stop, total P&L, which tickers

### Dashboard
- `positions.js`: Rewrote to group legs into spread cards (was showing raw OCC symbols)
- `positions.js`: Shows days held / max hold days per position
- `convergence.js`: MU shows NOT EXECUTABLE (chain too short)
- `checkin.js`: Watch signals show "no catalyst in window" instead of "need -1.00 more"
- `flow.js`: Click-to-expand with plain-English explanation of every field
- `earnings.js`: Grouped by week, SUPER SIGNAL badges, OPTIONS SWEET SPOT tags
- `health.js`: Adapter table + hit rate panel now render
- `congress.js`: Full detail — amount, performance stats, party, House/Senate
- `views.js`: Sector drill-down modal with constituent stocks

---

## Current Rule Set (Post-Fix)

| Rule | Value |
|------|-------|
| Max open spreads | 3 |
| Max contracts per spread | 2 |
| Stop loss | -80% |
| Gain target | +50% |
| Expiry guard | 5 DTE |
| Catalyst exit | 3 days after earnings |
| Time limit (no catalyst) | 14 days max |
| Macro gate | RISK_ON only (NEUTRAL + RISK_OFF block) |
| SPY 5d trend override | < -2% forces RISK_OFF |
| Portfolio health gate | 2+ positions >50% down = halt |

---

## What Needs To Happen Next

### Immediate (waiting on Kamil)
1. **New Alpaca credentials** → update .env ALPACA_API_KEY + ALPACA_SECRET_KEY
2. Reset DB:
   ```sql
   TRUNCATE options_trade_log;
   DELETE FROM convergence_signals WHERE time < now();
   ```
3. Restart uvicorn
4. Verify: `alphahound signals options-monitor` shows 0 positions

### Sprint 12 Priorities
1. **Azure Functions** — move FinBERT scoring off Windows server (CPU spikes)
2. **Email/Slack alerts** — notify Kamil when positions hit stop loss (not just dashboard)
3. **Direction balance** — never all LONG; require at least 1 SHORT signal before entering
4. **Live IV from Alpaca chain** — replace Black-Scholes strike estimation with real chain data
5. **MU chain fix** — MU at $1035 exceeds Alpaca's $890 max listed strike; need different expiry

---

## Golden Rules — NEVER VIOLATE

- Never add watermark back to scoring (orchestrator.py) — pure NOT EXISTS check only
- Never use `published_at=trade_date` for Quiver (causes permanent ON CONFLICT dedup)
- Never re-enable EDGAR (CIK noise) or StockTwits (403 Cloudflare)
- Never check volume in tech gate after hours (partial data blocks all trades)
- Never disable scheduler without re-enabling
- Always check **wrote count**, not just fetched count
- Options market orders ONLY during market hours (6:30 AM - 1:00 PM PT)
- Stop loss closes use `DELETE /v2/positions/{symbol}` — NOT POST /v2/orders
- Max 3 open spreads at any time — hard limit
- NEUTRAL macro = no new trades — only RISK_ON allows entry

---

## Architecture

### Pipeline (runs every 15 min via Windows Task Scheduler)
```
ingest_all.ps1
  → ingest_parallel.py (6 adapters parallel, ~90s)
  → compute_all (velocity, momentum)
  → score_smart.py (FinBERT, max 5000 posts, CATCHUP_CAP)
  → convergence-scan (970 tickers, ~45s)
  → options-monitor --close (fires stop losses)
  → options-execute (places new trades if RISK_ON + <3 positions)
```

### Lock file
- `logs/ingest.lock` — prevents overlapping runs
- Always removed at end of script (success OR failure)
- If stuck: `Remove-Item C:\alphahound_project\logs\ingest.lock -Force`

### Adapters (ON)
apewisdom, finnhub (news only), unusual_whales, massive, massive_history, quiver, substack, yahoo_finance, kalshi, earnings_calendar

### Adapters (OFF)
edgar (CIK noise), stocktwits (403), alpha_vantage (25 calls/day limit)

---

## Key Files Changed This Session

```
src/alphahound/engine/scoring/convergence_scorer.py
  - _write_result(): use actual timestamp (was rounding to hour — ROOT CAUSE of zero trades)
  - CATALYST_MIN_DAYS=7, CATALYST_MAX_DAYS=60 (was 14/45)
  - high_conviction_no_catalyst rule (score≥5.0, 4+pillars, non-neutral)

src/alphahound/engine/execution/options_executor.py
  - MAX_OPEN_SPREADS=3 hard limit
  - Max 2 contracts per spread
  - Portfolio health gate (halts if 2+ positions >50% down)
  - Alpaca live position cross-check for duplicates
  - NEUTRAL + RISK_OFF both block new entries

src/alphahound/engine/execution/options_monitor.py
  - Close uses DELETE /v2/positions/{symbol} (was broken)
  - MAX_HOLD_DAYS_CATALYST=3, MAX_HOLD_DAYS_NO_CATALYST=14
  - Days held shown in output
  - _fetch_alpaca_options_positions: no asset_class param (was 422)

src/alphahound/engine/signals/macro_context.py
  - RISK_ON threshold: 0.20 (was 0.15)
  - RISK_OFF threshold: -0.10 (was -0.15)
  - NEUTRAL now blocks trades (size_modifier=0.0, was 0.75)
  - SPY 5-day trend override (< -2% forces RISK_OFF)

src/alphahound/engine/health_monitor.py
  - Portfolio loss alert added (RED when stop loss hit)

dashboard/api.py
  - /api/positions: rewrote to use convergence_signals + options_trade_log
  - /api/congress: rewrote to use institutional_positions (was timing out)
  - /api/pipeline: fast backlog query (was 4300ms correlated subquery)

dashboard/static/js/positions.js  — full rewrite, spread grouping
dashboard/static/js/flow.js       — click-to-expand with plain English
dashboard/static/js/earnings.js   — grouped by week, super signal badges
dashboard/static/js/health.js     — adapter table + hit rate
dashboard/static/js/congress.js   — full detail with performance stats
dashboard/static/js/convergence.js — MU NOT EXECUTABLE, no structure button
dashboard/static/js/checkin.js    — watch signals show correct reason
dashboard/static/js/views.js      — sector constituent modal, jumpToTicker defined
dashboard/index.html              — all scripts bumped to v=15
```

---

## Session Start Protocol (unchanged)

1. `tabs_context_mcp` → get localhost:8080 tab
2. `javascript_tool` → `fetch('/api/assessment').then(r=>r.json()).then(d=>console.log(JSON.stringify(d)))`
3. Read assessment — gives full system picture in one call
4. Check `docs/status/assessment.json` for last written state

Never run manual scripts before reading assessment first.
