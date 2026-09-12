# AH2 — First Adapter Selection (STEP 7A)

**Step:** STEP 7A — Select First AH1 Data Source for AH2 Migration (selection/analysis only — no code, no infrastructure)
**Status:** COMPLETE — recommendation made, stopped for Program Manager review
**Date:** 2026-09-12

This document is the result of inspecting AH1's actual adapter code (not working from memory or docs summaries) to identify the best first data source to migrate into the AH2 Functions + Service Bus + PostgreSQL pipeline. **No adapter code was written. No Azure resources, PostgreSQL changes, or subscription reactivations were made.**

---

## 1. Method

Read directly, in full:
- `src/alphahound/engine/adapters/base.py` and `models.py` — the `BaseAdapter`/`Post` contract every adapter implements
- `src/alphahound/engine/storage.py` — how `Post`s actually get written (dedup mechanism, entity resolution)
- Every adapter module under `src/alphahound/modules/stocks/adapters/`: `yahoo_finance.py`, `apewisdom.py`, `finnhub.py`, `kalshi.py`, `unusual_whales.py`, `massive.py`, `massive_history.py`, `substack.py`
- `src/alphahound/engine/signals/earnings_calendar.py`
- `scripts/ingest_all.ps1` and `scripts/register_scheduled_task.ps1` — actual current cadence (confirms the 15-minute Task Scheduler trigger this whole exercise is meant to eventually replace with an Azure Functions timer)

## 2. Candidates excluded up front

- **`quiver`** — subscription cancelled (per `AH2_DEV_ENVIRONMENT.md`/`ways-of-working.md` history). Directly excluded by the "usable without reactivating a paid subscription" requirement.
- **`edgar`, `stocktwits`, `alpha_vantage`** — all three are currently disabled in AH1 (`OFF` in the adapter status list) for unrelated reasons (CIK noise, 403 Cloudflare, redundant with Massive). Since STEP 7A asks to evaluate sources "already represented in AH1" and these aren't currently active/usable, they're out of scope for a *first* migration regardless of subscription status.

Everything else currently `ON` (`apewisdom`, `finnhub`, `unusual_whales`, `massive`, `massive_history`, `substack`, `yahoo_finance`, `kalshi`, `earnings_calendar`) is a legitimate candidate. Of these, three stood out as the strongest fits and are compared in full below; the rest are addressed briefly in §4.

## 3. Full comparison — three strongest candidates

### 3.1 `yahoo_finance` (news headlines)

