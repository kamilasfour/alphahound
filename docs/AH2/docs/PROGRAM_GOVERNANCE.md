# AH2 Program Governance

## Source of truth

The Git repository is the authoritative source for:

- architecture
- roadmap
- decisions
- implementation tasks
- implementation reviews

Chat conversations are useful working sessions but are not the final project record.

## Roles

### Kamil — Business/Product Owner

- defines business goals
- sets priority
- approves major product changes
- approves capital deployment

### ChatGPT — Program Manager / Principal Architect

- maintains architecture
- converts goals into work packages
- owns roadmap and dependencies
- defines acceptance criteria
- reviews implementation against architecture
- coordinates independent review where useful

### Claude Chat + filesystem MCP — Primary Engineering Agent

- reads program docs
- inspects repository
- implements scoped task
- writes/runs tests
- updates implementation notes
- does not independently redefine architecture

## Work lifecycle

```text
BUSINESS OBJECTIVE
      |
PROGRAM DESIGN
      |
ADR / TASK
      |
CLAUDE IMPLEMENTS
      |
TESTS
      |
PROGRAM REVIEW
      |
ACCEPT / CORRECT
      |
MERGE
```

## Task naming

Use:

`AH2-001`, `AH2-002`, ...

Every task must include:

- objective
- background
- scope
- out of scope
- constraints
- acceptance criteria
- tests
- implementation notes
- status

## Review naming

Use:

`docs/reviews/AH2-001-REVIEW.md`

Review severity:

- BLOCKER
- MAJOR
- MINOR
- NOTE

A BLOCKER prevents acceptance.

## Architecture decisions

Major architectural choices require an ADR.

Existing accepted ADRs should not be silently overridden.
