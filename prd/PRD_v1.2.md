# AlphaHound — Product Requirements Document (v1.2)
## Multi-Industry Sentiment Intelligence Platform

**Author:** Kamil Asfour
**Date:** April 18, 2026
**Status:** DRAFT v1.2 — structural split, formalized math, missing sections added
**Supersedes:** `prd\PRD_v1.1.md` (April 16, 2026)
**Posture:** Challenge-priorities redline. Weights, priorities, and proof scope were re-examined, not only tidied.

---

## Document Structure

This PRD is split into two parts because AlphaHound is two products in one repo:

- **Part A — Engine PRD (industry-agnostic).** The core sentiment intelligence engine. Owns the scoring math, source-tier system, two-tier AI pipeline, industry configuration schema, data governance, SLOs, risk register, and legal framework. Stable contract that every industry module targets.
- **Part B — Stock Module PRD (first industry module).** The stock-specific instantiation of the engine. Owns data-source picks, scoring-weight defaults, the dual proof strategy ($5K→$1M + $1K→$50K), prediction-markets integration, dashboard UX, backtest methodology, and Phase 0 operating rules.

Changes that touch the *engine* go in Part A. Changes that only touch stocks go in Part B. When the two disagree, the engine wins.

Appendices hold the full industry-config YAML schema, a changelog, research citation placeholders, and open questions.

---

---

# PART A — ENGINE PRD (INDUSTRY-AGNOSTIC)

## A1. Executive Summary

AlphaHound is a real-time, industry-agnostic sentiment intelligence engine. It ingests social, news, institutional, alternative, and prediction-market data streams, scores them through a two-tier AI pipeline (FinBERT for speed, Claude for reasoning), detects cross-source divergence and cascade patterns, and matches current events to structurally similar historical analogs (the "Rhyme Engine").

The engine is industry-agnostic by design: the scoring math, pipeline, and storage are fixed, while data sources, entity taxonomy, keyword dictionaries, and scoring weights are declared per industry in an Industry Configuration file. A new industry module is a config + a set of source adapters, not a new codebase.

The first industry module is stocks (Part B). Later modules — real estate, auto, F&B, pharma, retail, politics, crypto — slot into the same engine.

## A2. Problem Statement & Thesis

### A2.1 The problem the engine solves

Sentiment-driven markets exist in many industries, but every existing sentiment tool is vertical-specific. LunarCrush is stocks and crypto. Brandwatch and Sprout Social are consumer brands. Zillow has no real sentiment product at all. No one ships a general-purpose engine where the same pipeline that scores $TSLA today scores "Austin housing" tomorrow and "Ozempic" the day after.

The missed opportunity is that the *hard part* — ingestion hardening, model serving, cross-source arithmetic, historical pattern matching, entity resolution — is the same across industries. Only the surface (sources, entities, weights) changes. Building N vertical products instead of one engine is wasteful.

### A2.2 The thesis

One engine, N industry modules. Prove the engine with stocks (Part B), then ship industry #2 in weeks, not quarters, because the core is frozen and the module is config.

### A2.3 What the engine is NOT

