# AlphaHound 2.0 — Step-by-Step Implementation Playbook

**Document:** `AH2/docs/IMPLEMENTATION_PLAYBOOK.md`  
**Status:** ACTIVE / CONTROLLING BUILD DOCUMENT  
**Business Owner:** Kamil  
**Program Manager / Principal Architect:** ChatGPT  
**Primary Engineering Agent:** Claude Chat + Filesystem MCP  
**Platform:** Microsoft Azure  
**Primary Database:** PostgreSQL  
**Primary Storage:** Azure Storage  

---

# 1. Purpose

This document controls the implementation sequence for AlphaHound 2.0 (AH2).

AH2 will be built in **small, gated steps**.

We do **not** proceed to the next step until:

1. The current step is complete.
2. Its validation checks pass.
3. ChatGPT reviews the result.
4. Kamil explicitly approves proceeding.

Claude must not work ahead.

---

# 2. Current Starting Position

The following are already available:

- Microsoft Azure environment
- Azure PostgreSQL database
- Azure Storage
- Existing AlphaHound 1.x codebase
- Existing AH1 data/integrations/code that may be reused selectively
- Existing AlphaHound architecture and trading research
- AH2 architecture documentation
- Claude Chat + Filesystem MCP workflow
- Git repository for version control

Current paid external subscriptions have been cancelled.

They will be reactivated **only when a specific AH2 step requires them**.

Examples may include:

- market-data providers
- Unusual Whales
- Quiver
- premium news/data feeds
- model/API providers
- broker/exchange services

Do not reactivate subscriptions early.

---

# 3. Scheduler Decision

## AH2 Default

**Azure Functions is the default scheduler and orchestration mechanism.**

Windows Task Scheduler will not be used for AH2 production workflows.

Possible narrow exceptions must be documented and explicitly approved.

Examples of acceptable exceptions might include:

- temporary local development utility
- one-time maintenance operation
- local machine-only diagnostic task

No business-critical AH2 process should depend on Windows Task Scheduler.

---

# 4. AH1 Protection Rule

AH1 remains intact.

Do not:

- remove AH1 scheduled jobs yet
- alter AH1 trading logic
- alter AH1 production tables destructively
- change AH1 API credentials
- repurpose AH1 production infrastructure without approval

AH1 is the reference system while AH2 is built.

AH2 is developed beside it.

---

# 5. Program Workflow

Every step follows:

```text
DESIGN STEP
    |
CHATGPT DEFINES REQUIREMENTS
    |
KAMIL APPROVES STEP
    |
CLAUDE IMPLEMENTS ONLY THAT STEP
    |
CLAUDE DOCUMENTS RESULTS
    |
CHATGPT REVIEWS
    |
KAMIL APPROVES
    |
NEXT STEP
```

Claude must never infer approval to continue.

---

# 6. Implementation Phases

AH2 will be implemented in the following gated sequence.

---

# STEP 0 — Confirm AH2 Repository & Documentation Structure

## Goal

Establish the project control structure before code changes.

## Required structure

```text
AH2/
  README.md
  CLAUDE.md

  docs/
    ARCHITECTURE.md
    CURRENT_STATE.md
    ROADMAP.md
    IMPLEMENTATION_PLAYBOOK.md
    PROGRAM_GOVERNANCE.md

    adr/
    plans/
    tasks/
    reviews/
```

## Claude work

None initially unless files need to be placed into the repository.

## Validation

Confirm:

- AH2 folder exists
- documentation is committed to Git
- Claude can read it through filesystem MCP
- AH1 and AH2 are clearly separated

## STOP / GO

**STOP after validation.**

Do not begin Azure development until Kamil approves Step 1.

---

# STEP 1 — Inventory Existing AH1 Scheduled Processes

## Goal

Understand exactly what the current system runs automatically.

The internal documentation describes:

- ingestion approximately every 5 minutes
- scoring / convergence approximately every 15 minutes
- execution following convergence during applicable market hours
- trade logging
- other supporting/monitoring processes may exist

We must inspect the actual repository and current server/task definitions rather than assume documentation is complete.

## Deliverable

Create:

`AH2/docs/AH1_SCHEDULER_INVENTORY.md`

For every automated process record:

| Field | Required |
|---|---|
| Task name | Yes |
| Current scheduler | Yes |
| Schedule/cadence | Yes |
| Script/module | Yes |
| Command/arguments | Yes |
| Inputs | Yes |
| Database tables used | Yes |
| External services used | Yes |
| Outputs | Yes |
| Dependencies | Yes |
| Failure behavior | Yes |
| Retry behavior | Yes |
| Can run concurrently? | Yes |
| AH2 disposition | Yes |

