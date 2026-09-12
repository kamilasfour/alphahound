# AH2 Development Environment

**Step:** STEP 4B — Azure Functions + Service Bus foundation test (executed, verified end-to-end)
**Status:** COMPLETE. Timer → Service Bus → Queue Consumer workflow deployed to `ah2-dev-func` and verified working, correlation ID propagating end-to-end. STEP 5 not started, pending Kamil's explicit authorization.
**Date:** 2026-09-10 (design) / 2026-09-11 (STEP 4A provisioned + remediated) / 2026-09-12 (STEP 4B implemented, deployed, verified)

---

## 1. Scope of this document

Section 2–7 below is the original design proposal (unchanged). Section 9 records what was actually provisioned on 2026-09-11 under explicit Step 4A authorization, including deviations from the design, and the same-day remediation pass that closed the RBAC gap and re-verified health.

---

## 2. Resource group

**New, dedicated resource group: `ah2-dev-rg`**

| Field | Value |
|---|---|
| Name | `ah2-dev-rg` |
| Region | West Central US (same as `alphahound-rg`, for lowest latency to PostgreSQL and to avoid cross-region data-transfer charges) |
| Purpose | Isolates all AH2 development infrastructure from AH1 production (`alphahound-rg`) and from unrelated projects |

This directly satisfies the AH1 Protection Rule (`IMPLEMENTATION_PLAYBOOK.md` §4) — nothing in `ah2-dev-rg` can touch `alphahound-rg` resources except the explicit, scoped PostgreSQL connection described in §7.

---

## 3. Proposed resources

