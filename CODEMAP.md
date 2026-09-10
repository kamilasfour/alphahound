# AlphaHound Codemap

Multi-industry sentiment intelligence engine. Python 3.11+ · Azure PostgreSQL · FastAPI dashboard · Alpaca paper trading.

| Backend source files | API endpoints | Data adapters | DB tables | Ops scripts |
|---|---|---|---|---|
| 39 | 20 | 12 | 21 | 17 |

---

## Data Pipeline

```
Adapters → raw_posts → Scoring (FinBERT / rule-based) → divergence_events (D-score + p-value)
  → Claude narrative → trade_advisor (Kelly sizing, tier, leveraged ETF routing, outlook)
  → executor (macro gate + technical gate) → Alpaca paper order → trade_log → hit_rate resolution
```

**Direct-write adapters** (bypass `raw_posts`): `price_snapshots` (Massive), `price_daily` (MassiveHistory), `options_flow` (UnusualWhales), `kalshi_contracts` (Kalshi), `institutional_positions` (Quiver), `earnings_calendar` (Finnhub).

---

## Entry Point — CLI

**`src/alphahound/cli.py`** · 29 KB · Typer app · sub-apps `db` and `signals` · installed as `alphahound` command via pyproject.toml. Bootstraps via `_bootstrap()`: walks parents for `.env`, configures logging, registers pool shutdown on exit.

### CLI Commands

| Command | Delegates to | Description |
|---|---|---|
| `ingest <source>` | adapters + storage.write_posts | Pull one named adapter by source string |
| `ingest-all` | source_adapters table | Pull all enabled adapters in sequence |
| `db check` | storage.get_conn | Postgres connectivity + row counts per table |
| `db tables` | storage.get_conn | List all DB tables with row counts |
| `db ingest-runs` | ingest_runs table | Recent ingestion job history |
| `db divergence-events` | divergence_events table | Recent D-score alerts |
| `signals velocity` | signals.velocity | Compute mention velocity for one entity |
| `signals compute-all` | signals.velocity | Velocity for entire watchlist |
| `signals score-new` | scoring.orchestrator | FinBERT batch score new retail_social + news_wire posts |
| `signals score-institutional` | scoring.institutional_flow_scorer | Rule-based score institutional_flow posts |
| `signals score-sectors` | scoring.sector_rollup_scorer | Aggregate constituent sentiment into sector ETF scores |
| `signals seed-relationships` | scoring.sector_rollup_scorer | Seed entity_relationships for sector constituents |
| `signals divergence-scan` | signals.divergence + narrative | Compute D-scores + generate Claude narratives |
| `signals trade-advice [ticker]` | signals.trade_advisor | Kelly-sized trade recommendations (one or all) |
| `signals kalshi-watch` | signals.kalshi_watcher + trade_advisor | Kalshi EV + half-Kelly opportunity scan |
| `signals earnings` | signals.earnings_calendar | Fetch + upsert Finnhub earnings calendar |
| `signals rhyme` | signals.rhyme_engine | Cosine similarity vs historical_events corpus |
| `signals hit-rate` | signals.hit_rate | Resolve trade_log outcomes vs price_snapshots |
| `signals execute [ticker]` | execution.executor | Place Alpaca paper orders from recommendations |
| `signals macro-check` | signals.macro_context | Print macro risk verdict + ETF signals |
| `signals tech-check <ticker>` | execution.technical_gate | MACD/RSI/EMA20 pre-trade check |
| `signals tech-backfill` | adapters.massive_history | Backfill price_daily OHLCV history |
| `signals backtest` | signals.hit_rate | Window-based signal accuracy backtest |

---

## Engine Layer

### Core Infrastructure

