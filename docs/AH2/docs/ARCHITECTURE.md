# AlphaHound 2.0 — Master Architecture

**Status:** Living Architecture  
**Platform:** Microsoft Azure  
**Primary Database:** PostgreSQL  
**Primary Language:** Python  
**Architecture name:** AH2

---

## 1. Vision

AlphaHound is evolving from an automated options convergence system into a cross-market intelligence and probability platform.

The core question becomes:

> Where does AlphaHound's estimated probability or expected return differ materially from what the market currently implies?

AH2 must support the same intelligence layer across multiple execution venues:

- Equities
- Kalshi
- Commodities / Futures
- Options
- ETFs
- Crypto where appropriate

The trading venue is downstream from the intelligence and probability engines.

---

## 2. Core architectural principles

### 2.1 Azure is the permanent cloud platform

AH2 remains Azure-native.

Primary services:

- Azure Functions
- Durable Functions / Durable Task where useful
- Azure Service Bus
- Azure Container Apps
- Azure Container Apps GPU where useful
- Azure Database for PostgreSQL
- Azure Key Vault
- Azure Application Insights
- Azure Storage
- Azure Container Registry

### 2.2 PostgreSQL is the system of record

Authoritative state belongs in PostgreSQL:

- source data
- normalized evidence
- features
- signals
- probabilities
- model versions
- market prices
- opportunity evaluations
- risk decisions
- compliance decisions
- orders
- fills
- positions
- outcomes
- model evaluation data
- audit trails

### 2.3 AH1 remains intact

AH1 is not refactored in place.

AH2 is built beside AH1.

Proven AH1 components may be reused or adapted after review.

### 2.4 AI interprets; deterministic systems control money

AI may:

- classify
- extract
- summarize
- cluster
- retrieve
- interpret contract language
- identify evidence
- assist feature generation

AI must not directly:

- determine unrestricted position size
- bypass risk logic
- bypass compliance logic
- submit orders

### 2.5 All inference goes through a Model Gateway

AH2 application logic must not depend on a specific AI provider, model, GPU provider, or the local Mac.

---

## 3. High-level system

```text
EXTERNAL DATA
     |
     v
DATA INGESTION
     |
     v
POSTGRESQL
     |
     v
SERVICE BUS
     |
     +------------------+
     |                  |
     v                  v
INTELLIGENCE        MARKET STATE
     |                  |
     +--------+---------+
              |
              v
      PROBABILITY ENGINE
              |
              v
      OPPORTUNITY ENGINE
              |
       +------+------+
       |             |
       v             v
    RESEARCH      RISK ENGINE
                      |
                      v
               COMPLIANCE GATE
                      |
                      v
               EXECUTION ROUTER
               /    |    |    \
          Equity  Kalshi Futures Options
```

---

## 4. Data layer

The Data Layer continuously ingests, timestamps, normalizes, deduplicates, and stores source information.

### Existing AH1 source families to evaluate for reuse

- ApeWisdom / Reddit
- Unusual Whales
- Quiver Quantitative
- Finnhub
- Polygon
- Substack
- Kalshi
- Yahoo Finance
- Earnings calendar
- FDA / PDUFA-related calendar data

### Future source families

#### Economics

- Federal Reserve
- FRED / ALFRED
- BLS
- BEA
- U.S. Treasury
- rate/futures-derived market data

#### Commodities

- EIA
- USDA
- NOAA / weather
- inventory data
- production data
- futures curves
- spot pricing
- shipping/logistics
- metals supply/demand

#### Markets

- equities
- options
- futures
- rates
- FX
- crypto
- prediction markets

### Every source record must preserve

- source identifier
- source timestamp
- ingestion timestamp
- raw-content reference
- entities
- market/instrument mapping
- provenance
- source quality/reliability metadata

Historical research must protect against look-ahead bias.

---

## 5. Azure Functions

Windows Task Scheduler is not part of the AH2 production architecture.

Functions should be small, independently testable, idempotent where relevant, and observable.

### Initial function families

#### `IngestMarketData`

