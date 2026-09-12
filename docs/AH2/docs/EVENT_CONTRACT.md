# AH2 Event Contract

**Step:** STEP 5 — Service Bus Event Contract (contract/schema only — no new workflows, no new Functions)
**Status:** COMPLETE
**Date:** 2026-09-12

This document formalizes the `AH2Event` envelope proven out in STEP 4B and defines the rules every AH2 event — present and future — must follow, plus the initial event vocabulary for the pipeline described in `ARCHITECTURE.md` and `ROADMAP.md`. Nothing in this document authorizes building the producers/consumers for the vocabulary below — that is future, separately-authorized work (STEP 6+).

---

## 1. The envelope

Every AH2 event is a JSON object with exactly these seven top-level fields. This matches the `AH2Event` dataclass implemented in `src/domain/events.py` and proven working end-to-end in STEP 4B — no code changes are required to conform.

| Field | Type | Required | Description |
|---|---|---|---|
| `event_id` | string (UUID4) | Yes | Unique identifier for this specific event instance. A new one is generated every time an event is published — including retries and replays of a logical operation (see §9, §10). |
| `event_type` | string | Yes | One of the vocabulary entries in §14, or a future addition following the naming rule in §2. |
| `correlation_id` | string (UUID4) | Yes | Identifies the end-to-end business transaction this event belongs to. See §7. |
| `source` | string | Yes | Identifies what produced the event. See §8. |
| `created_at` | string (ISO 8601) | Yes | UTC timestamp of when the event was constructed. See §6. |
| `schema_version` | string | Yes | Version of this envelope shape. See §3. |
| `payload` | object (JSON object) | Yes | Event-type-specific data. See §9. Never a bare list, string, or number — always a JSON object, even if empty (`{}`). |

No other top-level fields are permitted. Event-type-specific data belongs inside `payload`, never bolted onto the envelope.

---

## 2. Event naming rules

- `event_type` values are `SCREAMING_SNAKE_CASE`.
- Names describe something that **already happened** (past tense: `DATA_RECEIVED`, `ORDER_FILLED`), never a command or request to do something (not `PROCESS_DATA`, not `SUBMIT_ORDER`). Commands, if AH2 ever needs them, are a different concept from events and are out of scope for this contract.
- Names are `NOUN_VERB` or `NOUN_ADJECTIVE` in form, matching the vocabulary in §14 (`SIGNAL_DETECTED`, `RISK_APPROVED`).
- A breaking change to what a given `event_type` name means (different producer, incompatible payload shape) requires a **new name**, not a version bump of the existing one — e.g. `ORDER_FILLED_V2` rather than silently changing what consumers of `ORDER_FILLED` receive. This keeps `schema_version` (§3) scoped to the envelope only, and keeps every event-type name meaning exactly one stable thing forever.

---

## 3. Schema versioning rules

`schema_version` versions the **seven-field envelope shape defined in §1** — not any individual event type's payload shape.

- Format: `"<MAJOR>.<MINOR>"` as a string (matches the current `"1.0"` constant in `domain/events.py`).
- **MINOR** bump: an additive, backward-compatible change to the envelope (e.g. a new *optional* eighth field). Existing consumers must continue to work unmodified.
- **MAJOR** bump: any change that could break an existing consumer (removing/renaming one of the seven fields, changing a field's type, making a previously-optional envelope field required). This should be rare — the envelope has been stable since STEP 4B and should stay that way.
- Payload shape evolution for a specific `event_type` is governed by §2's naming rule (new name for a breaking change) and by the "minimum payload fields" listed per event type in §14 (additive-only for non-breaking evolution) — it does **not** consume envelope `schema_version` bumps.

---

## 4. Backward compatibility expectations

- Consumers **must** ignore unknown fields — both unknown top-level envelope fields (in case of a future MINOR bump) and unknown keys inside `payload`.
- Producers **must not** remove or rename any of the seven envelope fields, or change an existing field's type, without a MAJOR `schema_version` bump and explicit sign-off (this is a program-level decision, not something one function's author decides unilaterally).
- New payload fields for an existing `event_type` must be **additive and optional** with a documented default/absence behavior. A payload field that becomes required, or that changes meaning, requires a new `event_type` name per §2.
- Consumers must tolerate a missing optional payload field gracefully (not crash) — required fields are only the "minimum payload fields" listed per event type in §14.

---

## 5. Serialization format

