# AlphaHound — Master Research Brief (v2 — Refined)
## Run this through: Perplexity Deep Research, Gemini Deep Research, Claude, ChatGPT
## Save each AI's response separately, then bring all back for synthesis

---

## WHO I AM
I'm a full-stack AI developer building a real-time sentiment intelligence platform called "AlphaHound." I have an Azure server (Windows Server 2022), deep experience across Python/FastAPI, .NET, Node.js, React, and PostgreSQL. I've built AI-first products before. This is not hypothetical — I'm building this now and need actionable, specific intelligence to make architecture and product decisions.

## WHAT I'M BUILDING
AlphaHound is a multi-industry sentiment engine that starts with stock trading. The core platform is industry-agnostic — the same engine that detects "Reddit is bullish on $STNG while institutions are dumping shares" can detect "Reddit is bullish on a neighborhood while listing prices are dropping." Stock trading is Module 1. Real estate, automotive, F&B, and other industries come later.

### The Stock Trading Module (MVP) Does Three Things:

**1. Multi-Source Sentiment Scoring**
Ingest data from Reddit (r/wallstreetbets, r/stocks, r/investing), X/Twitter (cashtag volume), StockTwits (bull/bear ratios), news wires (Bloomberg, Reuters, MT Newswires), Substack (independent analysts), SEC filings (13F, insider transactions), and options flow (unusual activity). Score each ticker on a 1-10 scale with a separate confidence score (1-10). Detect when sources DIVERGE (retail bullish, institutions selling = distribution warning).

**2. Hidden Narrative Detection**
Use LLM reasoning (Claude API) to identify emerging narratives that haven't hit mainstream news yet — early Reddit DD posts gaining traction, Substack analysts flagging supply chain issues, unusual options activity clustering around specific strikes/dates. The "what's brewing that nobody's talking about yet" layer.

**3. Historical Pattern Matching ("Rhyme Engine")**
When a current market event occurs (e.g., 2026 Strait of Hormuz blockade), automatically find structurally similar historical events (1973 oil embargo, 1990 Gulf War, 2022 Russia-Ukraine) and use their outcomes to predict what happens next. Output: "This situation is 78% similar to the 1990 Gulf War. In that case, tanker stocks peaked 6-8 weeks after the initial spike and gave back 30% before stabilizing. You are in week 7."

### The Proof
I need to turn $5,000 into $1,000,000 using AlphaHound signals as the primary decision engine. Every trade will be logged with the specific signal that triggered it. This verifiable track record becomes the case study that sells the platform as a SaaS product.

## WHAT I NEED FROM YOU
I need comprehensive research across SEVEN areas. For each area, give me SPECIFIC, ACTIONABLE intelligence — not general overviews. Include URLs, pricing, technical specifications, accuracy benchmarks, and your opinionated recommendations. I'm making build-vs-buy decisions based on your answers.

---

## AREA 1: COMPETITIVE LANDSCAPE

What AI-powered stock sentiment analysis platforms exist today? For the top 15-20 platforms, compare:

- Data sources they ingest (Reddit, X, news, SEC, options flow)
- AI/ML approach (FinBERT, proprietary NLP, LLM, rule-based)
- Latency (real-time vs delayed)
- Published accuracy or backtested win rates
- API availability and pricing
- Historical data for backtesting (how far back?)
- Key strengths and weaknesses

Platforms to cover: LunarCrush, Sentifi, StockTwits, MarketPsych/Refinitiv, Accern, ICE Reddit Signals & Sentiment, Quiver Quantitative, Unusual Whales, SwaggyStocks, ApeWisdom, Stockgeist, TipRanks, Sentimentrader, FinBrain Technologies, **RavenPack** (major institutional player — cover this in depth), and any others you know about. Also cover open-source: FinBERT, FinGPT, VADER.

**Key questions:**
- Where is the GAP that no one fills well? **Specifically investigate whether any platform has commercialized "historical pattern matching" or a "rhyming engine" that matches current events to past crises.** This appears to be the blue ocean — confirm or deny.
- Is Reddit alpha decaying now that ICE sells Reddit sentiment to institutions? **ICE's Reddit Signals & Sentiment product processes 16B+ posts into structured market signals — if institutions have this, what edge does retail still have?**
- What's best-in-class accuracy? Has anyone published verifiable win rates?
- What would make someone switch from existing tools to AlphaHound?

