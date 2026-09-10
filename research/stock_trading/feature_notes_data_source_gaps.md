# Feature Note: Data Source Gap Analysis

## Purpose
The Master Research Brief covered the obvious data sources (Reddit, X, StockTwits, news wires, SEC, options flow). But there are many high-signal sources we under-weighted or missed entirely. This note catalogs the gaps.

## Tier 1 Gaps (High-Priority Additions)

### Substack (Under-Weighted)
Independent analysts often surface narratives BEFORE mainstream news. Many have paid tiers but free content is scrapable.

**Must-monitor Substacks:**
- **Doomberg** — energy, commodities, geopolitics (massively influential, moves markets)
- **The Macro Compass** (Alfonso Peccatiello) — rates, macro, bond markets
- **Matt Stoller's BIG** — antitrust, platform regulation, tech policy
- **Net Interest** (Marc Rubinstein) — banks, fintech, insurance
- **Capital Thinking** (Jamie Catherwood) — markets history, long-term patterns
- **The Daily Upside** — free broad financial news
- **Bethany McLean** — investigative finance (Enron-level exposés)
- **Epsilon Theory** (Ben Hunt) — narrative economics
- **The Grant Williams Podcast/Substack** — macro + precious metals
- **Paulo Macro** — macro trading
- **Fabius Maximus / Concoda** — monetary plumbing

**Technical approach:** RSS feeds (most Substacks expose `/feed`), scrape titles + free previews. LLM summarization to extract tickers and sentiment.

### YouTube / Podcast Transcripts
Massive untapped retail sentiment layer. Transcripts are readily available via YouTube API or Whisper.

