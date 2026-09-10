# Sprint 5 — Technical Brief
# Price Context + Actionable Signals
# Written: April 29, 2026

---

## Sprint Goal (One Sentence)

After this sprint, every divergence alert includes: current price, 5-day change vs SPY,
a Claude-written narrative explanation, congressional trade context, and analyst sentiment —
making alerts fully actionable for the first time.

---

## Technical Decisions (Pre-Made — Do Not Re-Debate)

### 1. Massive (price data)

**Endpoint:** `https://api.massive.com/v2/aggs/ticker/{ticker}/prev`
- Returns previous day's OHLCV for a ticker
- Use for: current price, daily change %

**Endpoint:** `https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}`
- Returns daily OHLCV for a date range
- Use for: 5-day price history, % change over 5 days

**SPY comparison:** pull SPY alongside every ticker. `(ticker_5d_change - SPY_5d_change)` = relative performance.

**Entity kind:** `ticker` — same as ApeWisdom. No new entity type needed.

**Source class:** NOT ingested as a `Post`. Price data goes into a new `price_snapshots` table (see schema below), NOT into `raw_posts`. Price is context, not sentiment content.

**New table needed:**
```sql
CREATE TABLE IF NOT EXISTS price_snapshots (
    time            TIMESTAMPTZ NOT NULL,
    entity_id       UUID NOT NULL REFERENCES entities(entity_id),
    price           DOUBLE PRECISION NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    volume          BIGINT,
    change_1d_pct   DOUBLE PRECISION,
    change_5d_pct   DOUBLE PRECISION,
    change_vs_spy   DOUBLE PRECISION,
    PRIMARY KEY (entity_id, time)
);
```
Convert to hypertable with 7-day chunks.

**Env var:** `MASSIVE_API_KEY`
**New file:** `src/alphahound/modules/stocks/adapters/massive.py`
**CLI:** `alphahound ingest --source massive`

---

### 2. Finnhub (social sentiment — fills Reddit gap)

**Endpoint:** `https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&from={date}`
- Returns Reddit + Twitter mention counts and sentiment scores per day
- Fields we care about: `reddit.mention`, `reddit.positiveScore`, `reddit.negativeScore`

**Endpoint:** `https://finnhub.io/api/v1/company-news?symbol={ticker}&from={from}&to={to}`
- Returns news articles with headlines
- Fields: `headline`, `summary`, `datetime`, `source`

**Mapping to Post:**
- Social sentiment: one Post per ticker per day. Text = synthetic summary of sentiment scores. `source_class = retail_social`, `tier = C`
- News headlines: one Post per article. Text = headline + ". " + summary. `source_class = news_wire`, `tier = C`

**Rate limit:** 60 calls/minute free tier. At 20 tickers × 2 endpoints = 40 calls per run. Safe.

**Env var:** `FINNHUB_API_KEY`
**New file:** `src/alphahound/modules/stocks/adapters/finnhub.py`
**CLI:** `alphahound ingest --source finnhub`

---

### 3. Alpha Vantage (news + earnings transcripts)

**Endpoint:** `https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey={key}`
- Returns news articles with pre-scored sentiment
- Fields: `title`, `summary`, `overall_sentiment_score`, `overall_sentiment_label`, `time_published`

**Endpoint:** `https://www.alphavantage.co/query?function=EARNINGS_CALL_TRANSCRIPT&symbol={ticker}&year={year}&quarter={quarter}&apikey={key}`
- Returns earnings call transcript text
- Fields: `transcript` (full text, may be long)

**Mapping to Post:**
- News: one Post per article. Text = title + ". " + summary. `source_class = news_wire`, `tier = C`
- Earnings transcripts: one Post per transcript chunk (split at 512 tokens for FinBERT). `source_class = analyst_curated`, `tier = B`

**Important:** earnings transcripts are `analyst_curated` — the FIRST time we have data in this source class. This is a new source class going live in Sprint 5.

**Rate limit:** 500 calls/day free tier. At 20 tickers × 2 endpoints = 40 calls per ingest. Safe.

**Env var:** `ALPHA_VANTAGE_API_KEY`
**New file:** `src/alphahound/modules/stocks/adapters/alpha_vantage.py`
**CLI:** `alphahound ingest --source alpha_vantage`

---

### 4. Quiver (congressional trades)

**Endpoint:** `https://api.quiverquant.com/beta/live/congresstrading`
- Returns all recent congressional stock trades
- Fields: `Ticker`, `Representative`, `Transaction` (Purchase/Sale), `Amount`, `Date`, `Party`

**Mapping:**
- Each trade = one Post. Text = synthetic: "Representative X (Party) {bought/sold} ${Amount} of {Ticker} on {Date}"
- `source_class = institutional_flow`, `tier = B`
- `entity_ids = [ticker]` — resolves to our canonical ticker entity

**Why institutional_flow not a separate class:** Congressional trades are a proxy for institutional/insider knowledge. Same class as EDGAR. Divergence math benefits from more data in the same class.

**ALSO write to `institutional_positions` table** for the 8% signal component:
```sql
INSERT INTO institutional_positions (filing_id, filer, entity_id, shares, filed_at, kind)
VALUES (...)
```
Use `kind = 'Congress'` (add to the CHECK constraint in a schema update).

**Rate limit:** Hobbyist plan — check docs, but 60 calls/min is typical.

