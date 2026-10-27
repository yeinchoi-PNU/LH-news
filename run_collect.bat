@echo off
rem LH-news: collect news on this PC and upload the result to GitHub.
rem Double-click to run now. To collect a past date: run_collect.bat 2026-10-20
chcp 65001 > nul
cd /d "%~dp0"
set PATH=C:\Program Files\Git\cmd;%PATH%
if not exist data\logs mkdir data\logs
set LOG=data\logs\pc-run.log

echo. >> %LOG%
echo ===== %date% %time% start ===== >> %LOG%
git pull --rebase --autostash >> %LOG% 2>&1
py -X utf8 collect.py %1 >> %LOG% 2>&1
git add data >> %LOG% 2>&1
git commit -m "news collect (PC) %date%" >> %LOG% 2>&1
git push >> %LOG% 2>&1
echo ===== %date% %time% end ===== >> %LOG%