| File | Purpose | Key exports |
|---|---|---|
| `engine/storage.py` | Shared Postgres layer. Connection pool (psycopg_pool, min 2/max 10). Entity upsert + in-memory cache. Normalized post ingest with dedup on (adapter_id, external_id, entity_id). Ingest + pipeline run bookkeeping. | `get_pool`, `get_conn`, `close_pool`, `EntityResolver`, `write_posts`, `start/finish_ingest_run`, `start/finish_pipeline_step`, `hash_author`, `load_adapter_meta` |
| `engine/adapters/base.py` | Abstract adapter contract (PRD A5.2). `__init_subclass__` validates required class vars at definition time. | `BaseAdapter` (ABC) — `adapter_id`, `source_class`, `tier`, `tos_basis`, `pull(since, cursor)` |
| `engine/adapters/models.py` | Pydantic Post model shared by all adapters and storage. | `Post` (BaseModel), `SourceClass` (Literal union) |
| `engine/global_markets.py` | Overnight global index snapshots via Yahoo Finance chart API. Computes regional verdicts (Asia/Europe/Futures) and `size_modifier` for risk framing. Self-contained; no imports from other engine modules. | `fetch_global_markets()`, `GlobalIndexSnapshot`, `GlobalMarketSummary` |

### Signals

| File | Purpose | Writes to |
|---|---|---|
| `engine/signals/divergence.py` | Core signal engine. Cross-source divergence D-score with permutation p-value. Pulls `sentiment_scores` window + synthesizes `options_flow` rows as sentiment. Writes alert per entity when D is significant. | `divergence_events` |
| `engine/signals/trade_advisor.py` | Maps `divergence_events` to `TradeRecommendation`: Direction (LONG/SHORT/NO_TRADE), SignalTier (LOW/MED/HIGH/EXTREME), half-Kelly position sizing, leveraged ETF routing via `LEVERAGED_ETF_MAP`, resolve-by `Outlook` with catalyst + exit condition. | `trade_log` (via `log_recommendation`) |
| `engine/signals/velocity.py` | Mention velocity from `raw_posts` counts over rolling windows. `VelocityResult` dataclass. | `signal_scores` |
| `engine/signals/narrative.py` | Anthropic Claude API (claude-3-opus). Generates 2-sentence narratives per unnarrated divergence alert using price context, recent headlines, and congress trades. Patches `divergence_events.components` JSONB. | `divergence_events` (narrative field) |
| `engine/signals/rhyme_engine.py` | Cosine similarity between current alert component vectors and `historical_events.phases.components` corpus. `RhymeMatch` dataclass with score + matched event. | `rhyme_matches` |
| `engine/signals/macro_context.py` | 1-day % changes in 10 ETF proxies from `price_daily` (UVXY, TLT, UUP, HYG, EWJ, FXI, EWG, EEM, SPY, QQQ). Produces `MacroVerdict` (RISK_OFF/NEUTRAL/RISK_ON) + `size_modifier`. 15-min TTL cache. | `MacroContext` (in-memory); executor reads verdict to block LONG orders on RISK_OFF |
| `engine/signals/hit_rate.py` | Resolves `trade_log` outcomes vs `price_snapshots`. Computes rolling accuracy windows. Updates `trade_log` with WIN/LOSS/PENDING. | `hit_rate`, `trade_log` (outcome field) |
| `engine/signals/kalshi_watcher.py` | Matches Kalshi open markets to `TradeRecommendation` list. EV + half-Kelly sizing. `KalshiOpportunity` dataclass with `display()`. | `KalshiOpportunity` (in-memory / CLI print) |
| `engine/signals/earnings_calendar.py` | Finnhub earnings calendar as `BaseAdapter`. Upserts `earnings_calendar`. `get_upcoming_earnings()` used by trade_advisor for resolve-by date logic. | `earnings_calendar` |

### Scoring

