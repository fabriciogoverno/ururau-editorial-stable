@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — AUTOPILOT UMA EXECUCAO
 echo ==========================================
cd /d "%~dp0sistema"
python ururau_autopilot_service.py --once
if %errorlevel% neq 0 (
    echo [ERRO] Autopilot falhou.
    pause
    exit /b 1
)
echo [OK] Autopilot executado.
pause
