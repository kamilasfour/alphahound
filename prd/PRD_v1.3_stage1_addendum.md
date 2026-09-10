# AlphaHound — PRD v1.3 Addendum: Two-Stage Strategy

**Author:** Kamil Asfour
**Date:** April 19, 2026
**Status:** Strategic addendum on top of PRD v1.2
**Supersedes:** Nothing — this document *adds* strategic framing on top of `PRD_v1.2.md`. All engine architecture, math, data governance, and risk framework from v1.2 remain in force except where explicitly overridden below.
**Posture:** Reframe, not rewrite. v1.2 was written assuming a one-stage "build engine, sell SaaS" thesis. The business thesis has evolved into two stages. The engine doesn't change; its near-term consumer and the data sources it pulls from do.

---

## 1. Why this document exists

On April 19, 2026, the project's strategic framing was revised mid-Sprint 2 after hitting real-world data access walls (StockTwits API frozen since 2021, Reddit official API gated behind manual review). The question "can we just pay for commodity sentiment data?" surfaced a deeper question about what AlphaHound actually is.

The answer: AlphaHound is **two products in sequence**, not one.

- **Stage 1** is a personal capital engine that uses every legitimate method available — including aggressive ingestion of public data that would be unsuitable for a resellable product — to turn a small personal account into material capital. The success metric is dollars in Kamil's account, not MRR.
- **Stage 2**, which begins only after Stage 1 produces funding, is the commercial sentiment intelligence platform described in `PRD_v1.2.md`. Resellable, ToS-clean, industry-agnostic, aimed at institutions and developers, not retail.

v1.2's assumption was that Phase 0 (personal validation) flowed seamlessly into a public SaaS launch. v1.3 corrects that: **Phase 0 is still real, but it is Stage 1's entire lifecycle, not a precursor to Stage 2.** Stage 2 starts as a partial rewrite, not a continuation.

## 2. Stage 1 — Personal Capital Engine

### 2.1 Goal
Turn $5,000 (Schwab equity) and $1,000 (Kalshi prediction market) into material capital — target $1M combined — using AlphaHound as the primary decision-support system. Capital is subsequently deployed to fund Kamil's other ventures (Forkcast, Qtrade, future projects) without dilutive outside investment.

### 2.2 Who the "user" is
Kamil. Only Kamil. No paying customers. No API consumers. No public product surface. The engine is a single-operator tool.

### 2.3 What changes vs. v1.2

**Scope reductions (removed from Stage 1):**
- No public API (`GET /signals/{ticker}` etc. — still built for internal use, not exposed)
- No free / paid subscription tiers
- No customer-facing dashboard polish
- No onboarding flow, billing, support, docs-for-outsiders
- No marketing site, GTM plan, CAC tracking
- No CI linter enforcing citation discipline for external-facing claims
- No publisher's exemption legal posture (not publishing to customers)
- No AI-washing SEC posture concerns (not a registered adviser, not making public accuracy claims)
- No Phase 0 as "public ritual with quarterly blog posts" — hit rate still tracked privately
- Multi-industry modules deferred indefinitely — stocks only until Stage 2