- Not an investment adviser (see A14).
- Not a managed portfolio.
- Not a toolkit you install and configure yourself — industry modules are first-party for now.
- Not a bulk social-data reseller (that's LunarCrush / ICE).

## A3. Engine Consumers (Personas)

The engine itself has two consumer classes; end-user personas live in each industry module (Part B3 for stocks).

### A3.1 Module Builders (internal)
First-party developers (starting with Kamil) who author new industry modules. They write config, pick data sources, and tune weights. They do not modify engine code.

### A3.2 API Consumers (external)
Developers and traders who call the engine through a per-module REST + WebSocket API. They see industry-shaped responses, not raw engine internals.

## A4. Engine Architecture Overview

```
[Per-Industry Adapters]           [Engine Core]                 [Per-Industry Outputs]
                        ingestion →                     → REST / WebSocket / dashboards
 stock adapters  ┐                 ┌ Source Classifier ┐
 re adapters     ├─→ raw posts ─→ ┤ Tier 1: FinBERT  ├→ scored events ──→ stock API
 auto adapters   ┤                 │ Tier 2: Claude    │                   re API
 (future) ...    ┘                 │ Divergence        │                   auto API
                                   │ Cascade           │
                                   │ Rhyme Engine      │
                                   └───────────────────┘
                                            │
                                   [Postgres + TimescaleDB]
                                            │
                                    [Industry Config]
                                (schema defined in A5)
```

The engine owns: ingestion framework, model serving, scoring math, divergence/cascade/rhyme computation, storage, API gateway, observability, and secrets.

Each industry module owns: source adapters, entity dictionaries, scoring weight overrides, historical pattern library, output formatting, and a list of API routes exposed.

## A5. Industry Configuration Schema (Core Product Contract)

This is the spine of the multi-industry thesis. An industry module is a single YAML file (plus a folder of adapter code) that conforms to this schema. The engine boots a module by reading its config and wiring adapters accordingly.

See **Appendix B** for the full stock example and stubs for real estate and auto.

### A5.1 Required top-level keys

| Key | Type | Purpose |
|---|---|---|
| `module_id` | string | Globally unique (`stocks`, `real_estate_us`, `auto_us`) |
| `version` | semver | Module version; engine pins to a range |
| `entities` | object | Entity types, aliasing rules, canonical ID source |
| `data_sources` | list | Each source: adapter class, credentials ref, rate limits, cost tier |
| `source_tiers` | object | A/B/C/D weight multipliers + membership rules |
| `scoring_weights` | object | 9 component weights (sum = 1.0); see A7.4 |
| `keyword_dictionaries` | object | Slang, sarcasm-density tags, stop-words per source |
| `historical_pattern_library` | list | Seed events for the Rhyme Engine |
| `output_actions` | object | Which API routes this module exposes |
| `legal_disclaimer` | string | Substituted into every API response |
| `kill_switches` | object | Module-level pause rules (accuracy floor, pipeline uptime) |

### A5.2 Contract rules

- The engine **never** hardcodes industry names or entity types. Every reference is keyed by `module_id`.
- A module can declare fewer than all 9 scoring components by setting a weight to 0, but the remaining weights MUST sum to 1.0. The engine rejects configs that don't normalize.
- Adapter classes must implement a single `pull(window, cursor) → List[Post]` interface. No adapter talks to the scoring engine directly.
- Entities must resolve to a canonical ID that persists across renames (e.g., a ticker after a symbol change, a neighborhood after a boundary redraw). Entity resolution is a first-class engine service (A9.3).

### A5.3 Versioning

Module configs are versioned with semver. The engine declares which module-config version ranges it supports. Breaking changes to the schema bump the engine's major version. This lets multiple modules upgrade independently.

## A6. Two-Tier AI Pipeline

### A6.1 Tier 1 — FinBERT (bulk scoring)

- Model: `ProsusAI/finbert`, self-hosted on Azure `Standard_NC4as_T4_v3` (T4 GPU).
- Throughput: ~500 posts/sec on T4; 100K posts in ~200 sec.
- Cost: ~$13/day VM.
- Output: `(entity_id, polarity ∈ [-1,1], confidence ∈ [0,1])` per post.
- Fine-tuning plan: per-industry head (stocks fine-tuned on labeled WSB/StockTwits; real estate on labeled Zillow/Redfin reviews; etc.). Engine provides the training harness; modules provide labeled data.
- Fallback: if GPU is unavailable, Tier 1 runs on `Standard_D8s_v3` CPU at ~20 posts/sec in batch mode (acceptable for non-real-time).

Engine rejects Tier 1 claims ≥85% F1 as a default — every module must carry its own measured F1 in `scoring_weights.metadata.tier1_f1` with a link to the evaluation notebook. See A17.4 citation rules.

### A6.2 Tier 2 — Claude API (reasoning)

- Called on an escalated subset of posts.
- Input: post text + 5-post context window + relevant entity's recent price/metric + 7-day sentiment baseline + any prediction-market signal pointed at the same entity.
- Output: `(narrative, divergence_flag, rhyme_trigger, confidence_adjustment)`.
- Prompting: System-1 / fast-intuitive classification, **not** Chain-of-Thought. CoT has been shown to degrade financial sentiment accuracy in several papers — cite in Appendix C before shipping.
- Cost target: <$10/day per industry module at 500–3,000 calls/day.

### A6.3 Escalation triggers

All triggers are configurable per module. Engine-default thresholds for stocks (overridable):

| Trigger | Default | Tuning note |
|---|---|---|
| Tier 1 confidence < τ_lowconf | τ=0.60 | Raise if Tier 2 budget is strained |
| Velocity spike > κ_σ over 7d baseline | κ=2.0 | Industry-dependent; meme stocks need higher |
| Source-class disagreement > δ | δ=0.4 (see A7.1) | The divergence metric itself |
| Prediction-market probability shift > μ (30m window) | μ=0.05 | Stocks only; real-estate module has no PM |
| New Tier-A source post on priority entity | always | Curated high-signal sources |
| Novel entity (not in last 30d) | always | Discovery path |

**Magic-number policy:** each threshold must ship with a sensitivity table (Part B9.3 shows the template). Initial values are placeholders until backtest tunes them.

## A7. Differentiator Math (Formalized)

The three headline differentiators in v1.1 were described as narratives. v1.2 commits them to math so they can be tested, tuned, and falsified.

### A7.1 Cross-Source Divergence Metric

**Intent:** detect when different classes of participants disagree about the same entity.

**Source classes** (per module; defaults shown for stocks):
- `retail_social` — Reddit, StockTwits, X retail
- `institutional_flow` — 13F, 13D, insider Form 4
- `options` — Unusual Whales / options flow
- `prediction_market` — Kalshi, Polymarket
- `analyst_curated` — Substack, YouTube, podcasts (Tier A/B only)
- `news_wire` — Benzinga, BusinessWire, wire services

For an entity `e` at time `t`, let `ŝ_c(e, t) ∈ [-1, 1]` be the class-level sentiment, computed as the tier-weighted mean of that class's FinBERT polarities in a rolling 24h window.

**Divergence score:**

```
D(e, t) = σ({ŝ_c(e, t)}_c) / μ_historical(σ)
```

where `σ` is the std-dev across source classes and `μ_historical(σ)` is the 90-day rolling mean of that std-dev for entity `e`. `D > 2.0` means "disagreement is in the top 2.5% of recent history." This is the divergence alert threshold and Tier-2 escalation trigger (δ in A6.3 maps to a D threshold per module).

**Null-distribution gate:** before a divergence fires an alert, the engine computes `D` under a permutation test (shuffle source labels within the 24h window, 1000 samples). If the observed `D` is not p<0.01 against the permuted distribution, the alert is suppressed as noise.

**Why not just a z-score of one variable:** a univariate z-score can't distinguish "everyone moved together" from "two camps fought." Std-dev across camps plus a permutation null captures the latter.

### A7.2 Global Cascade Scoring (stocks-specific, moved to Part B)

Cascade is a stock-market phenomenon (Asian → European → US sessions). It belongs to the Stock Module and is specified in Part B5.3. The engine exposes a "session flow" primitive that any industry module can use if it has session structure (e.g., politics modules might model polling-day cascades).

### A7.3 Rhyme Engine (DTW with Significance)

**Representation.** An event `E` is a multivariate time series in normalized space. Variables (defaults for stocks):

- Price path (% change from event day 0)
- Log-volume ratio vs 30-day baseline
- Realized volatility (rolling 10-day)
- Social volume (log, z-scored)
- Sentiment polarity (tier-weighted mean)

The engine normalizes each variable per event (subtract day-0 value, divide by event-specific scale). Events are compared on a 14–30-day window (configurable).

**Similarity.** DTW via `dtaidistance` with Sakoe-Chiba band width = 0.15 × series length. Per-variable DTW distances are computed and combined via weighted sum; weights are set per module (stocks default: price 0.4, social volume 0.2, sentiment 0.2, volatility 0.1, log-volume 0.1).

**Significance.** For every candidate match, the engine runs a null test: compute DTW distance against 500 randomly drawn window-matched segments of non-event periods. Only matches with p < 0.01 against the null are surfaced. This prevents 20-event spurious-match hell.

**Corpus management.** The seed corpus is 20–50 curated events per module. Module config declares which historical datasets back it (stocks: FNSPID, IMF banking-crisis DB, Reinhart/Rogoff). The engine refuses to run the Rhyme Engine on a module until the corpus has ≥15 events with labeled type + phase boundaries. This is a hard gate, not a soft warning.

**Phase position.** Each corpus event carries `phase_boundaries = [(label, day), ...]` e.g. `[("shock", 0), ("adaptation", 14), ("normalization", 60)]`. A match returns the phase position by projecting the current event onto the matched event's phase schedule.

**Output shape.** See Appendix B for the Rhyme Engine output JSON.

### A7.4 Scoring Weight Normalization (Deterministic)

v1.1 declared static weights and hand-waved a "dynamic adjustment" for volatility regimes. v1.2 makes the adjustment a deterministic function.

**Module declares base weights `w_i^base`** in config, with `Σ w_i^base = 1`.

**Regime multiplier table** (also in config). For each named regime (e.g., `high_vol`, `low_vol`, `earnings_week`), the module declares a multiplier vector `m_i^regime` with no normalization constraint.

**Active weights** at time `t` in regime `R(t)`:

```
ŵ_i(t) = (w_i^base * m_i^R(t)) / Σ_j (w_j^base * m_j^R(t))
```

This guarantees `Σ ŵ_i(t) = 1` at every tick. The regime itself is determined by engine-computed features (e.g., VIX quartile, earnings-calendar proximity, macro-event proximity) declared in the module config's `regime_classifier` block.

Worked example in Appendix B.

## A8. Source Tier System (Criteria-Based)

v1.1 labeled sources A/B/C/D subjectively. v1.2 makes the labels criteria-derived.

### A8.1 Tier definitions

| Tier | Multiplier | Criteria (ALL must hold) |
|---|---|---|
| A | 2.0× | 3+ year public track record; ≥1 independently-validated call that moved the market >5%; editorial process (not anonymous); institutional citation (Bloomberg, FT, SEC filing reference) |
| B | 1.5× | 1+ year track record; reputable imprint or independent newsletter with >10K paying subs; disclosed methodology |
| C | 1.0× | Retail-facing analyst or community with documented signal history; no obvious bot signature |
| D | 0.5× | Everything else — generic retail social posts, anonymous accounts |

### A8.2 Promotion / Demotion

- Promotion requires written evidence in the module's `source_tier_audit.md` log (new tier, reason, date, promoter initials).
- Quarterly automated demotion: any Tier A/B source whose signal-attributed trades (tracked via the proof account log) have <50% directional hit rate over a rolling 90-day window is auto-demoted one tier. Engine surfaces the demotion for human review before applying.
- Modules can override criteria but must document the override.

### A8.3 Bot signature detection (engine primitive)

The engine ships a bot-signature detector used by all modules. Features:
- Account age < 30 days
- Posting rate > 3σ above class median
- Duplicate-content hash rate > 20% across accounts in the same 24h window
- Known-bot-pattern regex (maintained by engine team)

Bot-flagged posts are still ingested but their tier multiplier is forced to 0.0 (drop from scoring) and they are tagged for manipulation-detection analytics (B7 P0 feature).

## A9. Data Governance

### A9.1 Retention
- Raw posts: 90 days in hot storage, then archive to Azure Blob cold tier for 2 years, then delete.
- Scored events: indefinite in Timescale hypertables; Timescale compression kicks in at 30 days.
- Trade logs: indefinite; these are the proof-case artifact.

### A9.2 PII
- Usernames are hashed on ingest (SHA-256 + per-module salt). Only the hash is stored.
- User-supplied text is scanned for PII patterns (phone, SSN, email, address) and redacted before storage. The engine ships a redaction library; modules invoke it in adapters.
- No linking hashes across modules.

### A9.3 Entity resolution
- Every entity has a canonical ID assigned at first observation.
- Aliases (ticker changes, company rebrands, neighborhood boundary redraws) are recorded in an `entity_aliases` table with `(alias, canonical_id, valid_from, valid_to)`.
- Historical queries resolve aliases via the validity window, not point-in-time.

### A9.4 Source Terms of Service compliance
- Each adapter declares its ToS basis in module config (`data_sources[].tos_basis`).
- Adapters for scraped sources (Substack free posts, YouTube transcripts) must include the specific ToS clause citation. Engine refuses to load adapters without `tos_basis` filled in.
- Paid content scraping: prohibited at the engine level. This is not a module choice.

## A10. System Architecture

### A10.1 Components

- **Ingestion workers** — Python async. One process per adapter, supervised by a systemd/Celery pool. Back-pressure via Redis queue.
- **Message queue** — Redis (hot path) + Azure Service Bus (durable, cross-zone).
- **Tier 1 inference** — single T4 GPU VM; horizontal scale when throughput exceeds 60% sustained.
- **Tier 2 orchestrator** — FastAPI service handling escalation calls to Claude, caching, retry.
- **Storage** — PostgreSQL 16 + TimescaleDB 2.x. Hypertables for event-shaped data (sentiment scores, prices, trades). Standard tables for metadata (entities, modules, auth).
- **API gateway** — FastAPI + Uvicorn behind Nginx. Per-module routers.
- **Observability stack** — Prometheus + Grafana (metrics), Loki (logs), OpenTelemetry traces. See A11.
- **Secrets** — Azure Key Vault; rotated quarterly.

### A10.2 Storage schema (authoritative)

Full DDL is in `architecture\database_schema.sql` (to be written next session). Minimum tables:

```sql
-- engine-level
modules(module_id PK, version, config_hash, enabled_at)
entities(entity_id PK, module_id FK, canonical_symbol, kind, created_at)
entity_aliases(alias_id PK, entity_id FK, alias, valid_from, valid_to)
source_adapters(adapter_id PK, module_id FK, class, tier, tos_basis, enabled)

-- hypertables (time-partitioned by Timescale)
raw_posts(time, post_id, adapter_id, entity_id, author_hash, text_hash, tier)
sentiment_scores(time, entity_id, source_class, polarity, confidence, tier)
signal_scores(time, entity_id, signal_1to10, confidence_1to10, weights_snapshot)
divergence_events(time, entity_id, D_value, p_value, components)
rhyme_matches(time, entity_id, current_event_id, corpus_event_id, dtw, p_value)
trade_log(time, module_id, signal_id, entity_id, side, size, pnl, venue)
prediction_market_prices(time, market_id, venue, probability, tickers_linked[])

-- module-supplied (stock module)
options_flow(time, entity_id, strike, expiry, side, premium, sweep_flag)
institutional_positions(filing_id PK, filer, entity_id, shares, filed_at, 13d_or_13f)
historical_events(event_id PK, module_id, kind, phases JSONB)
```

Indexing strategy: composite `(entity_id, time DESC)` on every hypertable. Partitioning interval: 7 days on `raw_posts`, 30 days elsewhere.

### A10.3 Failover

- Primary stack in Azure `eastus`. Warm standby in `eastus2` (replicated DB, dormant VMs).
- Ingestion adapters have a 5-minute SLA before failover triggers. Tier 1 GPU has a CPU fallback (A6.1).
- Tier 2 has a static-response cache for the last N escalations — if Claude is unavailable, the engine returns the cached narrative with a stale flag rather than dropping the event.
- Single-VM `repsportalvm` is dev/staging only; production uses the above two-region deployment once revenue covers it. Until then: accept the SPOF risk, document it in the risk register.

## A11. SLOs, SLIs, Observability

### A11.1 SLOs (first year)

| Dimension | SLO | Measurement |
|---|---|---|
| Ingest-to-scored-event latency (P50) | ≤ 90 seconds | trace span from adapter pull to signal_score row |
| Ingest-to-scored-event latency (P99) | ≤ 10 minutes | same |
| API availability | 99.0% monthly | uptime monitor on `/health` |
| API P95 response time | ≤ 500 ms | Prometheus histogram on FastAPI middleware |
| Tier 2 escalation rate | 3–8% of posts | running ratio |
| Tier 2 cost (per module) | ≤ $10/day | Claude usage API |
| Signal accuracy (stocks, directional) | ≥ 58% rolling 30d (Phase 0); ≥ 60% rolling 90d after Phase 0 | closed-position outcome vs signal direction |
| Divergence alert precision | ≥ 40% | % of alerts followed by >1σ price move within 48h |

SLOs are revisited quarterly. Breach of an SLO for two consecutive weeks triggers a post-mortem and — for accuracy SLOs — a kill-switch (Part B10).

### A11.2 Core SLIs
- `post_ingest_lag_seconds` (per adapter)
- `scoring_queue_depth` (Redis)
- `tier1_gpu_utilization`
- `tier2_call_latency_seconds`
- `tier2_cost_dollars_today` (counter)
- `divergence_alerts_24h` (counter per module)
- `signal_directional_hit_rate_30d` (gauge per module)
- `adapter_tos_violations` (counter; should be zero)

### A11.3 Alerting
- PagerDuty (or equivalent) integration. On-call rotation defined in Part B15.
- Alert only on SLO-burn budgets, not raw thresholds, to prevent alert fatigue.
- Signal-accuracy SLO alerts are daily email + dashboard, not page — these degrade slowly.

## A12. Security & Secrets

- All API credentials live in Azure Key Vault. No secrets in env files in the repo.
- Module configs declare a `credentials_ref` that resolves to a Key Vault entry at runtime.
- Per-environment Key Vaults (dev, staging, prod). Rotation quarterly, with an automated report of stale secrets.
- Every external call is logged with a correlation ID (no response bodies).
- API authentication: OAuth 2.1 with per-module scopes. Free-tier keys are rate-limited at the gateway.

## A13. Risk Register

| # | Risk | Likelihood | Impact | Mitigation | Owner | Review |
|---|---|---|---|---|---|---|
| R1 | Reddit/X API ToS or pricing change | High | High | Aggregator fallback (ApeWisdom, LunarCrush read-only); 30-day disable toggle per adapter | Kamil | Monthly |
| R2 | FinBERT model deprecated by upstream | Medium | Medium | Pin model version; maintain internal fine-tune; evaluate FinGPT / custom as alternates | Kamil | Quarterly |
| R3 | Claude API pricing/rate change | Medium | Medium | Abstract Tier 2 behind an LLM interface; prototype Llama-3-70B-FT fallback | Kamil | Quarterly |
| R4 | Polymarket US enforcement action | Medium | High (for PM track) | Kalshi-first posture; Polymarket gated behind geo-check; track CFTC rulings monthly | Kamil | Monthly |
| R5 | Proof-account drawdown | High | High (brand) | Kill-switch at 25% drawdown (Part B10.3); transparent trade log | Kamil | Weekly |
| R6 | Single-VM SPOF | High (today) | High (production) | Two-region deployment post-revenue; documented acceptance until then | Kamil | At each revenue milestone |
| R7 | Substack/YouTube scraping DMCA | Medium | Medium | RSS-only for Substack free content; YouTube transcripts via Data API terms; legal review at scale | Kamil | Before launch |
| R8 | Entity-resolution error (ticker change, merger) | Medium | Medium | Nightly alias validator against SEC feed; backfill job on mismatch | Kamil | Monthly |
| R9 | LLM hallucination in Tier 2 narratives | High | Medium | Narratives flagged as "model-generated"; never used as sole decision input; human spot-check weekly | Kamil | Weekly during Phase 0 |
| R10 | "AI washing" SEC scrutiny | Medium | High | Verified trade log as primary evidence; no accuracy claim without measured F1; citations required for every model claim (A17.4) | Kamil | Before each marketing push |
| R11 | Adversarial pumping / astroturfing detected by engine too late | High | High | Bot-signature detector (A8.3) + manipulation-detection feature (B7 P0) | Kamil | Monthly |
| R12 | Cost overrun on Tier 2 (Claude) | Medium | Medium | Hard daily cap in module config; escalation-rate circuit breaker; cached responses | Kamil | Weekly |

Risks are reviewed on the cadence in the Review column. New risks are added as identified — the register is living.

## A14. Legal Framework

### A14.1 Publisher's exemption

Under *Lowe v. SEC* (1985) and the 2024 federal court ruling protecting Seeking Alpha, publishers of bona fide financial analysis of general and regular circulation do not need to register as investment advisers.

- **Low risk:** selling sentiment scores, confidence indices, historical pattern matches, narrative summaries, prediction-market probabilities.
- **Moderate risk:** personalized alerts, aggregated short-seller positions.
- **High risk:** managed portfolios, copy-trading, automated Polymarket execution on behalf of customers.

### A14.2 Disclaimers (engine-injected)

Every API response for every module includes the module's `legal_disclaimer` string. For stocks, the default disclaimer is specified in Part B.

### A14.3 Proof-account safety (engine rules)

- Trade logs are published AFTER positions close, not before.
- Every publication carries: "The operator may hold positions in instruments mentioned."
- Engine never emits imperatives ("Buy X"); always probabilistic ("X signal score 8/10, confidence 7/10").

### A14.4 Prediction market gating (engine primitive)

The engine performs a geo-check before returning Polymarket data to a session. Kalshi is unrestricted for US users. Per-jurisdiction rules live in engine config; modules don't override them.

### A14.5 SEC 2026 "AI washing" posture

Every accuracy claim in engine/module documentation must link to a measured evaluation in `research\ai_models.md` with dataset, metric, and date. Marketing copy that predates measurement is prohibited. This is enforced by a CI linter on the PRD and the marketing site.

## A15. Business Model & Engine Economics

Module-level pricing is specified per module (Part B14). Engine-level economics:

- **Variable cost per API call:** dominated by Tier 2 escalation ($0.001–$0.01 per call depending on tokens). Gross margin on API tier must stay ≥70%.
- **Variable cost per module:** $600–$1,500/month infra + per-source fees (Part B14 for stocks).
- **Engine R&D amortization:** first 12 months, all engine improvements are charged against the stock module's revenue. Module 2 onward shares the engine cost.
- **Enterprise tier (engine licensing):** white-label deployments with customer-owned modules — pricing TBD, target ≥$50K/year.

## A16. Engine Development Timeline (Phase-linked)

| Phase | Engine milestone | Linked module gate |
|---|---|---|
| Architecture & schema | DB schema, adapter interface, module config parser | — |
| Pipeline MVP | Ingest → Tier 1 → Tier 2 → store round-trip, no differentiators | Stock module MVP data |
| Differentiator math | Divergence metric, Rhyme Engine with significance gate, weight normalization | Stock Phase 0 entry gate |
| Observability | SLO dashboards, alerting, cost caps | Stock Phase 0 entry gate |
| Hardening | Failover tested, secrets rotation, audit logs | Paid-tier launch gate |
| Second-module support | Real-estate adapter shell, entity resolution for non-ticker entities | Module 2 launch |

Concrete calendar in Part B12.

## A17. Open Questions & Research Gaps

### A17.1 Research files that are named but unwritten
- `research\competitive_landscape.md`
- `research\data_sources.md`
- `research\ai_models.md`
- `research\historical_patterns.md`
- `research\multi_industry_analysis.md`

Every citation below references one of these. Until they exist with actual URLs and dates, the corresponding claims in this PRD are placeholders.

### A17.2 Open math questions
- Divergence metric — should `D` use std-dev or median-absolute-deviation across source classes? (Heavy-tailed class distributions may prefer MAD.)
- Rhyme Engine — per-variable DTW weights are set by hand in v1.2. Should be learned from corpus via leave-one-out cross-validation.
- Regime classifier — what's the best regime discretization (quartile-based, HMM, rule-based)? Stocks-only question for Part B.

### A17.3 Open ops questions
- Single-operator on-call is not a plan. Either backup on-call exists or the kill-switch is aggressive enough that 3am incidents are non-issues.
- If Phase 0 stock accuracy fails the exit gate, does the project pivot (to a different module?), pause, or stop? Decision tree in Part B10.

### A17.4 Citation policy (engine-enforced)

Every numerical claim about external systems (FinBERT accuracy, dataset sizes, competitor pricing, regulatory thresholds) must cite `research\<file>.md#<anchor>`. CI linter (to be built) fails the build if a numbered claim lacks a citation. Placeholder `[CITATION NEEDED: ...]` is acceptable during drafting but blocks merge to main.

---

---

# PART B — STOCK MODULE PRD

## B1. Overview — Stock Module Thesis

AlphaHound's first industry module is stocks. The module instantiates the Engine (Part A) with stock-specific data sources, entities (tickers), scoring weights, and a historical pattern library anchored on financial crises and geopolitical shocks.

The module's commercial role is to generate two signal-attributed proof cases — a $5K→$1M equity track and a $1K→$50K prediction-market track — that serve as the credibility exhibit for the SaaS product built on top of the engine.

## B2. Problem Statement (Stock-Specific)

### B2.1 Retail sentiment tooling is bifurcated

Cheap-but-shallow (StockTwits bull/bear ratios, ApeWisdom mention counts) or expensive-but-institutional (RavenPack $50K+/yr, ICE Reddit Signals, ICE Polymarket distribution). No retail tool combines social, institutional, options, alternative analyst content, prediction markets, AND historical pattern matching at a retail-affordable price.

### B2.2 Confirmed gaps (need research citations)

`[CITATION NEEDED: All four AI research sources confirming no retail tool ships historical event-to-event pattern matching → research\competitive_landscape.md]`

- No retail tool detects cross-source divergence as defined in A7.1.
- No retail tool systematically ingests Substack analyst content or short-seller report releases in real time.
- No retail tool uses prediction-market probabilities as sentiment input AND execution venue.
- No retail tool tracks Congressional trading + 13D activist + short-seller + Substack + podcasts in one pipeline.

### B2.3 Why the commoditization of raw Reddit sentiment is fine

ICE launched Reddit Signals & Sentiment January 28, 2026, processing 16B+ posts for institutional clients. Raw Reddit polarity is now a commodity. The edge has moved upstream to curation (Tier A/B sources), cross-source divergence, and historical pattern matching. That's where the module is pointed.

## B3. Stock Module Personas

### B3.1 User Zero — Kamil
Full-stack AI developer. Trades Schwab thinkorswim + Merrill Lynch + Kalshi + Polymarket. Operates the dual proof accounts. Validates every signal personally for 90 days (Phase 0) before opening paid tiers.

### B3.2 Active Retail Swing Trader (primary)
3–10 trades/week, 1–5 day holds, $5K–$100K accounts. Pain: can't tell organic enthusiasm from manipulation; no historical context; drowns in noise. Willingness to pay: $49–149/month.

### B3.3 Quantitative Developer (secondary)
Builds algorithmic strategies, needs API + WebSocket + historical export. Pain: existing APIs are expensive or shallow. WTP: $149–299/month.

### B3.4 Financial Content Creator (tertiary)
YouTube/Substack creator; wants unique data points and visualizations. WTP: $49/month.

### B3.5 Prediction Market Trader (quaternary)
Active on Kalshi / Polymarket. Wants AI probability estimates and PM-vs-equity divergence alerts. WTP: $149–299/month.

## B4. Stock Module Data Sources

### B4.1 MVP tier (~$500/month total API)

| Source | Provides | Cost | Tier | Priority |
|---|---|---|---|---|
| ApeWisdom | Reddit mention volume, trending | Free | C | P0 |
| StockTwits API | Bull/bear ratios | Free (200/hr) | C | P0 |
| SEC EDGAR | 13F, 13D, Form 4, 8-K | Free | B | P0 |
| Unusual Whales | Options flow, sweeps, dark pool | $65–150/mo | B | P0 |
| FMP or Polygon.io | Prices, fundamentals, 30yr history | $79–199/mo | B | P0 |
| Google Trends (pytrends) | Search volume | Free | C | P1 |
| FRED | Macro data | Free | A | P1 |
| FINRA | Short interest (bi-monthly) | Free | A | P1 |
| CFTC COT | Futures positioning (weekly) | Free | A | P1 |

### B4.2 Phase 1.5 additions (~$10–110/mo)

| Source | Provides | Cost | Tier | Priority |
|---|---|---|---|---|
| Substack RSS (20 newsletters) | Doomberg, Net Interest, Macro Compass, Matt Stoller, Daily Upside, Epsilon Theory | Free | A–B | P1 |
| Quiver Quantitative | STOCK Act Congressional trades | $10/mo | B | P1 |
| Short-seller RSS | Hindenburg, Muddy Waters, Kerrisdale, Spruce Point | Free | A | P1 |
| SEC 13D feed | Activist investor positions | Free | A | P1 |
| The Transcript | Curated earnings call highlights | Free | B | P1 |
| BusinessWire / PR Newswire | Press releases | Free–$100/mo | C | P1 |
| Kalshi API | CFTC-regulated PM probabilities | Free (trading fees only) | A | P1 |
| Federal Register | Regulatory changes, comment periods | Free | A | P2 |

### B4.3 Phase 2 additions (~$90–280/mo)

| Source | Provides | Cost | Tier | Priority |
|---|---|---|---|---|
| Polymarket API | Crypto/geopolitics/election probabilities | Free | B | P2 |
| YouTube Data API + Whisper | Transcripts from Odd Lots, Meet Kevin, Macro Voices, Patrick Boyle, Ben Felix | $30–80/mo | B–C | P2 |
| Podcast transcription | Forward Guidance, Chat with Traders, Grant Williams, Compound & Friends | ~$30/mo | B | P2 |
| LunarCrush | X + Reddit + TikTok aggregated | $99–499/mo | C | P2 |
| Benzinga Pro | Real-time professional news | $99/mo | B | P2 |
| Seeking Alpha Quant | Systematic contributor scores | ~$20/mo | C | P2 |
| TipRanks API | Aggregated analyst ratings + price targets | $30–70/mo | C | P2 |

### B4.4 Production scale (~$1,000–2,000/mo once revenue supports it)
- Reddit API commercial license ($1,000+/mo)
- X/Twitter official API (~$215+/mo at 43K posts)
- SentimenTrader ($149/mo for historical sentiment backtesting)
- AlphaSense, Hedgeye — institutional add-ons

### B4.5 Skipped for MVP (with reason)
- Bloomberg / Reuters Terminal — enterprise pricing, overkill for retail.
- Direct X API enterprise tier ($7,500/mo) — use aggregator.
- RavenPack — we compete with them.
- Most alternative data (satellite, credit-card, etc.) — low ROI until institutional tier.

### B4.6 Each source's `tos_basis` (enforced by engine)
Populated in `architecture\modules\stocks\config.yaml` before any adapter goes live. `[CITATION NEEDED: research\data_sources.md#tos for each source]`.

## B5. Stock-Specific Scoring, Divergence, Cascade

### B5.1 Base scoring weights (stocks)

| Component | `w_i^base` | Source |
|---|---|---|
| Mention volume & velocity | 0.20 | ApeWisdom, StockTwits, Reddit |
| Options flow alignment | 0.18 | Unusual Whales |
| Sentiment polarity (FinBERT) | 0.13 | All social posts |
| Source consensus (1 − D) | 0.13 | A7.1 |
| Prediction market alignment | 0.10 | Kalshi / Polymarket |
| Institutional alignment (13F) | 0.08 | SEC EDGAR |
| LLM narrative quality | 0.08 | Claude Tier 2 |
| Alt analyst signal | 0.06 | Substack / YouTube / podcasts |
| Historical pattern match | 0.04 | Rhyme Engine |

Σ = 1.00. ✅

### B5.2 Regime multipliers

| Component | `high_vol` (VIX > Q3) | `low_vol` (VIX < Q1) | `earnings_week` |
|---|---|---|---|
| Mention volume & velocity | 1.5 | 0.8 | 1.2 |
| Options flow alignment | 1.3 | 1.0 | 1.6 |
| Sentiment polarity | 0.6 | 1.3 | 1.0 |
| Source consensus | 1.0 | 1.0 | 1.0 |
| Prediction market alignment | 1.5 | 1.0 | 1.2 |
| Institutional alignment | 1.0 | 1.0 | 0.9 |
| LLM narrative quality | 1.0 | 1.2 | 1.1 |
| Alt analyst signal | 0.9 | 1.5 | 1.0 |
| Historical pattern match | 1.5 | 1.0 | 0.9 |

Worked example (high-vol regime): raw products are `(0.20×1.5, 0.18×1.3, 0.13×0.6, 0.13×1.0, 0.10×1.5, 0.08×1.0, 0.08×1.0, 0.06×0.9, 0.04×1.5) = (0.300, 0.234, 0.078, 0.130, 0.150, 0.080, 0.080, 0.054, 0.060)`. Sum = 1.166. Normalized weights: `(0.257, 0.201, 0.067, 0.111, 0.129, 0.069, 0.069, 0.046, 0.051)`. ✅ Σ = 1.00.

### B5.3 Global Cascade Scoring (stocks)

**Sessions tracked:**
- Asian (7 PM – 3 AM ET): Nikkei, Hang Seng, Shanghai, KOSPI, ASX + Asian commodities + USD/JPY, AUD/USD
- European (3 AM – 9:30 AM ET): FTSE, DAX, CAC + Brent + EUR/USD, GBP/USD
- US pre-market (4 AM – 9:30 AM ET): /ES, /NQ, /CL, /GC, VIX futures
- Prediction market overnight (24/7): Polymarket/Kalshi probability shifts

**Cascade metric.** For sector `s` on day `t`, let `r_asia(s, t)`, `r_europe(s, t)`, `r_premkt(s, t)` be session returns. The cascade score is:

```
C(s, t) = β̂_1 * r_asia(s, t) + β̂_2 * r_europe(s, t) + β̂_3 * r_premkt(s, t) + ε
```

where `β̂_1..3` are fit quarterly via OLS on the last 5 years of session returns against the US cash-session return. `C(s, t)` is the engine's predicted US sector direction.

**Historical hit rate.** The module reports the rolling 90-day directional hit rate of `C` per sector on the dashboard. v1.1's "70% probability" example is retired — real numbers live here.

### B5.4 Sarcasm handling (stock module)

Research-confirmed: best sarcasm F1 on Reddit ≈ 72–76%. `[CITATION NEEDED: research\ai_models.md#sarcasm]`. Mitigations:

1. Volume > polarity for meme names (volume is harder to fake with sarcasm).
2. Custom WSB slang dictionary in `keyword_dictionaries.wsb_slang` (engine-managed module data).
3. Subreddit weighting: WSB posts get a polarity-weight multiplier of 0.6.
4. Tier-2 escalation for ambiguous polarity ≥ 0.5 but entropy in surrounding 5-post context > threshold.
5. Market-cap filter: exclude < $100M to avoid pump-and-dump targets.

## B6. Prediction Markets Module (Stock-Module-Scoped)

### B6.1 As sentiment input
- **Kalshi (primary).** CFTC-regulated. Clean API. Markets: Fed, CPI, NFP, earnings beats, GDP, weather, geopolitics.
- **Polymarket (secondary).** USDC-settled on Polygon. Rich geopolitical, election, crypto markets. Access gated by geo-check (A14.4); US enforcement posture monitored monthly (R4).
- **ICE validation.** ICE distributed Polymarket to institutional subscribers February 2026 — institutional validation of alt-data status.

### B6.2 As trading venue
Signal-attributed bets on Kalshi/Polymarket are the second proof track ($1K→$50K). Binary outcomes make win-rate math clean; no Greeks; no PDT; $5–$50 position sizing viable.

### B6.3 Event-to-instrument mapping

| Event type | PM play | Correlated equity play |
|---|---|---|
| Fed rate decisions | Kalshi Fed markets | TLT, IEF, XLF, KRE, SPY |
| CPI beat/miss | Kalshi CPI | TLT, TIP, GLD |
| Geopolitical escalation | Polymarket conflict | XLE, XOP, STNG, RTX, GLD |
| Election outcomes | Polymarket election | XLE ↔ XLV sector rotation |
| Earnings beat/miss | Kalshi earnings | Specific ticker options |
| Recession probability | Kalshi / Polymarket | IWM, XRT, HYG, TLT |
| Crypto regulation | Polymarket crypto | COIN, MARA, IBIT |

### B6.4 Cross-asset arbitrage (equity-implied probability)

v1.1 hand-waved "equity-implied probability." v1.2 specifies:

For a binary event `e` resolving at time `T`:
- **PM probability** `p_PM(e, t)` is direct.
- **Equity-implied probability** `p_EQ(e, t)` is computed from options IV skew around the correlated ticker's event date using a binary-barrier model (placeholder; exact formula to be spec'd in `architecture\cross_asset_arb.md`).

