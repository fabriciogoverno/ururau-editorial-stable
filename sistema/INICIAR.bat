@echo off
chcp 65001 >nul
cd /d "%~dp0"
wscript.exe //B "%~dp0INICIAR_SILENCIOSO.vbs"
exit /b 0