| File | Purpose | Writes to |
|---|---|---|
| `engine/scoring/orchestrator.py` | FinBERT batch scoring for `retail_social` and `news_wire` source classes only. Per-source-class watermark tracking for incremental runs. Optional `max_posts` cap. | `sentiment_scores`, `scoring_watermark` |
| `engine/scoring/finbert.py` | Local HuggingFace `ProsusAI/finbert` text-classification pipeline on CPU. Lazy init, thread-limited via `FINBERT_CPU_THREADS` env var, torch optional at import. | `FinBERTScorer.score_batch → SentimentScore list` |
| `engine/scoring/base.py` | Scorer factory and abstraction. `SentimentScore` NamedTuple (polarity, confidence). `get_scorer("finbert")` returns `FinBERTScorer`; `"runpod"` raises `NotImplementedError`. | `get_scorer`, `BaseScorer`, `SentimentScore` |
| `engine/scoring/institutional_flow_scorer.py` | Rule-based scorer for `institutional_flow` posts (congressional trades). Log-scale polarity + confidence from parsed trade amount. Separate watermark from FinBERT path. | `sentiment_scores`, `scoring_watermark` |
| `engine/scoring/sector_rollup_scorer.py` | Aggregates constituent stock sentiment into sector/ETF scores weighted by `entity_relationships` position sizes. Minimum coverage and constituent thresholds. Also seeds `entity_relationships` via `seed_entity_relationships()`. | `sector_sentiment`, `sentiment_scores` (source_class=sector_rollup), `entity_relationships` |

### Execution

| File | Purpose | Writes to / Notes |
|---|---|---|
| `engine/execution/executor.py` | Places Alpaca paper orders from trade_advisor output. Guards: market hours, `already_executed_today` dedup, portfolio cap (`MAX_DEPLOYED_PCT` env), macro verdict (blocks LONG on RISK_OFF), technical gate. Stamps `trade_log` with Alpaca order ID. | `trade_log`. **Known issue:** scaled notional is computed (`rec.position_usd × size_modifier × macro_size`) but `rec.position_usd` (unscaled) is passed to `place_order`. |
| `engine/execution/alpaca_broker.py` | `alpaca_trade_api` REST wrapper for paper trading account. Singleton pattern via `get_broker()`. Reads `APCA_API_KEY_ID` + `APCA_API_SECRET_KEY` from env. | `AlpacaBroker`: `place_order`, `get_all_positions`, `close_position`, `is_market_open`, `next_market_open` |
| `engine/execution/technical_gate.py` | Pre-trade chart filter from `price_daily`. Indicators: MACD cross, RSI overbought/oversold, volume vs 20d average, EMA20 trend, 5d momentum. Returns `TechCheckResult` with `TechVerdict` (CONFIRM/WEAK/REJECT/NO_DATA) + `size_modifier`. | `check(entity_id, ticker, direction) → TechCheckResult` |
| `engine/execution/close_positions.py` | Exit logic for open `trade_log` entries. Closes on: `resolve_by` date elapsed, stop-loss note in trade_log, or divergence D < `FADE_D_THRESHOLD` (1.5). Stamps `trade_log` with close order ID + PnL. | `trade_log` (closed_at, close_order_id, pnl fields) |

> **Known issues:**
> 1. `executor.py` computes a scaled notional but passes the unscaled `rec.position_usd` to `place_order`.
> 2. `alpaca_trade_api` is a runtime dependency absent from `pyproject.toml [project.dependencies]`.
> 3. `pyproject.toml` version is `0.0.3` but `__init__.__version__` is `0.0.1`.
> 4. `cli_trade_advice_body.py` is an orphaned fragment not imported by `cli.py`.
> 5. `analyst_curated` source class is not in orchestrator's `SCOREABLE_SOURCE_CLASSES` — Alpha Vantage + Substack posts are ingested but never FinBERT-scored.

---

## Data Adapters

All extend `BaseAdapter`. Path prefix: `src/alphahound/modules/stocks/adapters/`

