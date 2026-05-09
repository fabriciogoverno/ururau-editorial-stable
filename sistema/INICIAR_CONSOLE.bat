@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Ururau v100 - Painel

if not exist "logs" mkdir "logs"
if not exist "data" mkdir "data"
if not exist "imagens" mkdir "imagens"
if not exist "prints" mkdir "prints"

if not exist ".venv\Scripts\activate.bat" (
  echo Ambiente ainda nao instalado. Chamando INSTALAR.bat...
  call "%~dp0INSTALAR.bat" || exit /b 1
)

call ".venv\Scripts\activate.bat" || exit /b 1
python scripts_config_env.py || exit /b 1
python VALIDAR_ENV.py || exit /b 1
if exist "CORRIGIR_FILA_SEM_TEXTO_V84.py" python CORRIGIR_FILA_SEM_TEXTO_V84.py
if exist "CORRIGIR_V129_2_FILA_RSS.py" python CORRIGIR_V129_2_FILA_RSS.py

echo.
echo Iniciando painel v100...
python ururau_painel.py

echo.
echo Painel encerrado. Veja logs e prints se houve erro.
pause