| | |
|---|---|
| Existing AH1 module/path | `src/alphahound/modules/stocks/adapters/yahoo_finance.py` |
| Authentication requirements | **None.** Public RSS feed, only a `User-Agent` header is sent. |
| Current subscription/API dependency | None — free, public feed. |
| Rate limits (from implementation) | None documented by Yahoo; AH1 self-imposes 0.5s sleep between the ~20 watchlist tickers (~20 req/run, "zero risk of hitting limits" per the code's own comment). |
| Data returned | RSS `<item>` elements per ticker: headline title, description, `guid`, `pubDate`. One `Post` per headline. |
| Current AH1 DB destination | `raw_posts` (via `storage.write_posts`), `source_class='news_wire'`, `tier='C'`. |
| Dependencies | `httpx`, stdlib `xml.etree.ElementTree` — no extra pip packages beyond what's already in every adapter. |
| Migration complexity | **Low.** Single HTTP GET + XML parse per ticker, no pagination, no auth setup, no secret to provision in Azure. |
| Reliability concerns | Yahoo could change or retire the RSS format without notice (it's an unofficial/legacy feed); 404s per-ticker are already handled gracefully in the existing code. |
| Expected Azure Function cadence | Timer, ~15 min (matches AH1's current `ingest_all.ps1` cadence). |
| Expected AH2 normalized record type | `raw_source_events` (one per RSS item) → `evidence` (`evidence_type='news_headline'`). |
| Why it is/isn't a good first migration | **Strong candidate.** Zero secrets to manage means the very first AH2 Function doesn't also need to solve Key Vault/managed-identity secret access as a prerequisite — it can focus purely on ingestion → normalization → provenance → idempotency, which is exactly what STEP 7A is asking to prove out. Idempotency is already clean (`guid`-based `external_id`). Lowest operational complexity of everything evaluated. |

### 3.2 `apewisdom` (Reddit mention-volume aggregator)

| | |
|---|---|
| Existing AH1 module/path | `src/alphahound/modules/stocks/adapters/apewisdom.py` |
| Authentication requirements | **None.** Public API, no key. |
| Current subscription/API dependency | None — free tier, attribution required per ToS. |
| Rate limits (from implementation) | Not documented by ApeWisdom in the code's comments; AH1 pages through up to 5 pages per run with no explicit sleep between pages (only between adapters at the orchestration level). |
| Data returned | Ranked snapshot rows: ticker, mention count, mentions 24h ago, rank, rank 24h ago, upvotes. Not individual posts — a live aggregate snapshot only (no historical query). |
| Current AH1 DB destination | `raw_posts`, `source_class='retail_social'`, `tier='C'` — each row becomes one synthetic `Post` with a deterministic summary string as `text`. |
| Dependencies | `httpx` only. |
| Migration complexity | **Low-moderate.** Adds real pagination handling (up to 5 pages) — a genuinely useful pattern to prove out, but one more moving part than `yahoo_finance`. |
| Reliability concerns | ApeWisdom is a smaller, less institutionally-backed service than Yahoo or Finnhub — no evidence of instability in the code, but less of a track record. Snapshot-only (no historical replay from the source itself). |
| Expected Azure Function cadence | Timer, ~15 min. |
| Expected AH2 normalized record type | `raw_source_events` (one per hourly ticker snapshot) → `evidence` (`evidence_type='retail_mention_volume'`). |
| Why it is/isn't a good first migration | **Solid second choice.** No auth, and its hour-bucketed snapshot idempotency key (`{filter}:{ticker}:{YYYYMMDDTHH}`) is a genuinely different, useful pattern to demonstrate versus `yahoo_finance`'s natural-GUID approach — worth doing as an early *second* migration specifically to prove out that alternate idempotency shape, but the pagination adds just enough extra surface area that it's not the simplest possible starting point. |

### 3.3 `finnhub` (news, currently) — social sentiment path present but unused

| | |
|---|---|
| Existing AH1 module/path | `src/alphahound/modules/stocks/adapters/finnhub.py` |
| Authentication requirements | API key via `Authorization`-style query param (`token=`), read from `FINNHUB_API_KEY` env var. Raises at construction time if unset. |
| Current subscription/API dependency | Free tier of a real commercial API (Finnhub). Currently active/usable (not cancelled). |
| Rate limits (from implementation) | **60 calls/minute** (free tier), explicitly documented in the module docstring; AH1 self-imposes a 1.1s sleep between calls. At ~66 watchlist tickers × 1 endpoint (news only) per run, this comfortably fits. |
| Data returned | Two endpoints exist in the code: `/stock/social-sentiment` (Reddit/Twitter mention counts + scores) and `/company-news` (articles: headline, summary, source, URL, timestamp). **Only `/company-news` is actually called** — `pull()`'s own comment says social sentiment "is 403 on free tier, skip entirely"; `_pull_social_sentiment` exists in the file but is dead code today. |
| Current AH1 DB destination | `raw_posts`, `source_class='news_wire'` for news posts (the social-sentiment path, if ever re-enabled, would write `source_class='retail_social'`). |
| Dependencies | `httpx` only. |
| Migration complexity | **Moderate.** Real API key needs a real secret-management story in AH2 (Key Vault reference / managed identity, per `CLAUDE.md` rule 10) — meaningfully more setup than the two zero-auth candidates above. |
| Reliability concerns | The existing code already shows one third-party behavior change causing a silent scope reduction (social sentiment quietly dropped to news-only when it started 403ing) — a real signal that this free tier's available surface can shift without much warning. Migrating "faithfully" also means deciding whether to carry over the dead `_pull_social_sentiment` code or clean it up. |
| Expected Azure Function cadence | Timer, ~15 min. |
| Expected AH2 normalized record type | `raw_source_events` (one per article) → `evidence` (`evidence_type='news_article'`). |
| Why it is/isn't a good first migration | **Good, but not first.** It's the right adapter to migrate *once* AH2 has a proven secrets pattern (Key Vault reference for a Function App setting) — genuinely worth doing soon after the first migration — but bringing in secret management *and* a live commercial API's quirks in the very first exercise adds two variables at once where STEP 7A's own preference list ("low operational/API complexity for the first migration") argues for isolating them. |

## 4. Other `ON` adapters — briefly, why not chosen for *first*

- **`kalshi`** — no auth, genuinely interesting (`prediction_market` source class, would eventually map toward `market_states`/`outcomes` rather than `raw_source_events`/`evidence`) — but it bypasses AH1's own `Post`/`raw_posts` normalization entirely, writing straight to a bespoke `kalshi_contracts` table via a static ticker→series mapping table and multi-category search/matching logic. More moving parts, and it exercises a *different* part of the AH2 schema (STEP 6A's `signals`/`market_states`) than the `raw_source_events → evidence` pipeline STEP 7A's own listed goals ("exercise normalization/provenance") point toward for a first pass.
- **`massive` / `massive_history`** — real paid API ($29/mo, currently active), also bypasses `Post`/`raw_posts` (writes directly to `price_snapshots`/`price_daily`). `massive_history` in particular runs once daily, not on the recurring 15-minute cadence STEP 7A asks the first migration to demonstrate.
- **`substack`** — no auth, but reads its feed list from a live AH1 config table (`substack_feeds`) and *writes back* to it (auto-disabling feeds on repeated 403/404), which is a stateful side effect beyond simple ingestion — either that table needs migrating too, or the first AH2 version needs a hardcoded feed list, either of which is more first-migration scope than needed. Ticker-extraction logic (three overlapping heuristics + a false-positive word list) is also the most complex normalization logic of anything reviewed.
- **`earnings_calendar`** — reuses the Finnhub key, writes to a dedicated `earnings_calendar` table (not `raw_posts`), and isn't part of the 15-minute cadence in `ingest_all.ps1` — it's a lower-volume, calendar-style dataset rather than a recurring stream, less representative of "a realistic recurring ingestion workload" than the others.

## 5. Recommendation

**Migrate `yahoo_finance` first.**

It is the only candidate requiring **zero secrets** (no API key, no Key Vault reference, no managed-identity-to-third-party-auth story needed for v1), which means the first AH2 Function can focus entirely on what STEP 7A is actually testing — ingestion → `raw_source_events` → `evidence` normalization, idempotent dedup, and correlation-ID/provenance tracing through the pipeline STEP 6/6A already built — without also having to solve secret management as a prerequisite. Its existing AH1 implementation is small, self-contained, already idempotent (GUID-based `external_id`), already produces genuine `Post` objects (the exact shape AH2's `raw_source_events`/`evidence` tables were designed around), and runs on the same 15-minute recurring cadence the AH2 Functions timer is meant to eventually replace. Its only real risk — Yahoo could change the RSS format unannounced — is a well-understood, long-tail risk shared by essentially any free/public feed, and the existing code already degrades gracefully (per-ticker 404 handling) rather than failing the whole run.

`apewisdom` (pagination pattern) and `finnhub` (secret-management pattern) are both strong candidates for the *second* and *third* migrations respectively, each deliberately proving out one additional pattern AH2 will need soon — but starting with the adapter that isolates ingestion/normalization/idempotency from auth/secrets/pagination concerns gives the cleanest first proof point.

---

**STEP 7A is complete: three candidates fully compared, one recommended (`yahoo_finance`), with rationale. No adapter code was written, no Azure resources were created, PostgreSQL was not touched, no subscriptions were reactivated, and AH1 was not modified. Stopping here for Program Manager review — the actual STEP 7 migration is not authorized until Kamil explicitly approves it.**