| File | Source | Output / Table written | Notes |
|---|---|---|---|
| `alpha_vantage.py` | Alpha Vantage | `raw_posts` (analyst_curated, news_wire) | Earnings call transcripts chunked; news via NEWS_SENTIMENT endpoint |
| `apewisdom.py` | ApeWisdom | `raw_posts` (retail_social) | Synthetic posts from Reddit mention rank/count snapshots; no auth required |
| `edgar.py` | SEC EDGAR | `raw_posts` (institutional_flow) | 13F-HR, 13D, 13G, Form 4 Atom feeds; entity IDs use `CIK:` prefix |
| `finnhub.py` | Finnhub | `raw_posts` (retail_social, news_wire) | Per-ticker pull; news `source_class` overridden per Post object |
| `kalshi.py` | Kalshi API | `kalshi_contracts` (direct write) | `pull()` returns empty iterator; writes contract snapshots directly to DB |
| `massive.py` | Polygon.io | `price_snapshots` (direct write) | Prev-day bar + 5d change + vs SPY delta; no raw_posts |
| `massive_history.py` | Polygon.io | `price_daily` (direct write) | Daily OHLCV history; backfill + topup modes; feeds technical_gate + macro_context |
| `quiver.py` | Quiver Quantitative | `raw_posts` (institutional_flow) + `institutional_positions` | Congressional trades; `AMOUNT_MAP` parses dollar ranges to float |
| `stocktwits.py` | StockTwits | `raw_posts` (retail_social) | Author SHA-256 hashed with `ALPHAHOUND_AUTHOR_SALT_STOCKS` |
| `substack.py` | Substack RSS | `raw_posts` (analyst_curated) | Feed URLs loaded from `substack_feeds` table; tickers extracted from article text |
| `unusual_whales.py` | Unusual Whales | `options_flow` (direct write) | Flow alerts synthesized as sentiment polarity in `divergence._pull_sentiment_window` |
| `yahoo_finance.py` | Yahoo Finance RSS | `raw_posts` (news_wire) | Headline RSS per ticker; `resolve_watchlist` imported but unused in file |

---

## Watchlist Module

Path: `src/alphahound/modules/stocks/watchlist/`

| File | Purpose | Key exports |
|---|---|---|
| `watchlist.py` | Canonical ticker universes: `CORE_STOCKS`, `FULL_WATCHLIST` (core + ETFs), `SECTOR_CONSTITUENTS` (ETF → stock mapping), `OPTIONS_WATCHLIST`, `SENTIMENT_WATCHLIST`, `CONGRESS_WATCHLIST`, `SEED_WATCHLIST`, ETF category lists. | `resolve_watchlist(module_id, size)` — delegates to `_dynamic.top_mentioned` or returns `SEED_WATCHLIST` |
| `_dynamic.py` | Top-mentioned symbols from `raw_posts` in a configurable time window. Queries DB directly. | `top_mentioned(module_id, size, window_hours)` |

---

## Dashboard — FastAPI Backend

**`dashboard/api.py`** · 930 lines · FastAPI + psycopg_pool (min 2 / max 5) + simple monotonic-clock TTL dict cache · launched by `scripts/start_dashboard.ps1` via uvicorn.

### API Endpoints

| Endpoint | Cache TTL | Description |
|---|---|---|
| `GET /` | — | Serve `dashboard/index.html` (FileResponse) |
| `GET /api/summary` | 60s | Aggregate counts: alert_count, posts_24h, signals_logged, healthy_runs, entities_active, alerts_24h, engine_status |
| `GET /api/macro` | 120s | Macro verdict + score + size_modifier + per-ETF signal map (calls macro_context module directly) |
| `GET /api/global-markets` | 300s | Yahoo Finance global index snapshots with Asia / Europe / Futures verdicts and size_modifier |
| `GET /api/alerts` | — | Active divergence signals. `?show_all=false` → D≥4.0 (execution threshold); `?show_all=true` → D≥2.0 (monitoring). Returns full `_build_alert` payload: Kelly sizing, tier, leveraged ETF routing, outlook |
| `GET /api/alerts/history` | — | Historical alerts. Params: `?ticker`, `?direction`, `?min_conviction`, `?signal_type`, `?days_back=30`, `?limit=500` |
| `GET /api/ticker/{ticker}/history` | — | Full signal timeline for a single ticker across all time |
| `GET /api/tech-check/{ticker}` | — | Technical gate result: MACD, RSI, EMA20, volume ratio, 5d momentum. Returns TechVerdict + size_modifier |
| `GET /api/tech-check-direction` | — | Multi-ticker direction check for watchlist |
| `GET /api/positions` | — | Alpaca open positions: market value, unrealized P&L, cost basis (calls broker directly) |
| `GET /api/trade-log` | — | `trade_log` entries with Alpaca order IDs, outcome, PnL, resolve_by |
| `GET /api/options-flow` | — | Recent `options_flow` rows from Unusual Whales: premium, type, expiry, ticker |
| `GET /api/congress` | — | Congressional trades from `institutional_positions`: politician, ticker, amount, transaction type |
| `GET /api/earnings` | — | Upcoming earnings from `earnings_calendar` with date + estimate fields |
| `GET /api/universe` | — | Full watchlist table: price, change_1d_pct, change_5d_pct, change_vs_spy, d_value, direction, sentiment per ticker |
| `GET /api/sectors` | — | Sector ETF sentiment rollup: polarity, constituent_count, coverage_pct, d_value, has_alert |
| `GET /api/market-heatmap` | — | All tickers grouped into US Stocks / Sectors / Commodities / International / Macro/Rates with 5d% changes |
| `GET /api/sector-detail/{sector}` | — | Constituent breakdown for one sector ETF with individual stock price + sentiment |
| `GET /api/adapters` | — | Adapter health: last ingest run timestamp, error field, enabled status from source_adapters + ingest_runs |
| `GET /api/hit-rate` | — | Rolling signal accuracy from `hit_rate` table: win_rate, trade_count, avg_pnl per window |

