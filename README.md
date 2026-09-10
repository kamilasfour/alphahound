# AlphaHound — Two-Stage Sentiment Intelligence Engine

## What This Is

AlphaHound is a multi-source sentiment intelligence engine, built in two stages.

**Stage 1 (current): Personal capital engine.** A single-operator system using every legitimate ingestion method — aggregated social, institutional filings, analyst content, options flow, prediction markets — to turn a $5K equity account and a $1K prediction-market account into material capital. Success = dollars in the Schwab and Kalshi accounts. The engine is Kamil's tool, not a product.

**Stage 2 (future): Commercial sentiment platform.** Once Stage 1 produces funding, the engine is forked, pruned of ToS-gray sources, hardened with observability and compliance layers, and shipped as an API + white-label deployment for institutional and developer customers. Industry-agnostic (stocks first, then real estate, auto, pharma, etc.).

Stage 1 funds Stage 2. Neither stage is a precursor to the other in the v1.2 sense — Stage 2 starts as a fork, not a continuation. See `prd/PRD_v1.3_stage1_addendum.md` for the formal framing.

## The Proof (Stage 1)

Turn $5K → $1M using AlphaHound as the primary decision engine. Every trade is logged, timestamped, and attributable to a specific sentiment signal. The trade log is the credential Stage 2 inherits.

## Why Multi-Industry (Stage 2)

Sentiment drives many industries, not just stocks:
- **Real Estate:** Reddit/Twitter sentiment on neighborhoods, mortgage rate anxiety, "housing crash" narrative tracking → predict market tops/bottoms
- **Automotive:** EV sentiment, brand perception shifts, recall sentiment impact → predict sales, stock moves
- **F&B:** Restaurant brand sentiment, health trend tracking, supply chain disruption signals → predict revenue, franchise value
- **Healthcare/Pharma:** Drug approval sentiment, clinical trial social chatter, patient community forums → predict FDA decisions
- **Retail/Consumer:** Brand sentiment shifts, boycott detection, viral product tracking → predict earnings surprises
- **Politics:** Policy sentiment, election prediction, regulatory change detection → predict sector impacts
- **Crypto:** Already proven — social sentiment is the PRIMARY driver

The engine doesn't change across industries. Data sources and scoring weights change per industry. That's the product — and that's Stage 2's commercial pitch.

## Architecture Philosophy
```
┌─────────────────────────────────────────────────┐
│              ALPHAHOUND CORE ENGINE              │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Ingestion │→│ Scoring  │→│ Pattern Match │  │
│  │ Pipeline  │  │ Engine   │  │ (Rhyme Engine)│  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │         Industry Configuration Layer      │    │
│  │  - Data source selection per industry     │    │
│  │  - Scoring weights per industry           │    │
│  │  - Historical pattern library per sector  │    │
│  │  - Custom keyword/entity dictionaries     │    │
│  └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
         │              │              │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │ STOCKS  │   │  REAL   │   │  AUTO   │
    │ Module  │   │ ESTATE  │   │ Module  │
    │         │   │ Module  │   │         │
    └─────────┘   └─────────┘   └─────────┘
```

## Project Status (April 19, 2026)
- [x] Concept validated through manual trading (April 14-15, 2026)
- [x] Project folder, research plan, and v1.2 PRD created
- [x] Deep research on existing platforms and approaches
- [x] Sprint 0 — Azure Postgres + Timescale substrate stood up
- [x] Sprint 1 — First adapter (ApeWisdom) writing to DB via CLI
- [x] v1.3 addendum — Two-stage strategy (Stage 1 personal / Stage 2 commercial) formalized
- [ ] Sprint 2 — SEC EDGAR as second adapter + scheduled ingestion (IN PROGRESS)
- [ ] Sprint 3+ — Stage 1 scoring, divergence, FinBERT
- [ ] Stage 1 Phase 0 — Live trading validation with real capital
- [ ] Stage 1 exit — target $500K+ combined, decide on Stage 2
- [ ] Stage 2 planning (only after Stage 1 exit)

## Folder Structure
```
alphahound_project/
├── README.md                    ← You are here
├── research/                    ← Deep research on platforms, data, models, patterns
│   ├── research_plan.md         ← What to research and how
│   ├── questions_for_deep_research.md ← Ready-to-paste prompts for AI research
│   ├── competitive_landscape.md ← (fill during research)
│   ├── data_sources.md          ← (fill during research)
│   ├── ai_models.md             ← (fill during research)
│   ├── historical_patterns.md   ← (fill during research)
│   └── multi_industry_analysis.md ← (fill during research)
├── prd/
│   └── PRD_TEMPLATE.md          ← PRD skeleton, fill after research
├── architecture/
│   ├── core_engine.md           ← Industry-agnostic engine design
│   ├── industry_config_schema.md ← How industries plug in
│   ├── database_schema.sql      ← PostgreSQL + TimescaleDB
│   └── api_spec.yaml            ← REST API specification
├── proof/                       ← $5K → $1M trading log
│   └── trade_log.md             ← Every trade with signal attribution
├── src/                         ← Source code (build phase)
└── data/                        ← Training data, backtesting
```

## Tech Stack
- **Backend:** Python (FastAPI) — ML pipeline, data ingestion, scoring
- **Database:** PostgreSQL on Azure + TimescaleDB (time-series sentiment storage)
- **AI/ML:** FinBERT (quantitative scoring) + Claude API (qualitative reasoning/narrative)
- **Core Engine:** Industry-agnostic base with configurable modules
- **Data Sources:** Reddit, X, news APIs, SEC, industry-specific sources per module
- **Infrastructure:** Azure VM (Windows Server 2022 — repsportalvm)
- **Frontend:** React dashboard (after API is stable)

## The Business Model

**Stage 1 (now):** No business model — capital engine funded by Kamil, P&L retained by Kamil, used to fund other ventures (Forkcast, Qtrade, etc.) without outside investment.

**Stage 2 (future, post Stage 1 exit):**
1. **Prove it:** the Stage 1 trade log becomes the credential — verifiable signal-attributed performance
2. **Fork it:** engine is cloned, ToS-audited, hardened, pruned of personal-use-only sources
3. **Package it:** REST API returns scored sentiment for any ticker/entity/industry
4. **Sell it:** SaaS tiers — free (delayed), pro (real-time), enterprise (custom modules + white-label)
5. **Scale it:** new industry modules are config + data source plugins

## Created: April 15, 2026
## Two-stage strategy formalized: April 19, 2026 (v1.3 addendum)
## Owner: Kamil Asfour
## Stage 1 Target: $5,000 + $1,000 → $1,000,000 combined