- fetch configured feeds
- normalize
- persist
- publish new-data events

#### `IngestKalshi`

- discover markets
- capture contract metadata
- capture pricing/order book
- capture market rules
- capture settlement/resolution metadata

#### `ProcessNewEvidence`

Queue triggered.

- sentiment
- entity extraction
- event extraction
- embeddings
- deduplication
- evidence classification

#### `RunConvergence`

- evaluate reusable convergence signals
- create candidate opportunities
- preserve evidence explaining why a signal exists

#### `CalculateProbability`

- assemble features
- invoke statistical/ML probability model
- persist prediction
- persist model/version/features/evidence

#### `EvaluateOpportunity`

Compare AlphaHound fair value to market-implied value after:

- model uncertainty
- fees
- spread
- liquidity
- slippage
- capital utilization

Output:

- `TRADE_CANDIDATE`
- `PASS`

#### `RiskEvaluation`

- position limits
- concentration
- correlated exposure
- daily loss
- drawdown
- liquidity
- asset-class limits
- cash reserve

#### `ComplianceEvaluation`

- market/account restrictions
- provenance
- influence/conflict checks
- self-trade protection
- exchange limits
- resolution-rule validity

#### `ExecuteOrder`

Queue triggered.

Must receive a deterministic approved order instruction.

- validate idempotency
- validate approvals
- submit order
- persist venue order ID
- emit execution event

#### `MonitorPositions`

- mark-to-market
- exit-rule evaluation
- risk monitoring
- resolution monitoring

#### `ReconcileOrders`

Ensure internal state matches broker/exchange state.

#### `DailyPerformance`

- performance
- calibration
- risk
- model outcomes
- strategy outcomes

---

## 6. Durable workflows

Use Durable Functions / Durable Task for workflows where state, retries, dependencies, fan-out/fan-in, or long-running coordination are important.

Example Kalshi opportunity:

```text
MARKET DISCOVERED
      |
PARSE RULES
      |
GATHER EVIDENCE
      |
+-----+------+------+
|            |      |
MACRO       NEWS   MARKET
MODEL       MODEL  MODEL
|            |      |
+-----+------+------+
      |
PROBABILITY
      |
OPPORTUNITY
      |
RISK
      |
COMPLIANCE
      |
EXECUTE / PASS
      |
MONITOR
      |
RESOLUTION
      |
OUTCOME + CALIBRATION
```

Durable orchestration coordinates state.

Business logic remains in testable activities/services.

---

## 7. Azure Service Bus

Service Bus is the default asynchronous communication layer.

Initial event vocabulary:

- `DATA_RECEIVED`
- `EVIDENCE_PROCESSED`
- `SIGNAL_DETECTED`
- `PROBABILITY_UPDATED`
- `OPPORTUNITY_DETECTED`
- `RISK_APPROVED`
- `RISK_REJECTED`
- `COMPLIANCE_APPROVED`
- `COMPLIANCE_REJECTED`
- `ORDER_REQUESTED`
- `ORDER_SUBMITTED`
- `ORDER_FILLED`
- `POSITION_CHANGED`
- `MARKET_RESOLVED`
- `MODEL_DRIFT_DETECTED`

Benefits:

- decoupling
- retries
- independent scaling
- failure isolation
- observability
- auditability

---

## 8. Intelligence Engine

The Intelligence Engine converts unstructured information into structured evidence.

Capabilities:

- sentiment analysis
- entity extraction
- event extraction
- semantic similarity
- embeddings
- clustering
- reranking
- historical analog retrieval
- rule/contract interpretation
- evidence summarization
- anomaly detection

Existing FinBERT capability should be evaluated for reuse.

---

## 9. Model Gateway

All AI inference must use a provider-neutral gateway.

Conceptual request:

```text
task
model_family
input
context
required_schema
privacy_class
latency_class
```

Conceptual response:

```text
provider
model
model_version
result
confidence
latency_ms
timestamp
```

Potential backends:

- Azure CPU
- Azure Container Apps GPU
- Azure model APIs
- optional local Mac inference
- approved external model API when deliberately selected