| # | Resource | Type | Tier/SKU proposed | Decision |
|---|---|---|---|---|
| 1 | Function App | `Microsoft.Web/sites` (functionapp, Python) | **Consumption (Y1)** | CREATE |
| 2 | Function Storage Account | `Microsoft.Storage/storageAccounts` | **Standard, LRS, Hot** | CREATE (required by #1 — every Function App needs one) |
| 3 | Service Bus namespace | `Microsoft.ServiceBus/namespaces` | **Basic** | CREATE |
| 4 | Key Vault | `Microsoft.KeyVault/vaults` | **Standard** | CREATE |
| 5 | Application Insights | `Microsoft.Insights/components` (workspace-based) | **Pay-as-you-go, default 5 GB/mo free** | CREATE |
| 6 | Container Apps environment | `Microsoft.App/managedEnvironments` | — | **DEFERRED** — not needed until the Model Gateway/GPU phase (STEP 9+) |
| 7 | PostgreSQL | — | — | **REUSE** existing `alphahound-rg` server; see §6 |

---

## 4. Naming convention

### Dev environment (this step)

| Resource | Proposed name | Note |
|---|---|---|
| Resource group | `ah2-dev-rg` | |
| Function App | `ah2-dev-func` | |
| Function Storage Account | `ah2devfuncst01` | Storage account names **cannot** contain hyphens and must be lowercase alphanumeric, ≤24 chars, globally unique across all of Azure (not just the subscription). If taken, fall back to `ah2devfuncst<short-suffix>`. |
| Service Bus namespace | `ah2-dev-sb` | Namespace names are globally unique across Azure; confirm availability at creation time. |
| Key Vault | `ah2-dev-kv` | Also globally unique across Azure; if taken, `ah2-dev-kv-<short-suffix>`. |
| Application Insights | `ah2-dev-appi` | |

### Proposed convention for future production resources

`<project>-<environment>-<resource-abbreviation>[-<instance>]`

| Environment | Example |
|---|---|
| Development | `ah2-dev-func`, `ah2-dev-sb`, `ah2-dev-kv`, `ah2-dev-appi` |
| Production (future) | `ah2-prod-func`, `ah2-prod-sb`, `ah2-prod-kv`, `ah2-prod-appi` |
| Resource groups | `ah2-dev-rg`, `ah2-prod-rg` |

Standard Microsoft resource-type abbreviations are used (`func`, `sb`, `kv`, `appi`, `st`, `rg`) so names stay recognizable and consistent with common Azure naming guidance. Storage accounts drop hyphens per the platform constraint noted above (`ah2prodfuncst01`, etc.). Whether production ends up in this same subscription/region or a separate one is a decision for a later step — not addressed here.

---

## 5. Cost estimates

All figures below are current US pricing (West Central US or nearest-equivalent US region), pulled 2026-09-10 — Azure prices can change, so treat these as planning estimates, not a bill guarantee. Chosen tiers are the cheapest viable option in each case.

| Resource | Tier | Pricing model | Dev-scale estimate | Scale-to-zero? |
|---|---|---|---|---|
| Function App | Consumption (Y1) | 1M executions + 400,000 GB-s free per month, then $0.20/million executions + $0.000016/GB-s | **$0/month** at dev volumes (a timer test workflow won't come close to the free grant) | **Yes** — bills nothing when idle; this is the whole point of Consumption plan |
| Function Storage Account | Standard LRS, Hot | ~$0.018/GB/month + small transaction fees | **~$0.05–$1/month** (a few GB of function metadata/state at most) | No fixed minimum, but not literally zero — storage account isn't optional (required by every Function App) and always has *some* tiny footprint even near-idle |
| Service Bus | Basic | $0.05 per million operations, no base fee, queues only (no topics — fine for the STEP 4/5 single-queue test workflow) | **Under $0.10/month** at dev volumes | **Yes** — no monthly minimum on Basic |
| Key Vault | Standard | $0.03 per 10,000 operations, no storage fee | **Well under $1/month** at dev volumes | **Yes** — pure pay-per-operation, no base fee |
| Application Insights | Workspace-based, pay-as-you-go | First 5 GB/month free, then $2.30/GB | **$0/month** — dev-scale structured logging won't approach 5 GB/month | **Yes** — no fixed cost below the free tier |
| Log Analytics workspace (backing App Insights) | PerGB2018, 30-day retention | First 5 GB/month free, then ~$2.30-2.76/GB | **$0/month** at dev volumes | **Yes** |
| PostgreSQL | Existing Burstable B2s (already running for AH1) | Fixed monthly cost regardless of AH2 usage | **$0 incremental** — reusing what's already paid for; adding the `alphahound2` database costs nothing extra beyond the ~32 GiB storage already provisioned | **No** — Burstable tier has a fixed monthly cost whether idle or not, but this is an existing sunk cost, not new spend |

**Total estimated incremental monthly cost for the dev environment at light development-stage usage: roughly $1–2/month**, driven almost entirely by the Function Storage Account (the only resource here without a meaningful free tier). Everything else should realistically land at $0/month until usage grows well past dev-scale testing. (The added Log Analytics workspace, required because Application Insights is now workspace-based by default, does not change this — it shares the same 5 GB/month free tier.) The RBAC role assignments added in the remediation pass carry no cost (IAM is free).

**Cost growth to watch for later:** Service Bus Basic doesn't support topics/subscriptions — if STEP 5's event contract needs pub/sub (multiple consumers per event type) rather than simple queues, that's a move to Standard tier ($10/month base fee, no longer scale-to-zero). Not needed for the initial timer→queue→consumer test workflow in STEP 4, but worth flagging now since it changes the "scales to zero" answer for that resource.

---

## 6. What should be created now vs. deferred

| Create now (this step, pending approval) | Defer |
|---|---|
| `ah2-dev-rg` resource group | Container Apps environment (until Model Gateway/GPU phase) |
| Function App (`ah2-dev-func`, Consumption plan) | Service Bus Standard/Premium tier (Basic is sufficient until pub/sub is actually needed) |
| Function Storage Account | Production resource group / naming (production isn't being built yet) |
| Service Bus namespace (Basic) | A second PostgreSQL server (explicitly ruled out — reuse existing) |
| Key Vault (Standard) | Reactivating any cancelled data subscriptions (per §7 of the playbook — only when a specific step requires them) |
| Application Insights | VNet integration / Private Endpoint for Postgres (see §7 — start with the simpler public-access approach for dev) |
| ~~`alphahound2` database on the existing PostgreSQL server~~ | **Explicitly excluded from Step 4A authorization** — Kamil's Step 4A instruction said "reuse the existing PostgreSQL server; do not modify it in this step." Deferred to a later step (schema work, STEP 6). |

---

## 7. PostgreSQL — reuse decision and connectivity options

**Decision: reuse the existing `alphahound-rg` PostgreSQL Flexible Server. Do not create a second server.** Propose a new, separate database on that server — `alphahound2` — so AH2 schema work (STEP 6) has a clean space with zero risk of touching AH1 tables. This matches ADR-002 (PostgreSQL as system of record) and the AH1 Protection Rule.

**Step 4A / remediation status: not touched, in either pass.** No database, schema, or configuration change was made to the `alphahound-rg` PostgreSQL server. The `alphahound2` database creation described below remains a proposal for a future step.

### Connectivity options for Azure Functions → PostgreSQL

| Option | How it works | Security | Cost | Complexity |
|---|---|---|---|---|
| **A. Public access + SSL, dev firewall pattern** | Postgres Flexible Server networking stays in its current "Public access" mode with `sslmode=require` (already enforced); firewall allows the appropriate Azure access pattern (e.g. "Allow public access from any Azure service within Azure to this server") rather than a fixed IP allow-list | Moderate — traffic is encrypted end-to-end, but the server has a public endpoint | $0 extra | Low — no additional resources, works with Consumption plan |
| **B. VNet integration + Private Endpoint** | Function App gets VNet integration (requires **Premium plan**, not Consumption), Postgres gets a private endpoint, traffic never leaves the VNet | Highest — no public endpoint at all | Adds real cost — Premium plan starts around $150–180+/month minimum for one pre-warmed instance | High — VNet, subnet, private DNS zone, Premium plan migration |

**Important correction on Option A:** the Consumption plan does **not** give a Function App a small, permanently stable set of outbound IP addresses. Outbound IPs for Consumption-plan Functions are drawn from a documented but non-fixed pool for the region and can change as the platform scales instances. Do not design a firewall rule around "allow-list these N specific IPs" for a Consumption-plan Function App — that assumption will silently break. Dev firewall configuration should instead use the broader Azure-service access pattern, or be configured/validated based on the Function App's actual observed outbound behavior once it exists, rather than a static per-IP rule.

**Recommendation for dev: Option A, public access with SSL.** This is acceptable for AH2 dev — the database is brand new, empty, and isolated from AH1 by design (§6/§7's whole purpose). Paying for a Premium plan and building VNet infrastructure to protect an empty dev database isn't proportionate — it would roughly 100x the Function App cost alone for no real risk reduction at this stage. Credentials for the `alphahound2` connection should still go into Key Vault (not `.env`, not source) and be referenced by the Function App via a Key Vault reference / managed identity, per `CLAUDE.md` rule 10 — that's the actual security boundary that matters here, not network topology.

**Production / real-capital execution (later, not this step):** PostgreSQL networking must be explicitly revisited and will very likely need to be tightened — via VNet integration + Private Endpoint (Option B) or another controlled private-access design — before any AH2 workflow touches real capital. Public access with SSL, acceptable for an empty dev database, is not an acceptable end-state once AH2 is trading. This decision should be made explicitly in a future ADR/task, not assumed now.

---

## 8. What was explicitly NOT done in the design step (2026-09-10)

- No Azure resources were created, modified, or deleted.
- No Azure CLI commands were run.
- No Azure Functions code was written.
- No IaC (Bicep/Terraform/ARM) was written.
- STEP 4 was not started.

---

## 9. STEP 4A — Actual provisioning result (executed 2026-09-11)

Kamil explicitly authorized Step 4A: create the resource group, Function storage account, Service Bus Basic namespace + initial queue, Key Vault Standard, Application Insights, and a Python Function App on Consumption — reusing the existing PostgreSQL server untouched, no Container Apps, no AH1/reps-portal changes, no trading logic, no Step 4B.

### Resources created

| # | Resource | Actual name | Type | SKU/Tier | Location | Resource ID |
|---|---|---|---|---|---|---|
| 1 | Resource group | `ah2-dev-rg` | `Microsoft.Resources/resourceGroups` | — | westcentralus | `/subscriptions/374149b5-c9ee-451c-8a4b-5f76e800b6ae/resourceGroups/ah2-dev-rg` |
| 2 | Function storage account | `ah2devfuncst01` | `Microsoft.Storage/storageAccounts` | Standard_LRS, StorageV2, Hot | westcentralus | `/subscriptions/374149b5-c9ee-451c-8a4b-5f76e800b6ae/resourceGroups/ah2-dev-rg/providers/Microsoft.Storage/storageAccounts/ah2devfuncst01` |
| 3 | Service Bus namespace | `ah2-dev-svcbus` (renamed — see deviation below) | `Microsoft.ServiceBus/namespaces` | Basic | westcentralus | `/subscriptions/374149b5-c9ee-451c-8a4b-5f76e800b6ae/resourceGroups/ah2-dev-rg/providers/Microsoft.ServiceBus/namespaces/ah2-dev-svcbus` |
| 3a | Initial queue | `ah2-dev-test-queue` | `Microsoft.ServiceBus/namespaces/queues` | — (14-day TTL, dead-lettering on expiration, max delivery count 10) | westcentralus | `.../namespaces/ah2-dev-svcbus/queues/ah2-dev-test-queue` |
| 4 | Key Vault | `ah2-dev-kv` | `Microsoft.KeyVault/vaults` | Standard, RBAC authorization (no access policies) | westcentralus | `/subscriptions/374149b5-c9ee-451c-8a4b-5f76e800b6ae/resourceGroups/ah2-dev-rg/providers/Microsoft.KeyVault/vaults/ah2-dev-kv` |
| 5 | Log Analytics workspace | `ah2-dev-law` | `Microsoft.OperationalInsights/workspaces` | PerGB2018, 30-day retention | westcentralus | `/subscriptions/374149b5-c9ee-451c-8a4b-5f76e800b6ae/resourceGroups/ah2-dev-rg/providers/Microsoft.OperationalInsights/workspaces/ah2-dev-law` |
| 5a | Application Insights | `ah2-dev-appi` | `Microsoft.Insights/components` | Workspace-based, linked to `ah2-dev-law` | **westus2** (see deviation below) | `/subscriptions/374149b5-c9ee-451c-8a4b-5f76e800b6ae/resourceGroups/ah2-dev-rg/providers/microsoft.insights/components/ah2-dev-appi` |
| 6 | App Service plan | `ah2-dev-plan` | `Microsoft.Web/serverfarms` | Y1 / Dynamic (Consumption), Linux | westcentralus | `/subscriptions/374149b5-c9ee-451c-8a4b-5f76e800b6ae/resourceGroups/ah2-dev-rg/providers/Microsoft.Web/serverfarms/ah2-dev-plan` |
| 7 | Function App | `ah2-dev-func` | `Microsoft.Web/sites` | Consumption (Y1), Python 3.11, Linux, system-assigned managed identity | westcentralus | `/subscriptions/374149b5-c9ee-451c-8a4b-5f76e800b6ae/resourceGroups/ah2-dev-rg/providers/Microsoft.Web/sites/ah2-dev-func` |

Default hostname: `ah2-dev-func.azurewebsites.net`. Status confirmed `Running` immediately after creation (no code deployed yet — this is the expected state pre-STEP 4B).

### Deviations from the design doc (§2–§7 above), with reasons

1. **Service Bus namespace name changed from `ah2-dev-sb` to `ah2-dev-svcbus`.** Azure rejected `ah2-dev-sb` with `InvalidSuffix` — the `-sb` suffix is reserved by the Service Bus resource provider. Kept the same naming spirit, avoided the reserved suffix.
2. **Application Insights placed in `westus2`, not `westcentralus`.** `westcentralus` is not in the supported region list for `Microsoft.Insights/components` (confirmed via ARM error listing all valid regions). Used `westus2`, Azure's official paired region for West Central US, to keep this as close to the intended region as the platform allows. The backing Log Analytics workspace (`ah2-dev-law`) remains in `westcentralus`, matching everything else.
3. **Function storage connection uses identity-based auth, not a connection-string key.** `AzureWebJobsStorage` is configured via `AzureWebJobsStorage__accountName` + `AzureWebJobsStorage__credential=managedidentity` rather than embedding a storage account key as a connection string. This follows `CLAUDE.md` rule 10 (secrets belong in Key Vault or managed identity, not plaintext) more directly than the original design's implicit assumption of a connection-string app setting, and avoids ever having a storage key in an app setting at all.
4. **`alphahound2` database not created**, per explicit Step 4A instruction not to modify the PostgreSQL server this step (see §7 above). This item from the original §6 "create now" table is deferred, not done.

### STEP 4A remediation (executed 2026-09-11, same day)

Kamil requested a follow-up remediation pass, explicitly scoped to verification + the RBAC gap only — no Step 4B code.

**1. RBAC role assignments — RESOLVED.** All three required roles are now assigned, scoped only to `ah2devfuncst01` (not the resource group or subscription):

| Role | Role assignment name (GUID) | Role definition ID |
|---|---|---|
| Storage Blob Data Owner | `7a1b2c3d-4e5f-4061-9a2b-3c4d5e6f7a01` | `b7e6dc6d-f1e8-4753-8033-0f276bb0955b` |
| Storage Queue Data Contributor | `7a1b2c3d-4e5f-4062-9a2b-3c4d5e6f7a02` | `974c5e8b-45b9-4653-ba55-5f855dd0fb88` |
| Storage Table Data Contributor | `7a1b2c3d-4e5f-4063-9a2b-3c4d5e6f7a03` | `0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3` |

All assigned to principal `d355ff8b-278b-42d7-831f-86f5d706eacf` (`ah2-dev-func`'s system-assigned identity), `principalType: ServicePrincipal`. Confirmed present via `role_assignment_list` scoped to the storage account (all three returned, correct scope, correct principal). The original tool bug (dropping the `Microsoft.Authorization` provider segment for cross-provider nested resources under a `Resource`-type scope) was worked around by using a `ResourceGroup`-type scope instead and embedding `providers/Microsoft.Authorization/roleAssignments` directly as the child resource's `resourceType` string — this produces the correct ARM extension-resource path. No manual CLI commands were needed.

**2. Application settings — submission confirmed, independent read-back still not possible this session.** Attempted two verification paths beyond the original creation payload:
  - `appservice_webapp_settings_get-appsettings` (a dedicated Azure MCP command that does exist) — rejected by the tool itself as sensitive data requiring interactive consent, which this session's client doesn't support.
  - Re-asserting the identical settings via a PUT to the `Microsoft.Web/sites/config/appsettings` child resource (would have echoed the values back) — failed twice with a generic, non-descriptive tool error (not an application-level rejection).

  No independent read-back was obtained. The settings (`FUNCTIONS_WORKER_RUNTIME=python`, `FUNCTIONS_EXTENSION_VERSION=~4`, `AzureWebJobsStorage__accountName=ah2devfuncst01`, `AzureWebJobsStorage__credential=managedidentity`, `APPLICATIONINSIGHTS_CONNECTION_STRING=...`) remain as submitted in the original Step 4A creation PUT and were accepted with no error at that time (`linuxFxVersion: Python|3.11` was independently confirmed via `siteProperties.properties`). **A portal or CLI (`az functionapp config appsettings list`) spot-check is still the only way to get a fully independent read-back** — worth doing before STEP 4B if certainty matters more than the evidence already in hand.

**3. Host health — no errors found, general-info detectors returned no data (tool limitation, not a red flag).** `functionapp_get` confirms `status: Running` (checked twice). Ran three App Service diagnostic detectors: `functions_mi` (Managed Identity Validator), `functionsGeneralInfo`, and `FNAPPHostOffline` (startup issues). All three returned empty result tables — consistent across unrelated detector types (including a basic-info detector that would normally always return data), pointing to this Azure MCP session's diagnostic-detector rendering not surfacing table data at all, rather than the app itself lacking information. Read positively: an errors/issues detector (`FNAPPHostOffline`) reporting nothing is consistent with no reported startup errors. Combined with `Running` status, `enabled: true`, `availabilityState: Normal`, `usageState: Normal` from the original creation response, this is reasonable evidence the app is healthy enough for the Functions host to initialize once code is deployed — but it is not the same as watching a cold start succeed, which STEP 4B's actual deployment will do for the first time.

**4. Content-share app settings still intentionally not configured** — unchanged from the original Step 4A note; deferred to STEP 4B when the deployment method is decided.

**Confirmed not touched in this remediation pass:** PostgreSQL, AH1 (`alphahound-rg`), `reps-portal`, Container Apps, no application/trading code.

### Subscription-level changes made outside `ah2-dev-rg`

The following Azure resource providers were registered on the subscription during Step 4A (a one-time, subscription-wide setting change, not a billable resource, and not undone by deleting `ah2-dev-rg`): `Microsoft.ServiceBus`, `Microsoft.KeyVault`, `Microsoft.Web`, `Microsoft.Insights`, `Microsoft.OperationalInsights`. No further subscription-level changes were made during the remediation pass (RBAC role assignments are scoped to the storage account resource, not the subscription).

### Confirmed NOT done (per Step 4A / remediation constraints)

- No Container Apps environment created.
- No AH1 (`alphahound-rg`) resources modified.
- `reps-portal` resource group not touched.
- No trading logic deployed — `ah2-dev-func` has zero functions/code, matching its pre-STEP-4B state.
- STEP 4B (Azure Functions code: timer trigger → queue → consumer) not started.

### Estimated incremental monthly cost (actual, post-provisioning and remediation)

Consistent with §5 above: **roughly $1–2/month**, driven almost entirely by the Function Storage Account. All other resources (Function App Consumption, Service Bus Basic, Key Vault Standard, Application Insights + Log Analytics under the free tiers) should realistically bill $0/month at dev-scale testing volume. RBAC role assignments are free. This is an estimate based on published Azure pricing, not a bill guarantee.

**STEP 4A is complete, provisioned and remediated. The RBAC gap flagged after initial provisioning is now closed. The one remaining open item — independent app-settings read-back — is a nice-to-have confirmation, not a blocker, given the settings were accepted without error at creation and no startup errors were reported.**

---

## 10. STEP 4B — Azure Functions + Service Bus foundation test (executed 2026-09-12)

Kamil authorized STEP 4B: build and deploy the first real AH2 workflow — Timer Function → publish a test event → `ah2-dev-test-queue` → queue-triggered Function → structured success log — with Python 3.11, Azure Functions v4, managed-identity/secretless patterns, a correlation ID propagating publisher → Service Bus → consumer, and a specific event envelope. No trading logic, no Postgres changes, no AH1/`reps-portal` changes, no Container Apps, no paid-data subscriptions, no STEP 5.

### Files created

All under `docs/AH2/`:

| Path | Purpose |
|---|---|
| `src/function_app.py` | Entry point — timer trigger (output-bound to Service Bus) + queue trigger, both via the identity-based `ServiceBusConnection` app setting |
| `src/domain/events.py` | `AH2Event` envelope (`event_id`, `event_type`, `correlation_id`, `source`, `created_at`, `schema_version`, `payload`) + `new_event()` + JSON serialize/deserialize + validation |
| `src/application/timer_service.py` | `build_foundation_test_event()` — pure, testable business logic behind the timer trigger |
| `src/application/queue_consumer_service.py` | `process_foundation_test_message()` — pure, testable business logic behind the queue trigger |
| `src/infrastructure/observability/logging_setup.py` | `log_event()` — structured logging helper (Application Insights `custom_dimensions`) |
| `src/infrastructure/messaging/service_bus.py` | Shared binding constants + documented retry/dead-letter strategy |
| `src/infrastructure/configuration/settings.py` | Env-var based config (source name, queue name) |
| `src/shared/ids.py` | UUID generation, shared by `domain/events.py` |
| `src/host.json`, `src/requirements.txt`, `src/local.settings.json` (gitignored), `src/.funcignore` | Standard Azure Functions project files |
| `tests/conftest.py`, `tests/test_events.py`, `tests/test_timer_service.py`, `tests/test_queue_consumer_service.py`, `tests/test_logging_setup.py` | Full test suite (32 tests) |
| `pytest.ini`, `requirements-dev.txt` | Test configuration/dependencies |
| `build_zip.ps1` | Deployment packaging script (see "Deployment method" below — required after a real, environment-specific bug was found) |
| `.gitignore` (repo root) | Added `local.settings.json` |

### App settings added to `ah2-dev-func`

| Setting | Value | Purpose |
|---|---|---|
| `ServiceBusConnection__fullyQualifiedNamespace` | `ah2-dev-svcbus.servicebus.windows.net` | Identity-based Service Bus binding connection (no connection string) |
| `AH2_SOURCE_NAME` | `ah2-dev-func` | Used in the event's `source` field |
| `AH2_TEST_QUEUE_NAME` | `ah2-dev-test-queue` | Queue name, referenced via `%AH2_TEST_QUEUE_NAME%` binding expression rather than hard-coded twice |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` | Left set from STEP 4A; not actually exercised by the deployment method that ended up working (see below) |
| `WEBSITE_RUN_FROM_PACKAGE` | SAS URL to the deployment zip in blob storage | The deployment mechanism itself — see "Deployment method" |

### RBAC added for STEP 4B (Service Bus)

Scoped **only to `ah2-dev-test-queue`**, not the namespace or subscription:

| Role | Role assignment name (GUID) | Role definition ID |
|---|---|---|
| Azure Service Bus Data Sender | `8b2c3d4e-5f6a-4071-9a2b-3c4d5e6f7b01` | `69a216fc-b8fb-44d8-bc22-1f3c2cd27a39` |
| Azure Service Bus Data Receiver | `8b2c3d4e-5f6a-4072-9a2b-3c4d5e6f7b02` | `4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0` |

Both assigned to `ah2-dev-func`'s system-assigned identity (`d355ff8b-278b-42d7-831f-86f5d706eacf`). Combined with the STEP 4A remediation's storage roles (Blob Data Owner, Queue Data Contributor, Table Data Contributor, all scoped to `ah2devfuncst01`), this is the complete RBAC surface for STEP 4B — no connection strings, no secrets, anywhere.

A separate, temporary grant was also needed during deployment: Kamil's own AAD identity was given **Storage Blob Data Contributor**, scoped only to the `deploy` blob container (assignment `9c3d4e5f-6a7b-4081-9a2b-3c4d5e6f7c01`), so he could upload the deployment package via `az storage blob upload --auth-mode login` without a storage account key. This is a legitimate, narrowly-scoped, human-operator grant (not used by the running application) and can be revoked once STEP 4B's deployment approach is superseded by a permanent CI/CD pipeline.

### Test results

**32 of 32 tests passed** (pytest 9.1.1, local venv Python 3.13.5 — the deployed Function App runs Python 3.11; nothing in the test suite is Python-version-sensitive, so this discrepancy doesn't affect validity):

- `test_events.py` (19 tests) — event construction, unique ID generation, explicit correlation_id override, JSON round-trip (`to_json`/`from_json`, including bytes input matching a real Service Bus message body), and rejection of invalid JSON, non-object JSON, each individually-missing required field, and a non-dict payload
- `test_timer_service.py` (5 tests) — event type/source/payload shape, schema version, fresh IDs per call
- `test_queue_consumer_service.py` (5 tests) — round-trips the published event, preserves `correlation_id`/`event_id`, and raises `EventValidationError` on malformed JSON, missing required fields, and an empty body
- `test_logging_setup.py` (3 tests) — structured logging helper includes correlation fields, omits `None` fields, passes through arbitrary extra fields

Command: `pytest tests\ -v` from `docs/AH2/` (after `pip install -r requirements-dev.txt` in a dedicated venv). Full output captured in this conversation; zero failures, zero errors.

### Deployment method (and two real bugs found + fixed along the way)

This took considerably more troubleshooting than expected — both issues are documented here in detail because they will recur for any future deployment to this Function App using this same method.

**Why "run from package via external URL blob", not `func azure functionapp publish` or `az functionapp deployment source config-zip`:** Azure Functions Core Tools (`func`) is not installed on `repsportalvm`, and the standard `az functionapp deployment source config-zip` command was rejected outright by the Azure CLI ("The Azure CLI does not support this deployment path"). The newer `az functionapp deploy` (OneDeploy) command was also rejected ("This API isn't available in this environment yet"). Kudu/SCM (`ah2-dev-func.scm.azurewebsites.net`) returns `404` on every endpoint tried (VFS browsing, log streaming, log download) — from both the automation session and Kamil's own authenticated browser — indicating Kudu is not reachable at all for this Function App/environment, not merely an auth issue. **Working method:** upload a zip to blob storage (`ah2devfuncst01/deploy/ah2-dev-func-deploy.zip`), point `WEBSITE_RUN_FROM_PACKAGE` at it, and force a re-index with `az resource invoke-action ... --action syncfunctiontriggers` after each restart.

**Bug 1 — sys.path.** In this deployment mode, the Python worker does not reliably put `/home/site/wwwroot` (the directory containing `function_app.py`) on `sys.path`, so the sibling packages (`application/`, `domain/`, `infrastructure/`, `shared/`) failed to import with `ModuleNotFoundError: No module named 'application'`. **Fix:** `function_app.py` now explicitly does `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` before importing anything else, with a comment explaining why.

**Bug 2 — zip path separators.** After fixing Bug 1, the *same* `ModuleNotFoundError` persisted. Root cause: on this specific machine, **both** PowerShell's `Compress-Archive` and .NET's `[System.IO.Compression.ZipFile]::CreateFromDirectory()` produce zip entries using backslash (`\`) path separators (e.g. `application\queue_consumer_service.py`) instead of the ZIP-format-standard forward slash (`/`). Linux does not treat `\` as a directory separator, so on the deployed Linux host these were not nested folders at all — just oddly-named flat files — meaning `application` never existed as an importable package in the deployed content, regardless of the sys.path fix. **Fix:** `build_zip.ps1` (committed) manually walks `src/` and adds each file to the zip with an explicitly forward-slash-joined relative path (`$relativePath.Replace('\', '/')`), bypassing both broken APIs. It also excludes `local.settings.json` and `__pycache__`. **This script must be used for any future deployment of this Function App** — do not revert to a plain `Compress-Archive` one-liner.

**Deployment steps (for reference / next time):**
1. `pip install -r requirements.txt --target=".python_packages/lib/site-packages" --platform manylinux2014_x86_64 --python-version 3.11 --implementation cp --only-binary=:all: --upgrade` from `src/` — vendors dependencies for the correct platform (a plain local `pip install --target` on this Windows/Python-3.13 box pulls Windows/3.13 binary wheels, which also breaks on Linux — same class of issue as Bug 2, different symptom).
2. `& docs/AH2/build_zip.ps1` — builds the zip with correct path separators.
3. `az storage blob upload --account-name ah2devfuncst01 --auth-mode login --container-name deploy --name ah2-dev-func-deploy.zip --file ah2-dev-func-deploy.zip --overwrite`
4. `az resource invoke-action --resource-group ah2-dev-rg --name ah2-dev-func --resource-type "Microsoft.Web/sites" --action syncfunctiontriggers`
5. `az functionapp restart --name ah2-dev-func --resource-group ah2-dev-rg`

Steps 4 and 5 both appear necessary in practice — a restart alone was observed to serve stale cached code at least once; pairing it with an explicit `syncfunctiontriggers` call is what reliably picked up the new package in testing.

### Azure runtime verification

All verified via Application Insights (`AppTraces` in the `ah2-dev-law` Log Analytics workspace) and `az functionapp function list`:

- **Function host initializes correctly:** `az functionapp function list` shows both `AH2FoundationTimer` and `AH2FoundationQueueConsumer`, both enabled, Python.
- **Timer executes:** confirmed via the Functions host's own `Executing 'Functions.AH2FoundationTimer' (Reason='Timer fired at ...')` trace, both on `run_on_startup` and on the natural 5-minute schedule (`0 */5 * * * *`).
- **Message appears in Service Bus and consumer receives it:** confirmed by the queue-triggered function executing immediately after the timer, every time, with no manual intervention.
- **Correlation ID propagates end-to-end:** at `2026-09-12T11:57:16Z`, the publish log reads `AH2 foundation test event published (correlation_id=a1addf00-6c5f-4661-8e04-a9a15bb52bd8, event_id=40aca3dc-d7c5-40d7-8f8c-2751836cf8b8)` and the consume log — same timestamp — reads `AH2 foundation test event processed successfully (correlation_id=a1addf00-6c5f-4661-8e04-a9a15bb52bd8, event_id=40aca3dc-d7c5-40d7-8f8c-2751836cf8b8)`. Same `correlation_id`, same `event_id`, publisher through consumer.
- **Bonus/independent signal:** Application Insights' own distributed-tracing `OperationId` also matched across the timer and consumer invocations for a given run, corroborating the causal link independent of our own correlation_id field.

**Note on custom_dimensions:** `log_event()` still passes `correlation_id`/`event_id`/etc. via `extra={"custom_dimensions": {...}}`, which is the documented pattern for structured Application Insights properties — but in this environment's `AppTraces`, only the platform's own invocation metadata (`InvocationId`, `ProcessId`, `HostInstanceId`, `Category`) appeared in `Properties`; our custom fields did not surface there. Rather than spend further time on the SDK/worker internals, the pragmatic and now-verified fix was to embed `correlation_id`/`event_id` directly in the log **message text** as well, which is what the verification above relies on. This is a reasonable, durable pattern for future AH2 functions, not just a one-off workaround — plain-text search is simpler to rely on than a custom-dimensions pipeline whose behavior appears environment-dependent.

### Warnings / known limitations for future STEP 4B-adjacent work

- **No CI/CD pipeline exists.** Every deployment above was done manually via the steps listed. A future step should set up a real pipeline (GitHub Actions or Azure DevOps) using the same `build_zip.ps1` logic (or a Linux-native build agent, which would sidestep Bug 2 entirely since it wouldn't hit Windows's backslash-producing zip APIs).
- **Kudu/SCM is not usable for this Function App** in this environment — no VFS browsing, no log streaming, no log download, from either the automation session or a real authenticated browser. Any future troubleshooting should go straight to Application Insights/Log Analytics (`AppTraces`, `AppExceptions`) rather than attempting Kudu-based inspection.
- **`az functionapp deployment source config-zip` and `az functionapp deploy` (OneDeploy) are both unavailable for this Function App** in this environment — don't reattempt them without first understanding why (likely related to SCM/basic-auth publishing credentials being disabled, though this wasn't independently confirmed).
- **Kamil's temporary Storage Blob Data Contributor grant** (scoped to the `deploy` container) exists purely to support manual deployment via his own login and should be revisited/revoked once a real CI/CD identity takes over deployments.
- **The diagnostic-detector table-rendering limitation noted in STEP 4A** (empty `Table` fields from `appservice_webapp_diagnostic_diagnose`) persisted in STEP 4B — the Portal UI itself (`Diagnose and solve problems` → `Function App Down or Reporting Errors` → `Functions that are not triggering`) was the one path that surfaced the actual Python traceback and was essential to finding Bug 1.

**STEP 4B is complete: code written, tested (32/32 passing), deployed, and verified end-to-end on Azure with correlation ID propagation confirmed in logs. Stopping here per instruction — STEP 5 is not authorized until Kamil explicitly approves it.**