Arb window: when `|p_PM - p_EQ| > 0.10` AND both exceed liquidity thresholds, surface as a divergence candidate. Execution is manual in MVP, semi-automated in v2.

## B7. Stock Module Features (v1.2 re-prioritization)

### P0 — Must ship for MVP
1. Multi-source sentiment scoring (signal 1–10 + confidence 1–10) per ticker.
2. Cross-source divergence detection (A7.1 math).
3. Two-tier AI scoring (FinBERT + Claude).
4. REST API: `GET /signals/{ticker}`, `GET /narratives/{ticker}`, `GET /divergence/active`.
5. Rhyme Engine v1 (A7.3 math with significance gate).
6. Proof-account dashboard (equity trade log with signal attribution).
7. **Bot / manipulation detection (promoted from P2).** A8.3 primitive wired into module-specific pump-and-dump signatures (social-volume spike + zero institutional confirmation + low-liquidity stock = flag).

Rationale for promotion: if the engine amplifies pumped signals, the equity proof account blows up and the entire commercial thesis dies. This is not a v1.2 polish item.

### P1 — Ship for Phase 1.5
8. Substack ingestion (20+ priority newsletters).
9. Short-seller report monitoring (real-time Hindenburg/Muddy Waters/Kerrisdale).
10. Congressional trading tracker (STOCK Act via Quiver).
11. Activist investor 13D filings (Elliott, Pershing, Trian, Icahn, Starboard).
12. Kalshi data ingestion.
13. Global Cascade Scoring (B5.3) with measured hit rate.
14. Dashboard v1: signals list, divergence feed, Rhyme Engine results, trade log.

