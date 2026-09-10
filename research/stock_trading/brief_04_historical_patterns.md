# Research Brief 04: Historical Pattern Matching ("Things That Rhyme")
## Paste this entire brief into Perplexity / Gemini Deep Research / Claude

---

## CONTEXT
I'm building "AlphaHound" — a stock sentiment platform with a unique feature called the "Rhyme Engine." The idea: history doesn't repeat but it rhymes. When we see a current market event (e.g., 2026 Strait of Hormuz blockade), we want the system to automatically find structurally similar historical events (1973 oil embargo, 1990 Gulf War, 2022 Russia-Ukraine) and use their outcomes to predict what happens next.

This is the alpha layer — no one else does this well. Most sentiment platforms just tell you "Reddit is bullish on STNG." We want to say "Reddit is bullish on STNG, institutions are selling, AND the last 4 times a major shipping chokepoint was blocked, tanker stocks peaked 6-8 weeks after the initial spike and gave back 30% before stabilizing. You are currently in week 7."

I'm a developer building this on Azure (PostgreSQL/TimescaleDB, Python). I need to understand both the DATA and the ALGORITHMS for building this engine.

## WHAT I NEED

### Part 1: Historical Crisis Database
I need a comprehensive database of market-moving crises. For each event, document:

1. **Event name and date range**
2. **Crisis type** (supply chain, military, financial panic, pandemic, regulatory, natural disaster)
3. **Affected assets** (which sectors, commodities, currencies moved)
4. **Phase timeline** (shock phase → adaptation → normalization → new equilibrium)
5. **Peak-to-trough and recovery metrics** (how much did affected assets move? how long to recover?)

**Events to cover (at minimum):**

*Oil/Energy Crises:*
- 1973 Arab oil embargo
- 1979 Iranian Revolution oil shock
- 1990 Gulf War oil spike
- 2008 oil price spike to $147
- 2014-2016 oil price collapse
- 2020 COVID oil crash (negative prices)
- 2022 Russia-Ukraine energy crisis
- 2026 Strait of Hormuz blockade (current)

*Military/Geopolitical:*
- 1990 Gulf War (effect on defense stocks)
- 2001 Post-9/11 (defense spending surge)
- 2003 Iraq War
- 2014 Russia-Crimea annexation
- 2022 Russia-Ukraine invasion
- 2026 Iran-US war (current)

*Supply Chain Disruptions:*
- 2011 Japan earthquake/tsunami (semiconductor, auto supply chains)
- 2020-2022 COVID supply chain crisis
- 2021 Suez Canal blockage (Ever Given)
- 2021-2022 semiconductor shortage
- 2026 Hormuz blockade (helium, fertilizer, petrochemicals, LNG)

*Financial Panics:*
- 1987 Black Monday
- 1997 Asian Financial Crisis
- 2000 Dot-com bust
- 2008 Global Financial Crisis
- 2020 COVID crash
- 2022 crypto/SVB crisis

*Sentiment Extremes:*
- 2021 GameStop/AMC retail trading mania
- 2021 SPAC bubble peak
- 2022 crypto winter
- Every time Fear & Greed index hit single digits — what happened next?

### Part 2: Pattern Similarity Algorithms
How do you programmatically find "things that rhyme"?

1. **Event embedding approach:** Convert event descriptions to vector embeddings (using FinBERT or sentence transformers), then use cosine similarity to find matches. How well does this work?
2. **Price path correlation:** Given the price path of Oil during the first 30 days of Crisis A, find historical crises where Oil followed a similar 30-day path. Then look at what happened in days 31-90. What correlation methods work? (DTW — Dynamic Time Warping?)
3. **Feature-based matching:** Define crisis features (chokepoint involved? military action? supply disruption? demand destruction?) and match on feature vectors. What features matter most?
4. **Hybrid approach:** Combine text similarity + price path correlation + feature matching. How do you weight each component?

### Part 3: Datasets
Where can I get historical data to populate the Rhyme Engine?

1. **Historical price data** (daily OHLCV for stocks, commodities, currencies going back to 1970s — source and format)
2. **Historical events database** (structured data on crises, wars, policy changes — does this exist anywhere?)
3. **Historical Fear & Greed index** (CNN — how far back? downloadable?)
4. **Historical put/call ratios** (CBOE — how far back? API?)
5. **Historical 13F filings** (SEC EDGAR — bulk download method)
6. **Historical sector performance during crises** (any pre-built dataset?)
7. **Historical VIX term structure** (contango/backwardation history)

### Part 4: The "Rhyme Score"
How do I quantify "how much does the current situation rhyme with a historical event?"

1. What metrics should feed the rhyme score?
2. How do I normalize across different eras (1973 vs 2026 — different market structure, technology, scale)?
3. How many historical matches are needed for statistical significance?
4. How do I present this to a trader? (e.g., "This situation is 78% similar to the 1990 Gulf War. In that case, defense stocks gained another 12% over 3 months before plateauing.")

## WHAT I SPECIFICALLY WANT TO KNOW
1. **Has anyone built a "historical rhyming" system for financial markets before?** Any academic papers or commercial products?
2. **What's the most practical similarity algorithm for matching market events?** (Something I can implement in Python in a week, not a PhD thesis)
3. **Where do I get the historical data to seed this engine?** Specific URLs, APIs, or databases.
4. **How far back does the data need to go for this to be useful?** 10 years? 30 years? 50 years?
5. **What's the expected accuracy improvement from adding historical pattern matching to a sentiment-only model?**

## OUTPUT FORMAT
Start with the event database (table format), then the algorithm recommendations (ranked by practicality), then the data source list (with URLs), then the rhyme score design.

---
*Save the response as: `historical_patterns_results.md` in this folder*
