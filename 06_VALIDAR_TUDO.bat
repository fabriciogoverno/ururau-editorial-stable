@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0sistema"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
if not exist "logs" mkdir "logs"
echo ============================================================
echo  VALIDACAO GERAL - AMBIENTE, REGRAS, MONITOR E INTEGRACOES
echo ============================================================
echo.

echo [1/6] Validando ambiente .env...
python VALIDAR_ENV.py
if errorlevel 1 goto :erro

echo.
echo [2/6] Auditando regras editoriais...
python "ferramentas\validadores\AUDITAR_REGRAS_EDITORIAIS.py"
if errorlevel 1 goto :erro

echo.
echo [3/6] Validando monitor 24h...
python VALIDAR_MONITOR_24H.py
if errorlevel 1 goto :erro

echo.
echo [4/6] Validando operacao V47.4/F5/extracao...
python VALIDAR_V47_4_OPERACIONAL.py
if errorlevel 1 goto :erro

echo.
echo [5/6] Validando monitor continuo V47.6...
python VALIDAR_MONITOR_CONTINUO_V47_6.py
if errorlevel 1 goto :erro

echo.
echo [6/6] Validando integracoes e capacidade V47.7...
python VALIDAR_INTEGRACOES_V47_7.py
if errorlevel 1 goto :erro

echo.
echo [OK] Validacao geral concluida.
pause
exit /b 0

:erro
echo.
echo [ERRO] A validacao falhou. Veja a mensagem acima e os logs.
pause
exit /b 1

cd /d "%~dp0sistema"
python VALIDAR_V47_9_PREMIUM_OPERACIONAL.py