AH2 disposition must be one of:

- MIGRATE TO AZURE FUNCTION
- EVENT DRIVEN
- DURABLE WORKFLOW
- REMOVE
- KEEP TEMPORARILY IN AH1
- NEEDS REVIEW

## Important

Do not migrate anything during this step.

This step is inspection only.

## Validation

ChatGPT reviews the scheduler inventory against:

- AH1 documentation
- actual repo code
- actual scheduled task definitions available to Claude

## STOP / GO

**STOP.**

Kamil approves the migration map before Step 2.

---

# STEP 2 — Confirm Azure Resource Baseline

## Goal

Document what Azure resources already exist and what AH2 still needs.

## Existing resources expected

- Azure subscription
- resource group(s)
- PostgreSQL
- Azure Storage

## Inspect / confirm

Document:

- Azure region
- resource groups
- PostgreSQL server/database names
- networking configuration
- Storage account
- current App Service / VM resources if any
- Key Vault if already present
- Application Insights if already present
- Function Apps if already present
- Service Bus if already present
- Container Apps environment if already present

## Deliverable

Create:

`AH2/docs/AZURE_RESOURCE_BASELINE.md`

Do not place secrets in the document.

## Decision output

For each resource:

```text
EXISTS
CREATE
REUSE
REPLACE
NOT NEEDED YET
```

## STOP / GO

**STOP.**

No resources are provisioned until the baseline is reviewed.

---

# STEP 3 — Create AH2 Development Environment

## Goal

Create an isolated AH2 development environment without affecting AH1.

## Preferred naming concept

Exact names will be chosen after reviewing existing Azure conventions.

Conceptually:

```text
ah2-dev-functions
ah2-dev-servicebus
ah2-dev-insights
ah2-dev-keyvault
ah2-dev-containerapps
```

PostgreSQL may use the existing server with a dedicated AH2 database/schema if appropriate.

## Requirements

- AH2 development isolation
- no AH1 production impact
- least-privilege access
- no secrets in source
- clear environment naming

## Claude work

Claude may create Infrastructure-as-Code or documented provisioning steps only after this step is explicitly approved.

## Validation

Verify:

- environment separation
- connectivity
- identity/permissions
- logging
- cost controls

## STOP / GO

**STOP.**

---

# STEP 4 — Azure Functions Foundation

## Goal

Establish AH2's replacement for Windows Task Scheduler.

## Build

Python Azure Functions foundation supporting:

- Timer Trigger
- Service Bus Trigger
- HTTP health endpoint if useful
- shared configuration
- correlation IDs
- structured logging
- PostgreSQL connection layer
- dependency injection/service separation where practical

## Initial test workflow

```text
Timer Function
    |
    v
Publish test event
    |
    v
Azure Service Bus
    |
    v
Queue-triggered Function
    |
    v
Structured success log
```

No trading logic.

No model logic.

No external paid market data.

## Validation

Must demonstrate:

- timer executes
- message publishes
- consumer receives it
- correlation ID survives
- retries behave correctly
- failures are visible
- test suite passes

## STOP / GO

**STOP.**

This is the first major Claude implementation step.

---

# STEP 5 — Service Bus Event Contract

## Goal

Define the event language used throughout AH2.

## Initial event types

```text
DATA_RECEIVED
EVIDENCE_PROCESSED
SIGNAL_DETECTED
PROBABILITY_UPDATED
OPPORTUNITY_DETECTED
RISK_APPROVED
RISK_REJECTED
COMPLIANCE_APPROVED
COMPLIANCE_REJECTED
ORDER_REQUESTED
ORDER_SUBMITTED
ORDER_FILLED
POSITION_CHANGED
MARKET_RESOLVED
MODEL_DRIFT_DETECTED
```

## Standard event envelope

Every event should contain at minimum:

```text
event_id
event_type
correlation_id
source
created_at
schema_version
payload
```

## Requirements

- versioned schemas
- idempotency support
- replay-safe design
- dead-letter strategy

## STOP / GO

**STOP after contract review.**

---

# STEP 6 — AH2 PostgreSQL Schema Foundation

## Goal

Create AH2-native data structures without damaging AH1.

## Initial domains

- raw source events
- normalized evidence
- features
- models / model versions
- predictions
- probabilities
- market states
- opportunities
- risk decisions
- compliance decisions
- orders
- fills
- positions
- outcomes
- audit events

