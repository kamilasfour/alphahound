# =====================================================================
# register_scheduled_task.ps1
# One-time setup: registers the AlphaHound-Ingest scheduled task.
# Requires: run PowerShell as Administrator.
#
# What this creates:
#   - Task name: AlphaHound-Ingest
#   - Trigger:   every 15 minutes, indefinitely, starting at the next :00/:15/:30/:45
#   - Action:    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ingest_all.ps1
#   - User:      SYSTEM (runs whether logged in or not, survives reboot)
#   - Settings:  start when available if missed; don't stop on battery; allow run while idle
#
# To remove later:
#   Unregister-ScheduledTask -TaskName AlphaHound-Ingest -Confirm:$false
# =====================================================================

$ErrorActionPreference = "Stop"

$TaskName = "AlphaHound-Ingest"
$ScriptPath = "C:\alphahound_project\scripts\ingest_all.ps1"

if (-not (Test-Path $ScriptPath)) {
    throw "Wrapper script not found at $ScriptPath."
}

# If task exists, remove it first so this script is idempotent.
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task '$TaskName'..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

# Next boundary on :00/:15/:30/:45
$now = Get-Date
$minute = $now.Minute
$nextBoundary = $now.AddMinutes(15 - ($minute % 15)).AddSeconds(-$now.Second)

$Trigger = New-ScheduledTaskTrigger -Once -At $nextBoundary `
    -RepetitionInterval (New-TimeSpan -Minutes 15)

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

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
    -Description "AlphaHound: pull all enabled adapters and compute velocity signals every 15 min."

Write-Host "✅ Registered task '$TaskName'. First run at: $nextBoundary"
Write-Host ""
Write-Host "Verify:"
Write-Host "  Get-ScheduledTask -TaskName $TaskName"
Write-Host "  Get-ScheduledTaskInfo -TaskName $TaskName"
Write-Host ""
Write-Host "Logs: C:\alphahound_project\logs\ingest_YYYY-MM-DD.log"
Write-Host "DB:   alphahound db ingest-runs --tail 20"
