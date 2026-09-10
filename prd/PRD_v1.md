# AlphaHound — Product Requirements Document (v1.0)
## Multi-Industry Sentiment Intelligence Platform — Stock Trading Module

**Author:** Kamil Asfour | **Date:** April 15, 2026
**Status:** FINAL DRAFT — Ready for architecture and build
**Research Sources:** Perplexity Deep Research, Claude Sonnet 4.6, Gemini Deep Research, ChatGPT Deep Research (4 AI synthesis)

---

## 1. Executive Summary

AlphaHound is a real-time multi-industry sentiment intelligence platform. The stock trading module (MVP) ingests social media, news, institutional filings, and options flow data to produce scored trading signals with a unique differentiator: a "Rhyme Engine" that matches current market events to structurally similar historical crises and predicts outcomes based on how those crises resolved.

**The proof:** Turn $5,000 into $1,000,000 using AlphaHound signals as the primary decision engine, with every trade logged and attributable to a specific signal.

**The business:** SaaS platform selling sentiment data, signal scores, and historical pattern intelligence to retail traders, quantitative analysts, and eventually institutional clients. Later modules extend the same engine to real estate, automotive, F&B, and any industry where sentiment drives outcomes.

## 2. Problem Statement

### 2.1 The Problem
Current retail sentiment tools fall into two categories: cheap-but-shallow (StockTwits bull/bear ratios, ApeWisdom mention counts) or expensive-but-institutional (RavenPack at $50K+/yr, ICE Reddit Signals on the Consolidated Feed). No tool combines social sentiment, institutional flow, options activity, AND historical pattern matching in one platform at a price retail traders can afford.

### 2.2 The Gap (Confirmed by Research)
All four AI research sources independently confirmed: **no commercial platform has productized historical event-to-event pattern matching.** The closest implementations are a student CS50P project and a free TradingView indicator. This is a genuine blue ocean.

Additionally, no retail tool effectively detects **cross-source divergence** — when Reddit is bullish but institutional 13F filings show net selling and options flow shows heavy put buying. This divergence signal is where the real alpha lives, because raw Reddit sentiment is now commoditized (ICE launched Reddit Signals & Sentiment on January 28, 2026, processing 16B+ posts for institutional clients).

### 2.3 AlphaHound's Edge
1. **Rhyme Engine** — Historical pattern matching (blue ocean, zero competition)
2. **Cross-Source Divergence** — Social vs. institutional vs. options flow conflict detection
3. **Two-Tier AI** — FinBERT speed + LLM reasoning depth (industry best practice, not implemented by any retail tool)
4. **Global Cascade Scoring** — Asian → European → US market flow prediction (unique feature)
5. **Affordability** — $49-149/month vs. $50K+/year for institutional alternatives

## 3. User Personas

### 3.1 Primary: Active Retail Swing Trader (Us)
- Trades 3-10 times per week, holds 1-5 days
- Uses thinkorswim/Merrill, $5K-$100K accounts
- Wants: actionable signals with entry/exit/stop, confidence scores, "what's brewing that I don't know yet"
- Pain: drowning in noise, can't tell if Reddit hype is organic or manipulation, no historical context

### 3.2 Secondary: Quantitative Developer
- Builds algorithmic strategies, needs API access
- Wants: JSON sentiment scores per ticker, historical data for backtesting, real-time WebSocket feed
- Pain: existing APIs either too expensive (RavenPack) or too shallow (StockTwits)

### 3.3 Tertiary: Financial Content Creator
- Makes YouTube/Substack content about markets
- Wants: unique data points, historical comparisons, visual dashboards
- Pain: everyone uses the same charts and data

## 4. Core Features (Prioritized)

### P0 — Must Ship for MVP
1. **Multi-Source Sentiment Scoring** — Signal score (1-10) + confidence score (1-10) per ticker from Reddit, StockTwits, news, options flow, SEC filings
2. **Cross-Source Divergence Detection** — Alert when retail sentiment contradicts institutional positioning
3. **Two-Tier AI Scoring** — FinBERT bulk + Claude narrative reasoning
4. **REST API** — `GET /signals/{ticker}` returning JSON with score, confidence, components, narrative
5. **Historical Pattern Matching (Rhyme Engine)** — DTW-based event matching against 20+ curated historical crises
6. **Proof Account Dashboard** — Live $5K → $1M trade log with signal attribution

### P1 — Should Ship for v1.1
7. **Global Cascade Scoring** — Overnight Asian/European session analysis predicting US open
8. **Real-Time WebSocket Feed** — Streaming signal updates for algo traders
9. **Backtesting Module** — Walk-forward analysis of signals against 3-5 years of history
10. **Bot/Manipulation Detection** — Social volume spike + zero institutional confirmation = pump-and-dump flag

