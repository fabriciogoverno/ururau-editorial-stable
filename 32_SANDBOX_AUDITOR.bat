@echo off
cd /d "%~dp0sistema"
python -m ururau_ai_auditor.patch_sandbox
pause
