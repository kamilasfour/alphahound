# Stock Trading Research — Deep Research Questions

> Feed these into Perplexity, Gemini Deep Research, Claude, ChatGPT
> Save each answer as a separate .md file in this folder

## Round 1: Competitive Intelligence
1. "What are the top 20 AI-powered stock sentiment analysis platforms in 2026? Compare their data sources, accuracy, pricing, and API availability. Include both commercial and open-source options."

2. "How does ICE's Reddit Signals & Sentiment product work? What data does it capture, how much does it cost, and what institutions are buying it? Is the alpha from Reddit sentiment decaying as it becomes commoditized?"

3. "Compare FinBERT vs BloombergGPT vs FinGPT for financial sentiment analysis. What are the accuracy benchmarks on standard financial NLP datasets? Which handles social media slang and sarcasm best?"

4. "What alternative data sources are hedge funds using in 2026 that retail investors don't have access to? Specifically satellite data, app downloads, job postings, and social media signals."

## Round 2: Technical Architecture
1. "Design a real-time financial sentiment pipeline that ingests Reddit, X/Twitter, and news data, scores it with FinBERT, stores in PostgreSQL with TimescaleDB, and exposes via FastAPI. Include rate limiting, error handling, and cost estimates for 100K posts/day."

2. "What's the optimal architecture for combining FinBERT (fast, quantitative sentiment scoring) with Claude API (slow, qualitative narrative reasoning) in a single pipeline? When should you use each?"

3. "How do you build a historical pattern matching system for financial markets? Specifically, given a current market event (e.g., Strait of Hormuz blockade), how do you find structurally similar historical events and measure how correlated their subsequent price paths were?"

4. "What's the best way to store and query time-series sentiment data in PostgreSQL? Compare TimescaleDB extension vs native partitioning vs Citus for a dataset of 500K sentiment scores per day over 5 years."

## Round 3: The Alpha Edge
1. "What academic research exists on the predictive power of Reddit/WallStreetBets sentiment for stock returns? Cite specific papers, time periods, and win rates. Has the alpha decayed since 2021 (GameStop era)?"

2. "Historical analysis: When social media sentiment on a stock reaches 90%+ bullish, what happens to the stock price over the next 5, 10, and 30 days? Is extreme bullish sentiment a reliable contrarian sell signal?"

3. "What are the most reliable 'things that rhyme' in financial history? Specifically: oil embargoes (1973 vs 2026), wartime defense spending cycles, supply chain recovery timelines, and ceasefire trade patterns."

4. "How do institutional 13F filings (with a 45-day lag) compare to real-time social sentiment as a trading signal? Which has a higher information ratio? Can combining both improve predictions?"

## Round 4: Product & Business
1. "What would a SaaS pricing model look like for a real-time stock sentiment API? Compare per-query pricing vs subscription tiers vs freemium. What do competitors charge?"

2. "What are the legal requirements for selling AI-generated financial signals in the US? Do we need SEC registration, a disclaimer, or specific licenses?"

3. "What's the TAM (Total Addressable Market) for retail trading intelligence tools in 2026? How many active retail traders exist, what do they spend on data/tools, and what's the growth rate?"

## Round 5: Historical Pattern Matching (Things That Rhyme)
1. "Analyze the 1973 Arab oil embargo, 1990 Gulf War oil spike, 2022 Russia-Ukraine energy crisis, and 2026 Hormuz blockade. What are the structural similarities? How did tanker stocks, defense stocks, gold, and fertilizer stocks perform during and after each crisis? What was the typical timeline from crisis peak to normalization?"

2. "When has the CNN Fear & Greed Index been in 'Extreme Fear' (<20) while the S&P 500 was still above its 200-day moving average? What happened to the market over the next 30/60/90 days in each case?"

3. "Historical analysis of 'ceasefire trades': When a military conflict ends with a ceasefire, what happens to defense stocks in the 30 days after? Do they sell off immediately or hold gains? Compare across Gulf War, Iraq War, Afghanistan withdrawal, and Russia-Ukraine."

4. "When institutional fund flows (13F data) show net selling while retail sentiment (Reddit/StockTwits) shows peak bullishness, what happens to the stock over the next 30 days? Find 10+ historical examples."

## Round 6: Historical Rhyming Engine (Technical)
1. "How would you build a system that finds 'things that rhyme' in market history? Given a current event description, how do you search a database of historical events to find structural matches? What similarity metrics work — cosine similarity on event descriptions, correlation of subsequent price paths, or something else?"

2. "Create a taxonomy of market crisis types with historical examples: supply chain disruptions, military conflicts, financial panics, pandemic shocks, political transitions, regulatory changes, natural disasters. For each type, what are the typical phases (shock → adaptation → normalization) and how long does each phase last?"

3. "What open datasets exist for historical market events, crises, and their outcomes? Where can I get structured data on past oil crises with commodity price paths, historical defense spending cycles, sector rotation patterns after wars, gold price behavior during geopolitical crises?"

## Round 7: The $5K → $1M Proof Strategy
1. "What's the most capital-efficient path from $5K to $1M in active stock/options/futures trading? Assume access to real-time sentiment signals with 65% accuracy. Model the optimal position sizing, leverage usage, and compounding strategy."

2. "Study traders who have publicly documented turning small accounts into large ones. What strategies did they use? What was their average holding period, win rate, and position size relative to account? What role did leverage play?"

3. "If I have a sentiment signal with a 65% win rate and an average win of +8% vs average loss of -5%, what's the optimal Kelly Criterion position size? How long does it take to compound $5K to $1M at optimal sizing?"
