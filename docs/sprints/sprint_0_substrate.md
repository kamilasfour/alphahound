# Sprint 0 — Substrate ✅

**Dates:** April 18, 2026 (single day)
**Status:** Complete
**Goal:** Decide the substrate the codebase will sit on, before writing any code.

---

## Why this sprint existed

Before Sprint 1 could write files, we had to agree on: which database, hosted where, secrets strategy, Python version, how Claude and humans split work. Skipping this = rewriting everything in Sprint 3 when we realize SQLite can't host Timescale.

---

## Definition of done

- [x] Database target chosen and provisioned
- [x] Connection path from VM → DB verified
- [x] Tooling decisions written down
- [x] Scope boundaries set (what's in vs out for Sprint 1)

---

## What was decided

| Question | Decision | Why |
|---|---|---|
| Hosted DB vs VM-local | **Azure Postgres Flexible Server** | Separates app layer from data layer. VM becomes app host only. |
| Shared DB with Forkcast/MeshAI? | **Dedicated server** | Blast radius, Timescale isolation, legal artifact (trade log) shouldn't share fate with unrelated projects. |
| Postgres version | **17.9** | PG18 is too new for reliable Timescale compat; PG17 is the sweet spot. |
| Tier | **Burstable B2s** ($64/mo) | Dev workload; scale up later is easy. |
| Region | **West Central US** | Matches the `repsportalvm` VM for low latency. |
| Resource group | **`alphahound-rg`** (new) | Follows existing naming convention (`Forkcast-MVP`, `MeshAI`, `qdrive-production-rg`); clean blast radius. |
| Time-series | **TimescaleDB extension** | PRD A10.2 requires hypertables; Timescale is the only sane choice on Postgres. |
| Secrets (dev) | **`.env` file** | Less friction than Key Vault for local dev. Key Vault migration is a Sprint 8 task. |
| Secrets (prod) | **Azure Key Vault** | PRD A12 requirement. |
| SQL UI | **DBeaver Community** | PGAdmin 9.0 had session drop bugs with Azure PG. DBeaver is stable. |
| Script runner | **psql** (already on VM) | Command-line, reliable, scriptable. |
| Role split | Claude = PM/architect, Claude Code + Cursor = code, Kamil = executor | Established in `ground_rules.md`; carried forward. |

---

## What was provisioned

**Azure Database for PostgreSQL Flexible Server**
- Endpoint: `alphahound-rg.postgres.database.azure.com`
- Port: 5432
- Admin: `alphahound_admin`
- Auth: password (SSL required)
- Firewall: Kamil's IP + "Allow Azure services"
- TimescaleDB: enabled via `azure.extensions` parameter AND `shared_preload_libraries` (both required — the second one caught us out)

**Resource group:** `alphahound-rg`
**VM (app host):** `repsportalvm`, Windows Server 2022, Python 3.13.5, psql 15.12 pre-installed

---

## Things that went sideways (lessons for future sprints)

1. **Portal form defaulted to $609/mo.** Caught by switching Workload Type to Dev/Test + disabling HA. **Lesson:** every Azure wizard defaults to enterprise pricing — always inspect.
2. **PostgreSQL version defaulted to 18.** Caught before data was written. **Lesson:** Azure defaults are for brand new installs; pick explicitly.
3. **TimescaleDB needed two settings, not one.** First we enabled it in `azure.extensions`, which is necessary but not sufficient. Also needed to add `TIMESCALEDB` to `shared_preload_libraries` and restart. **Lesson:** Azure's UX here is misleading.
4. **PGAdmin 9.0 drops sessions mid-script.** We switched to DBeaver. **Lesson:** prefer DBeaver for ad-hoc SQL.

---

## What was explicitly NOT done (out of scope)

- Azure Blob storage (deferred to Sprint 5 — nothing to archive yet)
- Azure Key Vault (deferred — `.env` is fine for dev)
- Private endpoint / VNet integration (deferred to Sprint 3 — "allow Azure services" is fine for now)
- Git remote (open question — needed before Claude Code / Cursor can work on the repo remotely)

---

## Exit criteria — all green

- [x] Can connect from the VM with `psql`
- [x] Firewall verified with a successful `SELECT version();`
- [x] Cost estimate confirmed <$70/mo
- [x] Resource group separate from other projects
- [x] PRD A10.2 infrastructure requirements understood and committed to
