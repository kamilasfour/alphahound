# ADR-001 — Azure Functions Replace Windows Task Scheduler

**Status:** Accepted  
**Date:** 2026-09-09

## Decision

AH2 production scheduling and event-driven execution will use Azure Functions rather than Windows Task Scheduler.

## Context

AH1 currently uses Windows Task Scheduler for recurring ingestion and convergence work.

AH2 needs:

- cloud-native execution
- observability
- retries
- independent scaling
- event-driven workflows
- easier operations
- Service Bus integration

## Consequences

- AH1 Task Scheduler remains untouched during AH2 development.
- AH2 scheduled workloads are implemented as Functions.
- Long/stateful workflows may use Durable Functions/Durable Task.
- Financial logic should not be rewritten solely because orchestration changes.
