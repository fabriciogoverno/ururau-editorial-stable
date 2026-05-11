@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU - SCRAPLING COLETA v136
echo ==========================================
cd /d "%~dp0sistema"
set URURAU_SCRAPLING_V136_FONTES=20
set URURAU_SCRAPLING_V136_LINKS=40
python -m ururau.coleta.scrapling_spider_v136 --fontes=%URURAU_SCRAPLING_V136_FONTES% --links=%URURAU_SCRAPLING_V136_LINKS%
if %errorlevel% neq 0 (
    echo [ERRO] Scrapling coleta v136 falhou.
    pause
    exit /b 1
)
echo [OK] Scrapling coleta v136 executado.
pause