---

## AREA 2: DATA SOURCES & TECHNICAL ARCHITECTURE

For every data source I can plug into this engine, I need: API availability, authentication method, rate limits, pricing (free and paid tiers), data format, latency, historical data availability, legal status for commercial use, and Python library (if one exists).

**Sources to cover:**

*Social:* Reddit API (post-2023 pricing), X/Twitter API (**note: new pay-per-use model at $0.005/post, moderate usage ~$215/month — verify this and compare to flat tier pricing**), StockTwits API, **ApeWisdom** (aggregates Reddit stock mentions with sentiment — cover in detail), Discord finance servers, TikTok/FinTok

*News:* MT Newswires, Benzinga Pro, Seeking Alpha, Bloomberg, Reuters/Refinitiv, NewsAPI.org, Google News (SerpAPI)

*Financial:* SEC EDGAR (13F, insider, 8-K), FINRA (short interest), CFTC COT data, options flow (CBOE, Unusual Whales API, ORATS), dark pool data

*Alternative:* Google Trends (pytrends), satellite data providers (for oil storage, shipping traffic), job posting data (Indeed, LinkedIn), patent filings (USPTO API), government contracts (USAspending.gov), web traffic data (SimilarWeb), app download data (Apptopia, Sensor Tower)

*Market Data:* Alpha Vantage, Polygon.io, Yahoo Finance (yfinance), FRED

**Key questions:**
- What's the cheapest way to get real-time Reddit + X sentiment for 500+ tickers? Monthly cost? **Account for the trade-off between scraping (cheaper, legally risky) vs official APIs (expensive, legally safe). What's the legal risk specifically after Reddit's 2023-2026 ToS changes and X's post-Musk API restructuring?**
- Can I build a pipeline processing 100K posts/day for under $500/month in total API costs?
- Which sources have the highest signal-to-noise ratio for stock prediction? Rank them.
- **Azure VM sizing for production:** What do I need for FinBERT inference (100K posts/day), PostgreSQL/TimescaleDB storage, and FastAPI serving? Recommend specific Azure VM SKUs with monthly cost estimates. **Benchmark data: FinBERT fine-tuning requires 16-80 GB GPU memory. For inference, consider Standard_NV6ads_A10_v5 (~$550/month) or Standard_NC4as_T4_v3 (~$400/month). PostgreSQL: Standard_D4s_v3 (4 vCPU, 16 GB RAM) + Premium SSD. Verify and refine these.**

Also: Design a real-time sentiment pipeline architecture using Python/FastAPI, PostgreSQL/TimescaleDB, FinBERT for scoring, and Claude API for reasoning. Include the data flow, processing steps, storage schema, and API layer.

---

## AREA 3: AI MODELS & SENTIMENT SCORING

Compare FinBERT, FinGPT, BloombergGPT, VADER, RoBERTa (fine-tuned), and general LLMs (Claude, GPT-4o) for financial sentiment analysis:

- Accuracy on standard benchmarks (PhraseBank, FiQA, SemEval). **Benchmark reference: FinBERT achieves ~91% accuracy on financial datasets. GPT-4o reportedly outperforms FinBERT by up to 10% with proper prompt engineering. Verify these numbers and provide the latest benchmarks.**
- Performance on Reddit-style text (short, sarcastic, emoji-heavy, slang like "diamond hands," "ape," "HODL," "LFG," "apes together strong")
- Inference speed (posts/second)
- Self-hosting cost vs API cost. **Specifically: What's the inference cost for 100K posts/day on self-hosted FinBERT vs GPT-4o mini API calls? Break down the math.**
- Fine-tuning feasibility

**Key architecture question:** I'm planning a two-tier system — FinBERT for fast bulk scoring (100K posts/day) and Claude API for deep narrative reasoning (100-500 calls/day). **This two-tier approach is validated as industry best practice — but I need specifics on when to route to each tier.** What triggers escalation from Tier 1 (fast scoring) to Tier 2 (deep reasoning)? What's the accuracy improvement of the ensemble vs FinBERT alone?

**Scoring engine design:** I want to output a signal score (1-10) and confidence score (1-10) per ticker. What inputs should feed the score (sentiment polarity, volume, velocity, source reliability, institutional alignment, technical alignment, historical pattern match)? How should they be weighted? What's the minimum data points needed for a reliable score?

