# =====================================================================
# score_new.ps1
# Executed by Windows Task Scheduler every 30 minutes (AlphaHound-Score).
# Runs FinBERT scoring in isolation so CPU spikes don't block ingestion.
# Logs: C:\alphahound_project\logs\score_YYYY-MM-DD.log
#
# Future: this will be replaced by an Azure Function with parallel
# batch scoring across threads for higher throughput.
# =====================================================================

$ErrorActionPreference = "Continue"
$ProgressPreference    = "SilentlyContinue"

$ProjectRoot  = "C:\alphahound_project"
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
$LogDir       = Join-Path $ProjectRoot "logs"
$DateStamp    = Get-Date -Format "yyyy-MM-dd"
$LogFile      = Join-Path $LogDir "score_${DateStamp}.log"
$PythonExe    = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$StepRunner   = Join-Path $ProjectRoot "scripts\run_pipeline_step.py"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$env:PYTHONIOENCODING  = "utf-8"
$env:PYTHONUTF8        = "1"
$env:OMP_NUM_THREADS   = "2"
$env:MKL_NUM_THREADS   = "2"
$env:FINBERT_CPU_THREADS = "2"

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
    Write-Log "FATAL: venv not found at $VenvActivate"
    exit 1
}

try {
    Set-Location $ProjectRoot
    . $VenvActivate
} catch {
    Write-Log "FATAL: failed to activate venv: $($_.Exception.Message)"
    exit 1
}

Write-Log "=== score-new start (pid=$PID host=$env:COMPUTERNAME) ==="

# Cap at 500 posts per run — higher than main pipeline since this runs
# at half the frequency (30 min vs 15 min).
$scoreExit = Run-Step "score-new" @("signals", "score-new", "--max-posts", "500")

if ($scoreExit -ne 0) {
    Write-Log "=== score-new FAILED (exit=$scoreExit) ==="
    exit 1
}

Write-Log "=== score-new complete ==="
exit 0
