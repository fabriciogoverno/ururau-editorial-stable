@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Ururau v46.2 Premium - Instalar / validar / abrir

if not exist "logs" mkdir "logs"
if not exist "data" mkdir "data"
if not exist "data\imagens" mkdir "data\imagens"
if not exist "data\prints" mkdir "data\prints"

echo ============================================================
echo   URURAU v46.2 PREMIUM - INSTALAR / VALIDAR / ABRIR
echo ============================================================
echo Esta janela aparece durante instalacao e validacao.
echo Quando o painel visual abrir, esta janela sera fechada.
echo.

if not exist ".venv\Scripts\activate.bat" (
  echo [SETUP] Ambiente virtual nao encontrado. Instalando dependencias...
  call "%~dp0INSTALAR.bat"
  if errorlevel 1 goto :erro
) else (
  echo [OK] Ambiente virtual encontrado.
)

echo.
echo [1/4] Ativando ambiente virtual...
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :erro

echo [2/4] Normalizando ambiente...
python scripts_config_env.py
if errorlevel 1 goto :erro

echo [3/4] Validando .env...
python VALIDAR_ENV.py
if errorlevel 1 goto :erro

echo [4/4] Reparos seguros...
if exist "ferramentas\reparos\CORRIGIR_FILA_SEM_TEXTO_V84.py" python "ferramentas\reparos\CORRIGIR_FILA_SEM_TEXTO_V84.py"
if exist "ferramentas\reparos\CORRIGIR_V129_2_FILA_RSS.py" python "ferramentas\reparos\CORRIGIR_V129_2_FILA_RSS.py"
if exist "CORRIGIR_FILA_SEM_TEXTO_V84.py" python "CORRIGIR_FILA_SEM_TEXTO_V84.py"
if exist "CORRIGIR_V129_2_FILA_RSS.py" python "CORRIGIR_V129_2_FILA_RSS.py"

echo.
echo [OK] Validacao concluida. Abrindo painel visual...

echo ============================================================>> "logs\rodar_tudo.log"
echo URURAU v46.2 PREMIUM %date% %time%>> "logs\rodar_tudo.log"
echo Painel iniciado por RODAR_TUDO_VISIVEL.bat.>> "logs\rodar_tudo.log"
echo ============================================================>> "logs\rodar_tudo.log"

if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "%~dp0INICIAR_PAINEL_GUI.pyw"
) else (
  start "" pythonw "%~dp0INICIAR_PAINEL_GUI.pyw"
)
exit /b 0

:erro
echo.
echo [ERRO] Rodar Tudo falhou. Leia a mensagem acima.
echo A janela ficara aberta somente em caso de erro.
pause
exit /b 1