AH2 must continue operating when the local Mac is unavailable.

---

## 10. Compute strategy

### CPU

Prefer CPU for models/workloads that do not economically require GPU:

- FinBERT where performance is acceptable
- LightGBM
- XGBoost
- logistic models
- calibration
- statistics
- smaller classifiers

### GPU

Use Azure Container Apps GPU for workloads that materially benefit:

- larger open-source language models
- heavier embeddings/reranking
- experimental inference
- fine-tuning where appropriate

Do not use GPU by default.

### Local Mac

The local Mac is an optional private inference/research node.

It may support:

- local Hugging Face / MLX models
- experimentation
- private inference
- model benchmarks
- development

It is never a hard dependency.

---

## 11. Probability Engine

This is a core strategic component of AH2.

AH2 should increasingly estimate explicit probabilities instead of only bullish/bearish scores.

Examples:

```text
P(Fed cut by date X) = 0.68
P(CPI > threshold) = 0.72
P(WTI > threshold by date X) = 0.61
P(equity > target by date X) = 0.57
```

Persist:

- target/event definition
- probability
- confidence interval where available
- model
- model version
- feature set
- evidence references
- timestamp
- eventual outcome

---

## 12. Calibration

Probability quality must be continuously measured.

Track:

- Brier score
- log loss
- calibration curves
- calibration by confidence bucket
- category-specific calibration
- regime-specific calibration
- realized outcome
- drift

The long-term proprietary asset is the historical record connecting evidence, probability, market price, decisions, and outcomes.

---

## 13. Opportunity Engine

A high probability is not automatically an opportunity.

The engine evaluates:

```text
ALPHAHOUND FAIR VALUE
vs
MARKET IMPLIED VALUE
```

Then adjusts for:

- confidence
- model uncertainty
- fees
- spread
- liquidity
- slippage
- time to resolution
- capital utilization
- portfolio correlation

---

## 14. Market abstraction

Core intelligence must remain execution-venue independent.

```text
ALPHAHOUND CORE
     |
     +--> EQUITY EXECUTOR
     +--> KALSHI EXECUTOR
     +--> FUTURES EXECUTOR
     +--> OPTIONS EXECUTOR
```

---

## 15. Equity Executor

Initial autonomous equity execution should favor simplicity.

Initial research path:

- LONG
- CASH

Shorting may be added later after the core edge is validated.

Executor responsibilities:

- sizing
- order construction
- venue validation
- submission
- fill handling
- exits
- reconciliation

---

## 16. Kalshi Engine

Kalshi is a natural probability-market execution venue.

For each eligible market, AH2 should calculate:

- market implied probability
- AlphaHound fair probability
- raw edge
- confidence
- fees
- liquidity
- expected value
- resolution risk

Decision:

- `BUY_YES`
- `BUY_NO`
- `PASS`

### Resolution Parser

Persist structured interpretation:

- event definition
- resolution source
- resolution deadline
- threshold
- exceptions
- ambiguity score

Markets with unresolved/ambiguous rules should be rejected.

---

## 17. Commodities / Futures

Target areas may include:

- crude oil
- natural gas
- gold
- silver
- copper
- wheat
- corn
- other sufficiently liquid contracts

Features may include:

- futures curves
- spot pricing
- inventories
- production
- supply disruptions
- shipping
- weather
- currency
- macro
- related equities
- options positioning

Cross-market relationships are first-class features.

---

## 18. Options

Options remain useful as:

1. an intelligence source
2. a possible future execution venue

Options execution adds significant complexity:

- IV
- Greeks
- strike selection
- expiry selection
- spreads
- assignment
- multi-leg fill quality

AH2 should initially prioritize proving predictive edge through simpler venues while options remain paper/research unless explicitly promoted.

---

## 19. Risk Engine

Risk is deterministic.

Controls include:

- per-trade risk
- maximum position
- portfolio exposure
- correlated exposure
- sector exposure
- asset-class exposure
- daily loss limit
- drawdown limit
- cash floor
- liquidity threshold
- concentration limits
- kill switch

