# Research Brief 02: Data Sources & APIs
## Paste this entire brief into Perplexity / Gemini Deep Research / Claude

---

## CONTEXT
I'm building "AlphaHound" — a real-time stock sentiment platform on Azure (Python/FastAPI, PostgreSQL/TimescaleDB, Claude API). The platform ingests multi-source sentiment data, scores it, detects hidden narratives, and matches current events to historical patterns.

I need to understand every data source I can plug into this engine — what's available, what it costs, what the rate limits are, and what legal restrictions apply. I'm a developer building this for real, so I need API documentation links, not just descriptions.

## WHAT I NEED
For every data source below, provide:

1. **API availability** (official API, unofficial, scraping required)
2. **Authentication** (API key, OAuth, enterprise-only)
3. **Rate limits** (requests/min, posts/day, etc.)
4. **Pricing** (free tier limits, paid tier costs)
5. **Data format** (JSON, CSV, streaming, etc.)
6. **Latency** (real-time, delayed, daily batch)
7. **Historical data availability** (how far back, bulk download?)
8. **Legal status for commercial use** (ToS restrictions, redistribution rights)
9. **Python library** (if one exists, name it)
10. **Documentation URL**

## DATA SOURCES TO RESEARCH

### Social Media Sentiment
- **Reddit API** (official — what changed after 2023 pricing update? current cost for 100K posts/day?)
- **Reddit via Pushshift** (still available? alternatives?)
- **Reddit via Apify** (Reddit Intelligence AI scraper — cost, reliability)
- **ApeWisdom API** (WSB ticker mentions — still active?)
- **X/Twitter API** (current tiers — Basic $100/mo, Pro $5K/mo, Enterprise? What do you get at each tier?)
- **X/Twitter via Bright Data** (proxy-based scraping — legality, cost, reliability)
- **StockTwits API** (bull/bear ratios, message stream — free vs premium)
- **Discord** (finance server scraping — any APIs or tools?)
- **TikTok** (FinTok sentiment — any data access method?)
- **YouTube** (financial video sentiment — YouTube Data API v3 capabilities)

### News & Professional Content
- **MT Newswires** (we already have this via IEX — document the API)
- **Benzinga Pro API** (news, ratings, signals — pricing and endpoints)
- **Seeking Alpha API** (article sentiment, ratings — is there a public API?)
- **Bloomberg API** (BLPAPI — cost, access requirements)
- **Reuters/Refinitiv Eikon** (pricing, API access)
- **Substack** (unofficial scraping — substack-api Python library, legality)
- **Google News** (scraping via googlenews-python or SerpAPI)
- **NewsAPI.org** (pricing, coverage, delay)

### Financial & Institutional Data
- **SEC EDGAR** (13F filings, insider transactions, 8-K events — EDGAR full-text search API)
- **FINRA** (short interest data — access method, frequency)
- **CFTC COT data** (Commitments of Traders — API or download?)
- **Options flow** (CBOE, unusual activity — Unusual Whales API, Tradier, ORATS)
- **Dark pool data** (FINRA ADF — access method)
- **Insider trading** (OpenInsider, SEC Form 4 — scraping vs API)

### Alternative Data
- **Google Trends API** (pytrends library — rate limits, reliability)
- **Satellite data** (oil storage, shipping — providers and cost)
- **Job posting data** (Indeed, LinkedIn — APIs or scrapers)
- **Patent filings** (USPTO API)
- **Government contracts** (USAspending.gov API)
- **Web traffic** (SimilarWeb API — pricing)
- **App downloads** (Apptopia, Sensor Tower — pricing)

### Market Data
- **Bigdata.com** (we already have this — document what we get)
- **IEX Cloud** (we already have this via MT Newswires connector)
- **Alpha Vantage** (free tier limits, premium pricing)
- **Polygon.io** (real-time, pricing, websocket)
- **Yahoo Finance** (yfinance library — reliability, legal status)
- **FRED** (Federal Reserve economic data — free API)

## WHAT I SPECIFICALLY WANT TO KNOW
1. **What's the cheapest way to get real-time Reddit + X sentiment for 500+ tickers?** Model the monthly cost.
2. **Which data sources have the highest signal-to-noise ratio for stock prediction?** Rank them.
3. **What's the legal risk of scraping vs using official APIs?** Specifically for Reddit and X after their 2023-2024 ToS changes.
4. **Can I build a sentiment pipeline processing 100K posts/day for under $500/month in API costs?**
5. **What Python libraries exist for each source?** I want pip install, not build-from-scratch.

## OUTPUT FORMAT
Structured table for each category, then a recommended "starter stack" (the minimum sources I need for MVP) with total monthly cost estimate.

---
*Save the response as: `data_sources_results.md` in this folder*
