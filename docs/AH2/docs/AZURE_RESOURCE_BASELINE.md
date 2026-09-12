# Azure Resource Baseline

**Step:** STEP 2 — Confirm Azure Resource Baseline (per `IMPLEMENTATION_PLAYBOOK.md`)
**Status:** Complete.
**Confirmed by:** Kamil, 2026-09-10.
**Updated:** 2026-09-11 — resources listed as CREATE below were provisioned under Step 4A. See `AH2_DEV_ENVIRONMENT.md` §9 for full detail (actual names, resource IDs, deviations, and follow-ups).

---

## 1. Azure subscription & region

| Field | Value |
|---|---|
| Region | **West Central US** (dev resources; Application Insights landed in West US 2 — see note below) |
| Subscription ID | `374149b5-c9ee-451c-8a4b-5f76e800b6ae` ("Azure subscription 1") |
| Tenant ID | `330c25eb-026b-49c0-a220-c79b629aa93a` |

---

## 2. Resource groups

| Resource Group | Region | Current Contents |
|---|---|---|
| `alphahound-rg` | West Central US | PostgreSQL Flexible Server only (confirmed by Kamil) — untouched by Step 4A |
| `ah2-dev-rg` | West Central US | AH2 dev infrastructure, provisioned Step 4A: Function storage account, Service Bus namespace + queue, Key Vault, Log Analytics workspace, Application Insights, App Service plan, Function App |

`ah2-dev-rg` was created in Step 4A per `AH2_DEV_ENVIRONMENT.md` §2. No other AlphaHound-related resource groups exist in the subscription.

---

## 3. PostgreSQL

**Decision: EXISTS — REUSE**

| Field | Value |
|---|---|
| Server type | Azure Database for PostgreSQL — Flexible Server |
| Server name | `alphahound-rg` |
| Resource group | `alphahound-rg` |
| Region | West Central US |
| PostgreSQL version | 17.11 |
| Tier | Burstable B2s |
| Compute | 2 vCores |
| Memory | 4 GB RAM |
| Storage | 32 GiB |
| Database name | `alphahound` (from `.env` `DATABASE_URL`) |
| Admin user | `alphahound_admin` (from `.env` — password not reproduced here) |
| Port / SSL | 5432, `sslmode=require` |

This is the same server AH1 currently runs on. Per ADR-002, AH2 reuses this server — no new database technology is introduced. **Not modified in Step 4A** — Kamil's authorization explicitly excluded touching this server. The proposed `alphahound2` database (STEP 6 prep) remains a future step, not done.

**Open item (non-blocking):** exact networking configuration (public access + firewall rules vs. VNet-integrated/private endpoint) wasn't specified. See `AH2_DEV_ENVIRONMENT.md` §7 for the dev-vs-production connectivity recommendation.

---

## 4. Azure Storage

**Decision: CREATED (Step 4A)**

| Field | Value |
|---|---|
| Account name | `ah2devfuncst01` |
| Resource group | `ah2-dev-rg` |
| Region | West Central US |
| SKU | Standard_LRS, StorageV2, Hot tier |
| Purpose | Required backing storage for `ah2-dev-func` (every Function App needs one) |

Existing Storage accounts in the subscription belonging to unrelated projects were not reused, consistent with the original decision.

---

## 5. Networking configuration

Not separately provisioned. `ah2-dev-rg` resources use public endpoints with SSL/TLS (no VNet, subnet, or private endpoint), consistent with the dev-scale recommendation in `AH2_DEV_ENVIRONMENT.md` §7. Revisit before production or before any workflow touches real capital.

---

## 6. App Service / VM resources

**Decision: CREATED (Step 4A)** — App Service plan `ah2-dev-plan` (Consumption/Y1, Linux) in `ah2-dev-rg`, backing `ah2-dev-func`.

`alphahound-rg` still contains no App Service or VM resources — consistent with AH1's Windows Server (`repsportalvm`) staying out of scope for AH2 infrastructure.

---

## 7. Key Vault

**Decision: CREATED (Step 4A)**

| Field | Value |
|---|---|
| Name | `ah2-dev-kv` |
| Resource group | `ah2-dev-rg` |
| SKU | Standard |
| Authorization model | Azure RBAC (`enableRbacAuthorization: true`) — no legacy access policies |

