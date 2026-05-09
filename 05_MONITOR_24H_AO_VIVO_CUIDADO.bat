@echo off
chcp 65001 >nul
echo ============================================================
echo  ATENCAO: este atalho tenta rodar o monitor em modo AO VIVO.
echo  Use apenas se o .env tambem liberar publicacao direta.
echo  Para operacao normal, use 04_MONITOR_24H_RASCUNHO.bat.
echo ============================================================
echo.
choice /C SN /N /M "Confirmar tentativa de publicacao ao vivo? [S/N] "
if errorlevel 2 exit /b 1
cd /d "%~dp0sistema"
call "RODAR_MONITOR_24H_AO_VIVO.bat"
exit /b %errorlevel%
