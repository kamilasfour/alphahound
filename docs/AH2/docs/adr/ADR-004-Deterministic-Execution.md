# ADR-004 — Trading Execution and Risk Are Deterministic

**Status:** Accepted  
**Date:** 2026-09-09

## Decision

LLMs and generative models will not directly control capital or submit financial orders.

## Context

AI is useful for interpreting unstructured information, but financial execution must be reproducible, testable, bounded, and auditable.

## Consequences

AI may generate structured evidence/features.

Probability/ML systems may estimate outcomes.

The deterministic stack decides:

- eligibility
- opportunity threshold
- position size
- portfolio risk
- compliance
- order construction
- execution

Every order must trace back to persisted approved inputs.