### API Helpers

| Function | Purpose |
|---|---|
| `_build_alert(row, tier_weights)` | Constructs full alert dict: direction (weighted mean of components), conviction score, stop_pct, Kelly-sized position_usd, signal_tier, execute_ticker (leveraged ETF if HIGH/EXTREME), will_execute flag, outlook object |
| `_classify_signal(components)` | Labels signal type: options_led / confirmed / congress / retail_vs_institutional / news_vs_institutional / multi_source |
| `_get_outlook(entity_id, ...)` | Calls `trade_advisor._build_outlook` to get resolve_by date, catalyst, exit_condition, signal_basis |
| `cached(key, ttl) / cache_set(key, val)` | Simple monotonic-clock TTL dict cache shared across all endpoints |
| `get_pool() / get_conn()` | Connection pool singleton; context-manager borrow pattern matching engine/storage.py |

---

## Dashboard — Frontend (Vanilla JS SPA)

**`dashboard/index.html`** + **`dashboard/static/js/`** · No build step — plain ES module scripts served directly by FastAPI StaticFiles. Single page; sections shown/hidden by `nav.js`.

### JavaScript Modules

| File | Purpose | API calls / key functions |
|---|---|---|
| `main.js` | App initialization on DOMContentLoaded. Calls `initNav()` and loads the default view. | `init()`, `loadInitialView()` |
| `nav.js` | Hash-based tab/panel routing. Manages active state and triggers section render on navigation. | `initNav()`, `navigateTo(view)` |
| `config.js` | Shared constants: `UNIVERSE_CATS` (category groupings for universe table), `INTL_LABELS` (ETF display names), poll intervals. | `UNIVERSE_CATS`, `INTL_LABELS` |
| `utils.js` | Shared helpers used across all modules. | `fj(url)` — fetch JSON; `fP(n)` — format percent; `chgColor(n)` — red/green CSS var; `hmColor(n)` — heatmap background; relative time formatter |
| `alerts.js` | Active signals panel. Renders D-score cards with direction pill, conviction bar, Kelly position size, leveraged ticker routing indicator, outlook drawer (resolve-by, catalyst, exit condition), component breakdown. | `/api/alerts` |
| `history.js` | Alert history panel. Filterable table with ticker, direction, signal type, min conviction, days back controls. | `/api/alerts/history` |
| `narratives.js` | Divergence narratives panel. Claude-generated 2-sentence summaries with component polarity breakdown bars. | `/api/alerts` |
| `macro.js` | Macro context panel. Verdict badge (RISK_OFF/NEUTRAL/RISK_ON), score, size_modifier, per-ETF signal breakdown table. | `/api/macro` |
| `positions.js` | Open Alpaca positions panel. Market value, unrealized P&L, cost basis, quantity. | `/api/positions` |
| `tradelog.js` | Trade log panel. Executed trades with Alpaca order IDs, outcome (WIN/LOSS/PENDING), PnL, resolve-by date. | `/api/trade-log` |
| `flow.js` | Options flow panel. Unusual Whales alert table: ticker, premium, type (call/put), expiry, timestamp. | `/api/options-flow` |
| `congress.js` | Congressional trades panel. Quiver data: politician, ticker, amount range, transaction type, date. | `/api/congress` |
| `earnings.js` | Upcoming earnings panel. Finnhub calendar table: ticker, date, estimate, prior EPS. | `/api/earnings` |
| `health.js` | System health panel. Per-adapter last-run time, error indicator, enabled status from adapter registry. | `/api/adapters` |
| `summary.js` | Summary stats bar at page top. Alert count, posts 24h, entities active, engine status (live/stale). | `/api/summary` |
| `views.js` | Three complex views: (1) **Heatmap** — color tiles by 5d% across 5 categories; (2) **Sectors grid** — sentiment bar + D badge + price per sector ETF; (3) **Universe table** — 8-column (ticker, price, 1D%, 5D%, vs SPY, D-val, direction, sentiment); (4) **Global markets** — international ETF + macro/rates tile grids. | `/api/market-heatmap`, `/api/sectors`, `/api/universe` |

