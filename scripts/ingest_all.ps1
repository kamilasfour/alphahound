# =====================================================================
# ingest_all.ps1 - AlphaHound main pipeline (Sprint 12 — trimmed)
# Runs every 15 minutes via Windows Task Scheduler
#
# REMOVED (no longer needed):
#   - divergence-scan     (replaced by convergence-scan)
#   - score-sectors       (cosmetic, not used in trading decisions)
#   - trade-advice        (divergence-based, replaced)
#   - execute             (divergence-based executor, replaced by options-execute)
#   - hit-rate            (no resolved trades yet, wasted CPU every cycle)
#   - rhyme               (not used)
#   - close-positions     (divergence equity closer, replaced by options-monitor)
#
# KEPT:
#   1. ingest-all         (data pipeline — always needed)
#   2. compute-all        (velocity signals — feeds P3c)
#   3. score-institutional (institutional flow — feeds P7)
#   4. convergence-scan   (7-pillar engine — core)
#   5. options-monitor    (auto-close positions — market hours)
#   6. options-execute    (place new trades — market hours)
#   7. health-check       (system status)
# =====================================================================

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"

$ProjectRoot  = "C:\alphahound_project"
$LockFile     = Join-Path $ProjectRoot "logs\ingest.lock"

# ── Overlap guard ────────────────────────────────────────────────
# If a previous instance is still running, exit immediately
if (Test-Path $LockFile) {
    $lockAge = (Get-Date) - (Get-Item $LockFile).LastWriteTime
    if ($lockAge.TotalMinutes -lt 30) {
        Write-Host "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Previous run still active ($([int]$lockAge.TotalMinutes)m old) — skipping this cycle"
        exit 0
    } else {
        # Lock is stale (>30 min) — remove and continue
        Remove-Item $LockFile -Force
    }
}
# Create lock
"$PID" | Out-File $LockFile -Encoding ascii
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
$LogDir       = Join-Path $ProjectRoot "logs"
$DateStamp    = Get-Date -Format "yyyy-MM-dd"
$LogFile      = Join-Path $LogDir "ingest_${DateStamp}.log"
$PythonExe    = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$StepRunner   = Join-Path $ProjectRoot "scripts\run_pipeline_step.py"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8       = "1"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts $Message" | Out-File -FilePath $LogFile -Append -Encoding utf8
}

function Run-Step {
    param([string]$StepName, [string[]]$CliArgs)
    Write-Log "--- step:$StepName start ---"
    if ($CliArgs.Count -gt 0 -and $CliArgs[0] -match '\.py$') {
        $scriptPath = Join-Path $ProjectRoot $CliArgs[0]
        $output = & $PythonExe $scriptPath 2>&1
    } else {
        $output = & $PythonExe $StepRunner $StepName @CliArgs 2>&1
    }
    $exit = $LASTEXITCODE
    foreach ($line in $output) { Write-Log $line.ToString() }
    if ($exit -ne 0) { Write-Log "--- step:$StepName FAILED (exit=$exit) ---" }
    else             { Write-Log "--- step:$StepName ok ---" }
    return $exit
}

if (-not (Test-Path $VenvActivate)) {
    Write-Log "FATAL: venv not found at $VenvActivate"
    exit 1
}

Write-Log "=== ingest-all start (pid=$PID host=$env:COMPUTERNAME) ==="

try {
    Set-Location $ProjectRoot
    . $VenvActivate
} catch {
    Write-Log "FATAL: failed to activate venv: $($_.Exception.Message)"
    exit 1
}

$currentHour = (Get-Date).Hour

# ── 1. Ingest all adapters in parallel ────────────────────────────
$ingestExit = Run-Step "ingest-all" @("scripts\ingest_parallel.py")

# ── 2. Daily-only steps — 6am only ────────────────────────────────
if ($currentHour -eq 6) {
    Run-Step "massive-history" @("ingest", "--source", "stocks.massive_history") | Out-Null
    Run-Step "seed-catalysts"  @("signals", "seed-catalysts") | Out-Null
}

# ── 3. Velocity + institutional flow scoring ───────────────────────
$sigExit  = Run-Step "compute-all"          @("signals", "compute-all")
$instExit = Run-Step "score-institutional"  @("signals", "score-institutional")

# ── 4. Multi-Pillar Convergence Engine ────────────────────────────
Run-Step "convergence-scan" @("signals", "convergence-scan") | Out-Null

# ── 5. Options execution — market hours only (PST: 6:30 AM - 1:00 PM) ──────
# Server is PST. NYSE 9:30-16:00 ET = 6:30-13:00 PT
$currentMinute = (Get-Date).Minute
$marketOpen = ($currentHour -gt 6 -or ($currentHour -eq 6 -and $currentMinute -ge 30)) -and ($currentHour -lt 13)
if ($marketOpen) {
    Run-Step "options-monitor" @("signals", "options-monitor", "--close") | Out-Null
    Run-Step "options-execute" @("signals", "options-execute") | Out-Null
}

# ── 6. Health check — always last ────────────────────────────────
Run-Step "health-check" @("signals", "health-check") | Out-Null

# ── Exit code ─────────────────────────────────────────────────────
if ($ingestExit -ne 0 -or $sigExit -ne 0 -or $instExit -ne 0) {
    Write-Log "=== ingest-all FAILED (ingest=$ingestExit sig=$sigExit inst=$instExit) ==="
} else {
    Write-Log "=== ingest-all complete ==="
}

# Always remove lock on exit
Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
exit 0