**Critical problem — sarcasm, irony, and coded language:** Reddit and X are full of it. "To the moon 🚀" = bullish. "This is financial advice" = ironic (actually not advice). "Rug pull incoming" = bearish. "Bags are heavy" = holding at a loss. **How do existing best-in-class systems handle irony, sarcasm, and coded language in financial social media? Is there a sarcasm detection layer that can be added? Or is volume of mentions simply more reliable than polarity?** Include evidence from academic research or industry whitepapers.

---

## AREA 4: HISTORICAL PATTERN MATCHING ("THINGS THAT RHYME")

This is AlphaHound's unique differentiator — **no major competitor appears to have commercialized this. Confirm whether this is truly a blue ocean.**

I need to build an engine that, given a current market event, finds structurally similar historical events and uses their outcomes to predict what happens next.

**Historical events to catalog** (for each: timeline, affected assets, phase progression, peak-to-trough metrics, recovery timeline):

*Oil/Energy:* 1973 Arab oil embargo, 1979 Iranian Revolution, 1990 Gulf War, 2008 oil spike, 2014-2016 collapse, 2020 COVID crash, 2022 Russia-Ukraine, 2026 Hormuz blockade

*Military:* Gulf War 1990, Post-9/11, Iraq War 2003, Russia-Crimea 2014, Russia-Ukraine 2022, Iran-US 2026

*Supply Chain:* Japan earthquake 2011, COVID supply chains 2020-2022, Suez Canal 2021, semiconductor shortage 2021-2022, Hormuz blockade 2026

*Sentiment Extremes:* GameStop mania 2021, SPAC bubble 2021, crypto winter 2022, every time Fear & Greed hit single digits

**Algorithms:** How do I programmatically find "things that rhyme"? Compare: event embedding with cosine similarity, **price path correlation using DTW (Dynamic Time Warping) — this appears to be the most practical approach, confirm**, feature-based matching on crisis attributes, and hybrid approaches. Which is most practical to implement in Python? What libraries exist (tslearn, dtw-python, fastdtw)?

**Datasets:** Where do I get historical data to seed this engine? **Specific sources to investigate: WRDS/MarketPsych (covers 170 currencies, 3,000+ cities), FNSPID (time-aligned financial news and stock prices).** Also: historical price data back to 1970s, structured historical events databases, historical Fear & Greed index, historical put/call ratios, historical 13F filings, historical VIX term structure. Provide specific URLs and APIs.

**Key questions:**
- Has anyone built a "historical rhyming" system for financial markets before? Any academic papers or commercial products?
- **What's the minimum viable event database to start? Should I start with 20 manually curated events and scale, or do I need hundreds from day one?**
- How far back does the data need to go for useful pattern matching? 10 years? 30? 50?
- What's the expected accuracy improvement from adding historical pattern matching to a sentiment-only model?

---

## AREA 5: $5K → $1M PROOF STRATEGY

The math and strategy of compounding a small account using sentiment-driven signals.

**Kelly Criterion modeling:** With a 65% win rate, average win +8%, average loss -5% — what's the optimal position size? Model the path from $5K to $1M at **full Kelly, half-Kelly (recommended for small accounts — more conservative during losing streaks), and quarter-Kelly.** How many trades? How long?

**Max drawdown modeling:** **What happens during a 10-trade losing streak at each Kelly fraction? At what drawdown level does the strategy become unrecoverable? This is critical — the psychological pain of losing $1,000 is roughly 2x the joy of making $1,000 (loss aversion). Factor this into the risk management design.**

**Instruments by phase:** What should I trade at each stage?
- $5K-$25K: Options? Futures? Stock swing trades? **Note: PDT rule applies — max 3 day trades in 5 rolling business days while under $25K. How does this constrain the strategy?**
- $25K-$100K: How does strategy evolve once PDT restriction lifts?
- $100K-$1M: What changes at scale?

**Position sizing based on signal confidence:** How to size trades when confidence is 8-10 vs 5-7 vs below 5?

**Options leverage:** Which strategies work best with sentiment signals? Optimal DTE? Strike selection? How to avoid the common blowups?