### P2 — Future Roadmap
11. **Web Dashboard** (React) with interactive charts
12. **Options Strategy Recommender** based on signal confidence
13. **Multi-Industry Modules** (Real Estate, Auto, F&B)
14. **Mobile Alerts** (push notifications on divergence/extreme signals)

## 5. Data Sources

### MVP Stack (~$500/month total API cost)

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

### Production Additions (~$1,000-1,500/month)
| Source | Cost | When to Add |
|---|---|---|
| Reddit API (commercial license) | $1,000+/mo | When revenue covers it |
| X/Twitter (third-party aggregator) | ~$200/mo | When revenue covers it |
| LunarCrush (X+Reddit+TikTok aggregated) | $99-499/mo | Alternative to direct X API |
| Benzinga Pro (real-time news) | $99/mo | Production quality news |
| SentimenTrader (20K+ indicators) | $149/mo | Historical sentiment backtesting |

### Skip for MVP
- Bloomberg/Reuters (enterprise pricing, overkill)
- Satellite data (high cost, low ROI for stocks)
- Direct X API ($7,500/mo at full coverage — use aggregator instead)
- RavenPack ($50K+/yr — we're competing with them, not buying from them)

## 6. AI/ML Architecture

### Two-Tier System (Validated by All Research Sources)

**Tier 1 — FinBERT Fast Scoring (all posts, 100K/day)**
- Model: ProsusAI/finbert (self-hosted on Azure T4 GPU)
- Accuracy: ~87% F1 on financial news, ~65-70% on Reddit (untuned), ~80-85% (fine-tuned on WSB data)
- Speed: ~500 posts/sec on T4 GPU = 100K posts in ~200 seconds
- Cost: ~$13/day (Azure NC4as_T4_v3 VM)
- Output: (ticker, sentiment polarity -1 to +1, confidence 0-1)

**Tier 2 — Claude API Deep Reasoning (500-3,000 calls/day)**
- Triggered by: velocity spikes >2σ, source divergence, low FinBERT confidence (<0.60), novel entities, multi-entity posts
- Input: post text + 5-post context window + recent price + 7-day sentiment baseline
- Output: narrative summary, emerging theme, confidence adjustment, divergence warning, rhyme trigger
- Cost: ~$5-10/day at 500-3,000 calls
- Critical: Use System 1 prompting (fast, intuitive classification) NOT Chain-of-Thought — research shows CoT degrades financial sentiment accuracy

**Escalation rate:** 3-8% of posts escalate to Tier 2

### Scoring Engine

**Signal Score (1-10):**
| Component | Weight | Source |
|---|---|---|
| Mention volume & velocity | 25% | ApeWisdom, StockTwits, Reddit |
| Options flow alignment | 20% | Unusual Whales |
| Sentiment polarity (FinBERT) | 15% | All social posts |
| Source consensus | 15% | Cross-source agreement |
| Institutional alignment (13F) | 10% | SEC EDGAR |
| LLM narrative quality | 10% | Claude Tier 2 |
| Historical pattern match | 5% | Rhyme Engine |

**Dynamic adjustment:** During high-volatility events (earnings, Fed, geopolitical), increase volume/velocity weight to 40% and decrease polarity weight to 10%. Sentiment becomes "reactive" during stress — volume is more predictive.

**Confidence Score (1-10):**
| Component | Weight |
|---|---|
| Post volume (50+ = conf 5, 200+ = conf 8) | 40% |
| Source diversity (3+ platforms = higher) | 30% |
| Time recency (decays after 48h) | 20% |
| Bot filter pass rate | 10% |

**Minimum thresholds:**
- <10 posts: confidence 1-2 (alerting only, no trade signal)
- 10-50 posts: confidence 3-5 (directional signal)
- 50-200 posts: confidence 5-7 (actionable)
- 200+ posts: confidence 7-10 (high conviction)

### Sarcasm Handling
Research confirms sarcasm detection on Reddit achieves ~72-76% F1 at best. Practical mitigation:
1. **Volume > Polarity** for meme stocks (volume is harder to fake with sarcasm)
2. **Custom slang dictionary** maintained for WSB jargon
3. **Subreddit weighting** (WSB = higher sarcasm density, lower polarity weight)
4. **LLM escalation** for ambiguous cases
5. **Market cap filter** (exclude <$100M to avoid pump-and-dump targets)

## 7. Rhyme Engine (Historical Pattern Matching)

### Algorithm: Dynamic Time Warping (DTW)
- Library: `dtaidistance` (fastest: 0.000110 sec/comparison)
- Approach: Normalize price paths as % change from event day 0, use Sakoe-Chiba window (±15-20% of series length)
- Matching: Current 14-30 day price vector vs. historical database

### Three-Layer Matching
1. **Event Type Classification** (Claude API) — Embed current event description, classify as oil shock / military conflict / supply chain / sentiment extreme / financial panic
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
  ]
}
```

## 8. Global Cascade Scoring

### Sessions Tracked
1. **Asian (7 PM - 3 AM ET):** Nikkei, Hang Seng, Shanghai, KOSPI, ASX + Asian commodities + USD/JPY, AUD/USD
2. **European (3 AM - 9:30 AM ET):** FTSE, DAX, CAC + Brent crude + EUR/USD, GBP/USD
3. **US Pre-Market (4 AM - 9:30 AM ET):** /ES, /NQ, /CL, /GC futures + VIX futures

### Signal
"Asian energy sold off 2.1% overnight on Hormuz escalation → European energy amplified to -3.4% → US futures /CL down 1.8% pre-market → Historical cascade pattern predicts US energy open gap-down 70% probability"

## 9. System Architecture

```
[Data Ingestion — Async Python Workers]
  ApeWisdom (free) ──────────┐
  StockTwits API (free) ─────┤
  Reddit PRAW (free tier) ───┤──→ Redis/Azure Service Bus
  SEC EDGAR (free) ──────────┤      (message queue)
  Unusual Whales ($65/mo) ───┤
  FMP/Polygon ($199/mo) ─────┘

