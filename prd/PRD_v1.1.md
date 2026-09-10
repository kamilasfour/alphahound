# AlphaHound — Product Requirements Document (v1.1)
## Multi-Industry Sentiment Intelligence Platform — Stock Trading Module

**Author:** Kamil Asfour | **Date:** April 16, 2026
**Status:** FINAL DRAFT v1.1 — Ready for architecture and build
**Version Notes:** v1.1 adds prediction markets (data + trading venue), expanded data sources (Substack, YouTube/podcasts, short seller reports, Congressional trading, activist filings), and personal validation (user-zero) plan.
**Research Sources:** Perplexity Deep Research, Claude Sonnet 4.6, Gemini Deep Research, ChatGPT Deep Research (4 AI synthesis)

---

## 1. Executive Summary

AlphaHound is a real-time multi-industry sentiment intelligence platform. The stock trading module (MVP) ingests social media, news, institutional filings, options flow, alternative analyst content (Substack, podcasts, short seller reports), and prediction market probabilities to produce scored trading signals with a unique differentiator: a "Rhyme Engine" that matches current market events to structurally similar historical crises and predicts outcomes based on how those crises resolved.

**The proof (dual track):**
1. **Equity track:** Turn $5,000 into $1,000,000 using AlphaHound signals in a Schwab/Merrill account
2. **Prediction market track:** Turn $1,000 into $50,000 using AlphaHound signals on Kalshi/Polymarket

Both tracks log every trade with specific signal attribution, generating two verifiable case studies for the SaaS product.

**The business:** SaaS platform selling sentiment data, signal scores, historical pattern intelligence, and prediction market probabilities to retail traders, quantitative analysts, and eventually institutional clients. Later modules extend the same engine to real estate, automotive, F&B, and any industry where sentiment drives outcomes.

**User Zero:** Kamil runs the system on himself first — personal validation across both equities and prediction markets — before opening paid tiers.

## 2. Problem Statement

### 2.1 The Problem
Current retail sentiment tools fall into two categories: cheap-but-shallow (StockTwits bull/bear ratios, ApeWisdom mention counts) or expensive-but-institutional (RavenPack at $50K+/yr, ICE Reddit Signals on the Consolidated Feed, ICE Polymarket distribution). No tool combines social sentiment, institutional flow, options activity, alternative analyst content, prediction market probabilities, AND historical pattern matching in one platform at a price retail traders can afford.

### 2.2 The Gap (Confirmed by Research)
All four AI research sources independently confirmed: **no commercial platform has productized historical event-to-event pattern matching.** The closest implementations are a student CS50P project and a free TradingView indicator. This is a genuine blue ocean.

Additional gaps:
- No retail tool detects **cross-source divergence** — Reddit bullish + institutional 13F net selling + heavy put buying
- No retail tool systematically ingests **Substack analyst content** (Doomberg, Net Interest, Macro Compass) where institutional narratives first appear
- No retail tool monitors **short seller report releases** in real-time (Hindenburg drops move stocks 10-30% in days)
- No retail tool uses **prediction market probabilities** (Polymarket, Kalshi) as sentiment inputs AND trading venues
- No retail tool tracks **Congressional trading disclosures** as a signal layer

Raw Reddit sentiment is now commoditized (ICE launched Reddit Signals & Sentiment on January 28, 2026, processing 16B+ posts for institutional clients). The edge has moved upstream to curation, divergence detection, and alternative sources.

### 2.3 AlphaHound's Edge
1. **Rhyme Engine** — Historical pattern matching (blue ocean, zero competition)
2. **Cross-Source Divergence** — Social vs. institutional vs. options flow vs. prediction market conflict detection
3. **Two-Tier AI** — FinBERT speed + LLM reasoning depth (industry best practice, not implemented by any retail tool)
4. **Global Cascade Scoring** — Asian → European → US market flow prediction (unique feature)
5. **Prediction Markets Integration** — Data input AND trading venue (Kalshi/Polymarket)
6. **Alternative Analyst Content** — Substack, YouTube/podcast, short seller reports, activist filings
7. **Affordability** — $49-149/month vs. $50K+/year for institutional alternatives

## 3. User Personas

### 3.1 User Zero: Kamil (Personal Validation)
- Full-stack AI developer, Azure infrastructure
- Trades Schwab thinkorswim (stocks/options/futures/forex) + Merrill Lynch + Kalshi + Polymarket
- Goal: validate every signal personally before opening paid tiers
- Two proof accounts running in parallel (equity + prediction markets)
- Every trade logged with signal attribution for public track record

### 3.2 Primary: Active Retail Swing Trader
- Trades 3-10 times per week, holds 1-5 days
- Uses thinkorswim/Merrill/Robinhood + Kalshi, $5K-$100K accounts
- Wants: actionable signals with entry/exit/stop, confidence scores, "what's brewing that I don't know yet"
- Pain: drowning in noise, can't tell if Reddit hype is organic or manipulation, no historical context

