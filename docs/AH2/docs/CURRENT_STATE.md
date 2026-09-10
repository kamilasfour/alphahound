# AH2 — Current State / AH1 Baseline

**Purpose:** Define the validated starting point from which AlphaHound 2.0 will be built.

**Rule:** AH1 remains intact while AH2 is developed beside it.

---

## 1. Validated AH1 platform state

The existing AlphaHound system is a live/paper autonomous options trading engine built around convergence detection.

Validated platform characteristics:

- Python 3.11
- FastAPI
- TimescaleDB / PostgreSQL
- Alpaca paper trading
- Windows Server 2022
- approximately 1,025 tickers scanned
- ingestion every ~5 minutes
- scoring/convergence every ~15 minutes
- FinBERT sentiment processing
- seven-pillar convergence scoring
- options structure recommendation
- automated paper order placement
- dashboard visibility
- trade-context logging

The current system is operational enough to serve as a reference implementation and source of reusable components.

---

## 2. Existing AH1 data pipeline

Validated ingestion sources include:

- ApeWisdom / Reddit
- Unusual Whales
- Quiver Quantitative
- Finnhub
- Polygon
- Substack
- Kalshi
- Yahoo Finance
- Earnings calendar
- FDA/PDUFA-related event calendar

AH1 documentation indicates approximately 73,000 posts/items can be processed in a 24-hour period.

### AH2 disposition

**KEEP / REUSE CONCEPTUALLY**

- source adapters where stable
- normalized source timestamps
- provider authentication patterns
- proven ingestion logic
- source-specific transforms

**REFACTOR**

- scheduling/orchestration into Azure Functions
- event propagation into Service Bus
- shared normalized event/evidence contracts
- correlation IDs / observability
- retries/timeouts/idempotency standards

---

## 3. Existing AH1 scoring/intelligence

AH1 uses FinBERT to score new content from -1.0 bearish to +1.0 bullish.

Current convergence logic evaluates seven pillars on a 0 / 0.5 / 1.0 basis with a nonlinear convergence boost.

Validated pillars include:

- liquidity/scalability
- unusual options flow
- congressional activity
- government contract signals
- social velocity
- meta-convergence
- catalyst
- quant momentum

A Super Signal currently requires:

- composite >= 4.0
- 4+ pillars
- catalyst present
- catalyst generally 14-45 days away

### AH2 disposition

**KEEP**

- explainable evidence-backed signals
- convergence as a research feature
- catalyst awareness
- stricter source-specific gating
- ability to preserve why a signal fired

**REFACTOR**

- convergence becomes one feature family, not the sole definition of alpha
- pillar independence must be empirically validated
- fixed weights/boosts should eventually be challenged by outcome data
- explicit probability models should sit above/beside heuristic scores
- congressional activity should be modeled separately from true institutional flow

---

## 4. Existing market/data tables referenced by AH1

Validated tables referenced by the current convergence scan:

- `options_flow`
- `institutional_positions`
- `sentiment_scores`
- `price_snapshots`
- `earnings_calendar`
- `pdufa_calendar`

Validated output/logging tables include:

- `convergence_signals`
- `options_trade_log`

### AH2 disposition

**KEEP**

PostgreSQL as system of record.

**REFACTOR**

Create normalized AH2 schemas around:

- source events
- evidence
- features
- predictions
- probabilities
- opportunities
- risk decisions
- compliance decisions
- orders/fills
- outcomes
- model versions

Do not migrate/rename AH1 tables destructively during initial AH2 work.

---

## 5. Existing AH1 options structure engine

When a Super Signal is detected, AH1:

1. reads current price
2. calculates 30-day historical volatility
3. applies Black-Scholes
4. selects a structure
5. selects strikes and expiration
6. stores the plan alongside the signal

Structures include spreads/strangles.

### Known limitation

Pricing is based on historical volatility rather than live implied-volatility chain data.

AH1 documentation explicitly warns that estimated option prices can differ materially from tradable prices, particularly near earnings.

### AH2 disposition

**KEEP FOR RESEARCH/PAPER REFERENCE**

- structure-selection ideas
- Black-Scholes utilities where technically correct
- option-specific test cases
- full trade-plan persistence

**DO NOT MAKE CORE TO AH2**

Options are one executor, not AlphaHound's identity.

---

## 6. Existing AH1 execution

AH1 currently executes paper options orders through Alpaca.

Validated execution guards include:

- macro `RISK_OFF`
- market hours
- signal freshness (<20 minutes)
- duplicate ticker/day guard
- cash floor
- Super Signal gate
- position sizing
- catalyst requirement

Current target position risk is approximately 2% of equity, capped by contract rules.

### Known issue

The documented sizing logic can round zero contracts up to one, allowing actual maximum loss to exceed the nominal 2% target.