**Case studies:** Documented examples of traders who turned small accounts into large ones. What strategies? Win rates? Hold times? What killed the ones who failed?

**Risk management:**
- Max loss per trade as % of account
- Max concurrent positions
- Max daily loss before stopping
- PDT rule handling (under $25K)
- **Tax implications: Short-term capital gains vs long-term. At high trade frequency, what's the effective tax drag? How does this affect the compounding math?**

**Key question:** Is $5K → $1M realistic in 12-24 months with a 65% win rate? Be brutally honest about the probability.

---

## AREA 6: LEGAL & BUSINESS

**Legal:**
- Do I need SEC registration to sell AI-generated trading signals?
- What disclaimers are legally required?
- Am I liable if users lose money?
- **Selling "data/insights/scores" (low regulatory risk) vs selling "actionable buy/sell advice" (high regulatory risk) — where is the exact legal line? This distinction is critical for product design.**
- Reddit and X ToS for commercial data use — what's allowed in 2026?
- GDPR/CCPA implications?
- **SEC is actively scrutinizing AI trading tools in 2026. What specific enforcement actions or guidance have been issued? What are the red lines?**
- **Copy-trading risk: If I run a "proof" account ($5K → $1M) and users follow my trades, what's the regulatory risk of trading alongside users who copy my signals?**

**Business:**
- SaaS pricing model for a sentiment API (per-query vs subscription vs freemium)?
- TAM for retail trading intelligence tools in 2026?
- What do competitors charge?
- What's the fastest path to revenue?

---

## AREA 7: SIGNAL-TO-NOISE & DATA QUALITY

**This area is about making the data RELIABLE before we score it.** For each major data source (Reddit, X, StockTwits, news wires, SEC filings, options flow):

1. **Spam/bot percentage:** What's the known rate of bot activity, spam, and manipulation? How do I filter it? What tools/methods exist for bot detection on financial social media?
2. **Volume vs polarity:** Does mention VOLUME correlate more strongly with price movement than sentiment POLARITY? Provide academic evidence. **If volume is more reliable than polarity, this fundamentally changes the scoring engine design.**
3. **Minimum viable post count:** What's the minimum number of posts/mentions per ticker needed for a statistically reliable sentiment score? (10 posts? 50? 200?)
4. **High-volatility degradation:** How does signal quality degrade during high-volatility events (earnings, black swans, Fed decisions)? Does sentiment become MORE or LESS predictive during market stress?
5. **Latency chain:** What's the measured latency from social post → API availability → sentiment score → actionable signal? Map the full chain for Reddit and X. **If the total latency is >15 minutes, is the alpha already gone?**
6. **Data poisoning risk:** Can bad actors intentionally manipulate social sentiment to trigger false signals? Has this happened? (e.g., coordinated pump-and-dump via Reddit) How do the best systems detect and defend against it?

---

## BONUS: BACKTESTING FRAMEWORK

**Before going live with real money, I need to validate signals historically.** This will also be AlphaHound's strongest sales pitch — "here's how our signals performed over the last 5 years."

1. What's the best approach for backtesting sentiment-driven trading signals? (Walk-forward analysis, out-of-sample testing, Monte Carlo simulation?)
2. What historical sentiment data is available for backtesting? (Is there a dataset of Reddit/X sentiment going back 3-5 years that I can test against?)
3. What backtesting frameworks work well with sentiment data? (Backtrader, Zipline, QuantConnect, custom?)
4. How do I avoid look-ahead bias and survivorship bias in sentiment backtests?
5. What minimum backtest period is credible for investors/users? (1 year? 3 years? 5 years?)

---

## OUTPUT FORMAT
Structure your response with clear headers matching my 7 areas (plus bonus). For each area:
1. **Executive Summary** (3-5 bullet points — the key takeaways)
2. **Detailed Findings** (tables where applicable, specific numbers, URLs)
3. **Recommendation** (what should I build, buy, or skip — be opinionated)
4. **Sources** (URLs for everything you reference)

I'd rather have depth on the areas you know well than shallow coverage of everything. If you're uncertain about something, say so rather than guessing.

---

*After running this through multiple AIs, save each response as:*
- `perplexity_results.md`
- `gemini_results.md`
- `claude_results.md`
- `chatgpt_results.md`

*Then bring all four back for synthesis into the PRD.*