**Env var:** `QUIVER_API_KEY`
**New file:** `src/alphahound/modules/stocks/adapters/quiver.py`
**CLI:** `alphahound ingest --source quiver`

---

### 5. Claude Tier 2 Narrative

**Trigger:** After `divergence-scan` writes a new `divergence_events` row, check if it has a narrative. If not, call Claude.

**What to send Claude (the prompt):**
```
You are a financial analyst assistant. Summarize in exactly 2 sentences what is 
happening with {TICKER} based on the following data:

Divergence alert:
- Retail social sentiment: {retail_polarity} ({retail_post_count} posts)
- News wire sentiment: {news_polarity} ({news_post_count} articles)
- D-value: {d_value} (statistical significance: p={p_value})

Recent headlines (last 24h):
{top_5_headlines}

Price context:
- Current price: ${price}
- 5-day change: {change_5d_pct}%
- vs SPY: {change_vs_spy}%

Keep it factual, specific, and under 50 words total.
```

**Where to store:** `divergence_events.components` JSONB field already exists.
Add `"narrative": "..."` key to the existing components dict.

**Model:** `claude-sonnet-4-20250514`
**Max tokens:** 100 (narratives are short)
**Cost:** ~$0.003 per narrative at current pricing. At 9 alerts/day = ~$0.03/day = ~$1/mo. Negligible.

**New file:** `src/alphahound/engine/signals/narrative.py`
**CLI:** Called automatically from `divergence-scan` when new alert fires. No separate command needed.

---

### 6. Schema Changes (Sprint 5)

One new file: `architecture/schema_9_sprint5.sql`

Contents:
1. `price_snapshots` table + hypertable (defined above)
2. Update `institutional_positions` CHECK constraint to add `'Congress'` to allowed `kind` values
3. Seed new adapters: `stocks.massive`, `stocks.finnhub`, `stocks.alpha_vantage`, `stocks.quiver`
4. Seed new source_adapter: `analyst_curated` class appears for first time

---

### 7. Updated CLI Output Format

After Sprint 5, `alphahound db divergence-events` should show:

```
time                   ticker    D      p      price   5d%    narrative
─────────────────────────────────────────────────────────────────────────────────────
2026-04-29 14:45:00   BE        3.98   0.000  $4.82  -8.3%   Retail holding while analysts
                                                              downgrade hydrogen demand outlook.
2026-04-29 14:45:00   SNDK      3.50   0.000  $18.40 -5.1%   Storage sector selloff; retail
                                                              underestimating supply glut impact.
```

And `alphahound signals divergence --ticker BE` should show full detail:
- Price block (current, 5d change, vs SPY)
- Component breakdown (retail, news, analyst if available)
- Narrative
- Recent headlines (top 3)

---

### 8. Grafana Dashboard Update

Add to the existing `alphahound_main.json` dashboard:

**New panel: Price Context table**
```sql
SELECT e.canonical_symbol, ps.price, ps.change_1d_pct, ps.change_5d_pct, ps.change_vs_spy
FROM price_snapshots ps
JOIN entities e ON e.entity_id = ps.entity_id
WHERE ps.time = (SELECT MAX(time) FROM price_snapshots WHERE entity_id = ps.entity_id)
  AND e.kind = 'ticker'
ORDER BY ABS(ps.change_5d_pct) DESC
LIMIT 20;
```

**Update: Recent Divergence Alerts table** — add price and narrative columns.

---

### 9. Wrapper Script Update

Add to `scripts/ingest_all.ps1` after divergence-scan:

```powershell
# Sprint 5: pull price context for all active tickers
$priceOutput = & alphahound ingest --source massive 2>&1
$priceExit = $LASTEXITCODE
foreach ($line in $priceOutput) { Write-Log $line.ToString() }
```

Also add finnhub, alpha_vantage, quiver to the ingest-all sequence.
The `ingest-all` command reads from `source_adapters` table automatically —
just seeding the new adapters in the DB is enough.

---

## Build Order (Strict)

Build in this order. Each file must work before moving to the next.

1. `architecture/schema_9_sprint5.sql` — apply in DBeaver first
2. `src/alphahound/modules/stocks/adapters/massive.py` — price snapshots
3. `src/alphahound/modules/stocks/adapters/finnhub.py` — social + news
4. `src/alphahound/modules/stocks/adapters/alpha_vantage.py` — news + transcripts
5. `src/alphahound/modules/stocks/adapters/quiver.py` — congressional trades
6. `src/alphahound/engine/signals/narrative.py` — Claude Tier 2
7. `src/alphahound/cli.py` — update divergence-events display + signals divergence
8. `grafana/dashboards/alphahound_main.json` — add price panels
9. `scripts/ingest_all.ps1` — no change needed (ingest-all is automatic)

---

## Definition of Done

- [ ] `alphahound db divergence-events` shows price + narrative columns
- [ ] `alphahound signals divergence --ticker BE` shows full detail with price + narrative
- [ ] `SELECT COUNT(*) FROM price_snapshots` returns > 0
- [ ] `analyst_curated` source class has rows in `raw_posts`
- [ ] Congressional trades appear in `raw_posts` with source_class = institutional_flow
- [ ] Grafana dashboard shows price context panel
- [ ] All 4 new adapters visible in `SELECT * FROM source_adapters`
- [ ] `pytest -q` passes