- UTF-8 JSON, via `AH2Event.to_json()` / `AH2Event.from_json()` (or `to_dict()`/`from_dict()` when working with an already-parsed object, e.g. a Service Bus SDK message that's already handed you bytes).
- `payload` is a nested JSON object, never a JSON-encoded string inside a string (no double-encoding).
- No binary formats (no pickle, no protobuf) for this contract — plain JSON only, for the same reason AH1 favors simple, inspectable formats: anyone can read a dead-lettered message in the Portal without special tooling.

---

## 6. Timestamp format

- `created_at` is ISO 8601, always timezone-aware, always UTC (`+00:00` offset, e.g. `2026-09-12T11:57:16.123456+00:00`) — produced via `datetime.now(timezone.utc).isoformat()`, matching the current implementation.
- Naive (timezone-less) timestamps are never valid. A producer that emits one is non-conformant.
- Any other timestamp fields inside a `payload` (e.g. `filled_at`, `resolved_at` in §14) follow the same rule: ISO 8601, UTC, timezone-aware.

---

## 7. UUID requirements

- `event_id` and `correlation_id` are both UUID4 (random), lowercase, standard 36-character hyphenated string form (`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`), generated via `shared.ids.new_id()`.
- `event_id` is **always freshly generated** for every event instance — including a retry of a failed publish attempt, and including a deliberate replay (§10). Two events with the same `event_id` should be treated as the literal same event instance (e.g. delivered twice by Service Bus — see §12), not as two separate occurrences.
- `correlation_id` is fresh **only** for the first event in a business-transaction chain (see §7 continued in §8). Every downstream event in that chain reuses the same value — it is not regenerated by each producer.

---

## 8. Correlation ID rules

- A single `correlation_id` traces **one end-to-end business transaction** across every event it produces, from the first triggering event through however many downstream events result from it (e.g. one `DATA_RECEIVED` → the `EVIDENCE_PROCESSED`, `SIGNAL_DETECTED`, `PROBABILITY_UPDATED`, etc. events it eventually causes, if any).
- The event that **starts** a chain generates a fresh `correlation_id` (via `new_event()` with no `correlation_id` argument, as the STEP 4B timer does today).
- Every event a consumer publishes **as a direct consequence of processing** an upstream event must carry that upstream event's `correlation_id` forward unchanged (via `new_event(..., correlation_id=<upstream correlation_id>)`).
- Never reuse a `correlation_id` across two unrelated business transactions, and never generate a new one partway through an otherwise-continuous chain — doing either breaks the ability to trace a transaction end-to-end in Application Insights/logs, which is the entire purpose of the field.
- `correlation_id` is for tracing, not for idempotency — see §9 and §12 for the separate idempotency-key concept.

---

## 9. Source naming rules

- `source` identifies **what produced the event**, in the form `<function-app-name>:<function-name>` — e.g. `ah2-dev-func:timer` (the STEP 4B convention, kept as-is).
- The function-app name segment is lowercase, hyphen-separated, matching the actual Azure resource name.
- The function name segment matches the actual Azure Function name as registered (e.g. `AH2FoundationTimer`), so `source` can always be traced back to one specific deployed component without ambiguity.
- `source` describes the immediate producer only — it is not a substitute for `correlation_id`'s job of tracing the whole chain.

---

## 10. Payload rules

- `payload` is always a JSON object (dict), even when empty (`{}`) — never a bare array, string, or number at the top level (enforced today by `AH2Event.from_dict()`).
- Keys inside `payload` are `snake_case`.
- `payload` is the **only** place event-type-specific data lives — the envelope itself carries no domain data.
- `payload` must never contain secrets, credentials, or connection strings (same rule as `CLAUDE.md` rule 10 — Service Bus messages are not a secrets store).
- Large content (raw documents, full API responses) does not belong inline in `payload` — Service Bus Basic-tier queues cap message size at 256 KB. Payloads should carry a **reference** (a blob URI, or once STEP 6 exists, a PostgreSQL row identifier) to the full content, not the content itself. This is reflected in the vocabulary in §14 (e.g. `DATA_RECEIVED`'s `raw_data_ref`, not the raw data).
- PII in payloads should be limited to what's operationally necessary; AH2 is a market-signal/trading system, not a system that should be accumulating personal data by default.

---

## 11. Validation requirements

- Every event **must** pass through `AH2Event.from_dict()` / `AH2Event.from_json()` before being acted upon by a consumer — never hand-roll a dict and act on it without validating it first, on either the producer or consumer side.
- Producers construct events via `new_event()` (or a future event-type-specific factory built on top of it), never by hand-assembling a dict that bypasses validation.
- Validation checks, at minimum (already implemented): all seven envelope fields present, `payload` is a JSON object. Event-type-specific payload field validation (checking the "minimum payload fields" in §14 are present) is the responsibility of that event type's consumer, once it's built in a future step — this contract defines *what* must be validated, not the validation code for workflows that don't exist yet.
- A consumer that receives an event failing validation **must not** silently drop it — see §16 (poison-message behavior).

---

## 12. Retry expectations

- AH2 relies on the Service Bus queue's native retry mechanism (PeekLock semantics: an unhandled exception during processing leaves the message un-completed, and the platform redelivers it), not custom retry loops layered on top.
- Every AH2 queue is expected to be configured with `maxDeliveryCount` and dead-lettering on expiration, matching the pattern already established on `ah2-dev-test-queue` (`maxDeliveryCount=10`, `deadLetteringOnMessageExpiration=true`, 14-day TTL) — future queues (STEP 6+) should follow this same baseline unless a specific reason justifies deviating.
- Consumers must raise (not catch-and-swallow) on genuine processing failures, transient or not — swallowing an exception to "handle" a failure without either succeeding or re-raising defeats the platform's retry/dead-letter mechanism entirely, per the pattern already documented in `infrastructure/messaging/service_bus.py`.
- A consumer *may* choose to dead-letter a message immediately (via an explicit SDK call) rather than exhausting all delivery attempts, specifically for messages recognized as poison (§16) where retrying is known to be futile — this is a future implementation detail for whichever step builds real consumers, not something STEP 5 mandates a specific mechanism for.

---

## 13. Replay expectations

"Replay" means intentionally re-delivering a previously-processed event (e.g. from a dead-letter queue, or from an audit/log record) for reprocessing — as distinct from an *unintentional* platform-level redelivery, which is a duplicate (§12).

- A replayed event keeps its **original** `event_id`, `correlation_id`, and `created_at` — replaying does not mint a new `event_id`. This preserves lineage: anyone looking at logs later can tell a given `event_id` was processed more than once and when.
- Whether replay is safe is **event-type-specific** — see the "whether replay is safe" column in §14. In general:
  - Purely informational/terminal events (rejections, alerts) are safe to replay.
  - State-transition events (`PROBABILITY_UPDATED`, `POSITION_CHANGED`) are safe only if the consumer treats the payload as a state-set, not an increment.
  - Anything downstream of a broker call (`ORDER_REQUESTED`, `ORDER_SUBMITTED`) must **never** be replayed in a way that could re-trigger the broker call itself — replay of these is only safe for read-only reconciliation/bookkeeping purposes.
- No `is_replay` or `replay_count` field exists in the envelope today. Whether one is needed is flagged as an open decision — see §18.

---

## 14a. Idempotency expectations

- Every consumer that has a side effect (a database write, a broker call, an alert) must be safe to receive the **same** `event_id` more than once without duplicating that side effect. This is what makes retry (§12), duplicate delivery (§14b), and replay (§13) all survivable.
- The mechanism is an **idempotency key** — not necessarily `event_id` itself, since some event types have a more natural, stable business key (see the "idempotency key strategy" column in §14 for each type). Consumers should use upsert / `ON CONFLICT` / conditional-write patterns keyed on that idempotency key, not blind inserts or blind increments.
- This directly supports ADR-004's deterministic-execution principle: given the same event delivered N times, the resulting state must be identical to processing it once.

---

## 14b. Duplicate-event behavior

- Service Bus (like almost all message brokers) is **at-least-once**, not exactly-once — a consumer can crash after processing but before completing/acknowledging a message, causing the platform to redeliver it.
- A "duplicate" in this sense is the platform redelivering the same `event_id` — distinct from a deliberate "replay" (§13), though the defense is the same mechanism: idempotency keys (§14a).
- Consumers must detect and no-op on a duplicate rather than reprocess — silently reprocessing is the single most common source of bugs in message-driven systems (double-counted positions, duplicate orders), and is exactly the failure mode AH1's confirmed bugs (per `AH2_DEV_ENVIRONMENT.md` and `ARCHITECTURE.md` history) should not be allowed to recur in AH2.

---

## 15. Dead-letter behavior

- Matches the existing queue configuration (§12): after `maxDeliveryCount` failed attempts, or TTL expiration, Service Bus automatically moves a message to that queue's dead-letter sub-queue. No custom code is required for the mechanism itself.
- Dead-lettered messages are not silently ignored forever — actively monitoring dead-letter queue depth (e.g. an alert once a workflow exists) is a **future implementation concern** for whichever step builds real consumers and operational tooling; this contract only establishes that dead-lettering is the expected outcome of exhausted retries, not a design for monitoring it.

---

## 16. Poison-message behavior

- A "poison message" is one that will **never** succeed no matter how many times it's redelivered — malformed JSON, missing required envelope fields, or a payload failing type checks. `AH2Event.from_json()` / `from_dict()` raising `EventValidationError` is the detection point (already implemented, proven in STEP 4B's test suite).
- On detection, a consumer must log the failure with whatever identifying information is actually available (Service Bus `message_id`, `delivery_count` — `correlation_id` may not be extractable if the JSON itself didn't parse) and then let the message dead-letter, either by re-raising (natural exhaustion of `maxDeliveryCount`) or by an explicit immediate dead-letter call where that's implemented. A poison message must never be silently dropped without a dead-letter record — that would destroy the ability to investigate why it was malformed.

---

## 17. Logging/observability requirements

- Every event **must** be logged at both publish time and consume time via the shared `log_event()` helper (`infrastructure/observability/logging_setup.py`), at minimum including: `correlation_id`, `event_id`, `event_type`, `function_name`, `outcome` (e.g. `published`, `success`, `validation_failed`).
- **`correlation_id` and `event_id` must also be embedded directly in the human-readable log message text**, not only passed via `custom_dimensions` — this is a standing requirement, not a one-off STEP 4B workaround. STEP 4B found that `custom_dimensions` did not reliably surface as queryable fields in this environment's Application Insights (`AppTraces`), while plain message-text search reliably did. Future AH2 functions should follow the pattern already in `function_app.py` (e.g. `f"... (correlation_id={event.correlation_id}, event_id={event.event_id})"`) rather than relying on `custom_dimensions` alone.
- Both the success path and the failure path (validation failure, processing exception) must be logged — a consumer that fails silently with no log line is not acceptable.

---

## 18. Retention/audit expectations — and an open question for Program Manager review

- Service Bus queues are **not** a durable audit log — a message is gone once successfully processed (or once it expires/exhausts retries into the dead-letter queue, which itself is not permanent storage). Today, the *only* record that an event ever existed is:
  1. Application Insights / Log Analytics (`ah2-dev-law`), retained **30 days** (current workspace configuration), and
  2. Whatever a consumer chooses to durably persist as a side effect of its own processing (nothing yet, since no real consumers exist beyond the STEP 4B foundation test).
- **This is flagged as an open decision requiring Program Manager review, not something STEP 5 resolves:** AH2 is headed toward real-capital trading decisions (per `ROADMAP.md`), and a 30-day, non-immutable log retention is unlikely to satisfy eventual audit/compliance requirements for *why* a given order was placed, tracing back through `SIGNAL_DETECTED` → `PROBABILITY_UPDATED` → `OPPORTUNITY_DETECTED` → `RISK_APPROVED` → `COMPLIANCE_APPROVED` → `ORDER_REQUESTED`. A durable, likely-PostgreSQL-backed (per ADR-002) event log/audit table is the probable eventual answer, but building it is out of scope here — no new Azure resources, no PostgreSQL changes, per this step's explicit constraints. This document does not decide retention period, immutability requirements, or whether every event type needs full-payload audit storage versus just an index of `event_id`/`correlation_id`/`event_type`/timestamps — those are compliance/product decisions for the Program Manager, not implementation defaults to assume.
- A second open question in the same vein: whether `is_replay`/`replay_count` (§13) is worth adding to the envelope once real replay tooling is built, or handled entirely out-of-band (e.g. a separate replay log rather than a mutated event).

---

## 19. Initial AH2 event vocabulary

**These are documented for future implementation — none of the producers or consumers below exist yet.** Building any of them is separately-authorized future work (STEP 6+), not part of this step.

| Event type | Producer | Expected consumer(s) | Purpose | Minimum payload fields | Idempotency key strategy | Replay safe? |
|---|---|---|---|---|---|---|
| `DATA_RECEIVED` | Ingestion/adapter functions (future) | Evidence processing function | Raw external data (a document, API response, feed item) has been ingested and stored | `data_source`, `raw_data_ref` (pointer, not raw content), `received_at` | `data_source` + the source's own natural record ID | Yes |
| `EVIDENCE_PROCESSED` | Evidence processing function | Signal detection function | Raw data has been transformed into structured evidence | `evidence_id`, `data_source`, `evidence_type`, `evidence_ref` | `evidence_id`, deterministically derived from the source `DATA_RECEIVED` idempotency key | Yes, if evidence storage is upsert-based |
| `SIGNAL_DETECTED` | Signal detection / scoring function | Probability/convergence scoring function | A candidate trading signal identified from one or more evidence pillars | `signal_id`, `ticker`, `pillar`, `evidence_ids` (list) | `signal_id` (stable per ticker+pillar+evidence-set) | Yes |
| `PROBABILITY_UPDATED` | Convergence/probability scoring function | Opportunity detection function | Aggregate convergence score/probability for a ticker changed | `ticker`, `probability_score`, `contributing_signal_ids` | `(ticker, contributing_signal_ids)` or a dedicated `update_id` | Conditional — only if treated as state-set, not increment |
| `OPPORTUNITY_DETECTED` | Opportunity detection function | Risk approval function | A specific tradeable opportunity identified as a candidate | `opportunity_id`, `ticker`, `strategy_type`, `probability_score`, `proposed_structure` | `opportunity_id` | Yes for detection; downstream consumers must dedupe on `opportunity_id` |
| `RISK_APPROVED` | Risk approval function/gate | Compliance approval function | Opportunity passed risk checks (position limits, exposure, macro gate) | `opportunity_id`, `risk_checks_passed` (list), `approved_at`, `approver` (system/rule identifier) | `opportunity_id` | **No** — risk state can go stale; replay requires re-validation against current risk state, not blind reprocessing |
| `RISK_REJECTED` | Risk approval function/gate | Audit/monitoring | Opportunity failed risk checks | `opportunity_id`, `rejection_reasons` (list), `rejected_at` | `opportunity_id` | Yes — terminal/informational |
| `COMPLIANCE_APPROVED` | Compliance approval function/gate | Order request function | Opportunity passed compliance checks | `opportunity_id`, `compliance_checks_passed` (list), `approved_at` | `opportunity_id` | **No** — same staleness reasoning as `RISK_APPROVED` |
| `COMPLIANCE_REJECTED` | Compliance approval function/gate | Audit/monitoring | Opportunity failed compliance checks | `opportunity_id`, `rejection_reasons` (list), `rejected_at` | `opportunity_id` | Yes — terminal/informational |
| `ORDER_REQUESTED` | Order request function | Order submission function | A fully-specified order is ready to submit to the broker | `order_request_id`, `opportunity_id`, `ticker`, `order_legs`, `max_contracts` | `order_request_id`, freshly and uniquely generated | **No — must never be replayed.** Last safe point before touching real money; replay risks a duplicate real-money order |
| `ORDER_SUBMITTED` | Order submission function | Position tracking function | Order was sent to the broker and acknowledged | `order_request_id`, `broker_order_id`, `submitted_at` | `broker_order_id` | **No** — replay must never re-trigger a broker call; only safe for read-only reconciliation |
| `ORDER_FILLED` | Fill-monitoring function | Position tracking / P&L function | Broker executed an order (fully or partially) | `broker_order_id`, `fill_price`, `fill_quantity`, `filled_at` | `broker_order_id` + broker's own fill/execution ID (handles partial fills) | Conditional — safe only if position tracking is upsert/idempotent keyed on fill ID |
| `POSITION_CHANGED` | Position tracking function | Risk/monitoring functions, dashboard | Portfolio position state changed (opened/adjusted/closed) | `position_id`, `ticker`, `change_type`, `new_quantity`, `changed_at` | `position_id` + a monotonic version number | Conditional — state-set, not increment |
| `MARKET_RESOLVED` | Market-monitoring function (e.g. Kalshi) | Position tracking, probability scoring | A prediction-market contract resolved to a final outcome | `market_id`, `resolution_outcome`, `resolved_at` | `market_id` (informational consumers); `market_id` + `position_id` (settlement consumers) | Yes for informational; conditional for position-settlement |
| `MODEL_DRIFT_DETECTED` | Model-monitoring function | Alerting/ops function | Model calibration drifted beyond threshold vs. actual outcomes | `model_id`, `drift_metric`, `detected_at`, `threshold_exceeded` | `model_id` + `detection_window` (evaluation batch) | Yes — informational/alerting |

---

## 20. Conformance with the existing implementation

No changes to `domain/events.py`, `application/timer_service.py`, or `application/queue_consumer_service.py` were required — the STEP 4B implementation already conforms to every rule above (envelope shape, JSON serialization, UUID4 IDs, UTC ISO 8601 timestamps, fresh-vs-inherited `correlation_id`, validation on parse). A small conformance test suite (`tests/test_event_contract.py`) was added to **guard** this conformance going forward — it asserts the envelope's required fields exactly match this document's §1, and that generated IDs/timestamps are well-formed — rather than to fix anything that was broken.

**STEP 5 is complete: the event contract is documented, the existing implementation already conforms, and conformance is now covered by tests. No new Azure resources, no new Functions, no PostgreSQL/AH1 changes, no trading or probability logic. STEP 6 is not authorized until Kamil explicitly approves it.**