Empty at creation — no secrets have been written to it yet. Required by `CLAUDE.md` rule 10 and ADR-004 before any AH2 secret (Postgres credentials, provider API keys) moves out of plaintext `.env`.

---

## 8. Application Insights

**Decision: CREATED (Step 4A)**

| Field | Value |
|---|---|
| Name | `ah2-dev-appi` |
| Resource group | `ah2-dev-rg` |
| Region | **West US 2** (not West Central US — see deviation note in `AH2_DEV_ENVIRONMENT.md` §9; `westcentralus` is not a supported region for this resource type) |
| Mode | Workspace-based, linked to Log Analytics workspace `ah2-dev-law` (West Central US, PerGB2018, 30-day retention) |

---

## 9. Function Apps

**Decision: CREATED (Step 4A)**

| Field | Value |
|---|---|
| Name | `ah2-dev-func` |
| Resource group | `ah2-dev-rg` |
| Region | West Central US |
| Plan | `ah2-dev-plan` — Consumption (Y1), Linux |
| Runtime | Python 3.11 |
| Identity | System-assigned managed identity (principal ID `d355ff8b-278b-42d7-831f-86f5d706eacf`) |
| Status | Running, no code deployed |

Storage connection (`AzureWebJobsStorage`) is configured identity-based rather than via a connection-string key. **RBAC remediated 2026-09-11**: the system-assigned identity now holds Storage Blob Data Owner, Storage Queue Data Contributor, and Storage Table Data Contributor, scoped only to `ah2devfuncst01`. See `AH2_DEV_ENVIRONMENT.md` §9 "STEP 4A remediation" for role assignment IDs and the one remaining open item (independent app-settings read-back, non-blocking).

---

## 10. Service Bus

**Decision: CREATED (Step 4A)**

| Field | Value |
|---|---|
| Namespace | `ah2-dev-svcbus` (renamed from the originally proposed `ah2-dev-sb` — that suffix is reserved by Azure; see deviation note) |
| Resource group | `ah2-dev-rg` |
| Region | West Central US |
| SKU | Basic |
| Initial queue | `ah2-dev-test-queue` (14-day TTL, dead-lettering on expiration, max delivery count 10) |

---

## 11. Container Apps environment

**Decision: NOT NEEDED YET**

Consistent with roadmap sequencing — GPU/container compute isn't needed until Phase 3 (Model Gateway), well after the Functions foundation (Phase 1) is built. Explicitly excluded from Step 4A.

---

## Summary table

| Resource | Status | Decision |
|---|---|---|
| Resource group `alphahound-rg` | Exists | REUSE — untouched |
| Resource group `ah2-dev-rg` | Exists | CREATED (Step 4A) |
| PostgreSQL Flexible Server `alphahound-rg` | Exists | REUSE — untouched in Step 4A |
| Azure Storage `ah2devfuncst01` | Exists | CREATED (Step 4A) |
| Networking (VNet/private endpoint) | Not provisioned | Open — public access + SSL for dev, revisit for production |
| App Service plan `ah2-dev-plan` | Exists | CREATED (Step 4A) |
| Key Vault `ah2-dev-kv` | Exists | CREATED (Step 4A) — empty |
| Log Analytics workspace `ah2-dev-law` | Exists | CREATED (Step 4A) |
| Application Insights `ah2-dev-appi` | Exists | CREATED (Step 4A) — West US 2, not West Central US |
| Function App `ah2-dev-func` | Exists | CREATED (Step 4A) — running, no code, RBAC remediated 2026-09-11 |
| Service Bus namespace `ah2-dev-svcbus` + queue `ah2-dev-test-queue` | Exists | CREATED (Step 4A) — renamed from proposed `ah2-dev-sb` |
| Container Apps environment | Does not exist | NOT NEEDED YET |

---

## What was explicitly NOT done in Step 2 (2026-09-10, original baseline)

- No Azure resources were created, modified, deleted, or migrated.
- No secrets were written into this document.
- No infrastructure-as-code was written.

(Step 4A, executed 2026-09-11, is a separate, explicitly authorized step — see `AH2_DEV_ENVIRONMENT.md` §9 for its full record, including deviations and open follow-ups.)
