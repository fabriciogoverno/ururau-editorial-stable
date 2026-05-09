@echo off
chcp 65001 >nul
cd /d "%~dp0"
python scripts_config_env.py
python VALIDAR_ENV.py
echo.
echo Se apareceu [v46.2][OK], rode RODAR_TUDO_VISIVEL.bat.
pause