## Important

Do not copy every AH1 table into AH2.

The new schema should reflect AH2 architecture.

## Migration policy

- additive
- version controlled
- reversible where practical
- tested
- no destructive AH1 changes

## STOP / GO

**STOP after schema review.**

---

# STEP 7 — Migrate One Existing Data Source

## Goal

Prove AH1-to-AH2 ingestion migration using one source.

Do not migrate all sources at once.

## Selection criteria

Choose:

- currently understood
- inexpensive/free if possible
- useful for testing
- representative of other adapters

## Flow

```text
Azure Function
    |
External Source
    |
Normalize
    |
PostgreSQL
    |
DATA_RECEIVED event
```

## Required capabilities

- retries
- timeout
- deduplication
- source timestamp
- ingestion timestamp
- provenance
- correlation ID

## STOP / GO

**STOP and review before migrating source #2.**

---

# STEP 8 — Standard Evidence Layer

## Goal

Turn raw source records into normalized evidence.

## Evidence should support

- entity
- event
- asset/market mapping
- timestamp
- source
- source quality
- structured facts
- sentiment when relevant
- evidence text/reference
- confidence

## Important

This becomes shared infrastructure for:

- equities
- Kalshi
- commodities
- options

## STOP / GO

**STOP after evidence contract review.**

---

# STEP 9 — Model Gateway

## Goal

Create a provider-neutral interface for AI/ML inference.

## Initial providers

Start only with what is needed.

Possible:

```text
AZURE_CPU
AZURE_GPU
LOCAL_MAC
EXTERNAL_API
```

The local Mac will be added when it arrives.

AH2 must not depend upon it.

## Required logging

Every inference records:

- provider
- model
- version
- input/evidence references
- result
- confidence
- timestamp
- latency
- cost where available

## STOP / GO

**STOP.**

Do not deploy multiple open-source models simply because they are available.

---

# STEP 10 — Migrate / Validate FinBERT

## Goal

Move proven sentiment functionality behind the Model Gateway.

## Validation

Compare AH1 and AH2 on the same fixed sample.

Measure:

- result consistency
- throughput
- latency
- resource usage
- cost

## Decision

Only after benchmarking decide whether FinBERT runs on:

- Azure CPU
- Azure GPU
- local Mac later

## STOP / GO

**STOP after benchmark.**

---

# STEP 11 — Probability Engine Baseline

## Goal

Create the first explicit probability framework.

Do not begin with a giant AI model.

Start with measurable baselines.

Potential approaches:

- logistic regression
- LightGBM
- XGBoost
- Bayesian models
- calibrated classifiers

## Must persist

- target definition
- features
- model/version
- probability
- timestamp
- outcome
- calibration metrics

## Metrics

- Brier Score
- log loss
- calibration
- hit rate where relevant

## STOP / GO

**STOP after baseline evaluation.**

---

# STEP 12 — AlphaHound Lab / Replay Framework

## Goal

Make every strategy test reproducible.

Lifecycle:

```text
IDEA
-> HYPOTHESIS
-> BACKTEST
-> PAPER
-> SHADOW LIVE
-> LIMITED CAPITAL
-> PRODUCTION
```

## Critical requirement

Historical testing must only use information that would have been available at that historical point.

## STOP / GO

**STOP after first reproducible experiment.**

---

# STEP 13 — Kalshi Research Integration

## Goal

Add Kalshi as a probability research venue.

No real-money auto execution.

## Build

- market discovery
- market metadata
- market price/probability
- order book where useful
- market rules
- resolution source
- settlement date
- category mapping

## Subscription/API decision

Only reactivate/create required Kalshi access at this step.

## STOP / GO

**STOP after data/research integration.**

---

# STEP 14 — Kalshi Resolution Parser

## Goal

Convert Kalshi contract language into structured rules.

Persist:

```text
event_definition
resolution_source
deadline
threshold
exceptions
ambiguity_score
```

High ambiguity:

```text
PASS
```

## AI role

AI may interpret contract language.

Deterministic validation decides whether market is eligible.

## STOP / GO

**STOP after evaluation set review.**

---

# STEP 15 — Kalshi Fair Probability / Opportunity Engine

## Goal

Calculate:

```text
AlphaHound fair probability
vs
Kalshi implied probability
```

Then adjust for:

- uncertainty
- fees
- spread
- liquidity
- time to resolution

Output:

```text
TRADE_CANDIDATE
PASS
```

Still no live execution.

## STOP / GO

**STOP after paper/research results.**

---

