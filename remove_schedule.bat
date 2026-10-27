@echo off
rem LH-news: remove the daily task from Windows Task Scheduler.
powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'LH-news collect' -Confirm:$false; Write-Host 'Removed: LH-news collect'"
pause
