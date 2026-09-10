# AlphaHound — Deep Research Plan

## Objective
Before writing a single line of code, we need to understand the full landscape of AI-powered sentiment analysis platforms, their strengths, gaps, and what "alpha" we can actually capture. This research feeds directly into the PRD.

## Research Areas

### 1. Competitive Landscape — What Exists Today
Research these platforms deeply. For each, document: pricing, data sources, accuracy claims, API availability, and gaps.

**Commercial Platforms:**
- LunarCrush — Social intelligence for stocks & crypto (available as MCP connector)
- Sentifi — AI financial sentiment from news + social
- StockTwits — Community-driven sentiment with bull/bear ratios
- MarketPsych (Refinitiv) — NLP-driven sentiment from news & social media
- Accern — Real-time NLP for financial news
- S&P Global Market Intelligence — Institutional-grade sentiment
- ICE (Intercontinental Exchange) — Reddit Signals & Sentiment product
- Quiver Quantitative — Alternative data (Reddit, lobbying, insider trading)
- Unusual Whales — Options flow + social sentiment
- SwaggyStocks — Reddit-specific sentiment tracking
- ApeWisdom — WSB ticker mention tracking
- Stockgeist — Real-time social sentiment for stocks

**Academic / Open Source:**
- FinBERT — Pre-trained NLP model for financial sentiment
- VADER — Rule-based sentiment (baseline comparison)
- FinGPT — Open-source financial LLM
- BloombergGPT — Bloomberg's proprietary financial LLM (study architecture)

**Questions to Answer:**
- What data sources do they use?
- What's their latency (real-time vs delayed)?
- How do they handle sarcasm/irony in social posts?
- What's their reported accuracy?
- Do they offer historical data for backtesting?
- What do they charge?
- Where are the GAPS that AlphaHound can fill?

### 2. Data Sources — What Can We Actually Ingest
For each source, research: API availability, rate limits, cost, data format, and legal restrictions.

**Social Media:**
- Reddit API (free tier vs paid, rate limits, pushshift alternatives)
- X/Twitter API (pricing tiers since 2023 changes, firehose access)
- StockTwits API (bull/bear ratios, free vs premium)
- Discord (finance servers — how to tap into)
- TikTok/YouTube (emerging source — #FinTok sentiment)

**News & Professional:**
- Bloomberg Terminal API
- Reuters/Refinitiv
- MT Newswires (we already have this)
- Benzinga Pro API
- Seeking Alpha API
- CNBC / MarketWatch (scraping legality)

**Financial Data:**
- SEC EDGAR (13F filings, insider transactions, 8-K events)
- Options flow data (CBOE, unusual activity detection)
- Dark pool data (FINRA ADF prints)
- Short interest data (FINRA, S3 Partners)
- Futures COT data (CFTC Commitments of Traders)

**Alternative Data:**
- Google Trends (search volume as leading indicator)
- App download data (Apptopia — consumer behavior proxy)
- Satellite data (oil storage, shipping, parking lots)
- Job posting data (we already get this from RavenPack)
- Patent filings
- Government contract awards (USAspending.gov)

### 3. AI/ML Models — How to Score Sentiment
Research different approaches, accuracy benchmarks, and implementation complexity.

**Approaches to Evaluate:**
- FinBERT (fine-tuned BERT for financial text) — industry standard
- LLM-based reasoning (Claude/GPT for narrative detection vs pure sentiment)
- Ensemble models (combine FinBERT score + LLM reasoning + volume metrics)
- Custom fine-tuning on our own labeled financial data
- Zero-shot classification with modern LLMs

**Key Questions:**
- FinBERT accuracy on Reddit-style text (short, sarcastic) vs news articles?
- Can we use Claude API for the reasoning layer while FinBERT handles volume scoring?
- What's the compute cost per 1,000 posts analyzed?
- How to handle multi-language content?

### 4. Historical Patterns — "Things That Rhyme"
This is the alpha layer. Research historical market events that share structural similarities with current setups.

**Pattern Categories:**
- Supply chain disruptions (2021-2022 COVID supply chains, 2011 Japan earthquake, 1973 oil embargo)
- War premiums (Gulf War 1990, Iraq War 2003, Russia-Ukraine 2022, current Iran 2026)
- Ceasefire trades (historical pattern of "buy the rumor, sell the news" on peace deals)
- Sentiment extremes (what happened historically when Fear & Greed hit single digits?)
- Institutional vs retail divergence (when smart money exits while retail piles in — historical win rate)
- Sector rotation patterns (how long after a crisis does money rotate from defense/energy → tech/growth?)

**Data Needed:**
- Historical Fear & Greed index data
- Historical put/call ratios at extremes
- Historical sector rotation timing after crises
- Historical commodity price recovery timelines after supply disruptions

### 5. Legal & Compliance
Before we build and sell this, understand the legal landscape.

- SEC regulations on social media-derived trading signals
- FINRA guidance on alternative data usage
- Reddit/X Terms of Service for commercial data usage
- GDPR implications if serving European users
- Disclaimer requirements for financial signal products

## Research Output Format
For each area, create a markdown file in the `research/` folder with:
1. Executive summary (3-5 bullet points)
2. Detailed findings
3. Implications for AlphaHound (what we should build, what we should skip)
4. Sources with URLs

## Timeline
- Research phase: 3-5 days
- Synthesis + PRD: 2-3 days
- Architecture design: 2-3 days
- MVP build: 2-4 weeks

## How to Research
Kamil will do deep dives using multiple AI tools (Claude, Gemini, ChatGPT, Perplexity) and financial platforms. Each research session should produce a file in the `research/` folder. Once all areas are covered, we synthesize everything into the PRD.
