@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — NEURAL ENGINE PERSISTENTE
echo ==========================================
cd /d "%~dp0sistema"
python neural_runner.py
if %errorlevel% neq 0 (
    echo [ERRO] Neural Engine encerrou com falha.
    pause
    exit /b 1
)
echo [OK] Neural Engine encerrada.
pause
