# ADR-002 — PostgreSQL Remains the System of Record

**Status:** Accepted  
**Date:** 2026-09-09

## Decision

PostgreSQL remains the authoritative persistent state store for AH2.

## Context

AH1 already uses TimescaleDB/PostgreSQL concepts and stores market, signal, and trade context.

AH2 expands this into evidence, probabilities, opportunities, risk/compliance decisions, model versions, and outcomes.

## Consequences

- No new primary database technology is introduced without a future ADR.
- AH1 tables are not destructively migrated during early AH2 phases.
- External model providers receive task-specific payloads, not unrestricted DB access.
- Schema design must preserve provenance and replayability.
