# AH2 Data Architecture

**Step:** STEP 6 (AH2 PostgreSQL Schema Foundation) + STEP 6A (signals table follow-up)
**Status:** COMPLETE — schema designed, migrated, and verified on `alphahound2`
**Date:** 2026-09-12 (STEP 6) / 2026-09-12 (STEP 6A, same day)

This document describes the initial AH2 PostgreSQL schema: what each table is for, how provenance and idempotency are preserved, indexing/access-pattern expectations, and the Program Manager decisions this schema implements. See `docs/AH2/docs/MIGRATIONS.md` for how to actually run/roll back the migration, and `docs/AH2/docs/EVENT_CONTRACT.md` for the event vocabulary this schema exists to durably record.

---

## 1. Scope and relationship to AH1

- **Server:** the existing PostgreSQL Flexible Server in `alphahound-rg` (same server AH1 uses) — no new server, per the STEP 4A design decision.
- **Database:** a new, separate database, **`alphahound2`**. AH1's `alphahound` database — its tables, its data — is not touched, queried, or referenced anywhere in this schema or its migration.
- Nothing in this step ingests real data, runs any workflow, or implements any trading/probability logic. This is schema only — every table described below is empty except for the throwaway row used to verify the append-only trigger works (see §6).

---

## 2. Design principles

