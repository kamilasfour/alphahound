# ADR-003 — All AI Inference Uses a Model Gateway

**Status:** Accepted  
**Date:** 2026-09-09

## Decision

AH2 application components will use a provider-neutral Model Gateway for AI/model inference.

## Context

Potential compute/providers include:

- Azure CPU
- Azure Container Apps GPU
- Azure-hosted models
- optional local Mac
- selectively approved external providers

AH2 must not become coupled to any one provider.

## Consequences

- Callers request a task/model family, not a hard-coded infrastructure target.
- Every inference records provider, model, version, timestamp, and result metadata.
- The Mac is optional, never required for platform availability.
- Provider routing can change without rewriting business logic.