### P2 — Ship for v1.2 (post-Phase-0)
15. YouTube/podcast transcript pipeline (Whisper).
16. Polymarket data ingestion.
17. Kalshi trading module (automated bet placement from signals — second proof track).
18. Real-time WebSocket feed.
19. Backtesting module exposed in dashboard (walk-forward viewer).

### P3 — Ship for v2.0
20. Polymarket trading module.
21. React dashboard redesign.
22. Options strategy recommender.
23. Mobile push notifications.
24. Earnings-call-transcript monitoring (AlphaSense / Seeking Alpha).

### P4 — Future
25. Multi-industry modules (real estate, auto, F&B) — engine already ready, needs config + adapters.
26. Cross-asset arbitrage execution engine.
27. Institutional alt-data tier (satellite, credit-card, etc.).

## B8. UX / Dashboard Spec

Three wireframed screens for Phase 0. These are the minimum surface needed for user-zero to run the engine daily without writing SQL.

### B8.1 Daily Signal Board (home)

Purpose: "what should I care about today?"

Layout:
```
+--------------------------------------------------------------+
| AlphaHound — Daily Signal Board      [regime: high_vol]      |
+------------+---------+----------+----------+-----------------+
| Ticker     | Signal  | Conf     | Top driver                 |
|------------+---------+----------+-----------------------------|
| STNG       | 8.3     | 7.1      | Options flow + rhyme: 1990  |
| TLT        | 2.1     | 6.8      | PM probability shift +12%   |
| NVDA       | 6.9 ⚠   | 5.2      | Source divergence D=2.4     |
| ...                                                          |
+--------------------------------------------------------------+
| Overnight cascade: Asian energy -2.1% → European -3.4% → ... |
+--------------------------------------------------------------+
| Active Rhyme Matches (p<0.01): 3   [view all]                 |
| Active divergence alerts:      5   [view all]                 |
+--------------------------------------------------------------+
```