---

## Database Tables

Azure PostgreSQL Flexible Server · `alphahound` database

| Table | Written by | Read by | Description |
|---|---|---|---|
| `entities` | `storage.EntityResolver` | all signals + API | Canonical symbol registry. Unique on (module_id, canonical_symbol, kind). In-memory cache in EntityResolver. |
| `raw_posts` | `storage.write_posts` via text adapters | scoring, velocity, _dynamic watchlist | Normalized ingested content. Deduped on (adapter_id, external_id, entity_id). Source class, author hash, text, published_at, raw JSONB. |
| `sentiment_scores` | orchestrator, institutional_flow_scorer, sector_rollup_scorer | divergence, sector rollup, API | FinBERT + rule-based polarity/confidence per post per entity. Watermark-tracked for incremental scoring. |
| `divergence_events` | `signals.divergence` | trade_advisor, narrative, rhyme, executor, API | D-score + p-value + components JSONB (source class → polarity + narrative) per entity per time. |
| `trade_log` | `trade_advisor.log_recommendation`, executor | close_positions, hit_rate, API | Logged recommendations (signal venue) + Alpaca order IDs (live venue) + outcome + PnL + resolve_by. |
| `price_snapshots` | `adapters.massive` | narrative, trade_advisor, divergence, API | Prev-day close price + change_1d_pct + change_5d_pct + change_vs_spy per entity. |
| `price_daily` | `adapters.massive_history` | technical_gate, macro_context | Daily OHLCV bars from Polygon.io. Backfill + incremental topup modes. |
| `options_flow` | `adapters.unusual_whales` | divergence (synthetic sentiment), API | Unusual Whales alert rows: premium, put/call, expiry, ticker, timestamp. |
| `kalshi_contracts` | `adapters.kalshi` | kalshi_watcher (live API bypass) | Prediction market contract snapshots: market, yes/no price, volume, close_time. |
| `earnings_calendar` | earnings_calendar adapter | trade_advisor, API | Upcoming earnings per ticker: date, EPS estimate, prior EPS. |
| `institutional_positions` | `adapters.quiver` | API (/api/congress) | Congressional trade details: politician, ticker, amount, transaction type, filing date. |
| `signal_scores` | `signals.velocity` | CLI / diagnostic only | Mention velocity scores per entity per time window. |
| `sector_sentiment` | `scoring.sector_rollup_scorer` | API (/api/sectors) | Aggregated ETF/sector sentiment: polarity, constituent_count, coverage_pct, time. |
| `hit_rate` | `signals.hit_rate` | API (/api/hit-rate) | Rolling signal accuracy windows: win_rate, trade_count, avg_pnl. |
| `rhyme_matches` | `signals.rhyme_engine` | CLI / diagnostic only | Cosine similarity matches vs historical corpus: match score, matched event name, component vectors. |
| `scoring_watermark` | orchestrator, institutional_flow_scorer | same scorers | High-water mark timestamps for incremental FinBERT + rule-based scoring by source_class. |
| `ingest_runs` | `storage.start/finish_ingest_run` | API (/api/adapters), db ingest-runs CLI | Per-adapter ingest job bookkeeping: started_at, finished_at, post_count, error. |
| `source_adapters` | manual seed | cli.ingest-all, storage.load_adapter_meta | Adapter registry: source name, enabled flag, module, config JSONB. |
| `substack_feeds` | manual seed | `adapters.substack` | Substack RSS feed URLs for analyst newsletter ingestion. |
| `historical_events` | manual seed | `signals.rhyme_engine` | Historical market event corpus with named phases and component polarity vectors. |
| `entity_relationships` | `sector_rollup_scorer.seed_entity_relationships` | sector_rollup_scorer | Sector ETF → constituent stock mappings with position weight for sentiment aggregation. |

