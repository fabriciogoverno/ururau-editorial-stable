@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo  URURAU — ABRIR PAINEL EDITORIAL
echo ==========================================

if exist "sistema\ururau_autopilot_service.py" (
    echo [AUTOPILOT] Iniciando junto com o painel editorial...
    start "Ururau Autopilot" /min cmd /c "cd /d "%~dp0sistema" && python ururau_autopilot_service.py --interval=300"
) else (
    echo [AUTOPILOT][AVISO] ururau_autopilot_service.py nao encontrado. Abrindo painel sem Autopilot.
)

cd /d "%~dp0sistema"
set PYTHONPATH=%CD%;%PYTHONPATH%
python -c "import sitecustomize; import ururau_painel; ururau_painel.main()"

pause
