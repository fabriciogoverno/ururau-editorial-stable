@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "logs" mkdir "logs"
if not exist "data" mkdir "data"
if not exist "imagens" mkdir "imagens"
if not exist "prints" mkdir "prints"

echo ============================================================>> "logs\iniciar_oculto.log"
echo URURAU v132.3 - iniciar automatico oculto %date% %time%>> "logs\iniciar_oculto.log"
echo ============================================================>> "logs\iniciar_oculto.log"

REM 1) Instala automaticamente se ainda nao houver .venv. Sem exigir tecla do usuario.
if not exist ".venv\Scripts\activate.bat" (
  echo [SETUP] Ambiente ainda nao instalado. Rodando INSTALAR.bat automaticamente...>> "logs\iniciar_oculto.log"
  call "%~dp0INSTALAR.bat" >> "logs\iniciar_oculto.log" 2>&1
  if errorlevel 1 (
    echo [ERRO] INSTALAR.bat falhou. Veja logs\iniciar_oculto.log>> "logs\iniciar_oculto.log"
    exit /b 1
  )
)

REM 2) Ativa o ambiente e valida sem interação.
call ".venv\Scripts\activate.bat" >> "logs\iniciar_oculto.log" 2>&1
if errorlevel 1 exit /b 1

python scripts_config_env.py >> "logs\iniciar_oculto.log" 2>&1
python VALIDAR_ENV.py >> "logs\iniciar_oculto.log" 2>&1

REM 3) Repara dados antigos sem abrir console.
if exist "ferramentas\reparos\CORRIGIR_FILA_SEM_TEXTO_V84.py" python "ferramentas\reparos\CORRIGIR_FILA_SEM_TEXTO_V84.py" >> "logs\iniciar_oculto.log" 2>&1
if exist "ferramentas\reparos\CORRIGIR_V129_2_FILA_RSS.py" python "ferramentas\reparos\CORRIGIR_V129_2_FILA_RSS.py" >> "logs\iniciar_oculto.log" 2>&1

REM 4) Abre somente o painel visual. O console fica dentro da interface.
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "%~dp0INICIAR_PAINEL_GUI.pyw"
) else (
  start "" pythonw "%~dp0INICIAR_PAINEL_GUI.pyw"
)
exit /b 0
