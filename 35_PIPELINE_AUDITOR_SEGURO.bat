@echo off
cd /d "%~dp0"
echo ==============================================
echo URURAU AUDITOR IA - PIPELINE SEGURO
echo ==============================================
echo.
echo [1/4] Auditoria total
call 30_AUDITORIA_TOTAL.bat
echo.
echo [2/4] Testes de contrato
call 31_TESTES_CONTRATO.bat
echo.
echo [3/4] Sandbox Auditor
call 32_SANDBOX_AUDITOR.bat
echo.
echo [4/4] Plano de correcao
call 34_GERAR_PLANO_CORRECAO.bat
echo.
echo Pipeline concluido.
pause
