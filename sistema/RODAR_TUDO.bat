@echo off
chcp 65001 >nul
cd /d "%~dp0"
wscript.exe //B "%~dp0RODAR_TUDO_SILENCIOSO.vbs"
exit /b 0
