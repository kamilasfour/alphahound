# AlphaHound — Project Analysis Summary

**Date:** April 18, 2026
**Author:** Claude (PM) + Kamil
**Purpose:** One-page state of the project. For sprint-by-sprint detail see `SPRINT_TRACKER.md`.

> 📌 **Single source of truth for sprint state:** `docs/SPRINT_TRACKER.md`. Per-sprint details in `docs/sprints/`.

---

## 1. Project Snapshot

### What exists
- **PRD v1.2** — well-scoped, split into Engine (Part A, industry-agnostic) and Stock Module (Part B, first vertical). Math is formalized (divergence, Rhyme Engine, weight normalization). Kill-switches, SLOs, risk register, citation discipline all in place.
- **Engine skeleton** — `BaseAdapter` abstract contract + `Post` pydantic model. Enforces `adapter_id`, `source_class`, `tier`, `tos_basis` at subclass time. Good foundation.
- **Proof trade log** — 11 core Merrill positions + 2 swings seeded April 14, 2026. Schwab $5K sits in cash waiting for the engine's first signal.
- **Research corpus** — 4 AI research briefs (ChatGPT, Claude, Gemini, Perplexity) plus master brief.
- **`pyproject.toml`** — Python 3.11+, minimal deps (httpx, pydantic, typer).

### What's missing
- No module config loader (PRD A5 YAML schema specified but not parsed).
- Zero concrete adapters — all `__init__.py` files are empty.
- No storage layer, no CLI glue (`alphahound` entry point points at non-existent `cli.py`).
- No scoring primitives (divergence, Rhyme Engine, regime-weighted normalization).
- `architecture/` folder is empty — needs `database_schema.sql` as source of truth.
- No tests.

---

## 2. The Thesis (v1.3, two-stage)

**One-liner:** AlphaHound is built in two stages. **Stage 1** is Kamil's personal capital engine — aggressive multi-source ingestion, bespoke scoring, semi-automated execution, no customers — used to turn $6K starting capital into material funding for other ventures. **Stage 2** (only if Stage 1 succeeds and Kamil elects to productize) is a fork of the Stage 1 engine, pruned of ToS-gray sources and hardened for institutional/developer customers as a commercial SaaS.

**What Stage 1 is NOT:**
- Not a product anyone else uses
- Not bound by redistribution ToS (personal use only)
- Not publishing signals to customers — no publisher's exemption needed
- Not multi-industry — stocks only

**What Stage 2 is NOT (but Stage 1 can be):**
- Not permitted to use sources whose ToS restricts derived commercial products
- Not a single-operator tool
- Not permitted to couple signal→execution without explainability guardrails

**What stays constant across both stages:**
- Engine architecture (ingestion + two-tier AI + scoring + storage)
- Divergence math (PRD A7.1)
- Rhyme Engine (PRD A7.3)
- Kill-switches (PRD B10.3) — capital preservation is non-negotiable, Stage 1 especially
- Trade log as the proof artifact

Full framing: `prd/PRD_v1.3_stage1_addendum.md`.

---

## 3. Architecture at a Glance

```
[Per-industry adapters]         [Engine Core]              [Per-industry outputs]
                      ingestion →                   → REST / WebSocket / dashboards
 stock adapters  ┐                ┌ Source Classifier ┐
 re adapters     ├─→ raw posts ─→│ Tier 1: FinBERT   ├→ scored events ──→ stock API
 auto adapters   ┤                │ Tier 2: Claude    │                   re API
 (future) ...    ┘                │ Divergence        │                   auto API
                                  │ Cascade           │
                                  │ Rhyme Engine      │
                                  └───────────────────┘
                                            │
                                  [Postgres + TimescaleDB]
                                            │
                                   [Industry Config]
```

Engine owns: ingestion, model serving, scoring math, storage, API. Module owns: adapters, entity dictionaries, scoring weights, historical corpus.

---

## 4. Six Ingestion Source Classes (stocks defaults)

| Class | Example sources | Tier |
|---|---|---|
| Retail social | Reddit, StockTwits, X retail | C |
| Institutional flow | SEC EDGAR (13F, 13D, Form 4) | B |
| Options | Unusual Whales, dark pool sweeps | B |
| Prediction market | Kalshi, Polymarket | A–B |
| Analyst curated | Substack, YouTube, podcasts (tiered by track record) | A–C |
| News wire | Benzinga, BusinessWire | C |

---

## 5. Nine-Component Weighted Scoring (Stocks)

| Component | Base weight |
|---|---|
| Mention volume & velocity | 20% |
| Options flow alignment | 18% |
| Sentiment polarity (FinBERT) | 13% |
| Cross-source consensus (1 − divergence) | 13% |
| Prediction market alignment | 10% |
| Institutional alignment (13F) | 8% |
| LLM narrative quality (Claude) | 8% |
| Alt-analyst signal | 6% |
| Historical pattern match (Rhyme Engine) | 4% |

Weights shift by regime (high vol / low vol / earnings week) via a deterministic multiplier table. Sum always re-normalizes to 1.0.

---

## 6. Three Genuinely Novel Differentiators

1. **Cross-source divergence metric.** σ across source-class sentiment means, with a permutation null test (p<0.01 gate). Fires when retail is bullish but institutions are bearish (or vice versa). No retail tool does this.

