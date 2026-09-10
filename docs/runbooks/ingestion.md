# Runbook — Ingestion

**Scope:** the `AlphaHound-Ingest` Windows scheduled task, its PowerShell wrapper, and the two adapters it runs (ApeWisdom, StockTwits).

---

## What normal looks like

- Task runs every 15 minutes, on the :00/:15/:30/:45 boundaries.
- Each run completes in under 30 seconds.
- `alphahound db ingest-runs --tail 20` shows both adapters succeeding.
- `raw_posts` grows by roughly 100 (ApeWisdom) + 200–600 (StockTwits) rows per run.
- No errors in `C:\alphahound_project\logs\ingest_YYYY-MM-DD.log`.

---

## Check task health (30 seconds)

```powershell
# Is the task registered?
Get-ScheduledTask -TaskName AlphaHound-Ingest

# When did it last run, and did it succeed?
Get-ScheduledTaskInfo -TaskName AlphaHound-Ingest | Format-List LastRunTime, LastTaskResult, NextRunTime

# Recent run history from the DB (authoritative)
cd C:\alphahound_project
.\.venv\Scripts\Activate.ps1
alphahound db ingest-runs --tail 20
```

`LastTaskResult = 0` means success. Any other value = failed run; check logs.

---

## Read today's log

```powershell
Get-Content C:\alphahound_project\logs\ingest_$(Get-Date -Format 'yyyy-MM-dd').log -Tail 50
```

---

## Common failure modes

### 1. Task shows `LastTaskResult = 0x1` (generic error)

Most likely: the venv is missing or the package isn't installed editable. Reproduce manually:

```powershell
cd C:\alphahound_project
.\.venv\Scripts\Activate.ps1
alphahound ingest-all
```

If that works, the issue is environment-specific to SYSTEM. Check that the venv lives under `C:\alphahound_project\.venv` (not under a user profile directory).

### 2. `db check` fails with "password authentication failed"

`.env` out of sync with the real admin password. Fix:

```powershell
notepad C:\alphahound_project\.env
# Update DATABASE_URL password, save
alphahound db check
```

### 3. `db check` fails with "connection refused" / timeout

Firewall: your VM's public IP changed or isn't whitelisted. Fix in Azure Portal → Postgres → Networking → "Add current client IP" → Save. Confirm "Allow public access from any Azure service" is still checked.

### 4. StockTwits 429 rate-limited

Adapter logs `rate-limited on <SYMBOL>; backing off 60s`. If this happens often, reduce `watchlist_size` (default 20) or relax the interval (15 min → 30 min).

### 5. ApeWisdom returns 0 rows

Check their website directly: https://apewisdom.io/. If their API changed, the adapter will need a schema fix. See `tests/test_apewisdom_adapter.py` fixture vs. live response.

### 6. `raw_posts` isn't growing

Enabled adapter list query:
```sql
SELECT adapter_id, enabled FROM source_adapters;
```
If all show `enabled = false`, nothing will ingest. Re-enable:
```sql
UPDATE source_adapters SET enabled = true WHERE adapter_id IN ('stocks.apewisdom','stocks.stocktwits');
```

### 7. Signals not refreshing

`compute-all` only scores entities with ≥10 posts in the last 7 days. After a cold start you need ~24h before velocity becomes meaningful. During that warm-up the task still runs; the output is just "wrote 0 velocity signals" \u2014 not an error.

---

## Pause ingestion

Temporarily stop (keep definition, but no runs):
```powershell
Disable-ScheduledTask -TaskName AlphaHound-Ingest
# Re-enable when done:
Enable-ScheduledTask -TaskName AlphaHound-Ingest
```

Permanently remove:
```powershell
Unregister-ScheduledTask -TaskName AlphaHound-Ingest -Confirm:$false
```

To block a single adapter without removing the task:
```sql
UPDATE source_adapters SET enabled = false WHERE adapter_id = 'stocks.stocktwits';
```

---

## Install / reinstall the task

```powershell
# From an ELEVATED PowerShell session:
cd C:\alphahound_project\scripts
.\register_scheduled_task.ps1
```

The script is idempotent (unregisters + re-registers), so you can re-run it after changing the wrapper.

---

## Metrics to watch (build into Grafana in Sprint 4)

- `posts_fetched` per adapter per run — alarm if 0 for 4 consecutive runs
- Run duration P95 — alarm if >2 min (something's wrong with an adapter)
- `error IS NOT NULL` count in last hour — alarm if >0
- `raw_posts` row-growth rate per day — baseline for anomaly detection
