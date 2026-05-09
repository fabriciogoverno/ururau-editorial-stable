@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Ururau v46.2 - Instalador corrigido

if not exist "logs" mkdir "logs"
if not exist "data" mkdir "data"
if not exist "data\imagens" mkdir "data\imagens"
if not exist "data\prints" mkdir "data\prints"

echo ============================================================
echo   URURAU v46.2 - INSTALADOR CORRIGIDO E TOLERANTE
echo ============================================================
echo.
echo Log completo: logs\instalacao_v46_2.log
echo ============================================================> "logs\instalacao_v46_2.log"
echo URURAU v46.2 - %date% %time%>> "logs\instalacao_v46_2.log"
echo ============================================================>> "logs\instalacao_v46_2.log"

echo [1/8] Verificando Python...
set "PYTHON_CMD="
python --version >nul 2>nul && set "PYTHON_CMD=python"
if "%PYTHON_CMD%"=="" py -3 --version >nul 2>nul && set "PYTHON_CMD=py -3"
if "%PYTHON_CMD%"=="" (
  echo [ERRO] Python 3.10+ nao encontrado. Instale Python e marque Add Python to PATH.
  echo [ERRO] Python nao encontrado>> "logs\instalacao_v46_2.log"
  exit /b 1
)
%PYTHON_CMD% --version
%PYTHON_CMD% --version >> "logs\instalacao_v46_2.log" 2>&1

echo.
echo [2/8] Criando ambiente virtual...
if not exist ".venv\Scripts\activate.bat" (
  %PYTHON_CMD% -m venv .venv >> "logs\instalacao_v46_2.log" 2>&1
  if errorlevel 1 goto :erro
) else (
  echo Ambiente virtual ja existe.
)

echo.
echo [3/8] Ativando ambiente virtual...
call ".venv\Scripts\activate.bat" >> "logs\instalacao_v46_2.log" 2>&1
if errorlevel 1 goto :erro

echo.
echo [4/8] Atualizando pip/setuptools/wheel...
python -m pip install --upgrade pip setuptools wheel >> "logs\instalacao_v46_2.log" 2>&1
if errorlevel 1 goto :erro

echo.
echo [5/8] Instalando dependencias essenciais...
pip install -r requirements.txt >> "logs\instalacao_v46_2.log" 2>&1
if errorlevel 1 goto :erro

echo.
echo [6/8] Instalando dependencias opcionais de extracao...
echo      Se alguma falhar, o painel ainda deve abrir.
if exist requirements-optional.txt (
  pip install -r requirements-optional.txt >> "logs\instalacao_v46_2.log" 2>&1
  if errorlevel 1 echo [AVISO] Dependencias opcionais falharam. Continuando.
)

echo.
echo [7/8] Instalando Chromium do Playwright...
python -m playwright install chromium >> "logs\instalacao_v46_2.log" 2>&1
if errorlevel 1 echo [AVISO] Chromium do Playwright nao instalado agora. Continuando.

echo.
echo [8/8] Normalizando .env e compilando entradas principais...
python scripts_config_env.py >> "logs\instalacao_v46_2.log" 2>&1
if errorlevel 1 goto :erro
python VALIDAR_ENV.py >> "logs\instalacao_v46_2.log" 2>&1
if errorlevel 1 goto :erro
python -m py_compile VALIDAR_ENV.py scripts_config_env.py ururau_painel.py ururau_monitor.py > "logs\compile_smoke_v46_2.log" 2>&1
if errorlevel 1 (
  echo [ERRO] Falha de compilacao. Veja logs\compile_smoke_v46_2.log
  type "logs\compile_smoke_v46_2.log"
  exit /b 1
)

echo.
echo [OK] Instalacao concluida.
echo [OK] Agora execute RODAR_TUDO_VISIVEL.bat para abrir vendo erros.
exit /b 0

:erro
echo.
echo [ERRO] Falha na instalacao. Veja logs\instalacao_v46_2.log
echo Ultimas linhas do log:
powershell -NoProfile -Command "if (Test-Path 'logs\instalacao_v46_2.log') { Get-Content 'logs\instalacao_v46_2.log' -Tail 40 }"
exit /b 1
