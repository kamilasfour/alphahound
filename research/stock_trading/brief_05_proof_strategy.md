# Research Brief 05: $5K → $1M Proof Strategy
## Paste this entire brief into Perplexity / Gemini Deep Research / Claude

---

## CONTEXT
I'm building "AlphaHound" — a stock sentiment intelligence platform. To prove it works, I need to turn $5,000 into $1,000,000 using AlphaHound signals as the primary decision engine. Every trade will be logged with the specific signal that triggered it, creating a verifiable case study.

The $5K is in a Schwab thinkorswim account with access to: stocks, ETFs, options, futures (/MCL, /MGC, /NG), and 70+ forex pairs. I also have a Merrill Lynch account with $35K deployed in a long-term portfolio (separate from the $5K proof).

I have access to a sentiment engine that will produce signals with an expected ~60-70% win rate. I need to understand the MATH and STRATEGY of compounding a small account into a large one using sentiment-driven trading.

## WHAT I NEED

### Part 1: The Math of Compounding
1. **Kelly Criterion modeling:** If my signal has a 65% win rate with average win +8% and average loss -5%, what's the optimal position size as a % of account? Model the expected path from $5K to $1M at optimal Kelly, half-Kelly, and quarter-Kelly.
2. **Number of trades required:** At optimal sizing, how many trades does it take to go from $5K to $1M? How long at 1 trade/day? 3 trades/week? 1 trade/week?
3. **Drawdown modeling:** What's the maximum expected drawdown at each Kelly fraction? At what drawdown level does the strategy become unrecoverable?
4. **The role of leverage:** How does adding 2x-3x leverage (via options or futures) change the math? Model $5K with and without options leverage.

### Part 2: Case Studies — People Who Actually Did This
Research documented examples of traders who turned small accounts into large ones:

1. **Who are the verified cases?** (Not YouTube gurus — actual audited or publicly verified accounts)
2. **What strategies did they use?** (Options, momentum, mean reversion, event-driven?)
3. **What was their typical hold time?** (Intraday, swing 2-5 days, weeks?)
4. **What was their win rate and average trade?**
5. **How much leverage did they use?**
6. **How long did the journey take?**
7. **What blew up the ones who failed?** (Common mistakes in small-account growth)

### Part 3: Strategy Design for Sentiment-Driven Trading
Given that my edge comes from SENTIMENT SIGNALS (not technical analysis or fundamental analysis), what's the optimal trading strategy?

1. **Which instruments are best for a $5K account growing to $1M?**
   - Phase 1 ($5K-$25K): What to trade? (Stock options? Futures? Stock swing trades?)
   - Phase 2 ($25K-$100K): How does the strategy evolve as the account grows?
   - Phase 3 ($100K-$1M): What changes at scale?

2. **How to size positions based on signal confidence:**
   - Confidence 8-10: Position size = ?
   - Confidence 5-7: Position size = ?
   - Confidence 1-4: Skip or minimum size?

3. **Hold time optimization:**
   - If sentiment signals are most predictive over 1-5 days, what's the optimal entry-to-exit window?
   - Is there academic research on the decay rate of social sentiment alpha? (How quickly does the edge disappear after the signal fires?)

4. **Risk management for small accounts:**
   - Max loss per trade as % of account
   - Max open positions
   - Max daily loss before stopping
   - How to handle the PDT rule (Pattern Day Trader — under $25K)

### Part 4: Options as Leverage
Options are likely the fastest path from $5K to $1M due to leverage. Research:

1. **Which options strategies work best with sentiment signals?** (Long calls/puts, debit spreads, straddles before events?)
2. **Optimal DTE (days to expiration) for sentiment-driven options trades?** (Weeklies, monthlies, 45-day?)
3. **Strike selection based on signal confidence?** (ATM for high confidence, OTM for "lottery" signals?)
4. **Expected return distribution for options trades with 65% directional accuracy?**
5. **How to avoid the most common ways options traders blow up small accounts?**

### Part 5: Milestone Strategy
Map out the journey in phases:

| Phase | Account Size | Strategy | Instruments | Position Size | Hold Time | Goal |
|-------|-------------|----------|-------------|--------------|-----------|------|
| 1 | $5K-$10K | ? | ? | ? | ? | 2x |
| 2 | $10K-$25K | ? | ? | ? | ? | 5x |
| 3 | $25K-$100K | ? | ? | ? | ? | 20x |
| 4 | $100K-$500K | ? | ? | ? | ? | 100x |
| 5 | $500K-$1M | ? | ? | ? | ? | 200x |

## WHAT I SPECIFICALLY WANT TO KNOW
1. **Is $5K → $1M realistic in 12-24 months with a 65% win rate sentiment signal?** What does the math say?
2. **What's the single biggest reason small-account traders fail to compound?** (Overtrading? Poor sizing? Emotional decisions?)
3. **At what account size should I switch from options to stock/ETF swing trades?** (When does the leverage risk outweigh the benefit?)
4. **What's the optimal number of concurrent positions for a $5K account?** (1? 2? 3?)
5. **Has anyone used AI sentiment signals to compound a small account?** Any documented results?

## OUTPUT FORMAT
Start with the math (Kelly Criterion model with specific numbers), then the case studies (table format), then the phased strategy with specific instruments and position sizes. Be brutally honest about the probability of success.

---
*Save the response as: `proof_strategy_results.md` in this folder*