### AH2 disposition

**KEEP**

- deterministic execution
- stale-signal guard
- duplicate-order concept
- macro gating concept
- cash/exposure controls
- full order logging

**REPLACE / HARDEN**

- idempotency must be explicit and infrastructure-safe
- risk limits become true hard limits
- reconciliation becomes first-class
- execution separated from strategy
- Service Bus should carry approved order requests
- Azure Functions replace Task Scheduler
- no LLM directly submits orders

---

## 7. Existing AH1 orchestration

Current AH1 production/paper workflow is scheduled using Windows Task Scheduler.

Validated cadence:

- ingestion: every ~5 minutes
- scoring/convergence: every ~15 minutes
- convergence scan of ~1,025 tickers: ~90 seconds in documented state

### AH2 disposition

**REPLACE**

Windows Task Scheduler is not part of the AH2 production architecture.

Target:

- Azure Functions
- Service Bus
- Durable Functions/Durable Task where workflow state is useful
- Application Insights
- structured retries
- correlation IDs
- poison/dead-letter handling

---

## 8. Existing AH1 exit management

Current documentation says:

- position opening is automated
- winning position close remains manual
- live option chain/strike verification remains manual
- automatic close logic was planned but not yet complete

### AH2 disposition

Do not promote any executor to live capital until:

- entry is deterministic
- exit is deterministic
- reconciliation exists
- kill switch exists
- monitoring exists
- stale/replay protection exists
- paper/demo/shadow evidence is sufficient

---

## 9. Existing AH1 learning capability

`options_trade_log` records:

- signal context
- pillars
- score
- catalyst
- order context
- eventual P&L when closed

The existing concept already anticipates measuring per-pillar win rates and tuning thresholds from outcomes.

### AH2 disposition

**STRONGLY KEEP AND EXPAND**

This becomes the foundation of the AH2 Learning/Calibration dataset.

AH2 should persist the complete chain:

```text
SOURCE
-> EVIDENCE
-> FEATURES
-> MODEL/VERSION
-> PROBABILITY
-> MARKET PRICE
-> OPPORTUNITY
-> RISK
-> COMPLIANCE
-> ORDER
-> FILL
-> OUTCOME
```

---

## 10. KEEP / REFACTOR / REPLACE / REMOVE / NEW

### KEEP

- Python
- FastAPI where useful
- PostgreSQL/Timescale concepts
- working source adapters
- FinBERT capability
- convergence concept
- catalyst awareness
- evidence-backed explainability
- market-data integration patterns
- trade-context logging
- Alpaca integration as a reusable executor reference
- Kalshi adapter/source work already present
- current data as historical research input

### REFACTOR

- adapters into common ingestion contracts
- convergence into a feature family
- scoring into probability-oriented architecture
- data schema into event/evidence/prediction/outcome structure
- execution guards into shared deterministic Risk Engine
- signal logging into full provenance
- option/congressional terminology
- asynchronous processing around queues/events

### REPLACE

- Windows Task Scheduler -> Azure Functions
- tightly coupled workflow -> Service Bus + discrete services/functions
- direct model usage -> Model Gateway
- strategy-coupled execution -> Execution Router + venue executors
- loose retry behavior -> explicit retry/idempotency/dead-letter patterns
- nominal risk targets that can be exceeded -> hard deterministic limits

### REMOVE FROM AH2 CORE

- assumption that options are the primary/required execution instrument
- assumption that fixed pillar count alone proves independent convergence
- requirement that a single composite score be the final decision variable
- any LLM-to-order direct path

### NEW FOR AH2

- Azure Functions
- Durable workflows
- Azure Service Bus
- Model Gateway
- explicit Probability Engine
- calibration framework
- Opportunity Engine
- shared Risk Engine
- Compliance Gate
- Equity Executor
- Kalshi Executor
- Futures/Commodity Executor
- Options Executor as separate downstream venue
- Kalshi Resolution Parser
- AlphaHound Lab
- formal experiment lifecycle
- full observability
- model registry/versioning
- consumer research product possibility (`AlphaHound Markets`)

---

## 11. Current-state confidence

This document records validated behavior-level AH1 capabilities from the available internal system documentation and prior program review context.

Before individual AH1 source files are reused in AH2, Claude must inspect the current repository implementation and document the exact source path, dependencies, tests, and reuse decision in the applicable AH2 task.

AH2 must not assume that a documented AH1 behavior maps cleanly to a single reusable module.

---

## 12. Immediate conclusion

Do not rebuild the useful intellectual property from scratch.

Do not refactor AH1 in place.

Build AH2 beside AH1.

Reuse proven adapters, data concepts, scoring utilities, model code, integrations, and historical data selectively after source-level verification.

The architectural migration begins with infrastructure and contracts—not with changing the trading thesis.
