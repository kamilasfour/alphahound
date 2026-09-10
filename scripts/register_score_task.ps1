# =====================================================================
# register_score_task.ps1
# One-time setup: registers the AlphaHound-Score scheduled task.
# Requires: run PowerShell as Administrator.
#
# What this creates:
#   - Task name: AlphaHound-Score
#   - Trigger:   every 30 minutes, indefinitely
#   - Action:    powershell.exe -NoProfile -ExecutionPolicy Bypass -File score_new.ps1
#   - User:      SYSTEM
#
# To remove later:
#   Unregister-ScheduledTask -TaskName AlphaHound-Score -Confirm:$false
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName   = "AlphaHound-Score"
$ScriptPath = "C:\alphahound_project\scripts\score_new.ps1"

if (-not (Test-Path $ScriptPath)) {
    throw "Script not found at $ScriptPath."
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task '$TaskName'..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

# Offset by 7 minutes from the :00/:30 boundary so it doesn't overlap
# with AlphaHound-Ingest which fires on :00/:15/:30/:45.
$now = Get-Date
$minute = $now.Minute
$nextHalfHour = $now.AddMinutes(30 - ($minute % 30)).AddSeconds(-$now.Second).AddMinutes(7)

$Trigger = New-ScheduledTaskTrigger -Once -At $nextHalfHour `
    -RepetitionInterval (New-TimeSpan -Minutes 30)

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

$Principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "AlphaHound: FinBERT sentiment scoring, decoupled from ingestion pipeline. Future: Azure Function."

Write-Host "✅ Registered task '$TaskName'. First run at: $nextHalfHour"
Write-Host ""
Write-Host "Verify:"
Write-Host "  Get-ScheduledTask -TaskName $TaskName"
Write-Host "  Get-ScheduledTaskInfo -TaskName $TaskName"
Write-Host ""
Write-Host "Logs: C:\alphahound_project\logs\score_YYYY-MM-DD.log"
Write-Host "DB:   SELECT * FROM pipeline_runs WHERE step = 'score-new' ORDER BY started_at DESC LIMIT 10;"
