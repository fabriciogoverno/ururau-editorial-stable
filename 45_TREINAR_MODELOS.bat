@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — TREINAMENTO NEURAL FASE 1
echo ==========================================
cd /d "%~dp0sistema"
python -m ururau_ai_auditor.nn_engine.runner
if %errorlevel% neq 0 (
    echo [ERRO] Treinamento falhou.
    pause
    exit /b 1
)
echo [OK] Modelos treinados.
pause
