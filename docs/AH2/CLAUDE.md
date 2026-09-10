# AlphaHound 2.0 Engineering Rules

Claude is the primary implementation agent for AH2.

Before implementing any AH2 task:

1. Read `docs/ARCHITECTURE.md`.
2. Read `docs/CURRENT_STATE.md`.
3. Read `docs/ROADMAP.md`.
4. Read the assigned task in `docs/tasks/`.
5. Read relevant ADRs in `docs/adr/`.

## Non-negotiable engineering rules

1. Do not modify AH1 unless the task explicitly requires it.
2. AH1 is a reference implementation and must remain operational.
3. Do not change trading thresholds, model weights, or financial logic unless the task explicitly requires it.
4. LLMs must never directly submit orders.
5. Capital allocation, risk checks, compliance checks, and execution must remain deterministic.
6. Every trading decision must be reproducible from persisted inputs.
7. Every order operation must be idempotent.
8. External API calls must have explicit timeout, retry, and failure handling.
9. External AI/model providers must never receive unrestricted PostgreSQL access or database credentials.
10. Secrets must come from Azure Key Vault or approved local development secret storage.
11. Every model prediction must persist model name, version, timestamp, features/evidence references, prediction, and confidence where applicable.
12. Every workflow must support correlation IDs and traceability.
13. New execution paths must support demo/paper/shadow mode before live capital.
14. Do not expand task scope without explicit approval.
15. Do not replace a documented architectural decision without creating a new ADR and obtaining approval.
16. Prefer small, testable services/functions over large orchestration scripts.
17. Azure Functions orchestrate work; model inference should be isolated behind the Model Gateway.
18. PostgreSQL remains the system of record.
19. Service Bus is the default asynchronous decoupling mechanism.
20. Preserve observability through structured logs and Application Insights.

## Completion requirements

At the end of every task, update the task document with:

- files changed
- migrations added
- configuration added
- tests added
- tests executed and results
- known limitations
- deviations from task (should normally be none)
- implementation status

Do not mark work complete if acceptance criteria are not met.
