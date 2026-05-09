@echo off
cd /d "%~dp0sistema"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path logs\monitor.log) { Get-Content logs\monitor.log -Tail 120 } else { Write-Host 'logs\monitor.log ainda nao existe' }"
pause
