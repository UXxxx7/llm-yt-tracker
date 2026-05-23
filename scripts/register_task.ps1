# Registers a Windows Scheduled Task to run the tracker pipeline every 6h
# and on user logon. Run this script ONCE from an elevated PowerShell prompt.
#
# Uses `uv run` so the project venv at .venv is picked up automatically.

$ErrorActionPreference = "Stop"

$TaskName = "LLM-YT-Tracker-Refresh"
$ProjectRoot = "D:\YMX\llm-yt-tracker"
$UvExe = (Get-Command uv).Source
$LogFile = "$ProjectRoot\logs\cron.log"

if (-not (Test-Path "$ProjectRoot\logs")) {
  New-Item -ItemType Directory -Path "$ProjectRoot\logs" | Out-Null
}

$Action = New-ScheduledTaskAction `
  -Execute $UvExe `
  -Argument "run python -m pipeline.run" `
  -WorkingDirectory $ProjectRoot

$Trigger1 = New-ScheduledTaskTrigger -AtLogOn
$Trigger2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
            -RepetitionInterval (New-TimeSpan -Hours 6)

$Settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger @($Trigger1, $Trigger2) `
  -Settings $Settings `
  -Description "Refresh LLM YouTube Landscape Tracker every 6h" `
  -Force

Write-Host "Registered task '$TaskName'. Logs: $LogFile"
Write-Host "Run manually with: Start-ScheduledTask -TaskName '$TaskName'"