### 3.3 Secondary: Quantitative Developer
- Builds algorithmic strategies, needs API access
- Wants: JSON sentiment scores per ticker, historical data for backtesting, real-time WebSocket feed
- Pain: existing APIs either too expensive (RavenPack) or too shallow (StockTwits)

### 3.4 Tertiary: Financial Content Creator
- Makes YouTube/Substack content about markets
- Wants: unique data points, historical comparisons, visual dashboards
- Pain: everyone uses the same charts and data

### 3.5 Quaternary: Prediction Market Traders
- Active on Kalshi, Polymarket, Manifold
- Want: AI-driven probability estimates, divergence between prediction markets and equities
- Pain: no tool combines prediction market analysis with broader market sentiment

## 4. Core Features (Prioritized)

### P0 — Must Ship for MVP
1. **Multi-Source Sentiment Scoring** — Signal score (1-10) + confidence score (1-10) per ticker from Reddit, StockTwits, news, options flow, SEC filings
2. **Cross-Source Divergence Detection** — Alert when retail sentiment contradicts institutional positioning
3. **Two-Tier AI Scoring** — FinBERT bulk + Claude narrative reasoning
4. **REST API** — `GET /signals/{ticker}` returning JSON with score, confidence, components, narrative
5. **Historical Pattern Matching (Rhyme Engine)** — DTW-based event matching against 20+ curated historical crises
6. **Proof Account Dashboard** — Live $5K → $1M trade log with signal attribution

### P1 — Ship for v1.1 (Phase 1.5)
7. **Substack Ingestion** — RSS monitoring for 20+ priority newsletters (Doomberg, Net Interest, Macro Compass, etc.)
8. **Short Seller Report Monitoring** — Real-time detection of Hindenburg/Muddy Waters/Kerrisdale reports
9. **Congressional Trading Tracker** — STOCK Act disclosures via Quiver Quantitative
10. **Activist Investor 13D Filings** — Elliott, Pershing Square, Trian, Icahn, Starboard alerts
11. **Kalshi Data Ingestion** — CFTC-regulated prediction market probabilities as sentiment input
12. **Global Cascade Scoring** — Overnight Asian/European session analysis predicting US open

### P2 — Ship for v1.2 (Phase 2)
13. **YouTube/Podcast Transcript Pipeline** — Whisper-based transcription of top finance channels (Odd Lots, Meet Kevin, Macro Voices, etc.)
14. **Polymarket Data Ingestion** — Geopolitical, crypto, election markets as sentiment inputs
15. **Kalshi Trading Module** — AlphaHound signals placing bets via Kalshi API (second proof track)
16. **Real-Time WebSocket Feed** — Streaming signal updates for algo traders
17. **Backtesting Module** — Walk-forward analysis of signals against 3-5 years of history
18. **Bot/Manipulation Detection** — Social volume spike + zero institutional confirmation = pump-and-dump flag

### P3 — Ship for v2.0 (Phase 3)
19. **Polymarket Trading Module** — Automated geopolitical/event bet execution
20. **Web Dashboard** (React) with interactive charts
21. **Options Strategy Recommender** based on signal confidence
22. **Mobile Alerts** (push notifications on divergence/extreme signals)
23. **Earnings Call Transcript Monitoring** — via AlphaSense/Seeking Alpha/The Transcript

### P4 — Future Roadmap
24. **Multi-Industry Modules** (Real Estate, Auto, F&B)
25. **Cross-Asset Arbitrage Engine** — Kalshi vs Polymarket vs options-implied probability
26. **Alternative Data Integration** — Satellite, credit card, web traffic (institutional tier only)

## 5. Data Sources

### 5.1 MVP Tier (~$500/month total API cost)

| Source | What It Provides | Cost | Priority |
|---|---|---|---|
| **ApeWisdom** | Reddit mention volume, trending tickers | Free | P0 |
| **StockTwits API** | Bull/bear ratios, message stream | Free (200 calls/hr) | P0 |
| **SEC EDGAR** | 13F filings, insider Form 4, 8-K events | Free | P0 |
| **Unusual Whales API** | Options flow, dark pool, sweeps | $65-150/mo | P0 |
| **FMP or Polygon.io** | Market data, prices, fundamentals, 30yr history | $79-199/mo | P0 |
| **Google Trends** | Search volume (pytrends) | Free | P1 |
| **FRED** | Macro economic data | Free | P1 |
| **FINRA** | Short interest (bi-monthly) | Free | P1 |
| **CFTC COT** | Futures positioning (weekly) | Free | P1 |

### 5.2 Phase 1.5 Additions (+$40-200/month — high signal-to-noise, low cost)