[Processing — FastAPI + Celery on Azure]
  Tier 1: FinBERT on T4 GPU (~500 posts/sec)
    → (ticker, polarity, confidence)
    → Escalation check
  Tier 2: Claude API (500-3K calls/day)
    → (narrative, divergence, rhyme_trigger)
  Rhyme Engine: DTW matching
    → (similarity_score, phase_position, prediction)

[Storage — PostgreSQL + TimescaleDB]
  sentiment_scores (ticker, timestamp, score, confidence, source)
  signal_scores (ticker, timestamp, signal_1to10, confidence_1to10)
  narratives (ticker, timestamp, summary, category)
  historical_events (event_id, type, phases, asset_impacts)
  pattern_matches (current_event, historical_event, similarity)
  trade_log (trade_id, signal_id, entry, exit, pnl)

[API — FastAPI]
  GET  /signals/{ticker}
  GET  /narratives/{ticker}
  GET  /rhyme/{event}
  GET  /cascade/overnight
  GET  /divergence/active
  WS   /stream/{tickers}
```

## 10. Infrastructure & Budget

### Azure VMs
| Component | SKU | Monthly Cost |
|---|---|---|
| FinBERT Inference | Standard_NC4as_T4_v3 (T4 GPU) | ~$384 |
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
| **Total API** | **~$414-564/mo** |

### Total MVP Budget: ~$978-1,128/month

### CPU-Only Alternative: ~$600/month total
Replace T4 GPU with Standard_D8s_v3 (~$400/mo) — FinBERT inference drops to ~20 posts/sec but handles 100K/day in batch mode. Acceptable for non-real-time MVP.

## 11. $5K → $1M Proof Strategy

### The Math
Kelly Criterion: f* = (1.6 × 0.65 - 0.35) / 1.6 = **43.12%**

| Strategy | Risk/Trade | Trades to $1M | Time (3 trades/wk) | 10-Loss Streak Impact |
|---|---|---|---|---|
| Full Kelly (43.1%) | 43.1% | ~367 | ~2.4 years | -19.6% |
| **Half Kelly (21.6%)** | **21.6%** | **~724** | **~4.6 years** | **-10.3%** |
| Quarter Kelly (10.8%) | 10.8% | ~1,436 | ~9.2 years | -5.3% |

**Recommendation: Half Kelly.** Full Kelly is mathematically optimal but psychologically devastating. Loss aversion means a $1,000 loss hurts 2x more than a $1,000 gain feels good.

### PDT Rule Eliminated (April 2026)
FINRA eliminated the $25,000 Pattern Day Trader minimum in April 2026. The $5K account can now day-trade unlimited. This dramatically accelerates compounding.

### Instruments by Phase
| Phase | Account Size | Instruments | Position Sizing |
|---|---|---|---|
| 1 | $5K-$25K | Stock swings + long options (14-30 DTE, 30-45 delta) | Quarter to Half Kelly |
| 2 | $25K-$100K | Add intraday scalps, debit spreads | Half Kelly |
| 3 | $100K-$1M | Add futures, institutional-grade sizing | Half Kelly, 2% max loss/trade |

### Tax Optimization
File for Professional Trader Status + Section 475 Mark-to-Market election. This exempts from wash-sale rule and allows unlimited loss deductions.

### The Honest Assessment
$5K → $1M in 12-24 months requires extraordinary luck or Full Kelly (which risks ruin). At Half Kelly with 3-5 trades/week, the realistic timeline is **3-5 years**. The PURPOSE of the proof account is not to get rich quickly — it's to generate a 500+ trade, signal-attributed track record that becomes the sales evidence for AlphaHound SaaS.

## 12. Legal Framework

### The Publisher's Exemption
Under *Lowe v. SEC* (1985 Supreme Court) and the 2024 federal court ruling protecting Seeking Alpha, publishers of "bona fide" financial analysis of "general and regular circulation" do not need to register as investment advisers.

**Low risk:** Selling sentiment scores, confidence indices, historical pattern matches, narrative summaries
**Moderate risk:** Sending personalized alerts ("Based on YOUR portfolio...")
**High risk:** Operating a managed portfolio or copy-trading service

### Required Disclaimers
"AlphaHound provides data, scores, and analytical tools for informational purposes only. This is not investment advice, does not constitute a recommendation to buy or sell any security, and is not tailored to any individual's financial situation."

### Proof Account Safety
- Publish trade logs AFTER positions are closed (not before/during)
- Disclose: "The operator may hold positions in securities mentioned"
- Never output imperative statements ("Buy STNG") — always probabilistic ("STNG signal score 8/10, confidence 7/10")

### SEC 2026 AI Scrutiny
SEC explicitly targets "AI washing" — claiming AI does more than it actually does. Our verifiable trade log is BOTH the commercial proof AND the legal compliance mechanism.

## 13. Business Model

### Pricing
| Tier | Price | Features |
|---|---|---|
| Free | $0 | 5 tickers, 15-min delayed signals, no Rhyme Engine |
| Starter | $49/mo | 50 tickers, real-time signals, basic Rhyme Engine |
| Pro | $149/mo | Unlimited tickers, full Rhyme Engine, API access, backtesting |
| Enterprise | Custom | White-label, custom modules, historical data export |

### TAM
AI in Trading market: $24.5B in 2025, projected $68B by 2033. Retail trading intelligence specifically is a multi-billion dollar segment with 15M+ active retail traders in the US alone.

### Revenue Path
1. **Month 1-3:** Build MVP, begin proof account, no revenue
2. **Month 3-6:** Launch free tier, build user base, proof account generating track record
3. **Month 6-12:** Launch paid tiers, target 500 paying users at $49-149/mo = $25K-75K MRR
4. **Year 2+:** Enterprise API, multi-industry modules

## 14. Development Timeline

| Phase | Duration | Deliverable |
|---|---|---|
| Research | Week 1 | ✅ COMPLETE — this document |
| Architecture & DB Schema | Week 2 | System design, PostgreSQL schema, API spec |
| Data Pipeline (ingestion) | Week 2-3 | Workers for ApeWisdom, StockTwits, EDGAR, Unusual Whales |
| FinBERT Scoring Engine | Week 3-4 | Tier 1 inference on Azure T4 |
| Claude Integration (Tier 2) | Week 4 | Escalation routing + narrative extraction |
| Rhyme Engine v1 | Week 4-5 | 20-event seed DB + DTW matching |
| REST API | Week 5 | FastAPI endpoints for signals, narratives, rhymes |
| Backtesting | Week 5-6 | Walk-forward validation on FNSPID data |
| Proof Account Live | Week 6+ | First AlphaHound-attributed trade |
| Dashboard (React) | Week 8-10 | Web UI for non-API users |
| Public Launch | Month 3 | Free + paid tiers live |

## 15. Success Metrics

| Metric | Target | Timeframe |
|---|---|---|
| Signal accuracy (directional) | >60% | 3-month rolling |
| Proof account P&L | Positive | After 100 trades |
| Backtested win rate (OOS) | >58% | 3-year backtest |
| Rhyme Engine match accuracy | >65% directional | After 20 events |
| Free tier users | 1,000 | Month 3 |
| Paid subscribers | 500 | Month 6 |
| MRR | $50K | Month 12 |

---

*This PRD is based on synthesized research from Perplexity Deep Research, Claude Sonnet 4.6, Gemini Deep Research, and ChatGPT Deep Research. Every claim is cross-referenced across at least 2 of 4 sources. The Rhyme Engine blue ocean was confirmed by all 4 independently.*

*Next step: Architecture document + database schema + begin build.*