Rule: no imperative language. ⚠ = divergence flag, not a trade suggestion.

### B8.2 Ticker Drilldown

Purpose: "why is this ticker flagged?"

Sections:
- Signal score breakdown (9 components, active weights, current regime)
- Divergence panel (class-level polarities, D value, p-value, 7d chart)
- Rhyme match panel (top 3 historical analogs, similarity, phase position, chart overlay)
- Tier-A analyst hits in last 72h
- Prediction-market linked probabilities (if any)
- Trade log for this ticker (proof account)

### B8.3 Proof Account View

Purpose: "what has AlphaHound actually decided?"

Sections:
- Equity track: account value, cumulative P&L, open positions with entry signal IDs, closed trade log with directional hit/miss per trade.
- Prediction-market track: same shape, separate.
- Rolling 30d / 90d signal accuracy per track.
- Kill-switch status (green / yellow / red — see B10.3).
- Export CSV button.

No custom React work in Phase 0 — these can be Grafana dashboards or a trivial FastAPI-served HTML. Polish comes in P3.

## B9. Backtest Methodology (Gate Before Phase 0)

### B9.1 Walk-forward rules
- Training window: 3 years. Holdout window: 3 months. Step: 1 month.
- No look-ahead leakage: all features computed only from data timestamped ≤ the prediction timestamp.
- Entity inclusion: survivorship-biased universes (S&P 500 constituents today) are rejected. Use point-in-time constituent lists.

