# AH2 Development Environment

**Step:** STEP 3 — Create AH2 Development Environment (per `IMPLEMENTATION_PLAYBOOK.md`)
**Status:** Design/documentation only. **No Azure resources created, modified, or deleted. No Azure CLI run. No Functions code written.**
**Date:** 2026-09-10

---

## 1. Scope of this document

This is a design proposal for review — resource names, tiers, and cost estimates for the isolated AH2 development environment. Nothing here is provisioned. Per `IMPLEMENTATION_PLAYBOOK.md` STEP 3: *"Claude may create Infrastructure-as-Code or documented provisioning steps only after this step is explicitly approved."* That happens in a later step, not this one.

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
| PostgreSQL | Existing Burstable B2s (already running for AH1) | Fixed monthly cost regardless of AH2 usage | **$0 incremental** — reusing what's already paid for; adding the `alphahound2` database costs nothing extra beyond the ~32 GiB storage already provisioned | **No** — Burstable tier has a fixed monthly cost whether idle or not, but this is an existing sunk cost, not new spend |

**Total estimated incremental monthly cost for the dev environment at light development-stage usage: roughly $1–2/month**, driven almost entirely by the Function Storage Account (the only resource here without a meaningful free tier). Everything else should realistically land at $0/month until usage grows well past dev-scale testing.

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
| `alphahound2` database on the existing PostgreSQL server | |

---

## 7. PostgreSQL — reuse decision and connectivity options

**Decision: reuse the existing `alphahound-rg` PostgreSQL Flexible Server. Do not create a second server.** Propose a new, separate database on that server — `alphahound2` — so AH2 schema work (STEP 6) has a clean space with zero risk of touching AH1 tables. This matches ADR-002 (PostgreSQL as system of record) and the AH1 Protection Rule.

### Connectivity options for Azure Functions → PostgreSQL

| Option | How it works | Security | Cost | Complexity |
|---|---|---|---|---|
| **A. Public access + SSL, dev firewall pattern** | Postgres Flexible Server networking stays in its current "Public access" mode with `sslmode=require` (already enforced); firewall allows the appropriate Azure access pattern (e.g. "Allow public access from any Azure service within Azure to this server") rather than a fixed IP allow-list | Moderate — traffic is encrypted end-to-end, but the server has a public endpoint | $0 extra | Low — no additional resources, works with Consumption plan |
| **B. VNet integration + Private Endpoint** | Function App gets VNet integration (requires **Premium plan**, not Consumption), Postgres gets a private endpoint, traffic never leaves the VNet | Highest — no public endpoint at all | Adds real cost — Premium plan starts around $150–180+/month minimum for one pre-warmed instance | High — VNet, subnet, private DNS zone, Premium plan migration |

**Important correction on Option A:** the Consumption plan does **not** give a Function App a small, permanently stable set of outbound IP addresses. Outbound IPs for Consumption-plan Functions are drawn from a documented but non-fixed pool for the region and can change as the platform scales instances. Do not design a firewall rule around "allow-list these N specific IPs" for a Consumption-plan Function App — that assumption will silently break. Dev firewall configuration should instead use the broader Azure-service access pattern, or be configured/validated based on the Function App's actual observed outbound behavior once it exists, rather than a static per-IP rule.

**Recommendation for dev: Option A, public access with SSL.** This is acceptable for AH2 dev — the database is brand new, empty, and isolated from AH1 by design (§6/§7's whole purpose). Paying for a Premium plan and building VNet infrastructure to protect an empty dev database isn't proportionate — it would roughly 100x the Function App cost alone for no real risk reduction at this stage. Credentials for the `alphahound2` connection should still go into Key Vault (not `.env`, not source) and be referenced by the Function App via a Key Vault reference / managed identity, per `CLAUDE.md` rule 10 — that's the actual security boundary that matters here, not network topology.

**Production / real-capital execution (later, not this step):** PostgreSQL networking must be explicitly revisited and will very likely need to be tightened — via VNet integration + Private Endpoint (Option B) or another controlled private-access design — before any AH2 workflow touches real capital. Public access with SSL, acceptable for an empty dev database, is not an acceptable end-state once AH2 is trading. This decision should be made explicitly in a future ADR/task, not assumed now.

---

## 8. What was explicitly NOT done in this step

- No Azure resources were created, modified, or deleted.
- No Azure CLI commands were run.
- No Azure Functions code was written.
- No IaC (Bicep/Terraform/ARM) was written.
- STEP 4 was not started.

**STEP 3 is complete as a design document. Stopping here for review — STEP 4 is not authorized until this design is reviewed and approved.**