# STEP 16 — Shared Deterministic Risk Engine

## Goal

Create the capital-control layer.

Controls:

- maximum risk per trade
- maximum exposure
- category/asset exposure
- correlation exposure
- cash reserve
- daily loss
- drawdown
- liquidity
- kill switch

AI does not override these limits.

## STOP / GO

**STOP after risk tests.**

---

# STEP 17 — Compliance Gate

## Goal

Create an auditable pre-execution compliance layer.

Checks include:

- public-data provenance
- restricted market/person conditions
- influence/conflict conditions
- exchange limits
- self-trade protection
- market-rule confidence
- account status

## STOP / GO

**STOP after review.**

---

# STEP 18 — Kalshi Demo Executor

## Goal

Execute only against Kalshi demo/test environment.

## Required

- deterministic instructions
- idempotent submission
- reconciliation
- fill tracking
- monitor positions
- resolution
- P&L
- audit trail

## No live capital.

## STOP / GO

**STOP after sufficient demo evidence.**

---

# STEP 19 — Equity Research / Paper Executor

## Goal

Apply the same intelligence system to equities.

Initial preference:

```text
LONG
CASH
```

Keep the initial implementation simpler than AH1 options.

## Comparison

Run identical signals through:

- equity paper executor
- AH1/options research comparison where appropriate

Measure:

- return
- volatility
- drawdown
- Sharpe/Sortino
- hit rate
- expectancy
- slippage

## STOP / GO

**STOP after statistical review.**

---

# STEP 20 — Commodities Research

## Goal

Begin commodity-specific modeling only after the core platform proves itself.

Potential sources:

- EIA
- USDA
- NOAA
- futures data
- inventory
- production
- shipping
- macro
- FX
- related equities

No futures live execution until separately approved.

---

# STEP 21 — Optional Local Mac Integration

## Goal

Add the Mac as an optional inference worker.

The Mac must use the same Model Gateway interface.

Use for:

- Hugging Face models
- MLX
- experimentation
- private inference
- cost optimization

## Required fallback

If Mac unavailable:

```text
route to Azure
```

No business-critical dependency on home hardware.

---

# STEP 22 — Options AH2

## Goal

Reintroduce options only after AH2 predictive edge is demonstrated.

Required improvements over AH1:

- live option chain
- implied volatility
- Greeks
- liquidity checks
- spread validation
- multi-leg execution handling
- deterministic exits
- reconciliation

Paper first.

---

# STEP 23 — AlphaHound Markets Product Evaluation

## Goal

Evaluate commercial research/analytics product.

Potential product:

- market scanner
- AlphaHound fair probability
- market implied probability
- edge
- confidence
- evidence
- catalysts
- historical calibration
- alerts

Initial scope:

**research / analytics**

Not:

- personalized portfolio sizing
- customer-account auto execution

Legal/regulatory review happens before entering those areas.

---

# 7. Subscription Reactivation Policy

Current subscriptions remain cancelled.

Before reactivating any subscription, document:

```text
PROVIDER
PURPOSE
STEP REQUIRING IT
EXPECTED MONTHLY COST
EXPECTED DATA/FEATURE VALUE
ALTERNATIVE FREE/EXISTING SOURCE
APPROVAL
```

Do not subscribe because a provider "might be useful."

Every subscription must have an immediate AH2 use case.

---

# 8. Claude Operating Rule

Claude receives only the currently approved step.

Example:

> Read the AH2 architecture, current state, roadmap, implementation playbook, CLAUDE.md, and all accepted ADRs. We are currently authorized for STEP 1 only. Complete STEP 1 exactly as written. Do not implement STEP 2 or later steps.

Claude must update the step's required artifact.

Claude does not move forward independently.

---

# 9. ChatGPT Program Manager Review

After each step, ChatGPT reviews:

- architecture alignment
- completeness
- code quality
- hidden coupling
- scope expansion
- security
- Azure patterns
- retry/idempotency
- database impact
- observability
- trading-risk implications
- test coverage

The next step is not authorized until review is complete.

---

# 10. Current Program Status

As of this document:

```text
STEP 0 — Documentation / Repository Structure
STATUS: READY TO VALIDATE

STEP 1 — AH1 Scheduler Inventory
STATUS: NEXT

ALL OTHER STEPS
STATUS: NOT AUTHORIZED
```

The immediate next action is:

> **Validate Step 0, then authorize Claude only for Step 1: AH1 Scheduler Inventory.**

No Azure Functions should be written until the existing scheduled workload is fully inventoried and the migration map is reviewed.
