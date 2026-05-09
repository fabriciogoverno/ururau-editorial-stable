@echo off
setlocal
set ROOT=%~dp0
cd /d "%ROOT%"
echo ==============================================
echo URURAU AUDITOR IA - PIPELINE SEGURO
echo ==============================================
echo.
echo [1/4] Auditoria total
call "%ROOT%30_AUDITORIA_TOTAL.bat"
if errorlevel 1 goto erro
cd /d "%ROOT%"
echo.
echo [2/4] Testes de contrato
call "%ROOT%31_TESTES_CONTRATO.bat"
if errorlevel 1 goto erro
cd /d "%ROOT%"
echo.
echo [3/4] Sandbox Auditor
call "%ROOT%32_SANDBOX_AUDITOR.bat"
if errorlevel 1 goto erro
cd /d "%ROOT%"
echo.
echo [4/4] Plano de correcao
call "%ROOT%34_GERAR_PLANO_CORRECAO.bat"
if errorlevel 1 goto erro
cd /d "%ROOT%"
echo.
echo Pipeline concluido com sucesso.
pause
exit /b 0

:erro
echo.
echo PIPELINE INTERROMPIDO: uma etapa falhou.
pause
exit /b 1
