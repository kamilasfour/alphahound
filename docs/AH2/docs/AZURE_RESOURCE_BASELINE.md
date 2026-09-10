# Azure Resource Baseline

**Step:** STEP 2 — Confirm Azure Resource Baseline (per `IMPLEMENTATION_PLAYBOOK.md`)
**Status:** Partial — see "Tooling limitation" below. No Azure resources created, modified, deleted, or migrated.
**Date:** 2026-09-10

---

## Tooling limitation (read this first)

Claude has no Azure CLI or Azure API access in this environment — there is no available tool to query the live Azure subscription directly. Everything in this document is one of two things:

- **Confirmed from repo/config** — verifiable directly from source, cited below.
- **Unknown — needs Kamil to confirm** — requires running the Azure CLI commands listed in each section and pasting the output back, the same pattern used for `Get-ScheduledTaskInfo` in Step 1.

No "EXISTS / CREATE / REUSE / REPLACE / NOT NEEDED YET" decision is recorded for anything I couldn't verify — guessing here risks either provisioning a duplicate of something that already exists, or wrongly assuming something exists when it doesn't.

---

## 1. Azure subscription & region

**Status: Unknown — needs confirmation**

Nothing in the repo records a subscription ID, tenant, or default region.

Run and paste back:
```powershell
az account show --output table
az account list --output table
```

**Decision output:** *Pending.*

---

## 2. Resource groups

**Status: Partially inferable, not confirmed**

The Postgres hostname in `.env` (see §3) is `alphahound-rg.postgres.database.azure.com`. `alphahound-rg` is the **PostgreSQL Flexible Server name** — it is *not* necessarily the resource group name, even though the naming convention suggests it might be. This should not be assumed.

Run and paste back:
```powershell
az group list --output table
```

**Decision output:** *Pending.*

---

## 3. PostgreSQL

**Status: Confirmed to exist, details partially confirmed from `.env`**

From `DATABASE_URL` in `.env` (password redacted — not reproduced per this step's "no secrets in the document" rule):

| Field | Value |
|---|---|
| Server type | Azure Database for PostgreSQL — Flexible Server |
| Server FQDN | `alphahound-rg.postgres.database.azure.com` |
| Database name | `alphahound` |
| Admin user | `alphahound_admin` |
| Port | `5432` |
| SSL | Required (`sslmode=require`) |

Not confirmed from the connection string: region, compute tier/SKU, storage size, backup retention, firewall/VNet rules, high-availability configuration, or which resource group it lives in.

Run and paste back:
```powershell
az postgres flexible-server list --output table
az postgres flexible-server show --name alphahound-rg --resource-group <rg-name-from-§2>
az postgres flexible-server firewall-rule list --name alphahound-rg --resource-group <rg-name-from-§2>
```

**Decision output:** **EXISTS** (server + database confirmed reachable — this is what AH1 runs on today). Region/SKU/networking: *pending.*

---

## 4. Azure Storage

**Status: Unknown — no evidence in repo**

`IMPLEMENTATION_PLAYBOOK.md` §2 lists Azure Storage as part of the "current starting position," but no connection string, account name, or SDK dependency (`azure-storage-blob`, etc.) appears anywhere in `.env` or `pyproject.toml`. Either it exists but isn't wired into AH1 yet, or it doesn't exist yet.

Run and paste back:
```powershell
az storage account list --output table
```

**Decision output:** *Pending.*

---

## 5. Networking configuration

**Status: Unknown**

No VNet, subnet, private endpoint, or firewall configuration is referenced anywhere in the repo.

Run and paste back:
```powershell
az network vnet list --output table
```

**Decision output:** *Pending.*

---

## 6. App Service / VM resources

**Status: Unknown, but likely irrelevant**

AH1 currently runs on Windows Server 2022 (`repsportalvm`) outside Azure App Service — this looks like a self-managed VM or on-prem/other-cloud box, not an Azure compute resource. Worth confirming it isn't already an Azure VM before assuming it's out of scope.

Run and paste back:
```powershell
az vm list --output table
az webapp list --output table
```

**Decision output:** *Pending — likely NOT NEEDED YET for AH2 (Functions replace this role per ADR-001), but confirm `repsportalvm` isn't itself an Azure VM first.*

---

## 7. Key Vault

**Status: Unknown — no evidence in repo**

All current secrets (Postgres password, Finnhub/Massive/Quiver/Unusual Whales/Anthropic/Alpaca keys) live in plaintext `.env` on the Windows server, not in Key Vault. This is expected for AH1 (predates the AH2 rules) but is exactly what ADR-004/`CLAUDE.md` rule 10 requires AH2 to move away from.

Run and paste back:
```powershell
az keyvault list --output table
```

**Decision output:** *Pending — if none exists, disposition is **CREATE** (required by `CLAUDE.md` rule 10 and STEP 3/4 of the playbook).*

---

## 8. Application Insights

**Status: Unknown — no evidence in repo**

No Application Insights connection string or instrumentation key appears in `.env` or code.

Run and paste back:
```powershell
az monitor app-insights component show --output table
```

**Decision output:** *Pending — if none exists, disposition is **CREATE** (required for STEP 4 observability requirements).*

---

## 9. Function Apps

**Status: Confirmed NOT present in code**

`pyproject.toml` has no `azure-functions` dependency, and no `host.json`, `function.json`, or `local.settings.json` exists anywhere in the repository. No Azure Functions project has been scaffolded yet — this matches `IMPLEMENTATION_PLAYBOOK.md` STEP 4 being un-started.

Run and paste back (to check whether one exists in Azure despite no local scaffold):
```powershell
az functionapp list --output table
```

**Decision output:** **NOT NEEDED YET locally** (correctly — Functions scaffolding is STEP 4, not STEP 2). Azure-side existence: *pending.*

---

## 10. Service Bus

**Status: Unknown — no evidence in repo**

No `azure-servicebus` dependency, no connection string, no queue/topic names referenced anywhere in the codebase.

Run and paste back:
```powershell
az servicebus namespace list --output table
```

**Decision output:** *Pending — if none exists, disposition is likely **CREATE** (required by ADR-001 for AH2's async event architecture, STEP 5).*

---

## 11. Container Apps environment

**Status: Unknown — no evidence in repo**

`ARCHITECTURE.md` §10 mentions Azure Container Apps GPU as a future compute option for heavier model inference, but nothing indicates one exists yet.

Run and paste back:
```powershell
az containerapp env list --output table
```

**Decision output:** *Pending — almost certainly **NOT NEEDED YET** given the roadmap sequencing (GPU compute isn't needed until Phase 3, well after Functions foundation).*

---

## 12. Fastest path to completing this document

Running these two commands and pasting the output back closes most of the gaps above in one pass:

```powershell
az account show --output table
az resource list --output table
```

`az resource list` returns every resource in the subscription (name, resource group, type, location) in a single call — covers §1, §2, §4, §5, §6, §7, §8, §9, §10, and §11 at once. §3's deeper Postgres detail (SKU, firewall rules, HA config) needs the additional `az postgres flexible-server show` / `firewall-rule list` commands listed in that section.

---

## What was explicitly NOT done in this step

- No Azure resources were created, modified, deleted, or migrated.
- No secrets (the Postgres password or any API key) were written into this document.
- No decision above was guessed where evidence was unavailable — items are marked "Pending" rather than assumed.

**This step is incomplete pending the Azure CLI output above. Once provided, this document will be updated and then stopped for review before STEP 3 is authorized — per the playbook, STEP 3 does not begin until this baseline is reviewed.**
