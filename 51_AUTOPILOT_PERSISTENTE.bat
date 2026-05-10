@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — AUTOPILOT PERSISTENTE
 echo ==========================================
cd /d "%~dp0sistema"
python ururau_autopilot_service.py --interval=300
if %errorlevel% neq 0 (
    echo [ERRO] Autopilot encerrou com falha.
    pause
    exit /b 1
)
echo [OK] Autopilot encerrado.
pause
