# Research Brief 01: Competitive Landscape
## Paste this entire brief into Perplexity / Gemini Deep Research / Claude

---

## CONTEXT
I'm building a real-time stock sentiment intelligence platform called "AlphaHound." It's a multi-industry sentiment engine (starting with stock trading) that ingests data from Reddit, X/Twitter, Substack, news wires, SEC filings, and options flow to detect hidden narratives, divergence signals, and contrarian opportunities BEFORE they hit mainstream awareness.

The core differentiator is a "Rhyme Engine" — historical pattern matching that finds structurally similar past events to predict current outcomes. For example, matching the 2026 Strait of Hormuz blockade to the 1973 Arab oil embargo, 1990 Gulf War, and 2022 Russia-Ukraine crisis to predict how tanker stocks, defense stocks, and gold will behave.

The initial module is stock trading. I need to prove it works by turning $5K into $1M with verifiable, signal-attributed trades. Later, the platform expands to real estate, automotive, F&B, and any industry where sentiment drives outcomes.

I'm a full-stack AI developer building on Azure (PostgreSQL + TimescaleDB, Python/FastAPI backend, Claude API for reasoning). This is a real product I'm building, not a hypothetical.

## WHAT I NEED
A comprehensive competitive analysis of EVERY AI-powered stock sentiment analysis platform that exists today (2026). For each platform:

1. **Product name and URL**
2. **What data sources they ingest** (Reddit, X, news, SEC, options flow, etc.)
3. **Their AI/ML approach** (FinBERT, proprietary NLP, LLM-based, rule-based)
4. **Latency** (real-time, 15-min delay, daily, etc.)
5. **Accuracy claims** (any published win rates, backtested returns, academic validation)
6. **API availability** (REST API, WebSocket, bulk download, etc.)
7. **Pricing** (free tier, pro tier, enterprise)
8. **Historical data** (do they offer backtesting data? how far back?)
9. **Strengths** (what they do well)
10. **Weaknesses / Gaps** (what they miss, what users complain about)

## PLATFORMS TO COVER (at minimum)
**Commercial:**
- LunarCrush
- Sentifi
- StockTwits (bull/bear ratios, social sentiment)
- MarketPsych / Refinitiv
- Accern
- S&P Global Market Intelligence (social sentiment products)
- ICE (Intercontinental Exchange) Reddit Signals & Sentiment
- Quiver Quantitative
- Unusual Whales
- SwaggyStocks
- ApeWisdom
- Stockgeist
- Alphavantage (sentiment add-ons)
- Benzinga Pro (sentiment features)
- TipRanks (smart score, sentiment)
- Koyfin (social sentiment integration)
- TradeFollowers
- Sentimentrader
- VIX Central / CBOE sentiment tools
- FinBrain Technologies

**Open Source / Academic:**
- FinBERT
- FinGPT
- VADER (baseline)
- BloombergGPT (architecture study)

## WHAT I SPECIFICALLY WANT TO KNOW
1. **Where is the GAP?** What does NO ONE do well? Is it the rhyming/historical pattern matching? Is it combining institutional flow with social sentiment? Is it the speed of detection?
2. **Is Reddit alpha decaying?** ICE now sells Reddit sentiment to institutions. If everyone has the same data, where does the edge come from?
3. **What's the best-in-class accuracy?** Has anyone published verifiable win rates from social sentiment signals? What's realistic?
4. **What would make someone switch from StockTwits/LunarCrush to AlphaHound?** What's the killer feature gap?

## OUTPUT FORMAT
Give me a structured comparison table first, then a narrative analysis of gaps and opportunities. Be specific — I need URLs, pricing numbers, and technical details, not vague descriptions.

---
*Save the response as: `competitive_landscape_results.md` in this folder*
