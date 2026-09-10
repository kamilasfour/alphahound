# Feature Note: Prediction Markets — Data Source AND Trading Venue

## Dual Role in AlphaHound
Prediction markets serve TWO distinct purposes for AlphaHound:

1. **INPUT (Sentiment Data Source)** — prediction market probabilities are crowd-weighted sentiment signals with real money backing, making them potentially cleaner than Reddit/X.
2. **OUTPUT (Trading Venue)** — AlphaHound signals can be used to place bets directly on Polymarket, Kalshi, and similar platforms. This becomes a SECOND proof track alongside the $5K → $1M stock account.

## Why Prediction Markets as a Trading Venue Matters

### Cleaner Than Options
- **Binary outcomes** → easier to backtest, cleaner win-rate math
- **No time decay weirdness** — price converges linearly to resolution
- **No PDT rule**, no Greeks, no assignment risk
- **Lower capital requirements** — $5-$50 position sizes for testing signals
- **Kalshi is CFTC-regulated** — fully legal for US retail

### Event-Specific Markets Match Sentiment Signals 1:1
AlphaHound generates sentiment scores on events. Prediction markets ARE bets on those events:
- "Will Fed cut rates in June?" → directly bet on Kalshi
- "Will Iran close Strait of Hormuz by Q2?" → directly bet on Polymarket
- "Will CPI come in above 3.0%?" → directly bet on Kalshi
- "Will NVDA beat EPS estimates?" → directly bet on Kalshi

### Two Verifiable Track Records
Running parallel proof accounts:
- **Stock account**: $5K → $1M via options/swing trades (longer journey, higher skill ceiling)
- **Prediction market account**: $1K → $50K via Kalshi/Polymarket (faster validation cycle, binary outcomes)

Both logged with signal attribution. Both become sales evidence for the SaaS platform.

## Trading Venues to Integrate

### Kalshi (Primary — US-Legal)
- CFTC-regulated, fully legal for US residents
- Strong economic data markets (CPI, NFP, Fed, GDP)
- Earnings beat/miss markets
- Clean API: https://trading-api.readme.io/reference/getting-started
- Position size limits but adequate for AlphaHound's account sizes

### Polymarket (Secondary — Grey Area for US)
- Largest prediction market (~$5B+ annual volume as of 2026)
- Rich geopolitical, election, crypto markets
- USDC-settled on Polygon blockchain
- US users technically restricted (CFTC 2022 settlement), enforcement patchy
- API: https://docs.polymarket.com
- Need to verify 2026 US access status before production use

### PredictIt (Tertiary)
- Academic exemption, limited position sizes
- Politics-focused, high-signal
- US-legal

### Manifold Markets (Testing)
- Play-money but large user base
- Good sandbox for testing signal generation without capital at risk

## Signal Types Unlocked

### As Data INPUT
- Event probability deltas (overnight probability shifts)
- Cross-asset correlation (prediction market move → equity sector rotation)
- Consensus vs mispricing (Polymarket vs analyst consensus)
- Geopolitical event pricing (Middle East escalation probabilities)

### As Trading OUTPUT
- Direct bets on events AlphaHound scores high-conviction on
- Hedge positions (short Polymarket "Trump wins" while long Trump-trade equities)
- Event arbitrage (Kalshi vs Polymarket pricing gaps)
- Correlated equity plays (bet on Polymarket Fed cut + buy TLT)

## Mapping Events to Tradeable Instruments

| Event/Market | Prediction Market Play | Correlated Equity Play |
|--------------|------------------------|------------------------|
| Fed rate cut | Kalshi Fed markets | TLT, IEF, XLF, KRE |
| CPI above X% | Kalshi CPI markets | TLT, TIP, GLD |
| Geopolitical escalation | Polymarket conflict markets | XLE, XOP, STNG, RTX, GLD |
| Election outcomes | Polymarket election | Sector rotation (XLE vs XLV) |
| Earnings beat/miss | Kalshi earnings | Specific ticker options |
| Recession Q3 2026 | Kalshi/Polymarket | IWM, XRT, HYG, TLT |
| Crypto regulation | Polymarket crypto | COIN, MARA, IBIT |

## Personal Validation Plan (User Zero)
- Week 1-2: Paper trade Kalshi using AlphaHound signals, log every trade
- Week 3-4: $500 live Kalshi account, small position sizes
- Month 2: Scale to $2K, add Polymarket (geopolitical markets only)
- Month 3+: Parallel track with stock proof account
- Every bet logged with triggering signal + confidence score

## Implementation Priority
- **MVP (v1.0):** Skip both trading and data ingestion. Core equity pipeline first.
- **v1.1:** Add Kalshi DATA ingestion (probabilities as sentiment input).
- **v1.2:** Add Kalshi TRADING module (place bets via API from AlphaHound signals).
- **v1.3:** Add Polymarket data ingestion.
- **v2.0:** Full prediction market trading module with position sizing, Kelly math, portfolio tracking.

## Legal Notes
- **Kalshi** — fully legal, CFTC-regulated, ~$25K position limits per market
- **Polymarket** — US legal status uncertain in 2026, verify before production
- **Data display** — if we show Polymarket probabilities to users, check licensing vs ICE's $$ distribution
- **Marketing language** — "signal informs Kalshi bets" is fine; "we predict event outcomes" starts sounding like investment advice

## PRD Updates Needed
1. Area 2 (Data Sources) — add Kalshi + Polymarket as Tier 1 sources (Phase 2 build)
2. Area 3 (Scoring Engine) — add "Prediction Market Alignment" 10% weight
3. Area 4 (Rhyme Engine) — historical prediction market probabilities as pattern input
4. Area 5 (Proof Strategy) — add parallel prediction market proof account ($1K → $50K)
5. NEW Area — "Trading Execution Module" covering equity brokers + prediction market APIs
