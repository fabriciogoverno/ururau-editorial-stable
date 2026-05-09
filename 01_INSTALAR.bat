@echo off
chcp 65001 >nul
cd /d "%~dp0sistema"
call "INSTALAR.bat"
exit /b %errorlevel%
