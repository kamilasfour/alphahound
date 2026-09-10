# Multi-Industry Sentiment Analysis — Research Questions

## Core Question
How does sentiment analysis differ across industries? What's universal (the engine) vs what's industry-specific (the configuration)?

## Universal Components (The Engine)
These should work across ANY industry:
- Text ingestion from social media / news / forums
- Sentiment scoring (positive/negative/neutral + intensity)
- Volume tracking (mention frequency over time)
- Divergence detection (what public says vs what data shows)
- Extreme reversal signals (when sentiment hits 90%+ one direction)
- Historical pattern matching ("things that rhyme")
- Confidence scoring based on source reliability and signal convergence

## Industry-Specific Components (The Configuration)

### For Each Industry Module, Define:
1. **Data Sources** — Where does relevant sentiment live?
2. **Entities** — What are we tracking? (tickers, brands, addresses, products)
3. **Keywords/Taxonomy** — Industry-specific vocabulary
4. **Scoring Weights** — Which sources matter most?
5. **Historical Patterns** — What events rhyme in this industry?
6. **Output Actions** — What decisions does the sentiment drive?

### Stock Trading Module (MVP)
- **Sources:** Reddit (WSB, stocks), X cashtags, StockTwits, news wires, SEC filings, options flow
- **Entities:** Ticker symbols
- **Keywords:** Earnings, guidance, short squeeze, FDA, merger, buyback, etc.
- **Weights:** Institutional flow (30%), news (25%), social volume (20%), technicals (15%), macro (10%)
- **Patterns:** Earnings runs, ceasefire trades, sector rotation, supply chain disruption recovery
- **Actions:** BUY / SELL / HOLD / TRIM / ADD with price targets and stops

### Real Estate Module (Future)
- **Sources:** Reddit (r/realestate, r/REBubble, r/firsttimehomebuyer), Zillow reviews, X, local news, mortgage rate forums
- **Entities:** ZIP codes, MSAs, neighborhoods, REIT tickers
- **Keywords:** Inventory, days on market, price cuts, bidding wars, foreclosure, mortgage rates
- **Weights:** Listing data (35%), social sentiment (25%), economic indicators (20%), news (10%), Google Trends (10%)
- **Patterns:** 2008 housing crash signals, rate hike cycles, migration patterns
- **Actions:** BUY zone / SELL zone / HOLD / market timing signals

### Automotive Module (Future)
- **Sources:** Reddit (r/cars, r/electricvehicles, brand subs), X, YouTube reviews, JD Power, NHTSA complaints
- **Entities:** Brand names, model names, dealership chains, OEM tickers
- **Keywords:** Recall, quality, range anxiety, dealer markup, inventory, incentives
- **Weights:** Consumer sentiment (30%), sales data (25%), social volume (20%), news (15%), supply chain (10%)
- **Patterns:** Brand perception shifts after recalls, EV adoption S-curves, seasonal sales cycles
- **Actions:** Brand health score, sales prediction, stock impact score

### F&B Module (Future)
- **Sources:** Reddit (r/restaurant, brand subs), Yelp/Google reviews, X, TikTok food trends, health trend forums
- **Entities:** Brand names, restaurant chains, food products, CPG tickers
- **Keywords:** Health scare, viral menu item, boycott, price increase, shortage
- **Weights:** Social viral potential (30%), review sentiment (25%), health/safety news (20%), pricing data (15%), supply (10%)
- **Patterns:** Boycott impact curves, viral product sales spikes, health scare recovery timelines
- **Actions:** Brand risk score, trend alert, stock impact score

## Research Questions for Multi-Industry

1. "What sentiment analysis platforms serve industries OUTSIDE of finance? Are there tools for real estate sentiment, automotive brand perception, or restaurant industry intelligence? What do they cost and how good are they?"

2. "How does the reliability of sentiment analysis change across industries? Is Reddit sentiment more predictive for stocks than for real estate? Where does social media sentiment have the HIGHEST signal-to-noise ratio?"

3. "What industries have the LEAST sophisticated sentiment analysis tools today? Where is the biggest gap between available data and actionable intelligence?"

4. "How would you design a configurable sentiment scoring engine where the core NLP/ML pipeline is shared, but the data sources, entity types, keyword dictionaries, and scoring weights are swappable per industry module?"

5. "What's the TAM for sentiment intelligence across all industries combined? Break it down: financial services, real estate tech, automotive OEMs, CPG/F&B, healthcare/pharma, political consulting."

## The Key Insight
The engine that detects "Reddit is suddenly talking about STNG while institutions are selling" is the SAME engine that detects "Reddit is suddenly talking about a specific neighborhood while listing prices are dropping." The pattern is universal. The data sources and vocabulary change.

This is what makes AlphaHound a platform, not just a trading tool.