| Source | What It Provides | Cost | Priority |
|---|---|---|---|
| **Substack RSS** (20 newsletters) | Doomberg, Net Interest, Macro Compass, Matt Stoller, Daily Upside, Epsilon Theory, etc. | Free | P1 |
| **Quiver Quantitative** | Congressional trading (STOCK Act) | $10/mo | P1 |
| **Short seller RSS/scraping** | Hindenburg, Muddy Waters, Kerrisdale, Spruce Point | Free | P1 |
| **SEC 13D filings feed** | Activist investor positions (Elliott, Pershing, etc.) | Free | P1 |
| **The Transcript** (newsletter) | Curated earnings call highlights | Free | P1 |
| **BusinessWire/PR Newswire** | Company press releases (often ahead of aggregators) | Free-$100/mo | P1 |
| **Kalshi API** | CFTC-regulated prediction market probabilities | Free (usage-based) | P1 |
| **Federal Register** | Regulatory changes, comment periods | Free | P2 |

### 5.3 Phase 2 Additions (+$100-300/month)

| Source | What It Provides | Cost | Priority |
|---|---|---|---|
| **Polymarket API** | Crypto/geopolitics/election probabilities | Free (API) | P2 |
| **YouTube Data API + Whisper** | Transcripts from Odd Lots, Meet Kevin, Macro Voices, Patrick Boyle, Ben Felix, etc. | ~$30-80/mo | P2 |
| **Podcast transcription** | Forward Guidance, Chat with Traders, Grant Williams, Compound & Friends | ~$30/mo | P2 |
| **LunarCrush** | X+Reddit+TikTok aggregated sentiment | $99-499/mo | P2 |
| **Benzinga Pro** | Real-time professional news | $99/mo | P2 |
| **Seeking Alpha Quant** | Systematic contributor scores | ~$240/yr | P2 |
| **TipRanks API** | Aggregated analyst ratings + price targets | $30-70/mo | P2 |

### 5.4 Production Scale (~$1,000-2,000/month when revenue justifies)

| Source | Cost | When to Add |
|---|---|---|
| Reddit API (commercial license) | $1,000+/mo | When revenue covers it |
| X/Twitter official API (pay-per-use) | $215+/mo at ~43K posts | When revenue covers it |
| SentimenTrader | $149/mo | Historical sentiment backtesting |
| AlphaSense | $$$ | Earnings calls + expert network |
| Hedgeye Research | $$$ | Institutional contrarian signals |

### 5.5 Alternative Data (Institutional Tier Only)

| Source | Use Case |
|---|---|
| Flight tracking (ADS-B Exchange) | Private jet signals for M&A activity |
| AIS ship tracking | Tanker movements (already in cascade) |
| Satellite (MDA/Planet Labs/RS Metrics) | Oil storage, retail foot traffic |
| Second Measure / Bloomberg SMBL | Credit card spending data |
| SimilarWeb/Semrush | Company web traffic |
| Apptopia/Sensor Tower | App download trends |
| Revelio Labs | Job postings / hiring signals |

