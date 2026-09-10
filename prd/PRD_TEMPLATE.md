# AlphaHound — Product Requirements Document (TEMPLATE)

> **Status:** WAITING FOR RESEARCH
> **Fill this in after completing the deep research phase**
> **Each section should reference specific findings from the research/ folder**

---

## 1. Executive Summary
[2-3 paragraphs: What is AlphaHound, who is it for, what problem does it solve, why now?]

## 2. Problem Statement
[What's broken about current sentiment analysis? Reference competitive landscape findings.]

### 2.1 The Gap
[What specific gap did research reveal that no one is filling?]

### 2.2 Our Unique Edge
[What can we do that LunarCrush/StockTwits/Sentifi can't? Reference "things that rhyme" research.]

## 3. User Personas

### 3.1 Primary: Active Retail Trader (Us)
[Profile, pain points, current workflow, what they'd pay]

### 3.2 Secondary: Quantitative Analyst
[Profile, pain points, API needs]

### 3.3 Tertiary: Financial Content Creator
[Profile, how they'd use the data]

## 4. Product Features (Prioritized)

### P0 — Must Have for MVP
[List features that MUST ship for the product to function]
- [ ] Feature 1: ...
- [ ] Feature 2: ...

### P1 — Should Have
[Important but can wait for v1.1]

### P2 — Nice to Have
[Future roadmap items]

## 5. Data Sources & Ingestion
[Reference data_sources.md research]

### 5.1 Source Priority Matrix
| Source | Priority | Cost | Latency | Legal Status |
|--------|----------|------|---------|-------------|
| Reddit API | P0 | ? | ? | ? |
| ... | ... | ... | ... | ... |

### 5.2 Data Volume Estimates
[How much data per day? Storage requirements? Cost?]

## 6. AI/ML Architecture
[Reference ai_models.md research]

### 6.1 Sentiment Scoring Engine
[FinBERT vs LLM vs ensemble — what did research conclude?]

### 6.2 Narrative Detection Engine
[How does the "reasoning" layer work?]

### 6.3 Historical Pattern Matching
[Reference historical_patterns.md — how do we find "things that rhyme"?]

## 7. System Architecture
[High-level diagram, component breakdown, Azure infrastructure]

### 7.1 Data Pipeline
### 7.2 Processing Layer
### 7.3 Storage Layer
### 7.4 API Layer
### 7.5 Frontend (if applicable)

## 8. Database Schema
[PostgreSQL + TimescaleDB design]

## 9. API Specification
[Endpoints, authentication, rate limits, response format]

### 9.1 Core Endpoints
```
GET /api/v1/sentiment/{ticker}
GET /api/v1/signals/divergence
GET /api/v1/signals/extreme-reversal
GET /api/v1/historical/rhyme/{event_type}
POST /api/v1/scan
```

## 10. Scoring Methodology
[How is the 1-10 score calculated? What weights? How is confidence derived?]

## 11. Historical Pattern Engine
[How do we match current events to historical precedents? What similarity metrics?]

## 12. Output Format
[JSON spec from the AlphaHound prompt — refined based on research]

## 13. Success Metrics
[How do we know AlphaHound is working?]
- Backtested win rate on historical signals
- Forward-tested accuracy over 30/60/90 days
- User engagement metrics (if SaaS)
- Revenue targets (if SaaS)

## 14. Risks & Mitigations
[Reference legal research, alpha decay concerns, data quality issues]

## 15. Development Timeline
| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Research | Week 1 | Completed research files |
| PRD | Week 1-2 | This document, filled in |
| Architecture | Week 2 | System design, DB schema, API spec |
| MVP Backend | Week 3-4 | Data pipeline + scoring + API |
| MVP Frontend | Week 4-5 | Dashboard (if scoped) |
| Backtesting | Week 5-6 | Validate signals against history |
| Live Beta | Week 6+ | Run alongside manual trading |

## 16. Budget Estimate
[Azure costs, API costs, development time, total investment]

---

> **NEXT STEP:** Complete the research phase, then fill in each section of this PRD with specific findings. No section should contain assumptions — everything should be backed by research data.
