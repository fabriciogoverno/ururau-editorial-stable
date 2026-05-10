@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — INICIAR NEURAL ENGINE SERVICE
echo ==========================================
cd /d "%~dp0sistema"
python -c "from neural_service import get_neural; n=get_neural(); n.start(); print('Neural Engine iniciada.'); import time; time.sleep(2); print(n.status())"
if %errorlevel% neq 0 (
    echo [ERRO] Falha ao iniciar Neural Engine.
    pause
    exit /b 1
)
echo [OK] Neural Engine rodando em background.
pause