### 5.6 Skip for MVP
- Bloomberg/Reuters Terminal (enterprise pricing, overkill)
- Direct X API at enterprise tier ($7,500/mo — use aggregator or pay-per-use)
- RavenPack ($50K+/yr — we're competing with them, not buying from them)
- Most alternative data (high cost, low ROI until institutional tier)

## 6. Prediction Markets: Dual Role

### 6.1 As INPUT (Sentiment Data Source)
Prediction markets produce crowd-weighted probability signals with real money backing — potentially cleaner than Reddit/X where talk is cheap.

**Kalshi (primary):**
- CFTC-regulated US prediction exchange
- Clean API, legal for US retail
- Markets on Fed decisions, CPI, NFP, earnings beats, GDP, weather, geopolitics
- Start here (lowest regulatory risk)

**Polymarket (secondary):**
- Largest prediction market (~$5B+ annual volume)
- USDC-settled on Polygon blockchain
- Rich geopolitical, election, crypto markets
- US access grey area (CFTC 2022 settlement) — monitor 2026 status

**ICE Consolidated Feed Validation:**
ICE started distributing Polymarket data to institutional subscribers in February 2026. If ICE considers prediction market probabilities institutional-grade alt data, AlphaHound must ingest them.

### 6.2 As OUTPUT (Trading Venue)
AlphaHound signals drive bets directly on Kalshi/Polymarket. This becomes a second proof track alongside the equity account.

**Why trading prediction markets is a cleaner validation:**
- **Binary outcomes** — easier to backtest, cleaner win-rate math
- **No time decay weirdness** — price converges linearly to resolution
- **No PDT rule, no Greeks, no assignment risk**
- **Lower capital requirements** — $5-$50 position sizing for testing
- **Event-specific markets match sentiment signals 1:1**

### 6.3 Event-to-Instrument Mapping

| Event Type | Prediction Market Play | Correlated Equity Play |
|---|---|---|
| Fed rate decisions | Kalshi Fed markets | TLT, IEF, XLF, KRE, SPY |
| CPI beat/miss | Kalshi CPI markets | TLT, TIP, GLD |
| Geopolitical escalation | Polymarket conflict markets | XLE, XOP, STNG, RTX, GLD |
| Election outcomes | Polymarket election | Sector rotation (XLE vs XLV) |
| Earnings beat/miss | Kalshi earnings | Specific ticker options |
| Recession probability | Kalshi/Polymarket | IWM, XRT, HYG, TLT |
| Crypto regulation | Polymarket crypto | COIN, MARA, IBIT |

### 6.4 Cross-Asset Arbitrage
When Polymarket probability and equity-implied probability diverge, that's an alpha window. The latency chain:
1. News breaks (wire/Twitter)
2. Polymarket re-prices (minutes)
3. Options flow reacts (minutes to hours)
4. Equity sectors rotate (hours)
5. Analyst reactions (days)

AlphaHound catches steps 2-4 and routes capital to whichever asset class has the biggest mispricing.

## 7. AI/ML Architecture

### Two-Tier System (Validated by All Research Sources)

**Tier 1 — FinBERT Fast Scoring (all posts, 100K/day)**
- Model: ProsusAI/finbert (self-hosted on Azure T4 GPU)
- Accuracy: ~87% F1 on financial news, ~65-70% on Reddit (untuned), ~80-85% (fine-tuned on WSB data)
- Speed: ~500 posts/sec on T4 GPU = 100K posts in ~200 seconds
- Cost: ~$13/day (Azure NC4as_T4_v3 VM)
- Output: (ticker, sentiment polarity -1 to +1, confidence 0-1)

**Tier 2 — Claude API Deep Reasoning (500-3,000 calls/day)**
- Triggered by: velocity spikes >2σ, source divergence, low FinBERT confidence (<0.60), novel entities, multi-entity posts, prediction market probability shifts >5%, new Substack/short seller posts on priority tickers
- Input: post text + 5-post context window + recent price + 7-day sentiment baseline + prediction market probability
- Output: narrative summary, emerging theme, confidence adjustment, divergence warning, rhyme trigger
- Cost: ~$5-10/day at 500-3,000 calls
- Critical: Use System 1 prompting (fast, intuitive classification) NOT Chain-of-Thought — research shows CoT degrades financial sentiment accuracy

**Escalation rate:** 3-8% of posts escalate to Tier 2

### Scoring Engine (Revised for v1.1)

**Signal Score (1-10):**
| Component | Weight | Source |
|---|---|---|
| Mention volume & velocity | 20% | ApeWisdom, StockTwits, Reddit |
| Options flow alignment | 18% | Unusual Whales |
| Sentiment polarity (FinBERT) | 13% | All social posts |
| Source consensus | 13% | Cross-source agreement |
| Prediction market alignment | 10% | Kalshi/Polymarket |
| Institutional alignment (13F) | 8% | SEC EDGAR |
| LLM narrative quality | 8% | Claude Tier 2 |
| Alt analyst signal (Substack/YouTube/podcasts) | 6% | Curated analyst feeds |
| Historical pattern match | 4% | Rhyme Engine |

**Dynamic adjustment:**
- During high-volatility events (earnings, Fed, geopolitical): volume/velocity to 30%, polarity to 8%, prediction market weight to 15%
- During low-volatility drift: Substack/analyst weight to 12%, polarity to 16%

**Confidence Score (1-10):**
| Component | Weight |
|---|---|
| Post volume (50+ = conf 5, 200+ = conf 8) | 35% |
| Source diversity (4+ platforms = higher) | 30% |
| Time recency (decays after 48h) | 20% |
| Bot filter pass rate | 10% |
| Prediction market liquidity (if applicable) | 5% |

### Alt Analyst Tier Weighting
Not all sources are equal. Weight by historical track record:

| Source Tier | Examples | Weight Multiplier |
|---|---|---|
| Tier A (proven institutional) | Doomberg, Net Interest, Hindenburg, Muddy Waters | 2.0x |
| Tier B (reputable independent) | Macro Compass, Matt Stoller, Bethany McLean | 1.5x |
| Tier C (retail-focused) | Meet Kevin, Joseph Carlson, WSB top DD | 1.0x |
| Tier D (noise) | Generic Reddit posts, retail Twitter | 0.5x |

### Sarcasm Handling
Research confirms sarcasm detection on Reddit achieves ~72-76% F1 at best. Practical mitigation:
1. **Volume > Polarity** for meme stocks (volume is harder to fake with sarcasm)
2. **Custom slang dictionary** maintained for WSB jargon
3. **Subreddit weighting** (WSB = higher sarcasm density, lower polarity weight)
4. **LLM escalation** for ambiguous cases
5. **Market cap filter** (exclude <$100M to avoid pump-and-dump targets)

## 8. Rhyme Engine (Historical Pattern Matching)

### Algorithm: Dynamic Time Warping (DTW)
- Library: `dtaidistance` (fastest: 0.000110 sec/comparison)
- Approach: Normalize price paths as % change from event day 0, use Sakoe-Chiba window (±15-20% of series length)
- Matching: Current 14-30 day price vector vs. historical database

### Three-Layer Matching
1. **Event Type Classification** (Claude API) — Embed current event description, classify as oil shock / military conflict / supply chain / sentiment extreme / financial panic / regulatory shift / pandemic
2. **Price Path DTW** — Match current asset trajectory against same-type historical events
3. **Phase Position** — Estimate where we are in the typical crisis lifecycle (shock → adaptation → normalization)

### Seed Database: 20-50 Curated Events
Start manually, scale later via FNSPID dataset (29.7M stock prices + 15.7M news records, 1999-2023).

**Priority events:**
- 5 oil shocks (1973, 1979, 1990, 2008, 2022)
- 3 military conflicts (Gulf War, Iraq, Russia-Ukraine)
- 4 supply chain (Japan 2011, Suez 2021, COVID, semiconductor)
- 4 sentiment extremes (GameStop, crypto winter, COVID crash, current Iran)
- 4 macro (taper tantrum 2018, rate shock 2022, COVID emergency cuts, tariff volatility 2025)

Additional datasets: IMF Systemic Banking Crises Database (151 banking crises, 414 currency crises, 1970-2019), Reinhart/Rogoff database (800 years of financial crises).

### Historical Prediction Market Patterns (v1.1 addition)
For events where prediction markets existed historically, track how probability trajectories resolved:
- 2024 election cycle — Trump/Harris probability moves vs equity sector rotation
- COVID markets (2020) — Polymarket vs reality
- Fed meeting markets (2022-2025) — probability accuracy pre-decision

### Output Format
```json
{
  "current_event": "2026 Strait of Hormuz blockade",
  "event_type": "oil_supply_shock",
  "phase_position": "week 7 of estimated 8-12 week acute phase",
  "top_matches": [
    {
      "event": "1990 Gulf War oil shock",
      "similarity": 0.78,
      "what_happened": "Tanker stocks peaked week 6-8, gave back 30% over next 3 months",
      "current_implication": "If pattern holds, tanker stocks may be near peak"
    }
  ],
  "prediction_market_signal": {
    "kalshi_probability_de_escalation_30d": 0.34,
    "polymarket_probability_us_strike": 0.28,
    "historical_analog_resolution": "Gulf War markets priced resolution 2-3 weeks before actual"
  }
}
```

## 9. Global Cascade Scoring

### Sessions Tracked
1. **Asian (7 PM - 3 AM ET):** Nikkei, Hang Seng, Shanghai, KOSPI, ASX + Asian commodities + USD/JPY, AUD/USD
2. **European (3 AM - 9:30 AM ET):** FTSE, DAX, CAC + Brent crude + EUR/USD, GBP/USD
3. **US Pre-Market (4 AM - 9:30 AM ET):** /ES, /NQ, /CL, /GC futures + VIX futures
4. **Prediction Market Overnight (24/7):** Polymarket/Kalshi probability shifts during off-hours

### Signal
"Asian energy sold off 2.1% overnight on Hormuz escalation → European energy amplified to -3.4% → US futures /CL down 1.8% pre-market → Polymarket 'Hormuz blockade extends 30d' probability jumped 62% to 78% → Historical cascade pattern predicts US energy open gap-down 70% probability"

## 10. System Architecture

```
[Data Ingestion — Async Python Workers]
  ApeWisdom (free) ──────────┐
  StockTwits API (free) ─────┤
  Reddit PRAW (free tier) ───┤
  SEC EDGAR (free) ──────────┤──→ Redis/Azure Service Bus
  Unusual Whales ($65/mo) ───┤      (message queue)
  FMP/Polygon ($199/mo) ─────┤
  Substack RSS (free) ───────┤
  Short seller feeds ────────┤
  Quiver Congressional ──────┤
  13D activist filings ──────┤
  Kalshi API ────────────────┤
  Polymarket API ────────────┤
  YouTube/Podcast Whisper ───┘

[Processing — FastAPI + Celery on Azure]
  Source Classifier (Tier A/B/C/D weighting)
  Tier 1: FinBERT on T4 GPU (~500 posts/sec)
    → (ticker, polarity, confidence)
    → Escalation check
  Tier 2: Claude API (500-3K calls/day)
    → (narrative, divergence, rhyme_trigger)
  Rhyme Engine: DTW matching
    → (similarity_score, phase_position, prediction)
  Prediction Market Correlator
    → (equity_pm_divergence, arb_opportunity)

[Storage — PostgreSQL + TimescaleDB]
  sentiment_scores (ticker, timestamp, score, confidence, source, source_tier)
  signal_scores (ticker, timestamp, signal_1to10, confidence_1to10)
  narratives (ticker, timestamp, summary, category)
  historical_events (event_id, type, phases, asset_impacts)
  pattern_matches (current_event, historical_event, similarity)
  prediction_markets (market_id, venue, probability, timestamp, tickers_linked)
  alt_analyst_posts (author, source_tier, post_url, tickers, sentiment)
  trade_log_equity (trade_id, signal_id, entry, exit, pnl)
  trade_log_pm (bet_id, signal_id, venue, probability_entry, probability_exit, pnl)

[Execution — Trading Modules]
  Equity execution (manual/API — Schwab, Merrill)
  Kalshi execution (API — P2+)
  Polymarket execution (API — P3+)

[API — FastAPI]
  GET  /signals/{ticker}
  GET  /narratives/{ticker}
  GET  /rhyme/{event}
  GET  /cascade/overnight
  GET  /divergence/active
  GET  /prediction_markets/{topic}
  GET  /alt_analyst/recent
  GET  /short_sellers/active
  GET  /congressional/recent
  WS   /stream/{tickers}
  WS   /stream/prediction_markets
```

## 11. Infrastructure & Budget

### Azure VMs
| Component | SKU | Monthly Cost |
|---|---|---|
| FinBERT + Whisper Inference | Standard_NC4as_T4_v3 (T4 GPU) | ~$384 |
| PostgreSQL + FastAPI | Standard_D4s_v3 | ~$130 |
| Redis (message queue) | Azure Cache for Redis C1 | ~$50 |
| **Total Compute** | | **~$564/mo** |

### API Costs (MVP)
| Source | Monthly Cost |
|---|---|
| ApeWisdom | Free |
| StockTwits | Free |
| SEC EDGAR | Free |
| Unusual Whales | $65 |
| FMP/Polygon | $199 |
| Claude API (Tier 2) | ~$150-300 |
| **Total MVP API** | **~$414-564/mo** |

### MVP Total: ~$978-1,128/month

### Phase 1.5 Additional Costs (+$40-200/month)
| Source | Monthly Cost |
|---|---|
| Substack RSS | Free |
| Quiver Quantitative | $10 |
| Short seller RSS | Free |
| Kalshi API | Free (trading fees only) |
| The Transcript newsletter | Free |
| BusinessWire feed | Free-$100 |
| **Phase 1.5 addition** | **~$10-110/mo** |

### Phase 2 Additional Costs (+$100-300/month)
| Source | Monthly Cost |
|---|---|
| YouTube Data API + Whisper compute | $30-80 |
| Podcast transcription | $30 |
| Polymarket API | Free |
| Benzinga Pro (optional) | $99 |
| TipRanks API | $30-70 |
| **Phase 2 addition** | **~$90-280/mo** |

### Total at Full Data Coverage: ~$1,100-1,500/month

### CPU-Only Alternative: ~$600/month total
Replace T4 GPU with Standard_D8s_v3 (~$400/mo) — FinBERT inference drops to ~20 posts/sec but handles 100K/day in batch mode. Acceptable for non-real-time MVP.

## 12. Dual Proof Strategy

### 12.1 Equity Track: $5K → $1M

**The Math:**
Kelly Criterion: f* = (1.6 × 0.65 - 0.35) / 1.6 = **43.12%**

| Strategy | Risk/Trade | Trades to $1M | Time (3 trades/wk) | 10-Loss Streak Impact |
|---|---|---|---|---|
| Full Kelly (43.1%) | 43.1% | ~367 | ~2.4 years | -19.6% |
| **Half Kelly (21.6%)** | **21.6%** | **~724** | **~4.6 years** | **-10.3%** |
| Quarter Kelly (10.8%) | 10.8% | ~1,436 | ~9.2 years | -5.3% |

**Recommendation: Half Kelly.** Full Kelly is mathematically optimal but psychologically devastating.

**PDT Rule Eliminated (April 2026):** FINRA eliminated the $25,000 Pattern Day Trader minimum. The $5K account can now day-trade unlimited.

**Instruments by Phase:**
| Phase | Account Size | Instruments | Position Sizing |
|---|---|---|---|
| 1 | $5K-$25K | Stock swings + long options (14-30 DTE, 30-45 delta) | Quarter to Half Kelly |
| 2 | $25K-$100K | Add intraday scalps, debit spreads | Half Kelly |
| 3 | $100K-$1M | Add futures, institutional-grade sizing | Half Kelly, 2% max loss/trade |

### 12.2 Prediction Market Track: $1K → $50K

**Why run this in parallel:**
- Faster validation cycle (binary outcomes resolve in days/weeks)
- Lower capital at risk during signal validation
- Cleaner win-rate math (no Greeks, no path dependency)
- Separate case study for SaaS marketing
- Different risk profile tests engine robustness

**Phased deployment:**
| Phase | Bankroll | Venue | Position Sizing | Goal |
|---|---|---|---|---|
| 1 (Paper) | N/A | Kalshi paper trading | $10-50 theoretical | Validate signals |
| 2 (Live small) | $500 | Kalshi | $10-30 per bet | 2x bankroll |
| 3 (Scale) | $1,000-5,000 | Kalshi + Polymarket | 2-5% Kelly | 5x bankroll |
| 4 (Production) | $5,000-50,000 | Kalshi + Polymarket | Half Kelly | Full validation |

**Market types by priority:**
1. Fed decisions (Kalshi) — clear sentiment-to-outcome mapping
2. Economic data releases — CPI, NFP, GDP (Kalshi)
3. Earnings beats/misses (Kalshi)
4. Geopolitical events (Polymarket)
5. Elections (Polymarket)
6. Crypto regulation (Polymarket)

### 12.3 Tax Optimization (Both Tracks)
File for Professional Trader Status + Section 475 Mark-to-Market election. This exempts from wash-sale rule and allows unlimited loss deductions. Prediction market winnings taxed as ordinary income (currently — CFTC-regulated events may get capital gains treatment; consult CPA).

### 12.4 The Honest Assessment
$5K → $1M in 12-24 months requires extraordinary luck or Full Kelly (which risks ruin). At Half Kelly with 3-5 trades/week, the realistic timeline is **3-5 years**.

The PURPOSE of BOTH proof accounts is not to get rich quickly — it's to generate **signal-attributed track records that become the sales evidence for AlphaHound SaaS**. Two track records across two asset classes is dramatically more credible than one.

## 13. Legal Framework

### The Publisher's Exemption
Under *Lowe v. SEC* (1985 Supreme Court) and the 2024 federal court ruling protecting Seeking Alpha, publishers of "bona fide" financial analysis of "general and regular circulation" do not need to register as investment advisers.

**Low risk:** Selling sentiment scores, confidence indices, historical pattern matches, narrative summaries, prediction market probabilities
**Moderate risk:** Sending personalized alerts ("Based on YOUR portfolio..."), displaying aggregated short seller positions
**High risk:** Operating a managed portfolio, copy-trading service, or automated Polymarket execution for customers

### Required Disclaimers
"AlphaHound provides data, scores, and analytical tools for informational purposes only. This is not investment advice, does not constitute a recommendation to buy or sell any security or place any bet, and is not tailored to any individual's financial situation. Prediction market participation may be restricted in your jurisdiction."

### Proof Account Safety (Both Tracks)
- Publish trade logs AFTER positions are closed (not before/during)
- Disclose: "The operator may hold positions in securities or prediction market contracts mentioned"
- Never output imperative statements ("Buy STNG", "Bet YES on Polymarket") — always probabilistic ("STNG signal score 8/10, confidence 7/10")

### Prediction Market Specific Legal
- **Kalshi** — fully CFTC-regulated, legal for US users, $25K/market position limits typically
- **Polymarket** — US legal status grey (2022 CFTC settlement), monitor 2026 enforcement landscape
- **Marketing language** — "signal informs prediction market bets" is fine; "we predict event outcomes" starts sounding like gambling advice

### SEC 2026 AI Scrutiny
SEC explicitly targets "AI washing" — claiming AI does more than it actually does. Our verifiable trade logs (equity + prediction market) are BOTH the commercial proof AND the legal compliance mechanism.

### Alt Analyst Content Legal
- **Substack scraping** — public RSS is fair game; paid content is not
- **YouTube/podcast transcripts** — transcribing for internal analysis is fair use; republishing full transcripts is not
- **Short seller reports** — publicly published reports are citable; summarize and link, don't copy
- **Never claim endorsement** from Doomberg, Hindenburg, etc.

## 14. Business Model

### Pricing
| Tier | Price | Features |
|---|---|---|
| Free | $0 | 5 tickers, 15-min delayed signals, no Rhyme Engine, no prediction markets |
| Starter | $49/mo | 50 tickers, real-time signals, basic Rhyme Engine, Kalshi data |
| Pro | $149/mo | Unlimited tickers, full Rhyme Engine, API access, backtesting, Polymarket data, alt analyst feeds |
| Trader | $299/mo | Everything in Pro + real-time WebSocket + prediction market arb alerts + priority API |
| Enterprise | Custom | White-label, custom modules, historical data export, managed deployment |

### TAM
AI in Trading market: $24.5B in 2025, projected $68B by 2033. Retail trading intelligence specifically is a multi-billion dollar segment with 15M+ active retail traders in the US alone. Prediction markets growing fast — Kalshi and Polymarket combined handle $10B+ annual volume.

### Revenue Path
1. **Month 1-3:** Build MVP, begin equity proof account, no revenue
2. **Month 3-6:** Add Phase 1.5 sources, begin prediction market proof account, launch free tier
3. **Month 6-12:** Launch paid tiers, target 500 paying users at $49-299/mo = $25K-150K MRR
4. **Month 12-18:** Phase 2 sources live, API customers onboarded
5. **Year 2+:** Enterprise tier, multi-industry modules, alternative data tier

### Competitive Positioning
- **vs LunarCrush** ($99-499/mo): They have social aggregation, we have Rhyme Engine + divergence + prediction markets
- **vs Unusual Whales** ($65-150/mo): They have options flow, we have full-stack sentiment + options + historical
- **vs RavenPack** ($50K/yr): They serve institutions, we serve retail at 1/300th the price
- **vs Quiver Quantitative** ($10/mo): They have Congressional trading, we integrate it plus 10 other sources

## 15. Development Timeline

| Phase | Duration | Deliverable |
|---|---|---|
| Research | Week 1 | ✅ COMPLETE — PRD v1.0 + v1.1 |
| Architecture & DB Schema | Week 2 | System design, PostgreSQL schema, API spec |
| Data Pipeline — MVP sources (ingestion) | Week 2-3 | Workers for ApeWisdom, StockTwits, EDGAR, Unusual Whales, FMP |
| FinBERT Scoring Engine | Week 3-4 | Tier 1 inference on Azure T4 |
| Claude Integration (Tier 2) | Week 4 | Escalation routing + narrative extraction |
| Rhyme Engine v1 | Week 4-5 | 20-event seed DB + DTW matching |
| REST API | Week 5 | FastAPI endpoints for signals, narratives, rhymes |
| **Equity Proof Account Live** | **Week 5-6** | **First AlphaHound-attributed trade on personal Schwab/Merrill** |
| Backtesting | Week 5-6 | Walk-forward validation on FNSPID data |
| Phase 1.5 Ingestion | Week 6-8 | Substack, Congressional, short sellers, Kalshi data, 13D filings |
| **Kalshi Proof Account Live** | **Week 8** | **First AlphaHound-attributed Kalshi bet** |
| Dashboard (React) | Week 8-10 | Web UI for non-API users |
| Phase 2 Ingestion | Week 10-14 | YouTube/podcast transcripts, Polymarket, enhanced analysts |
| **Public Free Tier Launch** | **Month 3** | **First external users** |
| Paid Tiers Launch | Month 4-6 | Starter/Pro/Trader live |
| **Kalshi Trading Module** | **Month 6** | **Automated bet execution from signals** |
| Enterprise Conversations | Month 9+ | White-label/API enterprise deals |
| Multi-Industry Module 1 | Year 2 | Real estate sentiment module |

## 16. Success Metrics

| Metric | Target | Timeframe |
|---|---|---|
| Signal accuracy (equity, directional) | >60% | 3-month rolling |
| Signal accuracy (prediction market) | >62% | 3-month rolling |
| Equity proof account P&L | Positive | After 100 trades |
| Prediction market proof P&L | Positive | After 50 bets |
| Backtested win rate (OOS) | >58% | 3-year backtest |
| Rhyme Engine match accuracy | >65% directional | After 20 events |
| Alt analyst signal lift | +3-5% accuracy improvement | vs baseline |
| Prediction market arb opportunities caught | 10+ per month | Month 6+ |
| Free tier users | 1,000 | Month 3 |
| Paid subscribers | 500 | Month 6 |
| MRR | $50K | Month 12 |
| MRR (with new tiers) | $150K | Month 18 |

## 17. Phase 0: Personal Validation (User Zero)

Before any external launch, Kamil runs AlphaHound exclusively on himself for ~90 days.

### Goals
1. Dog-food the full signal pipeline daily
2. Log all equity trades with signal attribution
3. Log all Kalshi/Polymarket bets with signal attribution
4. Identify false positives, missed signals, UX gaps
5. Tune scoring weights based on actual win rates
6. Build confidence before opening to external users
7. Generate initial track record for marketing

### Phase 0 Deliverables
- Daily AlphaHound report (automated, portfolio-aware)
- Signal log with attribution (CSV/DB)
- Weekly retrospective (what worked, what didn't)
- Monthly scoring weight tuning based on realized accuracy
- Quarterly public blog post on lessons learned (builds audience pre-launch)

### Phase 0 Exit Criteria
- Signal accuracy ≥58% over 90 days (equity)
- Signal accuracy ≥60% over 90 days (prediction markets)
- Positive P&L on both accounts
- At least 100 signal-attributed trades
- No major pipeline failures in final 30 days

---

## Appendix A: Key Differences v1.0 → v1.1

| Area | v1.0 | v1.1 |
|---|---|---|
| Data sources | 6 primary + 4 secondary | 6 MVP + 8 Phase 1.5 + 7 Phase 2 |
| Prediction markets | Not included | Dual role (data + trading venue) |
| Proof accounts | Single ($5K → $1M equity) | Dual ($5K → $1M equity + $1K → $50K prediction) |
| Alt analyst sources | Reddit only | + Substack, YouTube, podcasts, short sellers, Congressional, activists |
| Scoring weights | 7 components | 9 components (added prediction market alignment, alt analyst signal) |
| Pricing tiers | 3 tiers ($0/$49/$149) | 5 tiers ($0/$49/$149/$299/Enterprise) |
| Phase 0 | Implicit | Explicit 90-day personal validation |
| Budget | $978-1,128/mo | $1,100-1,500/mo at full coverage |

---

*This PRD is based on synthesized research from Perplexity Deep Research, Claude Sonnet 4.6, Gemini Deep Research, and ChatGPT Deep Research. Every claim is cross-referenced across at least 2 of 4 sources. The Rhyme Engine blue ocean was confirmed by all 4 independently. Prediction market integration and alt analyst expansion added in v1.1 based on direct user feedback and ICE's February 2026 Polymarket distribution validating institutional demand.*

*Next step: Architecture document + database schema + begin Phase 0 build.*
