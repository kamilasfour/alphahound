# AlphaHound — Sprint Tracker

**Last updated:** May 2, 2026
**Current sprint:** Sprint 9 (complete)
**Handoff doc:** `docs/HANDOFF.md` — read this first in a new session

---

## 🎯 Strategic posture

- **Stage 1 — Personal capital engine (current).** Goal = grow $5K Schwab + $1K Kalshi to $500K+.
- **Stage 2 — Commercial platform (future).** Starts only after Stage 1 exit.

---

## 🗺️ Sprint map

| # | Sprint | One-line goal | Status |
|---|---|---|---|
| 0-4 | Foundation | DB, pipes, FinBERT, Grafana | ✅ Done |
| 5 | Price context | Massive, Finnhub, Quiver, Claude narratives | ✅ Done |
| 6 | Options + institutional | Unusual Whales + congressional scoring | ✅ Done |
| 6.5 | Trade advisor | Kelly sizing + trade_log corpus | ✅ Done |
| 7 | Analyst ingestion | Substack RSS + earnings calendar | ✅ Done |
| 8 | Rhyme Engine | Pattern matching + hit rate tracking | ✅ Done |
| 9 | Alpaca paper trading | Signal → Alpaca paper orders → hit rate validation | ✅ Done |
| 9.5 | Technical gate | MACD/RSI/EMA/Volume/Momentum pre-execution filter | ✅ Done |
| 9.7 | Sector/ETF universe | Central watchlist, sector rollup scorer, entity relationships | ✅ Done |
| 10 | Live trading | Engine drives real trades, Kalshi bets automated | 🎯 Next |

---

## 📍 Sprint 9.5 — What was delivered

**Closed May 2, 2026.**

### New modules (2)

**`engine/execution/technical_gate.py`** — 5-check technical confirmation gate.
- MACD (12/26/9) — line vs signal direction
- RSI (14) — not overbought for LONG, not oversold for SHORT
- Volume — current vs 20-day average (ratio ≥ 1.0 = confirm)
- EMA trend (20) — price above/below EMA matches direction
- Momentum — 5d return sign matches direction
- Scoring: 4-5 = CONFIRM (full size), 3 = WEAK (50% size), ≤2 = REJECT (skip)
- Pure Python — no pandas/numpy dependency
- NO_DATA verdict passes through cleanly if < 35 bars available

**`modules/stocks/adapters/massive_history.py`** — Daily OHLCV history adapter.
- Backfill mode: 60 days per ticker (run once via `alphahound signals tech-backfill`)
- Topup mode: last 5 days (run daily via scheduler)
- Writes to `price_daily` table
- Backfill confirmed: 37 tickers × ~43 bars = ~1,590 rows

**Schema (`schema_14_sprint9_5.sql`):** `price_daily` table — one row per ticker per trading day.

### New CLI commands (3)
```powershell
alphahound signals tech-backfill          # one-time 60d OHLCV backfill
alphahound signals tech-check --ticker X  # show all 5 indicators + verdict
alphahound ingest --source massive_history # daily topup (add to scheduler)
```

### Validation
- AAPL LONG → CONFIRM 5/5 ✅
- AAPL SHORT → REJECT 2/5 ✅ (gate correctly blocks chart-contradicted trades)

### Key decisions
- Pure Python indicators — no pandas. Keeps dependencies minimal.
- WEAK verdict executes at 50% size rather than skipping — preserves signal value
- NO_DATA passes through at full size — don't block trades when history is thin
- Volume ratio ≥ 1.0 required — filters low-conviction price moves

---

## 📍 Sprint 9 — What was delivered

**Closed May 2, 2026.**

### New modules (3)

**`engine/execution/alpaca_broker.py`** — Alpaca paper trading broker wrapper.
- Connects to Alpaca paper API via SDK
- `place_order()` — notional market orders (buy / sell_short)
- `get_position()` / `get_all_positions()` — current open positions
- `close_position()` — market close of full position
- `is_market_open()` / `next_market_open()` — market hours guard
- Singleton `get_broker()` for CLI reuse
- Paper account confirmed: PA32DU6RYVJJ, $5,000 equity

**`engine/execution/executor.py`** — Order execution logic.
- `execute_all()` — places paper orders for all current recommendations above min_d
- `execute_ticker()` — single ticker execution
- Guards: market closed, already open, already executed today, position too small
- Stamps `alpaca_order_id` + `alpaca_status` back to `trade_log`

