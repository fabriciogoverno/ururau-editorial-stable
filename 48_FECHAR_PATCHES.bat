@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — FECHAMENTO DE PATCHES (24h)
echo ==========================================
cd /d "%~dp0sistema"
python fechar_patches.py
if %errorlevel% neq 0 (
    echo [AVISO] Fechamento nao completou.
    pause
    exit /b 1
)
echo [OK] Fechamento concluido.
pause
