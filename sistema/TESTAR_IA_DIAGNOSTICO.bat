@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================
echo  URURAU v46.8 - TESTE DE DIAGNOSTICO DA IA
echo ==============================================
echo.
python VALIDAR_AUDITORIA_IA_V46_8.py --openai
echo.
echo Veja tambem: logs\ia_diagnostico.log
pause