**`engine/execution/close_positions.py`** — Position lifecycle manager.
- `close_aged_positions()` — evaluates all open positions against 3 exit criteria:
  1. Hard exit: `resolve_by` date passed
  2. Stop loss: price breached stop_price from trade_advisor
  3. Signal faded: divergence D < 1.5
- `force_close()` — manual close by ticker
- Updates `trade_log` with `pnl`, `closed_at`, `close_order_id`

**Schema (`schema_13_sprint9.sql`):**
- `trade_log` extended: `alpaca_order_id`, `alpaca_status`, `filled_price`, `closed_at`, `close_order_id`
- Indexes for open position lookups

### New CLI commands (2)
```powershell
alphahound signals execute                    # place paper orders for all current alerts
alphahound signals execute --ticker AAPL     # single ticker
alphahound signals execute --min-d 3.0       # raise conviction threshold
alphahound signals close-positions           # check + close aged positions
alphahound signals close-positions --ticker AAPL  # force close one position
```

### Key decisions in Sprint 9
- Alpaca base URL must be `https://paper-api.alpaca.markets` (no `/v2` suffix — SDK adds it)
- Notional orders used (not qty) — fractional shares, cleaner sizing
- Market hours guard: `execute` exits cleanly when market closed, shows next open time
- Deduplication: skips tickers already open in Alpaca or already executed today
- Exit logic reads `outlook.resolve_by` from `trade_log.notes` JSONB

---

## 📊 Engine state as of Sprint 9 close

| Metric | Value |
|---|---|
| Active adapters | 9 |
| Signal coverage | ~72% |
| Alpaca paper account | PA32DU6RYVJJ — $5,000 equity |
| Paper orders placed | 0 (market closed — weekend) |
| historical_events seeded | 291+ |
| hit_rate resolved | 0 (first batch May 5) |
| Entities in divergence scan | 1,182+ |
| Active alerts per scan | 17-20 |

---

## 🎯 May 5 Checkpoint (Critical)

**Run these on Monday May 5 at market open:**

```powershell
# 1. Check first resolved hit rate outcomes
alphahound signals hit-rate

# 2. Run rhyme scan — corpus now has 5+ days of history
alphahound signals rhyme

# 3. If hit rate >= 55%, execute paper trades
alphahound signals divergence-scan
alphahound signals trade-advice
alphahound signals execute

# 4. Check positions end of day
alphahound signals close-positions
```

**Gate to Sprint 10 (live trading):** hit rate ≥ 55% on ≥ 20 resolved signals.

---

## 🎯 Sprint 10 — Live Trading (next)

**Goal:** Flip Alpaca from paper to live. Add DTW to Rhyme Engine. Automate Kalshi bets.

**Prerequisites before starting:**
- Hit rate ≥ 55% confirmed on paper (May 5+ data)
- Manual review of first 5 paper trades
- Live Alpaca account funded

**What to build:**
1. Live Alpaca toggle — `ALPACA_LIVE=true` env flag, separate live account keys
2. DTW pattern matching in Rhyme Engine (needs 90d+ price series — available ~July)
3. Kalshi automated bet placement (EV > 0 threshold)
4. Position sizing ramp — start at 25% of Kelly, scale up as hit rate validates

---

## 🔑 Key decisions locked in

| Decision | Outcome |
|---|---|
| Execution broker | Alpaca (paper Sprint 9, live Sprint 10) |
| Bankroll | $5,000 Schwab + $1,000 Kalshi |
| Position sizing | Half-Kelly, 10% max, min $25 |
| Rhyme Engine | Cosine similarity now, DTW Sprint 10 |
| Hit rate gate | Must show ≥55% hit rate on paper before going live |
| Claude model | claude-sonnet-4-6 |
| Substack | Self-hosted blogs only (substack.com Azure-blocked) |
| Earnings calendar | Finnhub daily job at 6am |
| Alpaca base URL | https://paper-api.alpaca.markets (no /v2 suffix) |

---

## 📝 Open questions

1. **May 5 checkpoint** — first hit rate batch resolves. Gate to live trading.
2. **AAPL signal validation** — engine had D=2.94 SHORT on Apr 30 earnings day. Check vs actual price move.
3. **Rhyme corpus growth** — by May 15 we'll have ~500 historical events. Re-run rhyme scan then.
4. **SMA signal** — D=4.83 from Kevin Hern blank-date trade. Monitor for false signal pattern.
5. **Kalshi** — test `kalshi-watch` at 9:30am ET to validate stock contracts are available.

---

## 🚦 Status legend

- ✅ Complete | 🎯 Next | ⏳ Planned | ⛔ Blocked
