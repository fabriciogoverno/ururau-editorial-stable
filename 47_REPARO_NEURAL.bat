@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — REPARO NEURAL AUTONOMO (Fase 2)
echo ==========================================
cd /d "%~dp0sistema"
python -m ururau_ai_auditor.nn_engine.integrador
if %errorlevel% neq 0 (
    echo [AVISO] Reparo neural nao completou.
    pause
    exit /b 1
)
echo [OK] Ciclo de reparo concluido.
pause