1. **Provenance over convenience.** Almost every table carries a foreign key or reference back to whatever produced it (`raw_source_event_id` on `evidence`, `source_evidence_ids` on `features`, `probability_id` on `opportunities`, etc.), so any row's lineage back to a raw ingested event can be reconstructed.
2. **Idempotency by construction.** Every table that corresponds to an `EVENT_CONTRACT.md` event type carries a `UNIQUE` constraint matching that event type's documented idempotency key (see §5's per-table table), so a future consumer can use `INSERT ... ON CONFLICT DO NOTHING` (or `DO UPDATE` where a state-set semantic applies) rather than needing custom duplicate-detection logic.
3. **Correlation-ID tracing.** Every table that originates from an AH2 event carries `correlation_id`, so a single business transaction can be traced across `raw_source_events → evidence → ... → orders → fills → positions` via one SQL filter, matching `EVENT_CONTRACT.md` §8.
4. **JSONB only where the shape is genuinely variable.** Columns like `evidence.structured_fields`, `opportunities.proposed_structure`, `orders.order_legs`, and `audit_events.payload` use JSONB because their shape legitimately varies by evidence type / strategy type / event type. Everything with a stable, known shape (IDs, tickers, prices, timestamps, decision outcomes) is a real, typed, indexed column — this schema is not "one JSONB blob per table."
5. **Explicit primary keys and timestamps everywhere.** Every table uses `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` for its surrogate key (compact, sequential, standard Postgres identity columns — available and recommended since PG 10+, and this server runs PG 17.11) plus an explicit `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

---

## 3. Program Manager decisions implemented in this schema

### 3.1 Audit history (PM decision)

- **PostgreSQL — specifically the `audit_events` table — is the authoritative durable audit store.** Application Insights remains observability-only (short retention, not immutable, not designed as a system of record — as already flagged as an open gap in `EVENT_CONTRACT.md` §18).
- `audit_events` preserves exactly what was asked: `event_id`, `correlation_id`, `event_type`, `schema_version`, `source`, `event_created_at` (the *original* envelope timestamp, distinct from `recorded_at`, when this row was written), the full `payload` verbatim, and `reference_ids` (a small JSONB map of which domain entities — e.g. `opportunity_id`, `order_request_id` — this event pointed to, for filterable queries without parsing the full payload every time).
- **Append-only is enforced at the database level, not just by convention.** A trigger (`trg_audit_events_no_update` / `trg_audit_events_no_delete`) raises an exception on any `UPDATE` or `DELETE` against `audit_events`. This was verified against the real database (see §6) — an attempted `UPDATE` and `DELETE` were both rejected by Postgres itself.

### 3.2 Replay (PM decision)

- **No `is_replay` or `replay_count` field was added to the `AH2Event` envelope** — matching the explicit instruction, and consistent with `EVENT_CONTRACT.md` §13's original "open question" framing (now resolved by this decision).
- Replay is tracked entirely out-of-band via two dedicated tables:
  - **`replay_requests`** — one row per requested replay, preserving `replay_request_id`, `original_event_id` (FK to `audit_events.event_id` — a replay can only target something that's actually in the durable audit record), `reason`, `requested_by`, `requested_at`, `target_workflow`, `target_version`, and a `status` lifecycle (`pending` → `in_progress` → `completed`/`failed`/`blocked`).
  - **`replay_history`** — one row per replay *attempt* (a request can be attempted more than once), recording `outcome` (`success` / `failure` / `skipped_side_effect_guard`) and arbitrary `details`.
- `replay_requests.involves_financial_side_effect_types` is a boolean bookkeeping flag — see §3.3.

### 3.3 Financial side-effect safety (PM decision)

- `RISK_APPROVED`, `COMPLIANCE_APPROVED`, `ORDER_REQUESTED`, and `ORDER_SUBMITTED` are explicitly **not blindly replayable**. This is documented at the point of highest visibility — as a comment directly above each corresponding table (`risk_decisions`, `compliance_decisions`, `orders`) in the migration file itself, so anyone editing this schema later sees the warning in context, not just in a separate doc.
- `replay_requests.involves_financial_side_effect_types` exists so that any future replay-execution tooling has a structural flag to check before acting — **this schema does not implement that enforcement logic itself** (there is no replay-execution code yet — that's future, separately-authorized work). The `replay_history.outcome` value `skipped_side_effect_guard` is reserved for exactly that future check to record "this replay was correctly blocked from reproducing a financial side effect."
- Concretely: replaying one of these four event types may **reconstruct or evaluate state** (e.g., re-running a risk calculation against `market_states`/`probabilities` as they exist today, to see what a decision *would* be) but must never automatically re-insert a new `risk_decisions`/`orders` row that triggers a real downstream action. Enforcing that distinction in code is Step 7+ work; this schema only provides the structural hooks (the flag, the `audit_events` immutability, the FK linking a replay back to its original event) that such code will need.

### 3.4 STEP 6A decisions (audit payload discipline, retention, current-positions view)

- **`audit_events` retention is indefinite for now.** No automated purge/archival exists or is planned yet — this resolves the retention half of the open question raised in `EVENT_CONTRACT.md` §18 and STEP 6 §7.4. (The *payload-size* half of that question is addressed by the next two points, separately from retention *period*.)
- **`audit_events.payload` must contain only structured decision-reconstruction data** — the fields actually needed to understand and reconstruct why a decision was made (scores, checks evaluated, references, structured parameters), not arbitrary supporting material.
- **Large raw documents, articles, or prompts must never be duplicated into `audit_events`.** Persist a reference, an ID, or a content hash instead (the same pattern `raw_source_events.raw_data_ref` already establishes) — `payload` points at where the large content lives, it does not contain it.
- **~64 KB is a soft target for `audit_events.payload`, not a database-enforced limit.** No `CHECK` constraint or trigger enforces this (Postgres/JSONB has no practical trouble storing more, and a hard limit would risk silently rejecting a legitimate audit write) — it is guidance for whoever writes producer code in a future step, not something this schema blocks.
- **No `current_positions` view was created.** This was already the case after STEP 6 (see §7) and remains deliberate — explicitly deferred until real position/execution workflows exist, per this decision.

---

## 4. Table reference

All 21 tables live in `alphahound2`, `public` schema (18 from STEP 6 + `signals`, `probability_signals`, `opportunity_signals` from STEP 6A).

| Table | Maps to (event contract) | Purpose |
|---|---|---|
| `raw_source_events` | `DATA_RECEIVED` | Raw external data ingestion record (a *reference* to the raw content, not the content itself) |
| `evidence` | `EVIDENCE_PROCESSED` | Normalized, structured evidence derived from raw source events |
| `features` | — (see §7) | Derived/engineered feature values used by scoring |
| `models` / `model_versions` | — | Model registry: named models and their versioned, trained instances |
| `predictions` | — (see §7) | Raw model output for a given input |
| `signals` | `SIGNAL_DETECTED` | **(STEP 6A)** A candidate trading signal identified from one or more evidence/feature pillars |
| `probabilities` | `PROBABILITY_UPDATED` | Aggregate convergence probability for a ticker |
| `probability_signals` | — | **(STEP 6A)** Junction table: which signals contributed to a given probability (FK-enforced, replaces reliance on the bare event-ID array for anything with a real `signals` row) |
| `market_states` | — | Point-in-time market/macro condition snapshots (e.g. a macro gate state) |
| `opportunities` | `OPPORTUNITY_DETECTED` | A specific candidate tradeable opportunity |
| `opportunity_signals` | — | **(STEP 6A)** Junction table: which signals an opportunity traces back to directly (FK-enforced) |
| `risk_decisions` | `RISK_APPROVED` / `RISK_REJECTED` | Risk gate decisions — **not blindly replayable** |
| `compliance_decisions` | `COMPLIANCE_APPROVED` / `COMPLIANCE_REJECTED` | Compliance gate decisions — **not blindly replayable** |
| `orders` | `ORDER_REQUESTED` / `ORDER_SUBMITTED` | Order lifecycle — **not blindly replayable** |
| `fills` | `ORDER_FILLED` | Broker fill/execution records (supports partial fills) |
| `positions` | `POSITION_CHANGED` | Append-only position-change history (not a single mutable "current state" table — see §7) |
| `outcomes` | `MARKET_RESOLVED` | Realized outcomes (prediction-market resolution, or other ground truth) |
| `audit_events` | *all events* | Immutable, append-only, authoritative durable record of every AH2 event |
| `replay_requests` / `replay_history` | — | Out-of-band replay tracking (PM decision §3.2) |

---

## 5. Indexes and expected access patterns

| Table | Indexes | Expected query pattern |
|---|---|---|
| `raw_source_events` | `UNIQUE(data_source, source_record_id)`, `correlation_id`, `received_at` | "Has this external record already been ingested?" (idempotency check); "everything ingested in this time range" |
| `evidence` | `correlation_id`, `raw_source_event_id`, `ticker`, `evidence_type`, GIN on `structured_fields` | "All evidence for ticker X"; "all evidence of type Y"; ad-hoc queries inside structured fields |
| `features` | `(ticker, feature_name)`, `computed_at` | "Latest value of feature F for ticker X" |
| `model_versions` | `(model_id, is_active)` | "Which version of model M is currently active?" |
| `predictions` | `(ticker, predicted_at)`, `model_version_id` | "Recent predictions for ticker X"; "all predictions from model version V" |
| `probabilities` | `(ticker, created_at)` | "Probability history for ticker X" |
| `market_states` | `(state_type, observed_at)`, partial index on `(ticker, observed_at)` where ticker present | "Current macro gate state"; "state history for ticker X" |
| `opportunities` | `ticker`, `status`, `correlation_id` | "Open opportunities awaiting risk review" (`status = 'detected'`); full transaction trace via `correlation_id` |
| `signals` | `ticker`, `signal_type`, `correlation_id`, `created_at`, partial index on `expires_at` where present, GIN on `convergence_metadata`/`catalyst_details` | "Active (non-expired) signals for ticker X"; "all signals of type Y"; ad-hoc queries inside convergence/catalyst metadata |
| `probability_signals` / `opportunity_signals` | composite PK (covers the forward lookup), plus a reverse index on `signal_id` | "Which signals fed probability P / opportunity O" (forward, via PK); "which probabilities/opportunities did signal S influence" (reverse, via the `signal_id` index) |
| `risk_decisions` / `compliance_decisions` | `opportunity_id`, `(decision, decided_at)` | "Decision history for opportunity X"; "recent rejections and why" |
| `orders` | `opportunity_id`, `status` | "Orders awaiting submission"; "order for opportunity X" |
| `fills` | `(order_id, filled_at)` | "All fills for order X, in sequence" |
| `positions` | `position_id`, `(ticker, changed_at)` | "Full change history for position P"; "position history for ticker X" |
| `outcomes` | partial unique on `market_id`, `(ticker, resolved_at)` | "Has market M resolved yet?" (idempotency); "resolved outcomes for ticker X" |
| `audit_events` | `event_type`, `correlation_id`, `event_created_at`, GIN on `payload`, GIN on `reference_ids` | "Everything that happened for correlation X" (the primary audit/debugging query); "all events of type Y in a time range"; ad-hoc payload search |
| `replay_requests` | `original_event_id`, `status` | "Pending replay requests"; "has event E ever been replayed?" |
| `replay_history` | `(replay_request_id, executed_at)` | "Attempt history for replay request R" |

---

## 6. Verification performed

Since Claude has no network path to the Postgres server from its sandbox, verification split into two parts:

1. **Structural (offline, automated):** `tests/test_db_migrations.py` uses Alembic's offline SQL-generation mode to confirm the migration creates all tables, the append-only trigger/function, and expected foreign keys — without needing a live connection. Part of the standard AH2 test suite.
2. **Live (manual, by Kamil):**
   - STEP 6: `alembic upgrade head` applied cleanly against the real `alphahound2` database; `verify_schema.py` confirmed all 18 expected tables (+ `alembic_version` = 19) and version stamp `ah2_0001`; `verify_audit_append_only.py` confirmed the append-only trigger genuinely rejects `UPDATE`/`DELETE`.
   - STEP 6A: `alembic upgrade head` applied the additive `ah2_0002` migration; `verify_schema.py` re-run confirmed all 21 tables (+ `alembic_version` = 22) and version stamp `ah2_0002`. See the STEP 6A chat report for the exact table list and test counts at that point in time.

---

## 7. Open questions for Program Manager / future-step review

1. ~~Where does `SIGNAL_DETECTED` persist?~~ **Resolved by STEP 6A:** `signals` is now a first-class table, with FK-backed junction tables (`probability_signals`, `opportunity_signals`) linking it to `probabilities` and `opportunities`. `probabilities.contributing_signal_event_ids` (the original bare UUID array) is left in place, unchanged, as a legacy/fallback field for any signal that predates having a real `signals` row — new code should prefer the junction tables.
2. **`features`/`predictions` idempotency is looser than most other tables.** Their `UNIQUE` constraints (`(ticker, feature_name, computed_at)` and none at all on `predictions`, respectively) guard against exact-timestamp duplicates but not against "the same underlying computation re-run with a slightly different timestamp." This is fine for a schema foundation but worth revisiting once real feature-computation code exists.
3. **`positions` has no materialized "current state" view** — confirmed deliberate per the STEP 6A PM decision (§3.4): deferred until real position/execution workflows exist.
4. **Audit retention period is now resolved (indefinite, §3.4), and payload discipline is now resolved (structured data only, references not raw content, ~64 KB soft target, §3.4).** What remains genuinely open: whether a *hard* limit or automated archival will ever be needed as volume grows — not a concern at this schema-foundation stage.

**STEP 6 and STEP 6A are complete: schema designed, documented, migrated, and verified against the real `alphahound2` database, including the additive `signals` table and its FK-backed links to `probabilities` and `opportunities`. No AH1 tables/databases were touched. No external data was ingested. No Step 7 adapters, trading logic, or probability models were built. STEP 7 is not authorized until Kamil explicitly approves it.**