### B9.2 Transaction-cost model
- Commissions: $0 (Schwab/Merrill modern rates).
- Spread: half-spread of 5 bps on liquid large-caps, 20 bps on mid-caps, 50 bps on small-caps. Measured from historical NBBO snapshots, not assumed.
- Slippage: market-impact model = `impact_bps = k × (size / 20d_ADV)^0.5`, `k=10` for default. Sensitivity table B9.4.
- Borrow cost for shorts: historical HTB rates from FINRA; default 2% APR for GC.

### B9.3 Threshold sensitivity
Every magic number in scoring and divergence (`τ`, `κ`, `δ`, `μ`) is swept across ±50% of its default, and backtest performance (Sharpe, max DD, hit rate, turnover) is plotted. Thresholds with convex, wide-optimum regions pass; thresholds with razor-thin optima are refactored or dropped.

### B9.4 Slippage stress
Backtest is rerun with `k` at 1×, 2×, 3×. If Sharpe > 0.5 only at `k=1`, the strategy is not production-ready.

### B9.5 Out-of-sample gate
Backtest is run on 2019–2024; forward test on 2025-Jan through the date Phase 0 starts. OOS forward test must show directional hit rate ≥ 55% to open Phase 0. If it fails, Phase 0 does not start — retune or rescope.

### B9.6 Deliverable
`research\backtest_stocks_v1.md` with notebooks, plots, and threshold choices. `[CITATION NEEDED: link once generated]`

## B10. Phase 0 — User Zero Validation

### B10.1 Entry criteria (NEW in v1.2)

Phase 0 does not start until ALL of:
- Engine pipeline round-trip (ingest → Tier 1 → Tier 2 → store → API) is green for 7 consecutive days.
- Signal SLO dashboard is live (A11.2 SLIs visible in Grafana).
- Backtest OOS forward test (B9.5) shows ≥ 55% directional hit rate over ≥ 200 trades.
- Risk register (A13) is fully populated and reviewed.
- Kill-switch automation (B10.3) is implemented and tested against simulated drawdowns.
- Publisher-exemption disclaimer injected in every API response.
- Both proof accounts are funded and wired (Schwab/Merrill + Kalshi).

If any bullet is false, Phase 0 is not "delayed" — it is not started. No exceptions.

### B10.2 Exit criteria
- Signal directional hit rate ≥ 58% over 90 days (equity).
- Signal directional hit rate ≥ 60% over 90 days (prediction market).
- Positive P&L on both accounts (after costs).
- ≥ 100 signal-attributed equity trades, ≥ 50 prediction-market bets.
- No major pipeline failures (SLO breach < 3 days cumulative) in the final 30 days.
- Tier-2 cost cap respected (< $10/day average).

### B10.3 Kill-switch decision tree

Kill-switches are mechanical, not discretionary.

**Equity track (any of):**
- Drawdown > 25% from peak → **PAUSE** all new signal-driven trades; manual close-out policy only; resume only after root-cause review and one-week green run.
- Rolling 30d directional hit rate < 48% over ≥ 30 trades → **PAUSE**; trigger retune sprint; resume when rolling hit rate > 55% in a paper-trade replay.
- Single trade loss > 10% of account → **REVIEW** within 24h; not automatic pause, but root-cause documented.
- Pipeline SLO breach > 24h → **PAUSE** new trades until green.

**Prediction-market track (any of):**
- Drawdown > 40% from peak → **PAUSE**.
- Rolling 30d resolution hit rate < 50% over ≥ 20 bets → **PAUSE**; retune.
- Single bet loss > 15% of bankroll → violates position-sizing rule; **REVIEW** process, not just trade.

**Project-level (STOP, not PAUSE):**
- After 2 full PAUSE cycles in any 90-day window with no improvement → project STOPS, PRD is rewritten, stock module may be replaced by a different first module.
- Phase 0 exit gate failed after 180 days → same.

### B10.4 Phase 0 deliverables (unchanged from v1.1)
- Daily AlphaHound report (automated, portfolio-aware).
- Signal log with attribution (CSV + DB).
- Weekly retrospective.
- Monthly scoring-weight retune from realized hit rates.
- Quarterly public blog post (builds pre-launch audience).

## B11. Dual Proof Strategy (Numbers Revisited)

### B11.1 Equity track: $5K → $1M

Kelly: `f* = (b*p - q)/b`. With `p=0.65`, `b=1.6`, `q=0.35`:
`f* = (1.6*0.65 - 0.35)/1.6 = 0.431` → Full Kelly = 43.1%.

**CRITICAL:** `p=0.65` and `b=1.6` are *assumed* inputs. They should be *measured* outputs of backtest (B9) and Phase 0 (B10). Kelly sizing before those numbers exist is theater.

Interim sizing rule: **Quarter Kelly (10.8%) for the first 50 trades** regardless of backtest numbers. Move to Half Kelly only after 50 signal-attributed trades with measured `p ≥ 0.60` and measured `b ≥ 1.4`. This downgrades v1.1's default.

| Strategy | Risk/trade | Trades to $1M* | Time at 3/wk | 10-loss streak |
|---|---|---|---|---|
| Full Kelly (43.1%) | 43.1% | ~367 | 2.4 yr | −19.6% |
| Half Kelly (21.6%) | 21.6% | ~724 | 4.6 yr | −10.3% |
| **Quarter Kelly (10.8%)** | **10.8%** | **~1,436** | **9.2 yr** | **−5.3%** |

*Assumes constant measured edge; real-world edge decays. $5K→$1M is a 5-year story at best, not 18 months.

**PDT rule eliminated April 2026:** FINRA removed the $25K minimum. Small-account day-trading is viable.

**Instruments by phase:**

| Phase | Account | Instruments | Sizing |
|---|---|---|---|
| 1 | $5K–$25K | Stock swings + long options (14–30 DTE, 30–45 Δ) | Quarter Kelly |
| 2 | $25K–$100K | Add intraday scalps, debit spreads | Half Kelly (conditional on measured edge) |
| 3 | $100K–$1M | Add futures | Half Kelly, 2% max loss/trade |

### B11.2 Prediction-market track: $1K → $50K

| Phase | Bankroll | Venue | Sizing | Goal |
|---|---|---|---|---|
| 1 (paper) | — | Kalshi paper | $10–50 theoretical | Validate signals |
| 2 (live small) | $500 | Kalshi | $10–30/bet | 2× bankroll |
| 3 (scale) | $1K–$5K | Kalshi + Polymarket | 2–5% Kelly | 5× bankroll |
| 4 (production) | $5K–$50K | Kalshi + Polymarket | Half Kelly | Full validation |

**Market priority:** Fed (Kalshi) > econ data (Kalshi) > earnings (Kalshi) > geopolitical (Polymarket) > elections (Polymarket) > crypto reg (Polymarket).

### B11.3 Tax
Professional Trader Status + Section 475 Mark-to-Market election (exempts wash-sale, allows unlimited loss deductions). PM winnings currently taxed as ordinary income; CFTC-regulated events may get capital-gains treatment — consult CPA, cite in research.

### B11.4 Honest assessment (updated)

Dual proof strategy is **marketing collateral generation**, not a path to financial independence. If Phase 0 exits green, the resulting track record (100+ equity trades, 50+ PM bets, all signal-attributed) is the SaaS product's primary sales evidence. If Phase 0 fails the exit gate (B10.2), the project stops or pivots per B10.3.

## B12. Stock Module Development Timeline

| Week | Engine track | Stock module track | Gate |
|---|---|---|---|
| 1 | Schema, adapter interface, module-config parser | Stock config v0.1 draft | — |
| 2 | Ingestion framework, Redis queue | ApeWisdom, StockTwits, EDGAR, UW, FMP adapters | — |
| 3 | Tier 1 FinBERT on T4 | Finish MVP adapters, entity resolution for tickers | — |
| 4 | Tier 2 escalation, cost caps | Scoring weights v1, regime classifier | — |
| 5 | Divergence metric + permutation test | Rhyme Engine seed corpus (20 events) | Backtest can start |
| 6 | Rhyme Engine with significance gate | Backtest v1 run, threshold sweeps | Backtest B9 |
| 7 | Observability (dashboards, alerting) | Backtest refine, OOS forward test | — |
| 8 | Security/secrets, failover drill | Dashboard v0 (Grafana), kill-switch automation | **Phase 0 entry gate (B10.1)** |
| 9–21 | Phase 0 operating (13 weeks) | Daily reports, weekly retros, monthly retunes | Phase 0 exit gate (B10.2) |
| 22 | Public free-tier launch prep | Marketing site, onboarding flow | — |
| 23 | Free tier live | — | — |
| 24–26 | Paid tiers | Starter, Pro, Trader | — |
| 27 | Kalshi trading automation | Second proof track automated | — |
| 28+ | Engine prep for module 2 | Real-estate adapter skeleton | — |

v1.1's weekly schedule is preserved in substance but tightened: Phase 0 does not begin until week 8 (was week 5 in v1.1). Adding proper backtest methodology and kill-switches is the delta.

## B13. Success Metrics

