# AH1 Scheduler Inventory

**Step:** STEP 1 — Inventory Existing AH1 Scheduled Processes (per `IMPLEMENTATION_PLAYBOOK.md`)
**Status:** Inspection complete. No migration performed. No AH1 files modified.
**Inspected by:** Claude (filesystem MCP), reading actual repo code + live `Get-ScheduledTaskInfo` output from repsportalvm.
**Date:** 2026-09-10

---

## Method

This inventory was built by reading the actual implementation, not by trusting prior documentation:

- All `register_*.ps1` files in `scripts\`
- All `.ps1` wrapper scripts they invoke
- `src\alphahound\cli.py` (every `signals` / `ingest` subcommand actually called by the wrappers)
- `scripts\ingest_parallel.py`, `scripts\run_pipeline_step.py`, `scripts\assessment_service.py`, `scripts\status_monitor.py`
- Live task state from `Get-ScheduledTaskInfo` (run by Kamil, 2026-09-10)

Two of the five live tasks (`AlphaHound-Earnings`, `AlphaHound-StatusMonitor`) have no matching `register_*.ps1` in this repo — their exact Task Scheduler settings (execution time limit, restart count, multiple-instances policy) could not be confirmed from source. This is called out per-row below rather than guessed.

**Known context at inventory time:** all five tasks are currently paused. This was done intentionally by Kamil ahead of the AH2 rebuild, not a discovered failure.

---

## 1. AlphaHound-Ingest

| Field | Value |
|---|---|
| Task name | `AlphaHound-Ingest` |
| Current scheduler | Windows Task Scheduler, `SYSTEM` account, registered via `register_scheduled_task.ps1` |
| Schedule/cadence | Every 15 min, aligned to :00/:15/:30/:45 |
| Script/module | `scripts\ingest_all.ps1`, which chains: `scripts\ingest_parallel.py` → `alphahound signals compute-all` → `alphahound signals score-institutional` → `alphahound signals convergence-scan` → *(market hours only, 6:30am–1pm PT)* `alphahound signals options-monitor --close` → `alphahound signals options-execute` → `alphahound signals health-check`. At 6am only, also runs `alphahound ingest --source stocks.massive_history` and `alphahound signals seed-catalysts`. |
| Command/arguments | Action: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\alphahound_project\scripts\ingest_all.ps1"`. Internally each step runs via `.venv\Scripts\python.exe scripts\run_pipeline_step.py <step_name> <cli args>`, except the ingest step which runs `python.exe scripts\ingest_parallel.py` directly. |
| Inputs | Enabled rows in `source_adapters`; live HTTP responses from each adapter's external API; existing `entities`, `price_daily`, `earnings_calendar`, `pdufa_calendar` rows used by convergence/options logic |
| Database tables used | **Read:** `source_adapters`, `entities`, `price_snapshots`/`price_daily`, `sentiment_scores`, `options_flow`, `institutional_positions`, `earnings_calendar`, `pdufa_calendar`. **Write:** `raw_posts`, `ingest_runs`, velocity signal tables, `convergence_signals`, `options_trade_log`, `pipeline_runs` (tracked by `run_pipeline_step.py` for every sub-step) |
| External services used | ApeWisdom, Finnhub, Unusual Whales, Massive, Substack, Yahoo Finance, Kalshi (currently-enabled adapters); Alpaca paper trading (`options-monitor`/`options-execute`); QuiverQuant adapter code present but inactive (subscription cancelled) |
| Outputs | `logs\ingest_YYYY-MM-DD.log`; DB writes above; potential paper option orders via Alpaca during market hours |
| Dependencies | `.venv`, `.env` (DB creds + API keys), running Postgres/TimescaleDB, network access to each provider + Alpaca |
| Failure behavior | `$ErrorActionPreference = "Continue"` — each step runs independently; a failed step is logged (`FAILED (exit=N)`) but does **not** stop later steps. The script always `exit 0` at the very end regardless of step failures (the only true fatal case is a missing `.venv`, which exits 1 immediately). |
| Retry behavior | None at script level (`subprocess.run` executes each step once). Task Scheduler has no `RestartCount` configured for this task — a failed run just waits for the next 15-min trigger. |
| Can run concurrently? | No. Guarded two ways: a file lock (`logs\ingest.lock`, self-clears if >30 min old) **and** Task Scheduler `MultipleInstances IgnoreNew` with a 10-min `ExecutionTimeLimit`. See Finding #3 below — a hard-killed instance can leave Task Scheduler believing an instance is still running, silently skipping all future triggers. |
| AH2 disposition | **NEEDS REVIEW.** This is one Windows task doing the work of ~7 distinct concerns chained sequentially — exactly the "large orchestration script" pattern `CLAUDE.md` rule 16 says to avoid. Recommend decomposing per the sub-step breakdown below rather than migrating as one Azure Function. |

