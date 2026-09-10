# Feature Note: Global Market Cascade Analysis

## The Insight
Markets don't open in isolation. Asian markets (Tokyo, Shanghai, Hong Kong, Seoul) open 13-14 hours before US markets. European markets (London, Frankfurt, Paris) open 5-6 hours before US. The price action and sentiment from each session cascades into the next.

## What AlphaHound Should Track

### Session-by-Session Cascade
1. **Asian Session (7 PM - 3 AM ET)**
   - Nikkei 225, Hang Seng, Shanghai Composite, KOSPI, ASX 200
   - Asian commodities (SGX iron ore, Shanghai copper, Tokyo gold)
   - USD/JPY, AUD/USD, USD/CNY as early sentiment proxies
   - Signal: If Asian markets sell off on overnight news, does that predict US open direction?

2. **European Session (3 AM - 9:30 AM ET)**
   - FTSE 100, DAX 40, CAC 40, Euro Stoxx 50
   - Brent crude (ICE), European natural gas (TTF)
   - EUR/USD, GBP/USD as sentiment gauges
   - Signal: European reaction to Asian moves — amplification or mean reversion?

3. **US Pre-Market (4 AM - 9:30 AM ET)**
   - Futures: /ES, /NQ, /YM, /RTY
   - Commodity futures: /CL, /GC, /SI, /NG
   - VIX futures
   - Signal: How do US futures react to Asian + European price action?

4. **US Regular Session (9:30 AM - 4 PM ET)**
   - The actual trades happen here
   - But 60-70% of the day's direction is often set by the cascade above

### Cross-Market Correlations to Monitor
- **Oil in Asia → Energy in Europe → XLE at US open**
- **Asian tech (KOSPI, TAIEX) → European tech → Nasdaq futures**
- **Gold in Shanghai → Gold in London → /GC at US open**
- **USD/JPY overnight → risk-on/risk-off tone for US equities**
- **European bank stocks → XLF direction**
- **VIX futures overnight → expected US volatility**

### Historical Pattern Dimension
The Rhyme Engine should also track global cascade patterns:
- During the 2022 Russia-Ukraine crisis, did European energy selloffs predict US energy moves?
- During COVID crash (March 2020), which session led the selloff?
- During 2026 Hormuz blockade, Asian tanker stocks (COSCO, SCI) moved before STNG/FRO — is that a leading indicator?

### Futures as Sentiment
Futures markets trade nearly 24 hours (Sun 6 PM - Fri 5 PM ET). They ARE the global cascade in real-time:
- /ES (S&P 500 futures) — the single most important overnight indicator
- /CL (WTI crude futures) — geopolitical sentiment proxy
- /GC (gold futures) — safe haven/fear gauge
- /VX (VIX futures) — forward-looking volatility expectations
- Term structure matters: VIX contango = calm, VIX backwardation = fear

### Implementation Priority
- **MVP:** Track overnight futures (/ES, /CL, /GC) and major Asian/European indices in the morning sentiment report. Flag when overnight moves exceed 1% as a pre-market alert.
- **V2:** Build a cascade scoring model — "Asian session was -1.5%, European session amplified to -2%, probability of US open gap-down is X%"
- **V3:** Historical cascade patterns in the Rhyme Engine — "The last time Asian markets sold off 2%+ on oil news while European markets amplified, US opened down 1.8% on average"

## For PRD
Include as a feature in the scoring engine. The daily signal output should include a "Global Cascade Score" showing how overnight sessions are trending and what that predicts for the US session.
