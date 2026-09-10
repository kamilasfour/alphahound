# =====================================================================
# start_dashboard.ps1
# Starts the AlphaHound dashboard API server
# Access: http://localhost:8080  or  http://10.0.0.4:8080
# Stop: Ctrl+C
# =====================================================================

$ProjectRoot  = "C:\alphahound_project"
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
$Port         = 8080

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8       = "1"

Write-Host ""
Write-Host "  ALPHAHOUND DASHBOARD" -ForegroundColor Cyan
Write-Host "  ─────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Local:   http://localhost:$Port" -ForegroundColor White
Write-Host "  Network: http://10.0.0.4:$Port" -ForegroundColor White
Write-Host ""
Write-Host "  Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

Set-Location $ProjectRoot
. $VenvActivate

# Open browser after 2 seconds
Start-Job -ScriptBlock { Start-Sleep 2; Start-Process "http://localhost:8080" } | Out-Null

# Start uvicorn — use venv explicitly to avoid system Python313 conflict
# NOTE: --reload removed (was causing 25-35% CPU from filesystem watching)
$uvicorn = Join-Path $ProjectRoot ".venv\Scripts\uvicorn.exe"
& $uvicorn dashboard.api:app --host 0.0.0.0 --port $Port
