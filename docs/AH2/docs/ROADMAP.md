# AlphaHound 2.0 Roadmap

**Status:** Active  
**Program principle:** Infrastructure and evidence quality first; live capital last.

---

## Phase 0 — Program Foundation

### Goals

Create the governance that allows ChatGPT to act as Program Manager and Claude to implement safely through filesystem MCP.

### Deliverables

- AH2 repository/folder structure
- `ARCHITECTURE.md`
- `CURRENT_STATE.md`
- `ROADMAP.md`
- `CLAUDE.md`
- ADR framework
- task framework
- review framework

### Exit criteria

- documentation committed to Git
- Claude can locate and read all program documents
- no AH2 implementation begins outside a documented task

---

## Phase 1 — Azure Foundation

### Goals

Replace Windows Task Scheduler architecture with Azure-native orchestration without changing financial strategy logic.

### Deliverables

- Azure Functions project structure
- timer-triggered ingestion function skeleton
- convergence scheduling skeleton
- Azure Service Bus integration
- PostgreSQL configuration
- Key Vault integration
- Application Insights
- correlation IDs
- retry/idempotency framework
- health checks
- local/dev configuration
- CI test path where available

### Initial task

`AH2-001 — Azure Foundation & Project Skeleton`

### Exit criteria

- deployable Azure Function baseline
- queue message round trip works
- Postgres connectivity works
- secrets not in code
- structured logging works
- no trading behavior changed

---

## Phase 2 — Data & Event Architecture

### Goals

Create normalized contracts for source data and evidence.

### Deliverables

- source/event schema
- evidence schema
- provider registry
- adapter interface
- AH1 adapter reuse map
- ingestion idempotency
- deduplication
- source provenance
- source quality metadata
- replay support

### Candidate task sequence

- AH2-002 Event & Evidence Schema
- AH2-003 Adapter Contract
- AH2-004 Migrate First AH1 Adapter
- AH2-005 Event Replay / Idempotency

---

## Phase 3 — Model Gateway & Intelligence

### Goals

Decouple all model inference from application code.

### Deliverables

- Model Gateway API/service
- model registry
- Azure CPU provider
- Azure GPU provider
- optional local Mac provider interface
- structured output validation
- model/version logging
- FinBERT migration/reuse
- embeddings
- entity/event extraction
- evidence classification

### Exit criteria

Same task can run through multiple providers without changing caller logic.

---

## Phase 4 — Probability Engine

### Goals

Move from heuristic score-only decisions toward calibrated explicit probabilities.

### Deliverables

- prediction target definitions
- feature assembly
- baseline probability models
- confidence handling
- outcome tracking
- Brier score
- log loss
- calibration curves
- backtest/replay framework
- historical analog framework
- model comparison

### Important rule

Convergence score remains available as a feature; it is not assumed to be the final decision model.

---

## Phase 5 — Opportunity Engine

### Goals

Convert predictions into economically meaningful opportunity assessments.

### Deliverables

- market-implied probability normalization
- fair value comparison
- fee model
- spread/slippage model
- liquidity filters
- model uncertainty adjustment
- expected value
- opportunity ranking
- `TRADE_CANDIDATE` / `PASS`

---

## Phase 6 — Kalshi Research Engine

### Goals

Use AH2 probability infrastructure against Kalshi markets before execution.

### Deliverables

- Kalshi market ingestion
- order book history
- market probability history
- rules/resolution ingestion
- Resolution Parser
- ambiguity score
- category mapping
- evidence gathering by market
- fair-value calculation
- opportunity scanner
- research dashboard/API

### Exit criteria

AH2 can rank Kalshi markets by measured potential mispricing with full evidence and no live execution.

---

## Phase 7 — Shared Risk & Compliance

### Goals

Build deterministic controls before any new autonomous venue is promoted.

### Deliverables

- hard exposure limits
- per-trade limits
- daily loss
- drawdown
- concentration
- correlation exposure
- kill switch
- stale-signal protection
- compliance provenance
- self-trade prevention
- venue/account restrictions
- audit records

---

## Phase 8 — Kalshi Demo Executor

### Goals

Test end-to-end autonomous event-contract trading without live capital.

### Deliverables

- deterministic `BUY_YES / BUY_NO / PASS`
- Kalshi demo API
- idempotent orders
- reconciliation
- order/fill state machine
- monitoring
- market settlement handling
- outcome capture
- P&L reporting

### Promotion path

Demo -> shadow live -> limited live capital only after explicit approval.

---

## Phase 9 — Equity Executor

### Goals

Use the same intelligence/probability layer for equities.

### Initial bias

Prefer simple autonomous behavior first:

- LONG
- CASH

### Deliverables

- equity opportunity translation
- execution
- exits
- reconciliation
- risk integration
- paper trading
- performance comparison against Kalshi and AH1 options

---

## Phase 10 — Commodities / Futures

### Goals

Add commodity-specific data, models, and execution only after the platform foundation is proven.

### Deliverables

- EIA/USDA/NOAA sources
- futures/curve data
- inventory/supply models
- cross-market features
- commodity-specific probability targets
- paper futures execution
- risk/margin framework

---

## Phase 11 — Options AH2 Executor

### Goals

Reintroduce options as an execution choice rather than AlphaHound's identity.

### Required before promotion

- live option chain
- implied volatility
- Greeks
- liquidity/spread filters
- reliable multi-leg execution
- reconciliation
- deterministic exits

Run in paper mode until statistically justified against simpler instruments.

---

## Phase 12 — AlphaHound Markets

### Goal

Evaluate a commercial analytics/research product built on the same intelligence infrastructure.

### Potential product

- Kalshi/event-market scanner
- AlphaHound fair probability
- market implied probability
- edge
- confidence
- evidence
- catalyst timeline
- rules
- historical calibration
- alerts

### Legal posture

Research/standardized analytics first.

Personalized advice or delegated customer execution requires explicit regulatory/legal work before implementation.

---

# Program priorities

When conflicts occur, prioritize:

1. Data correctness
2. Reproducibility
3. Risk safety
4. Probability calibration
5. Execution correctness
6. Observability
7. Performance
8. Feature breadth
9. UI polish

---

# What we deliberately are NOT doing first

- rewriting every AH1 adapter
- adding many new signals
- optimizing fixed pillar weights before outcomes justify it
- live Kalshi auto trading
- live futures trading
- live options AH2 execution
- consumer account auto trading
- tying AH2 to the local Mac
- introducing non-Azure infrastructure without a measured need
