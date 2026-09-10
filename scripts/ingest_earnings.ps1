# =====================================================================
# ingest_earnings.ps1
# Runs once daily (suggested: 6:00am ET) to pull upcoming earnings dates.
# Separate from ingest_all.ps1 because:
#   - Earnings dates don't change every 15 minutes
#   - Finnhub has rate limits — no need to hammer it 96x/day
#   - Single Finnhub call covers all watchlist tickers for next 30 days
#
# Schedule in Task Scheduler:
#   Trigger: Daily at 6:00am
#   Action: powershell -File C:\alphahound_project\scripts\ingest_earnings.ps1
# =====================================================================

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"

$ProjectRoot  = "C:\alphahound_project"
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
$LogDir       = Join-Path $ProjectRoot "logs"
$DateStamp    = Get-Date -Format "yyyy-MM-dd"
$LogFile      = Join-Path $LogDir "earnings_${DateStamp}.log"
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
    $output = & $PythonExe $StepRunner $StepName @CliArgs 2>&1
    $exit = $LASTEXITCODE
    foreach ($line in $output) { Write-Log $line.ToString() }
    if ($exit -ne 0) { Write-Log "--- step:$StepName FAILED (exit=$exit) ---" }
    else             { Write-Log "--- step:$StepName ok ---" }
    return $exit
}

if (-not (Test-Path $VenvActivate)) {
    Write-Log "FATAL: venv not found"
    exit 1
}

Set-Location $ProjectRoot
. $VenvActivate

Write-Log "=== earnings calendar start (pid=$PID host=$env:COMPUTERNAME) ==="

$ingestExit = Run-Step "earnings-ingest" @("ingest", "--source", "earnings_calendar")
$earningsExit = Run-Step "earnings-upcoming" @("signals", "earnings", "--days", "14")

if ($ingestExit -ne 0) {
    Write-Log "=== earnings calendar FAILED ==="
    exit 1
}

Write-Log "=== earnings calendar complete ==="
exit 0
