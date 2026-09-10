# Register AlphaHound Assessment Service as Windows Scheduled Task
# Runs every 15 minutes, all day, every day
# Run once as Administrator

$ErrorActionPreference = "Stop"
$ProjectDir = "C:\alphahound_project"
$Python     = "$ProjectDir\.venv\Scripts\python.exe"
$Script     = "$ProjectDir\scripts\assessment_service.py"
$LogDir     = "$ProjectDir\logs"
$TaskName   = "AlphaHound-Assessment"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
    Write-Host "Created log directory: $LogDir"
}

$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument $Script `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 15) -Once -At (Get-Date)

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Action      $Action `
    -Trigger     $Trigger `
    -Settings    $Settings `
    -Principal   $Principal `
    -Description "AlphaHound Assessment Service - generates intelligence assessment every 15 minutes"

Write-Host ""
Write-Host "Task registered: $TaskName"
Write-Host "Schedule : Every 15 minutes"
Write-Host "Script   : $Script"
Write-Host ""
Write-Host "Starting first run now..."
Start-ScheduledTask -TaskName $TaskName
Write-Host "Done. Check /api/assessment in 30 seconds."
