@echo off
rem LH-news: re-collect the past 7 days (yesterday back to 7 days ago) and upload to GitHub.
rem Takes about 10-15 minutes. Double-click to run.
chcp 65001 > nul
cd /d "%~dp0"
call run_collect.bat last7
echo Done. Log: data\logs\pc-run.log
pause