**Retail-influence channels:**
- Meet Kevin, Joseph Carlson, Patrick Boyle, Ben Felix
- Tom Nash, Stephanie Link, Jim Cramer clips
- WSB YouTubers (Matt Kohrs, Trey's Trades)

**Analyst / institutional podcasts:**
- Odd Lots (Bloomberg) — THE podcast institutional traders listen to
- Invest Like the Best (Patrick O'Shaughnessy)
- Macro Voices (Erik Townsend) — macro + commodities
- The Compound & Friends (Ritholtz group)
- Animal Spirits (Ritholtz)
- Chat with Traders (Aaron Fifield)
- Grant Williams Podcast
- Forward Guidance (Blockworks)

**Technical approach:** YouTube Data API v3 for metadata, yt-dlp + Whisper for transcripts. Store transcript + timestamp. Run ticker extraction + sentiment scoring on paragraphs.

### Analyst / Institutional Research
- **Seeking Alpha Quant grades** — systematic scoring system, has predictive value
- **TipRanks** — aggregated analyst ratings + price targets
- **Hedgeye** — institutional research, contrarian positioning
- **Zacks Rank** — #1/#5 rank changes are tradeable signals
- **Short seller reports**: Hindenburg Research, Muddy Waters, Kerrisdale Capital, Spruce Point, Citron Research (returned 2026)
- **Activist investor letters**: 13D filings from Elliott, Pershing Square, Trian, Starboard, Carl Icahn, ValueAct

**Why short seller reports matter:** When Hindenburg drops a report, the target stock often drops 10-30% in days. Being among the first to ingest + score these is huge alpha.

### Earnings Call Intelligence
- **The Transcript** (free newsletter) — curates earnings call highlights across hundreds of companies
- **AlphaSense** — expensive but institutional-grade transcript + expert call search
- **Seeking Alpha transcripts** — free transcripts with delay
- **Motley Fool transcripts** — also free

**Why it matters:** Management tone, forward guidance changes, and new narrative introduction happen on earnings calls BEFORE analyst reports cycle through.

### Congressional Trading
- **STOCK Act filings** — congressmembers must disclose trades
- **Quiver Quantitative** — aggregates this, has API
- **Capitol Trades** (2iQ) — real-time alerts

**Why it matters:** Pelosi's trades alone moved markets. Systemically tracking all 535 members' disclosed trades is a known alpha source.

## Tier 2 Gaps (Secondary Additions)

### Social Media Beyond Reddit/X
- **Discord finance servers** — real-time retail chat (legally grey to scrape, but some have public channels)
- **Bluesky** — growing X alternative, finance community forming
- **Threads (Meta)** — Meta's X competitor
- **TikTok/FinTok** — younger retail sentiment, harder to scrape but influential on meme stocks
- **Telegram channels** — crypto-heavy plus stock pump groups
- **LinkedIn** — executive posts, corporate signals, layoff announcements
- **4chan /biz/** — edge case but has moved microcaps historically (GME, AMC precursors)

### News Wire Expansion
- **BusinessWire, PR Newswire, GlobeNewswire** — raw company press releases (often 30-60 min ahead of news aggregators)
- **FD Alerts** — conference call presentations, IR events
- **FactSet StreetAccount** — institutional news aggregator
- **Briefing.com** — real-time news/analysis for traders

### Crypto / On-Chain (for future crypto expansion)
- **Nansen** — smart money wallet tracking
- **Arkham Intelligence** — entity labeling
- **Dune Analytics** — custom on-chain queries
- **Santiment** — crypto sentiment + on-chain fusion
- **Glassnode** — on-chain metrics
- **CoinGlass** — liquidation data, funding rates

## Tier 3 Gaps (Nice-to-Have / V2+)

### Political / Policy
- **Federal Register** — regulatory changes, comment periods
- **Congressional hearing schedules** — Senate Banking, House Financial Services
- **Lobbying disclosures** — OpenSecrets API
- **Committee vote trackers** — tradeable before bill passage

### Academic
- **SSRN** — working papers on market anomalies (often tradeable alpha)
- **arXiv q-fin** — quant research papers
- **Review of Financial Studies**, **Journal of Finance** — academic journals

### Alternative Data
- **Flight tracking (ADS-B Exchange)** — private jet movements signal M&A meetings
- **AIS ship tracking** — tanker movements (already in global cascade notes)
- **Satellite imagery** — MDA, Planet Labs, RS Metrics for retail foot traffic, oil storage levels
- **Credit card data** — Second Measure, Bloomberg SMBL (expensive)
- **Web traffic** — SimilarWeb, Semrush (company-level internet traffic)
- **App downloads** — Apptopia, Sensor Tower (app-based company revenue proxy)
- **Job postings** — LinkedIn, Indeed, Revelio Labs (hiring trends = growth/contraction signal)

### Investor Relations
- **Company IR pages** — investor presentations, guidance updates
- **8-K filings** — material events (already in brief but worth emphasizing for real-time monitoring)
- **Insider Form 4** — real-time insider buying/selling

### Whistleblower / Litigation
- **FINRA complaint database**
- **SEC whistleblower case filings**
- **Class action databases** — Stanford Securities Class Action Clearinghouse

## Source Scoring Framework
Each data source should be evaluated on:

| Dimension | Weight |
|-----------|--------|
| Signal-to-noise ratio | 25% |
| Latency (how fast after event) | 20% |
| Cost (API/scraping cost) | 15% |
| Legal risk | 15% |
| Coverage (tickers/events) | 10% |
| Uniqueness (not in other sources) | 10% |
| Reliability (uptime/consistency) | 5% |

## Implementation Priority for MVP

**Phase 1 MVP sources (already in PRD):**
- Reddit (via ApeWisdom + official API)
- X/Twitter (pay-per-use $0.005/post)
- StockTwits (free API)
- SEC EDGAR (free)
- Options flow (Unusual Whales $65/mo)
- News (FMP + Polygon)

**Phase 1.5 additions (cheap, high-signal):**
- Substack RSS feeds (free, ~20 priority newsletters)
- The Transcript (free email)
- Congressional trading (Quiver Quantitative)
- Short seller report monitoring (RSS + website scraping)

**Phase 2 additions:**
- YouTube transcripts for top 10 finance channels
- Podcast transcripts for Odd Lots, Macro Voices, Forward Guidance
- Kalshi + Polymarket ingestion
- BusinessWire/PR Newswire feeds

**Phase 3 additions:**
- Full analyst report ingestion (Seeking Alpha Quant, TipRanks)
- Alternative data (satellite, web traffic, job postings)
- Crypto on-chain (if expanding to crypto)

## Cost Estimate for Expanded Source Mix
- Substack scraping: $0/month (RSS)
- YouTube API: ~$0-50/month (within free tier for top 20 channels)
- Podcast transcripts: Whisper API ~$30/month for 20 podcasts
- Congressional trading: Quiver $10/month
- Short seller monitoring: $0/month (RSS + scraping)
- News wires (PR/BusinessWire): $0-100/month
- **Total Phase 1.5 expansion: +$40-200/month over MVP budget**

## PRD Updates Needed
1. Area 2 (Data Sources) — add Substack, YouTube/podcasts, Congressional trading, short seller reports as Tier 1.5 sources
2. Area 3 (Scoring Engine) — weight contributor-type sources differently (institutional newsletter > anonymous Reddit post)
3. Area 7 (Signal-to-Noise) — note that Substack has FAR higher signal-to-noise than Reddit for the audience that reads it
4. Add "Data Source Expansion Roadmap" section showing MVP → Phase 1.5 → Phase 2 → Phase 3