**Scope additions (in-scope for Stage 1, out-of-scope in v1.2):**
- Aggressive ingestion of sources whose ToS restricts *redistribution* but permits *personal use*:
  - Seeking Alpha (public free articles; paid content only if Kamil is subscribed)
  - Substack paid newsletters Kamil subscribes to
  - Full YouTube transcripts via Whisper (personal research use)
  - Full podcast transcripts (personal research use)
  - Finance Discord servers Kamil is a member of
  - Benzinga Pro, RavenPack, AlphaSense — permitted if cost-justified by trading P&L (not restricted by "cannot resell" clauses since we don't resell)
- LLM-intensive workflows with no regulatory explainability requirement (Claude scores whatever makes sense, narrative outputs are read by Kamil only)
- Personalized scoring weights — engine can be biased toward Kamil's actual trading style, sector preferences, and risk tolerance
- Semi-automated execution coupling (engine signal → broker order with minimal human latency) — not permitted in v1.2's customer-facing product, fine for personal use

### 2.4 What remains unchanged from v1.2

The entire engine architecture, math, and infrastructure continue to apply:

- Two-tier AI pipeline (FinBERT Tier 1 + Claude Tier 2)
- Cross-source divergence metric (A7.1)
- Rhyme Engine with DTW + significance gate (A7.3)
- Deterministic regime-weighted scoring normalization (A7.4)
- Source tier system A/B/C/D (A8)
- Entity resolution (A9.3)
- PostgreSQL + TimescaleDB schema (A10.2)
- Kill-switches (B10.3) — particularly the drawdown kill-switches which matter *more* in Stage 1 because this is real money, not customer-managed money
- Cost caps on Tier 2 Claude calls, GPU compute, total monthly burn
- Trade log as legal evidence artifact (still matters — Kamil may eventually disclose performance to investors or the SEC if Stage 2 fundraises)

### 2.5 Guardrails

"Aggressive ingestion" is not "no ingestion rules." The following lines are not crossed in Stage 1:

1. **No CFAA violations.** Scraping public data is fine; bypassing authentication (credential stuffing, exploiting auth bugs) is federal crime. Hard line.
2. **No insider trading.** Sources must be legally available to the public or to Kamil as a paying subscriber. No material non-public information obtained through improper channels.
3. **No market manipulation.** Engine signals are for Kamil's own decisions, not published to influence others. Trade log remains private until Stage 2.
4. **No reckless IP exposure on sources needed long-term.** Scraping that gets Kamil's IP permanently banned from Seeking Alpha before extracting value is self-defeating. Rate limits, backoff, rotation where responsible.
5. **All kill-switches from v1.2 §B10.3 remain binding.** 25% drawdown pauses equity trading. 40% drawdown pauses PM. Project-level STOP after 2 PAUSE cycles. The capital engine must not be a capital destruction engine.

### 2.6 Exit criteria (when Stage 1 ends)

Stage 1 transitions to Stage 2 when *either* of these is true:

- **Success:** Combined equity + PM bankroll reaches $500K+, with measured 90-day directional hit rate ≥60%, and Kamil elects to productize.
- **Pivot:** Stage 1 either succeeds and funds other ventures (Forkcast, Qtrade) to sufficient scale that Stage 2 becomes lower priority, or fails to hit its targets and the project is archived or restructured.

**There is no guaranteed transition.** Stage 1 succeeding does not mandate Stage 2. Stage 2 is a separate strategic decision made with Stage 1 capital in hand.

## 3. Stage 2 — Commercial Sentiment Intelligence Platform

### 3.1 Goal
Ship the multi-industry sentiment engine described in `PRD_v1.2.md`. Sell API access, white-label deployments, and custom industry modules to institutional and developer customers. Funded initially by Stage 1 P&L; later by revenue and, if warranted, outside capital.

### 3.2 Relationship to Stage 1 codebase
Stage 2 is a **fork and prune**, not a continuation:

- Core engine, schema, and scoring math: **kept** (this is the reusable investment)
- Ingestion adapters: **audited and pruned** (ToS-gray sources removed or replaced with licensed equivalents)
- Personalized scoring weights: **reset to defaults**
- Stage-1-specific execution coupling: **removed** (Stage 2 is decision support, not execution)
- Legal framework from v1.2 §A14: **reinstated in full**
- Publisher's exemption posture: **reinstated**
- CI citation linter: **reinstated**
- SLOs, observability, security hardening: **fully applied** (these were relaxed in Stage 1)
- Multi-industry modules: **priority resumes** (second module chosen based on Stage 1 learnings)

### 3.3 Timing
Stage 2 planning begins no earlier than Stage 1 exit. No Stage 2 sprints exist in the tracker until that point. Placeholder only.

## 4. What this means for in-flight work

**Sprint 2 (in progress as of April 19, 2026):** continues with SEC EDGAR as second adapter. EDGAR is Stage-1-and-Stage-2 clean (free, public-domain, ToS-unambiguous). No rework.

**Sprint 3 onward:** re-planned under Stage 1 framing. Expect the following sprint-level changes:

- New sprint type: **aggressive ingestion sprints** (Substack paid, SA scraping, podcast transcription at scale)
- New sprint: **execution coupling** (engine → broker semi-automation). May intersect with Qtrade depending on how that project evolves.
- Removed sprint: **public launch preparation** (marketing, onboarding, billing)
- Deferred sprints: **multi-industry module #2** (real estate or auto) — pushed to Stage 2
- The existing Sprint 4 (Grafana) keeps its shape but targets "ugly dashboards for Kamil" instead of "customer-facing observability"

Detailed sprint-by-sprint updates live in `docs/SPRINT_TRACKER.md`, not here.

## 5. Legal posture (plain-English)

Stage 1 is a personal trading tool. Kamil trading his own money, using data he legally has access to, making his own decisions, is:

- Not investment advising (no external clients)
- Not publishing (no public signal distribution)
- Not an unregistered security (no investors in the engine itself)
- Not market manipulation (not attempting to move prices)

ToS violations from aggressive scraping are civil contract matters, not criminal matters, and the damages model for personal-use-only breach is generally limited. Kamil accepts this risk explicitly.

None of this advice is legal advice. If Stage 1 scales to a point where counsel becomes worthwhile (e.g., six-figure monthly P&L), engaging a securities lawyer is a sprint-level task.

## 6. What this document does NOT change

To be explicit:

- `PRD_v1.2.md` remains the authoritative engine specification
- All math, schema, kill-switches, cost caps, and infrastructure decisions remain
- Sprint 0 and Sprint 1 outputs remain valid
- The trade log remains the proof artifact
- The `ground_rules.md` working agreement remains in force

This document is additive strategic framing, not a rewrite.

---

## Appendix A — Decision log

| Decision | Rationale |
|---|---|
| Two-stage framing | Neither "pure SaaS" nor "pure trading tool" correctly described Kamil's intent; both are true in sequence |
| Stage 1 ToS posture relaxed | Personal-use ingestion doesn't carry the resale liability that a public product would |
| Multi-industry deferred | Stocks are the capital engine; other industries distract from Stage 1 goal |
| No Phase 0 public ritual | Public commitment to performance creates pressure to publish signals early, which is out of scope |
| Kill-switches retained | Stage 1 is real money; capital preservation remains non-negotiable |
| Stage 2 as fork not continuation | Cleaner than trying to "upgrade" Stage 1 into a public product; data source audit is easier as a prune operation |