### Sub-step breakdown (for future decomposition — not required by the STEP 1 table, included for planning value)

| Internal step | Suggested AH2 mapping (per `ARCHITECTURE.md` §5) |
|---|---|
| `ingest_parallel.py` (6 adapters) | `IngestMarketData` — timer-triggered Azure Function |
| `compute-all` (velocity) | Feature computation — likely folds into `ProcessNewEvidence` |
| `score-institutional` | Feature computation — likely folds into `ProcessNewEvidence` |
| `convergence-scan` | `RunConvergence` |
| `options-monitor --close` | `MonitorPositions` |
| `options-execute` | `EvaluateOpportunity` → `RiskEvaluation` → `ComplianceEvaluation` → `ExecuteOrder` (currently these are fused into one step — AH2 must split eligibility, risk, compliance, and submission into separate deterministic stages per ADR-004) |
| `health-check` | Observability — folds into Application Insights instead of a manual step |
| `massive-history` / `seed-catalysts` (6am only) | One-off/daily `IngestMarketData` variant or `DailyPerformance`-style timer |

---

## 2. AlphaHound-Score

| Field | Value |
|---|---|
| Task name | `AlphaHound-Score` |
| Current scheduler | Windows Task Scheduler, `SYSTEM` account, registered via `register_score_task.ps1` |
| Schedule/cadence | Every 30 min, offset +7 min from the :00/:30 boundary (deliberately avoids colliding with `AlphaHound-Ingest`) |
| Script/module | `scripts\score_new.ps1` → `alphahound signals score-new --max-posts 500` |
| Command/arguments | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\alphahound_project\scripts\score_new.ps1"` |
| Inputs | Unscored rows in `raw_posts` (news_wire / retail_social / analyst_curated source classes) |
| Database tables used | **Read:** `raw_posts`, `sentiment_scores`, `scoring_watermark`. **Write:** `sentiment_scores`, `pipeline_runs` |
| External services used | None — FinBERT runs in-process/locally, no external API call |
| Outputs | `logs\score_YYYY-MM-DD.log`; up to 500 new `sentiment_scores` rows per run |
| Dependencies | `.venv`, local FinBERT model weights, CPU (thread count capped via `OMP_NUM_THREADS=2`, `MKL_NUM_THREADS=2`, `FINBERT_CPU_THREADS=2`) |
| Failure behavior | Single step; on failure the script logs `FAILED` and exits 1 |
| Retry behavior | None at script level; no `RestartCount` in the registered task |
| Can run concurrently? | No — `MultipleInstances IgnoreNew`, 20-min `ExecutionTimeLimit`. No separate lock file; relies solely on Task Scheduler's own instance guard. |
| AH2 disposition | **MIGRATE TO AZURE FUNCTION.** Clean fit for a queue-triggered `ProcessNewEvidence` function. Per ADR-003, FinBERT inference should move behind the Model Gateway rather than running in-process — see `IMPLEMENTATION_PLAYBOOK.md` STEP 9/10. |

---

## 3. AlphaHound-Assessment