| Metric | Target | Window |
|---|---|---|
| Signal accuracy (equity, directional) | ≥ 60% | rolling 90d post-Phase 0 |
| Signal accuracy (prediction market) | ≥ 62% | rolling 90d post-Phase 0 |
| Equity proof P&L | positive | after 100 trades |
| PM proof P&L | positive | after 50 bets |
| Backtest OOS hit rate | ≥ 58% | 3-year backtest |
| Rhyme Engine match precision | ≥ 65% directional | after 20 matches |
| Alt-analyst signal lift | +3–5% hit rate vs non-alt baseline | post-Phase 0 |
| PM arb opportunities surfaced | 10+/month | month 6+ |
| Free-tier users | 1,000 | month 3 post-launch |
| Paid subscribers | 500 | month 6 post-launch |
| MRR | $50K | month 12 |
| MRR | $150K | month 18 |
| Tier-2 cost / MRR | ≤ 5% | ongoing |
| Pipeline SLO breaches | ≤ 1/month | ongoing |

## B14. Infrastructure & Budget

### B14.1 Azure compute
| Component | SKU | Monthly |
|---|---|---|
| FinBERT + Whisper inference | Standard_NC4as_T4_v3 | ~$384 |
| Postgres + FastAPI | Standard_D4s_v3 | ~$130 |
| Redis | Azure Cache for Redis C1 | ~$50 |
| **Total compute** | | **~$564** |

### B14.2 API costs (MVP)
| Source | Monthly |
|---|---|
| ApeWisdom | Free |
| StockTwits | Free |
| SEC EDGAR | Free |
| Unusual Whales | $65 |
| FMP/Polygon | $199 |
| Claude API (Tier 2) | $150–300 |
| **MVP API total** | **$414–564** |

### B14.3 MVP total
~$978–1,128/month.

### B14.4 Phase 1.5 additional
~$10–110/month (Substack free, Quiver $10, Kalshi free, BusinessWire $0–100, etc.).

### B14.5 Phase 2 additional
~$90–280/month (YouTube $30–80, podcasts $30, Polymarket free, Benzinga $99, TipRanks $30–70).

### B14.6 Full coverage total
~$1,100–1,500/month.

### B14.7 CPU-only fallback
Replace T4 with Standard_D8s_v3 (~$400/mo); FinBERT drops to ~20 posts/sec. Viable for non-real-time MVP. Total → ~$600/month.

### B14.8 Cost kill-switches
- Tier-2 daily cap: $15 (alert at $10).
- GPU monthly cap: $500 (alert at $400).
- Total monthly burn cap in Phase 0: $1,500 (alert at $1,200).
- Breach → engine throttles Tier-2 rate and pages owner.

## B15. Staffing & On-Call

### B15.1 Team at launch
Kamil, solo. This is a real constraint.

### B15.2 On-call
- Primary: Kamil.
- Backup: none at MVP. Consequence: the kill-switches in B10.3 and the cost caps in B14.8 must be aggressive enough that no 3am human decision is required.
- Escalation plan: if Kamil is unreachable for > 24h, engine pauses all trading and new signal generation automatically. This is a module config setting, not a runbook.

### B15.3 When to hire
Hire #1 (operations / data engineer) at $25K MRR. Hire #2 (frontend / UX) at $75K MRR. Hire #3 (second module owner, e.g., real estate) at $150K MRR.

## B16. Go-To-Market (Paid Tiers)

### B16.1 First 100 paying users
- The dual proof-account track record is the primary acquisition asset. Public trade log (with T+close delay) + quarterly retro blog posts drive inbound.
- Launch channels: Twitter/X (finance side), r/algotrading, r/quant, Substack cross-promotion with Tier-A sources (Doomberg, Net Interest) if their terms allow.
- Early-bird pricing: 50% lifetime discount for first 100 paying users in exchange for public testimonial.

### B16.2 CAC assumptions
- Organic-first (trade log + blog): CAC target < $30/user.
- Paid search (secondary, after product-market fit): CAC target < $150 for Pro tier.
- Payback: ≤ 3 months at Starter, ≤ 2 months at Pro.

### B16.3 Pricing (unchanged from v1.1 unless noted)

| Tier | Price | Features |
|---|---|---|
| Free | $0 | 5 tickers, 15-min delayed signals, no Rhyme, no PM |
| Starter | $49/mo | 50 tickers, real-time, basic Rhyme, Kalshi data |
| Pro | $149/mo | Unlimited tickers, full Rhyme, API, backtesting, Polymarket data, alt-analyst feeds |
| Trader | $299/mo | Pro + WebSocket + PM arb alerts + priority API |
| Enterprise | Custom | White-label, custom modules, historical data export, managed deployment |

### B16.4 Competitive positioning
- vs LunarCrush ($99–499): we have Rhyme Engine + divergence + PM.
- vs Unusual Whales ($65–150): we have full-stack sentiment layered on top of options.
- vs RavenPack ($50K/yr): we serve retail at 1/300th the price.
- vs Quiver ($10/mo): we integrate Quiver plus 10 other sources.

---

---

# APPENDICES

## Appendix A — Changelog

### v1.2 (April 18, 2026) — this document
Posture: challenge-priorities redline. Split PRD into Engine (Part A) and Stock Module (Part B). Formalized divergence metric (A7.1), Rhyme Engine significance gate (A7.3), and scoring-weight normalization (A7.4). Added Industry Configuration Schema (A5) as first-class contract. New sections: Data Governance (A9), SLOs/SLIs (A11), Security (A12), Risk Register (A13), Backtest Methodology (B9), Phase 0 entry criteria (B10.1), Kill-switches (B10.3), UX wireframes (B8), Staffing/on-call (B15), GTM (B16). Promoted bot/manipulation detection from P2 to P0 (B7). Downgraded default Kelly sizing to Quarter until Phase 0 measures the real edge (B11.1). Added cost kill-switches (B14.8). Added citation placeholders; committed to a CI linter that fails builds with un-cited numerical claims. Retired v1.1 cascade narrative ("70% probability") and replaced with a measurable cascade model (B5.3).

### v1.1 (April 16, 2026)
Added prediction markets (data + venue). Added alt-analyst content (Substack, YouTube, podcasts, short sellers, Congressional, activists). Expanded scoring from 7 to 9 components. Added Phase 0 (90-day personal validation). Added 5-tier pricing.

### v1.0 (April 15, 2026)
Initial PRD: 7 sources, single proof account, stock-module only.

## Appendix B — Industry Configuration Schema (Worked Examples)

### B.1 YAML schema (authoritative)

```yaml
module_id: <string, globally unique>
version: <semver>
engine_required: <semver range>

entities:
  canonical_source: <string>            # where canonical IDs come from
  kinds:                                # e.g. [ticker, sector, etf]
    - name: <string>
      id_pattern: <regex>
  alias_policy:
    auto_resolve: <bool>
    validity_tracking: <bool>

data_sources:
  - adapter: <python class path>
    class: <source_class>               # retail_social | institutional_flow | ...
    tier: <A | B | C | D>
    credentials_ref: <keyvault path>
    rate_limit: { calls_per_min: int, burst: int }
    tos_basis: <string>                 # ToS clause cite (REQUIRED)
    cost_tier: <free | low | medium | high>

source_tiers:
  multipliers: { A: 2.0, B: 1.5, C: 1.0, D: 0.5 }
  promotion_log: <path to audit markdown>

scoring_weights:
  base: { <component>: <0..1>, ... }    # sum must = 1.0
  regimes:
    <regime_name>:
      trigger: <expression>             # e.g. "vix_percentile > 75"
      multipliers: { <component>: <float>, ... }
  metadata:
    tier1_f1: <float>
    tier1_eval_notebook: <path>

keyword_dictionaries:
  slang: <path>
  sarcasm_tags: <path>
  stop_words: <path>

historical_pattern_library:
  corpus_path: <path>
  min_events_required: 15
  dtw_variable_weights:
    <variable>: <float>
    ...

regime_classifier:
  features:
    - name: vix_percentile
      formula: <expression>
    - ...

output_actions:
  api_routes:
    - GET /signals/{entity}
    - GET /divergence/active
    - ...
  websocket_channels:
    - /stream/{entity}

legal_disclaimer: |
  <module-specific disclaimer string>

kill_switches:
  accuracy_floor_30d: 0.48
  pipeline_uptime_floor: 0.97
  cost_cap_daily_dollars: 15
  drawdown_pause_percent: 0.25
```

### B.2 Stock module (populated)