---

## External API Integrations

| Service | Used by | Data provided | Auth |
|---|---|---|---|
| Alpha Vantage | `alpha_vantage.py` | Earnings call transcripts (chunked), news sentiment | API key (env) |
| ApeWisdom | `apewisdom.py` | Reddit mention leaderboard snapshots | None (public) |
| SEC EDGAR | `edgar.py` | 13F-HR, 13D, 13G, Form 4 Atom feeds | None (public) |
| Finnhub | `finnhub.py`, `earnings_calendar.py` | Social sentiment aggregate, company news, earnings calendar | API key (env) |
| Kalshi | `kalshi.py`, `kalshi_watcher.py` | Prediction market contracts + open markets live scan | API key (env) |
| Polygon.io (Massive) | `massive.py`, `massive_history.py` | Prev-day price bars, full daily OHLCV history | API key (env) |
| Quiver Quantitative | `quiver.py` | Congressional trades with politician + amount | API key (env) |
| StockTwits | `stocktwits.py` | Retail social stream per ticker symbol | Public endpoint |
| Substack RSS | `substack.py` | Analyst newsletter RSS/Atom feeds | None (public RSS) |
| Unusual Whales | `unusual_whales.py` | Options flow alerts + expiry breakdown | API key (env) |
| Yahoo Finance | `yahoo_finance.py`, `global_markets.py` | RSS headline news per ticker; global index chart data | None (public) |
| Anthropic Claude | `signals/narrative.py` | 2-sentence divergence narrative generation | `ANTHROPIC_API_KEY` (env) |
| Alpaca Markets | `execution/alpaca_broker.py` | Paper trade order placement + position management | `APCA_API_KEY_ID` + `APCA_API_SECRET_KEY` (env) |
| Azure PostgreSQL | `engine/storage.py`, `dashboard/api.py` | All persistent storage | `DATABASE_URL` conn string (env) |

---

## Operational Scripts

Path: `scripts/` · Mix of Python diagnostics and PowerShell schedulers / Windows Task Scheduler registration.

| File | Type | Purpose |
|---|---|---|
| `session_start.py` | Python | Full session init: runs ingest-all + score-new + divergence-scan in sequence |
| `run_pipeline_step.py` | Python | Run a single named pipeline step (ingest / score / divergence / execute) with logging |
| `close_all_positions.py` | Python | Force-close all open Alpaca paper positions immediately |
| `check_backlog.py` | Python | Report unscored post backlog size per source class |
| `check_divergence.py` | Python | Print recent divergence_events with D values to console |
| `check_keys.py` | Python | Verify all required env API keys are present and non-empty |
| `check_signals.py` | Python | Print recent signal_scores + current trade recommendations |
| `global_markets.py` | Python | One-shot global markets snapshot print (calls engine/global_markets.py) |
| `diagnose.py` | Python | DB connectivity + table row counts diagnostic |
| `diagnose2.py` | Python | Adapter-level ingest health diagnostic (last run per adapter) |
| `diagnose3.py` | Python | Signal pipeline state diagnostic (scoring watermarks + divergence counts) |
| `start_dashboard.ps1` | PowerShell | Launch uvicorn serving dashboard/api.py on configured port |
| `ingest_all.ps1` | PowerShell | Scheduled ingest-all wrapper with file logging and error capture |
| `ingest_earnings.ps1` | PowerShell | Scheduled earnings calendar fetch wrapper |
| `score_new.ps1` | PowerShell | Scheduled FinBERT scoring run wrapper |
| `register_scheduled_task.ps1` | PowerShell | Register Windows Task Scheduler tasks for ingest + score pipeline |
| `register_score_task.ps1` | PowerShell | Register scoring-specific Windows Task Scheduler task |
| `register_assessment_task.ps1` | PowerShell | Register assessment-service Windows Task Scheduler task |
| `assessment_service.py` | Python | Generates `docs/status/assessment.json` + DB row every 15 min — feeds `/api/assessment` |
| `status_monitor.py` | Python | Purpose undocumented — no comments or register script explain it |