| Field | Value |
|---|---|
| Task name | `AlphaHound-Assessment` |
| Current scheduler | Windows Task Scheduler, `SYSTEM` account, registered via `register_assessment_task.ps1` |
| Schedule/cadence | Every 15 min, starting from whenever the task was registered (**not** boundary-aligned like `AlphaHound-Ingest`, so its cadence can drift out of phase) |
| Script/module | `scripts\assessment_service.py` (Python, run directly — no `.ps1` wrapper) |
| Command/arguments | `.venv\Scripts\python.exe scripts\assessment_service.py`, working directory `C:\alphahound_project` |
| Inputs | `docs\status\system_summary.json`, `pipeline_health.json`, `ingestion_health.json` (all written by `AlphaHound-StatusMonitor`); live HTTP GET to `http://localhost:8080/api/macro` and `http://localhost:8080/api/positions` |
| Database tables used | **Read:** `convergence_signals`, `options_trade_log`. **Write:** `assessments` (creates the table itself via `CREATE TABLE IF NOT EXISTS` on first run) |
| External services used | None directly — calls its own local dashboard API on `localhost:8080` |
| Outputs | `docs\status\assessment.json`; rows in `assessments` |
| Dependencies | `.venv`, `.env`, Postgres, **and a running dashboard/uvicorn process on port 8080** — see Finding #4 |
| Failure behavior | DB reads for signals/positions are individually try/excepted (fail soft to empty), but an unexpected exception outside those blocks is uncaught and exits non-zero |
| Retry behavior | **Yes** — the only one of the five tasks with retries configured: `RestartCount 2`, `RestartInterval 1 min`, `ExecutionTimeLimit 5 min` (all set directly in `register_assessment_task.ps1`) |
| Can run concurrently? | `MultipleInstances` not explicitly set in the register script (Task Scheduler default applies); no internal lock file |
| AH2 disposition | **EVENT DRIVEN.** This is a read-model/dashboard aggregator, not a trading decision. Recommend rebuilding as a timer function or Service Bus consumer that queries Postgres directly — the `localhost:8080` dependency is Windows-server-specific and won't exist in Azure. |

---

## 4. AlphaHound-Earnings

| Field | Value |
|---|---|
| Task name | `AlphaHound-Earnings` |
| Current scheduler | Windows Task Scheduler — **registered outside this repo.** No `register_*.ps1` exists for it; only the wrapper `ingest_earnings.ps1` exists, whose header comment documents the *intended* schedule rather than a script that created it. |
| Schedule/cadence (observed live via `Get-ScheduledTaskInfo`) | Daily, 6:00 AM |
| Script/module | `scripts\ingest_earnings.ps1` → `alphahound ingest --source earnings_calendar` then `alphahound signals earnings --days 14` |
| Command/arguments | Per the script's own header comment: `powershell -File C:\alphahound_project\scripts\ingest_earnings.ps1`. The actual registered Action/Settings could not be confirmed from source — see Follow-up below. |
| Inputs | Finnhub earnings-calendar API (single call covers the full watchlist, next 30 days) |
| Database tables used | Writes earnings-calendar data consumed later by the convergence scan's catalyst pillar; reads it back via `signals earnings --days 14` for the printed summary |
| External services used | Finnhub |
| Outputs | `logs\earnings_YYYY-MM-DD.log`; earnings-calendar rows |
| Dependencies | `.venv`, `.env` (Finnhub key), Postgres |
| Failure behavior | Exits 1 if the ingest step fails; the `signals earnings` step isn't explicitly gated on ingest success |
| Retry behavior | **Unknown** — no register script in repo to confirm |
| Can run concurrently? | **Unknown** — no register script in repo to confirm |
| AH2 disposition | **NEEDS REVIEW.** Low-frequency, low-complexity — otherwise a cheap early candidate for an `IngestMarketData`-family timer function, once its live registration is located. |

---

## 5. AlphaHound-StatusMonitor

