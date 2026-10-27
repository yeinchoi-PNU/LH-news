@echo off
rem LH-news: register run_collect.bat in Windows Task Scheduler (every day 08:00).
rem If the PC is off at 08:00, it runs as soon as the PC is turned on.
rem To remove it later: double-click remove_schedule.bat
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$a = New-ScheduledTaskAction -Execute (Join-Path (Get-Location) 'run_collect.bat') -WorkingDirectory (Get-Location);" ^
  "$t = New-ScheduledTaskTrigger -Daily -At 08:00;" ^
  "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;" ^
  "Register-ScheduledTask -TaskName 'LH-news collect' -Action $a -Trigger $t -Settings $s -Force | Out-Null;" ^
  "Write-Host 'Registered: LH-news collect (daily 08:00)'"
pause