```yaml
module_id: stocks
version: 0.2.0
engine_required: ">=0.1.0,<1.0.0"

entities:
  canonical_source: SEC CIK mapping
  kinds:
    - name: ticker
      id_pattern: "^[A-Z]{1,5}(\\.[A-Z])?$"
    - name: sector
      id_pattern: "^XL[A-Z]$"
  alias_policy:
    auto_resolve: true
    validity_tracking: true

data_sources:
  - adapter: stocks.adapters.apewisdom.ApeWisdomAdapter
    class: retail_social
    tier: C
    credentials_ref: kv://stocks/apewisdom
    rate_limit: { calls_per_min: 60, burst: 120 }
    tos_basis: "ApeWisdom free API ToS, accessed YYYY-MM-DD"
    cost_tier: free
  - adapter: stocks.adapters.stocktwits.StockTwitsAdapter
    class: retail_social
    tier: C
    credentials_ref: kv://stocks/stocktwits
    rate_limit: { calls_per_min: 200, burst: 200 }
    tos_basis: "StockTwits API ToS §4"
    cost_tier: free
  - adapter: stocks.adapters.edgar.EdgarAdapter
    class: institutional_flow
    tier: B
    credentials_ref: kv://stocks/edgar
    rate_limit: { calls_per_min: 10, burst: 10 }
    tos_basis: "SEC.gov public data; 10 req/s compliance"
    cost_tier: free
  # ... (options, PM, substack, short-sellers, quiver, 13D, etc.)

source_tiers:
  multipliers: { A: 2.0, B: 1.5, C: 1.0, D: 0.5 }
  promotion_log: research/source_tier_audit.md

scoring_weights:
  base:
    mention_volume_velocity: 0.20
    options_flow_alignment: 0.18
    sentiment_polarity: 0.13
    source_consensus: 0.13
    prediction_market_alignment: 0.10
    institutional_alignment: 0.08
    llm_narrative_quality: 0.08
    alt_analyst_signal: 0.06
    historical_pattern_match: 0.04
  regimes:
    high_vol:
      trigger: "vix_percentile > 75"
      multipliers: &high_vol_mults
        mention_volume_velocity: 1.5
        options_flow_alignment: 1.3
        sentiment_polarity: 0.6
        source_consensus: 1.0
        prediction_market_alignment: 1.5
        institutional_alignment: 1.0
        llm_narrative_quality: 1.0
        alt_analyst_signal: 0.9
        historical_pattern_match: 1.5
    low_vol:
      trigger: "vix_percentile < 25"
      multipliers:
        mention_volume_velocity: 0.8
        options_flow_alignment: 1.0
        sentiment_polarity: 1.3
        source_consensus: 1.0
        prediction_market_alignment: 1.0
        institutional_alignment: 1.0
        llm_narrative_quality: 1.2
        alt_analyst_signal: 1.5
        historical_pattern_match: 1.0
    earnings_week:
      trigger: "any(entity.earnings_in_next_5d)"
      multipliers:
        mention_volume_velocity: 1.2
        options_flow_alignment: 1.6
        sentiment_polarity: 1.0
        source_consensus: 1.0
        prediction_market_alignment: 1.2
        institutional_alignment: 0.9
        llm_narrative_quality: 1.1
        alt_analyst_signal: 1.0
        historical_pattern_match: 0.9
  metadata:
    tier1_f1: null  # TBD from measured evaluation
    tier1_eval_notebook: research/ai_models.md#finbert_stocks_eval

historical_pattern_library:
  corpus_path: data/rhyme_corpus/stocks.jsonl
  min_events_required: 20
  dtw_variable_weights:
    price: 0.4
    social_volume: 0.2
    sentiment: 0.2
    volatility: 0.1
    log_volume: 0.1

output_actions:
  api_routes:
    - GET /signals/{ticker}
    - GET /narratives/{ticker}
    - GET /rhyme/{event}
    - GET /cascade/overnight
    - GET /divergence/active
    - GET /prediction_markets/{topic}
    - GET /alt_analyst/recent
    - GET /short_sellers/active
    - GET /congressional/recent
  websocket_channels:
    - /stream/{tickers}
    - /stream/prediction_markets

legal_disclaimer: |
  AlphaHound provides data, scores, and analytical tools for informational
  purposes only. This is not investment advice, does not constitute a
  recommendation to buy or sell any security or place any bet, and is not
  tailored to any individual's financial situation. Prediction market
  participation may be restricted in your jurisdiction.

kill_switches:
  accuracy_floor_30d: 0.48
  pipeline_uptime_floor: 0.97
  cost_cap_daily_dollars: 15
  drawdown_pause_percent: 0.25
```

### B.3 Real-estate module (stub — shows what swaps)

```yaml
module_id: real_estate_us
version: 0.0.1
engine_required: ">=0.1.0,<1.0.0"

entities:
  canonical_source: HUD + Census tract ID
  kinds:
    - name: metro
    - name: neighborhood
    - name: zip

data_sources:
  - adapter: real_estate.adapters.redfin.RedfinAdapter
    class: retail_social          # same class, different source
    tier: B
    # ...
  - adapter: real_estate.adapters.zillow.ZillowAdapter
  - adapter: real_estate.adapters.reddit_localsubs.RedditLocalSubsAdapter
  - adapter: real_estate.adapters.hud.HudAdapter
    class: institutional_flow     # federal housing data
    tier: A

scoring_weights:
  base:
    mention_volume_velocity: 0.25
    sentiment_polarity: 0.20
    source_consensus: 0.15
    institutional_alignment: 0.15  # HUD / Fed / mortgage data
    alt_analyst_signal: 0.10
    historical_pattern_match: 0.15
    # 3 stock-specific components zeroed out
    options_flow_alignment: 0.0
    prediction_market_alignment: 0.0
    llm_narrative_quality: 0.0

# ... etc
```

Observation: `options_flow_alignment = 0` and `prediction_market_alignment = 0` demonstrates the engine's tolerance for modules that don't use every component. Remaining weights re-normalize to 1.0.

### B.4 Auto module (stub)

```yaml
module_id: auto_us
version: 0.0.1
entities:
  kinds:
    - name: make_model        # e.g. "Ford F-150"
    - name: manufacturer      # e.g. "Ford Motor Company"
    - name: recall_campaign
# Data sources center on NHTSA recalls, owner forums (F150Forum, TeslaMotorsClub),
# dealer inventory signals (TrueCar), and manufacturer equity (pulls from stocks module).
```

## Appendix C — Research Citations (To Be Filled)

The following claims in this PRD carry `[CITATION NEEDED]` tags:

| # | Claim | PRD location | Target research file |
|---|---|---|---|
| C1 | All four AI research sources confirmed no retail pattern-matching product | B2.2 | research\competitive_landscape.md |
| C2 | FinBERT ~87% F1 on financial news, ~65–70% on Reddit, ~80–85% fine-tuned | A6.1 | research\ai_models.md#finbert |
| C3 | Sarcasm F1 on Reddit ≈ 72–76% | B5.4 | research\ai_models.md#sarcasm |
| C4 | CoT degrades financial sentiment accuracy | A6.2 | research\ai_models.md#cot_vs_system1 |
| C5 | ICE Reddit Signals launch 2026-01-28, 16B+ posts | B2.3 | research\competitive_landscape.md#ice |
| C6 | ICE Polymarket distribution 2026-02 | B6.1 | research\competitive_landscape.md#ice |
| C7 | FNSPID dataset 29.7M prices + 15.7M news 1999–2023 | A7.3 | research\historical_patterns.md#fnspid |
| C8 | IMF banking-crisis DB 151 + 414 records 1970–2019 | A7.3 | research\historical_patterns.md#imf |
| C9 | Reinhart/Rogoff 800 years of crises | A7.3 | research\historical_patterns.md#reinhart_rogoff |
| C10 | AI-in-Trading market $24.5B 2025 → $68B 2033 | B16.4 | research\multi_industry_analysis.md#tam |
| C11 | Kalshi + Polymarket combined $10B+ annual volume | B16.4 | research\competitive_landscape.md#prediction_markets |
| C12 | PDT rule eliminated April 2026 | B11.1 | research\data_sources.md#finra |
| C13 | Lowe v. SEC 1985 + 2024 Seeking Alpha ruling | A14.1 | research\legal.md |
| C14 | 2022 CFTC Polymarket settlement | B6.1 | research\legal.md |

**Process:** a Phase-0-blocking task is to open each file, populate each citation with at least URL + date + relevant quote, and remove the `[CITATION NEEDED]` tags. The CI linter blocks merges to main until this list is empty.

## Appendix D — Open Questions to Answer Before v1.3

1. **Divergence metric form.** Std-dev vs MAD across source classes. Empirical test on Phase 0 data.
2. **Rhyme Engine variable weights.** Learn from corpus via LOO-CV instead of hand-setting.
3. **Regime classifier.** Rule-based quartiles vs HMM. Cost/benefit unclear.
4. **Entity resolution for multi-word entities** (real estate, auto). Engine service or module job?
5. **Backup on-call.** Can the engine actually run unattended for 48h given aggressive kill-switches, or is a human always required?
6. **Second module choice.** Real estate, auto, or something else? Depends on Phase 0 learnings.
7. **Tier-2 LLM fallback.** Llama-3-70B fine-tuned candidate — how close can we get on narrative quality?
8. **Module-level vs engine-level entity resolution** — where does `TSLA → Tesla Inc → Elon Musk` live?
9. **Signal-attributed trade log public format.** T+close delay is correct; what about failed-signal transparency (signals that fired but weren't traded)?
10. **AI-washing compliance artifact.** Do we need a third-party audit of the "AI accuracy" claims before enterprise conversations, or is the public trade log enough?

---

*v1.2 does not replace research. It makes the research gaps legible and gate-blocking. When Appendix C is empty and Appendix D has answers, v1.3 ships.*