| Field | Value |
|---|---|
| Task name | `AlphaHound-StatusMonitor` |
| Current scheduler | Windows Task Scheduler — **registered outside this repo.** No `register_*.ps1` exists for it. |
| Schedule/cadence | Per the script's own docstring: "every 30 minutes." Live `NextRunTime` spacing is consistent with this but the registered trigger definition itself wasn't found in source. |
| Script/module | `scripts\status_monitor.py` (Python, run directly) |
| Command/arguments | Presumed `python.exe scripts\status_monitor.py` — exact registered Action unverified, no register script in repo |
| Inputs | Reads directly from Postgres; no external API calls |
| Database tables used | **Read:** `raw_posts`, `ingest_runs`, `options_flow`, `source_adapters`, `sentiment_scores`, `pipeline_runs`, `scoring_watermark`, `entities`, `price_snapshots`, and **`divergence_events`** (⚠ see Finding #2). **Write:** `docs\status\ingestion_health.json`, `scoring_health.json`, `pipeline_health.json`, `system_summary.json`; conditionally inserts into `health_checks` |
| External services used | None |
| Outputs | 4 JSON status files under `docs\status\`; `health_checks` rows when problems are detected |
| Dependencies | `.venv`, `.env`, Postgres |
| Failure behavior | `sys.exit(1)` if overall status is RED, and `sys.exit(1)` on any uncaught exception. This matches the live `LastTaskResult=1` observed for this task. |
| Retry behavior | **Unknown** — no register script in repo |
| Can run concurrently? | **Unknown** — no register script in repo |
| AH2 disposition | **NEEDS REVIEW.** Functionally the `MonitorPositions`/observability piece, but built partly on the retired divergence-scorer model (Finding #2) and needs correction before it's a safe migration input. Its live registration should also be located so its actual settings are known. |

---

## Excluded from this inventory (not a scheduled process)

**`scripts\start_dashboard.ps1`** — launches the FastAPI/uvicorn dashboard in the foreground (opens a browser, runs uvicorn in the console, stops on Ctrl+C). It is not registered in Windows Task Scheduler anywhere found in this repo. It's excluded from the table above because it isn't automated, but it's flagged here because `AlphaHound-Assessment` (row 3) quietly depends on it being up (`localhost:8080`), and AH2 will need an explicit answer for how/where the dashboard or its replacement runs.

---

## Findings / discrepancies worth reviewing before Step 2

1. **Two live tasks have no register script in the repo.** `AlphaHound-Earnings` and `AlphaHound-StatusMonitor` exist on repsportalvm but their exact `ExecutionTimeLimit` / `RestartCount` / `MultipleInstances` settings can't be confirmed from source — only the wrapper scripts they call are in-repo. Suggest running `Get-ScheduledTask -TaskName "AlphaHound-Earnings","AlphaHound-StatusMonitor" | Get-ScheduledTaskInfo` plus `(Get-ScheduledTask -TaskName ...).Actions` and `.Settings` to close this gap, and saving the result as a `register_*.ps1` for each so they're reproducible.
2. **`status_monitor.py` still queries the retired divergence-scorer schema** — the `divergence_events` table and a `d_value`/`executable_d_threshold` threshold, from the architecture `CURRENT_STATE.md` §3 says was replaced by the convergence engine. This is dead or misleading logic and should be resolved (removed or updated) before `AlphaHound-StatusMonitor` is used as a migration input.
3. **All five tasks show `LastRunTime` frozen at 6/28/2026** in the live `Get-ScheduledTaskInfo` output pulled 2026-09-10, despite `NextRunTime` continuing to advance. Per Kamil, this is intentional — everything was paused ahead of the AH2 rebuild — recorded here only as the observed state at inventory time, not as a defect.
4. **`AlphaHound-Assessment` depends on the dashboard's own HTTP API** (`localhost:8080/api/macro`, `/api/positions`) instead of querying Postgres directly, which in turn depends on the unscheduled `start_dashboard.ps1` process being manually running. This implicit dependency chain won't translate to Azure as-is.
5. **`AlphaHound-Ingest` is a single task doing the work of ~7 distinct pipeline stages** chained in one PowerShell script — see the sub-step breakdown in section 1 for a proposed decomposition.

---

## What was explicitly NOT done in this step

- No AH1 code, tables, or scheduled tasks were modified.
- No Azure resources were created or inspected (that's STEP 2).
- No migration was performed — the "AH2 disposition" values above are recommendations for review, not actions taken.

**This step is complete. Awaiting review before STEP 2 is authorized.**
