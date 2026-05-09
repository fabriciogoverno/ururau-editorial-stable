@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo  URURAU v46.8 - VALIDACAO SEM CHAMAR OPENAI
echo ==============================================
echo.
python VALIDAR_AUDITORIA_IA_V46_8.py
echo.
echo Veja tambem: logs\ia_diagnostico.log
pause