---

## Scheduled Tasks (Windows Task Scheduler)

Live on repsportalvm. Three have a matching `register_*.ps1` in this repo; two do not (set up outside source control — treat as undocumented until someone finds/writes their setup).

| Task Name | Trigger | Runs | Description | Registered via |
|---|---|---|---|---|
| `AlphaHound-Ingest` | Every 15 min, aligned to :00/:15/:30/:45 | `ingest_all.ps1` | Main pipeline: `ingest_parallel.py` (6 adapters, parallel) → `compute-all` → `score-institutional` → `convergence-scan` → *(market hours 6:30am–1pm PT only)* `options-monitor --close` → `options-execute` → `health-check`. 6am-only extras: `massive-history` + `seed-catalysts`. Logs: `logs/ingest_YYYY-MM-DD.log`. | `register_scheduled_task.ps1` |
| `AlphaHound-Score` | Every 30 min, offset +7 min from :00/:30 (avoids overlapping Ingest) | `score_new.ps1` | FinBERT sentiment scoring (`score-new --max-posts 500`), split out from the main pipeline so CPU spikes don't block ingestion. Logs: `logs/score_YYYY-MM-DD.log`. | `register_score_task.ps1` |
| `AlphaHound-Assessment` | Every 15 min | `assessment_service.py` (direct — no `.ps1` wrapper) | Generates `docs/status/assessment.json` + DB row; feeds `/api/assessment`. | `register_assessment_task.ps1` |
| `AlphaHound-Earnings` | Daily, 6:00 AM | `ingest_earnings.ps1` | Pulls upcoming earnings dates (Finnhub) for the watchlist, next 30 days. | ⚠️ Not in `scripts/` — registered outside this repo |
| `AlphaHound-StatusMonitor` | Unknown | `status_monitor.py` | Purpose not documented. | ⚠️ Not in `scripts/` — registered outside this repo |

**⚠️ Status as of Sept 9, 2026** (`Get-ScheduledTaskInfo`): every task's `LastRunTime` is frozen at **6/28/2026** — ~2.5 months ago — despite `NextRunTime` showing upcoming times. Result codes from that last run:

| Task | Last Result | Meaning |
|---|---|---|
| `AlphaHound-Ingest` | `267014` (hex `0x41306`) | `SCHED_S_TASK_TERMINATED` — killed, most likely by the 10-min `ExecutionTimeLimit` in `register_scheduled_task.ps1` |
| `AlphaHound-Assessment` | `1` | Generic failure |
| `AlphaHound-StatusMonitor` | `1` | Generic failure |
| `AlphaHound-Score` | `0` | Success — but also hasn't run again since |
| `AlphaHound-Earnings` | `0` | Success — same freeze |

**Leading theory:** `AlphaHound-Ingest` was hard-killed mid-run on 6/28. Its `MultipleInstances` setting is `IgnoreNew` — if Task Scheduler's internal state still believes an instance is "running," it would silently skip every subsequent trigger, explaining why *all* tasks stopped updating at the same moment. Unconfirmed pending `Get-ScheduledTask -TaskName "AlphaHound-Ingest" | Select State` on the server. If `State` shows `Running`, unregister + re-register the task.

---

*AlphaHound v0.0.3 · Python ≥3.11 · hatchling · ruff + pytest (dev) · 14 external API integrations*
