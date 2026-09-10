# AlphaHound 2.0 (AH2)

AlphaHound 2.0 is the next-generation architecture for AlphaHound.

AH1 remains intact as the working reference implementation. AH2 is built beside it and reuses proven components selectively rather than refactoring AH1 in place.

## Product thesis

> AlphaHound is an information-to-probability engine that identifies mispriced outcomes across markets.

AH2 is not fundamentally a stock bot, options bot, Kalshi bot, or LLM trading system.

It is a cross-market intelligence, probability, research, risk, and execution platform.

## Primary platform

- Microsoft Azure
- Python
- Azure Functions
- Durable Functions / Durable Task where appropriate
- Azure Service Bus
- Azure Container Apps
- Azure Container Apps GPU where needed
- PostgreSQL
- Azure Key Vault
- Application Insights
- Optional local Mac inference node

## Documentation

Start here:

1. `docs/ARCHITECTURE.md`
2. `docs/CURRENT_STATE.md`
3. `docs/ROADMAP.md`
4. `CLAUDE.md`
5. `docs/tasks/AH2-001.md`

## Program ownership

- Kamil: business direction, priorities, capital decisions
- ChatGPT: Program Manager / Principal Architect
- Claude Chat + filesystem MCP: Primary Engineering Agent
- Independent reviewer model: selective review of high-risk components