2. **Rhyme Engine.** DTW similarity of current event to curated historical corpus (20+ seed events: banking crises, geopolitical shocks). Only matches surviving a null-distribution test are surfaced. Outputs phase position ("you're in day 14 of the 1990 tanker-rally pattern").

3. **Two-tier AI pipeline.** FinBERT on a T4 GPU scores ~500 posts/sec at ~$13/day. Claude gets called only on escalated events (5–8% of posts) for narrative reasoning. Cost capped at ~$10/day per module.

---

## 7. Dual Proof Strategy

| Track | Bankroll | Venue | Target | Purpose |
|---|---|---|---|---|
| Equity | $5K | Schwab | $1M | Primary proof — logged, signal-attributed trades |
| Prediction market | $1K | Kalshi (+ Polymarket later) | $50K | Secondary proof — binary outcomes, clean win-rate math |

**Sizing rule:** Quarter Kelly (~10.8%) until ≥50 signal-attributed trades establish measured edge. Honest assessment: dual proof is *marketing collateral generation*, not a fast path to financial independence.

---

## 8. Guardrails

- **Kill-switches** — mechanical, not discretionary (25% drawdown → pause, 30d hit rate <48% → pause, SLO breach >24h → pause).
- **Cost caps** — Tier-2 Claude at $15/day hard, GPU at $500/mo, total monthly burn at $1,500 in Phase 0.
- **Legal** — publisher's exemption posture (Lowe v. SEC); trade logs published T+close only; no imperative language ("signal score 8/10" not "buy").
- **Citation discipline** — every numerical claim ties to a research file; CI linter blocks merges on uncited claims.

---

## 9. Sprint 0 — COMPLETE ✅ | Sprint 1 — COMPLETE ✅ | Sprint 2 — IN PROGRESS 🧪

For details, see `docs/sprints/sprint_0_substrate.md`, `docs/sprints/sprint_1_first_pipe.md`, and `docs/sprints/sprint_2_multi_source.md`.

**Sprint 0 outcome:** Azure Postgres 17.9 Flexible Server provisioned (`alphahound-rg.postgres.database.azure.com`), Timescale enabled, firewall configured, tooling decisions locked.

**Sprint 1 outcome:** Schema applied (8 hypertables + 4 standard tables), `BaseAdapter` contract shipped, ApeWisdom adapter written and run, CLI working, 100 rows in `raw_posts` from a live pull.

**Sprint 2 status (as of April 19, 2026):** infrastructure shipped (`ingest_runs`, watchlist, velocity math, scheduled task, runbook, tests). Second adapter pivoted mid-sprint — StockTwits retired (API blocking), Reddit deferred (registration gated), **SEC EDGAR selected as second source** (free, public-domain, ToS-clean, adds `institutional_flow` class). Two-stage strategy formalized in `prd/PRD_v1.3_stage1_addendum.md`.

---

## 10. Sprint 3 — NEXT 🎯

**Goal:** Tier 1 AI + divergence. FinBERT scores every post's polarity; cross-source divergence metric (PRD §A7.1) fires when ApeWisdom sentiment disagrees with EDGAR institutional-flow sentiment. First sprint where "signal" means something real.

**Detail doc:** to be written at Sprint 2 close.

---

## 11. Open Questions / Parked

1. **Qtrade integration.** Likely the execution layer for Sprint 9. Decision deferred until Sprint 9 planning.
2. **Divergence metric form** — std-dev vs MAD across source classes. Empirical test on live data in Sprint 3+ (PRD A17.2).
3. **Rhyme Engine variable weights** — hand-set v1.2, should be learned via LOO-CV (PRD A17.2).
4. **Stage 2 second module** — real estate vs auto vs other. Decide at Stage 1 exit based on learnings.
5. **Stage 1 on-call** — can engine run unattended 48h given aggressive kill-switches? Becomes relevant in Sprint 10 (live trading).
6. **Tier-2 LLM fallback** — Llama-3-70B-FT as Claude alternate. Prototype when cost becomes an issue (Stage 2 concern).
7. **Reddit API approval** — submitted April 19, 2026. Timeline unpredictable. Not blocking any sprint.
8. **When to engage securities counsel** — worth doing once Stage 1 hits six-figure monthly P&L per v1.3 §5.

---

## 12. Tech Stack (Committed)

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Web framework | FastAPI |
| DB | Azure PostgreSQL 17 Flexible Server + TimescaleDB |
| ORM / driver | `psycopg` (v3) + SQLAlchemy |
| Queue | Redis (Azure Cache) — Sprint 2+ |
| Tier-1 model | FinBERT (`ProsusAI/finbert`) on Azure T4 VM — Sprint 2+ |
| Tier-2 model | Claude API — Sprint 3+ |
| Secrets | `.env` (dev) → Azure Key Vault (staging/prod) |
| VCS | Git (remote TBD — likely private GitHub) |
| Host | Azure VM `repsportalvm` (Windows Server 2022) — dev/staging |
| Tooling | Claude (PM/architecture), Claude Code + Cursor (edits) |

---

*This document is the reference state-of-project as of the end of Sprint 0. It gets updated at the end of each sprint, not during.*
