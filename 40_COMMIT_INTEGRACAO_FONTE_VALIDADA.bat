@echo off
cd /d "%~dp0"
echo ==============================================
echo COMMIT SEGURO - INTEGRACAO FONTEVALIDADA
echo ==============================================
echo.
echo Este script versiona APENAS o workflow.py alterado pelo instalador V47.29.
echo Nao adiciona configs locais, banco, logs, imagens ou credenciais.
echo.
git status --short
echo.
echo Se o arquivo sistema/ururau/publisher/workflow.py aparecer como modificado, ele sera commitado.
echo.
pause
git add sistema/ururau/publisher/workflow.py
git commit -m "feat: integrar FonteValidada ao workflow real"
if errorlevel 1 goto fim
git push origin auditor-ia
:fim
git status --short
pause