---

## 20. Execution safety

Required controls:

### Idempotency
The same logical order cannot be submitted twice.

### Reconciliation
Internal state must match venue state.

### Kill switch
Immediate block on new execution.

### Circuit breakers
Trading halts on configured failure/risk conditions.

### Stale decision protection
Old signals cannot execute unexpectedly.

### Venue state validation
Execution validates market status/hours/tradability.

---

## 21. Compliance

Every automated decision should retain enough provenance to reconstruct why the system traded.

Persist:

- signal timestamp
- source/evidence timestamps
- public source references
- model/version
- probability
- market probability
- opportunity score
- risk decision
- compliance decision
- order timestamp
- venue order ID
- fills
- eventual outcome

The system must not intentionally support:

- spoofing
- wash trading
- self-trading
- market manipulation
- prohibited nonpublic information
- exchange-limit circumvention
- trading of markets the participant can improperly influence

---

## 22. AlphaHound Lab

No strategy moves directly to production.

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

Persist:

- hypothesis
- dataset period
- features
- model/version
- transaction assumptions
- performance
- calibration
- approval state

---

## 23. Consumer research product

A future product may expose standardized AlphaHound research.

Working concept: **AlphaHound Markets**

Example:

```text
MARKET: Fed cuts by October

Market implied probability: 43%
AlphaHound fair probability: 61%
Potential edge: +18 pts
Confidence: High
```

Potential features:

- probability scanner
- evidence
- catalyst timeline
- bull/bear case
- probability history
- historical calibration
- market rules
- alerts

Initial product should remain research/analytics focused. Personalized advisory or customer-account auto-execution requires separate legal/regulatory review.

---

## 24. Observability

Application Insights should track:

- Function execution
- Service Bus failures/queue depth
- API failures
- model latency/errors
- stale data
- probability anomalies
- risk/compliance rejection
- order execution
- reconciliation mismatches
- workflow duration

Every workflow receives a correlation ID.

Trace path:

```text
SOURCE
 -> INGESTION
 -> EVIDENCE
 -> MODEL
 -> PROBABILITY
 -> OPPORTUNITY
 -> RISK
 -> COMPLIANCE
 -> ORDER
 -> FILL
 -> OUTCOME
```

---

## 25. Security

Use Azure Key Vault for:

- Kalshi credentials
- broker credentials
- market data credentials
- database secrets
- model/API keys

Principles:

- least privilege
- managed identity where practical
- no secrets in Git
- no unrestricted DB access from external inference
- explicit provider privacy classification

---

## 26. Documentation governance

The Git repository is the authoritative documentation source.

Structure:

```text
AH2/
  README.md
  CLAUDE.md
  docs/
    ARCHITECTURE.md
    CURRENT_STATE.md
    ROADMAP.md
    adr/
    plans/
    tasks/
    reviews/
```

Major design decisions require ADRs.

Implementation work requires a task document.

---

## 27. Engineering organization

### Kamil

- business direction
- product direction
- priorities
- capital decisions

### ChatGPT

Program Manager / Principal Architect:

- architecture
- roadmap
- task decomposition
- acceptance criteria
- design decisions
- model strategy
- risk architecture
- implementation review

### Claude Chat + filesystem MCP

Primary Engineering Agent:

- inspect repo
- implement tasks
- write tests
- migrations
- APIs
- Azure infrastructure/application integration
- UI
- bug fixes

### Independent reviewer

Used selectively on high-risk areas:

- execution
- capital/risk
- probability/calibration
- reconciliation
- security
- compliance

---

## 28. Definition of success

AH2 succeeds when it can demonstrate that it can:

1. estimate outcomes with measurable calibration
2. identify economically meaningful market mispricing
3. preserve full evidence/provenance
4. execute deterministically and safely
5. operate across multiple market venues
6. learn from outcomes
7. remain explainable, auditable, scalable, and maintainable

The long-term moat is the dataset connecting:

> information -> probability -> market price -> decision -> trade -> outcome
