@echo off
cd /d "%~dp0"
echo Verificando processos Python que podem estar mantendo o banco aberto...
tasklist | findstr /I "python.exe pythonw.exe"
echo.
echo Se houver outro painel/monitor aberto, feche-o antes de iniciar novamente.
echo Este script nao apaga banco e nao mata processos automaticamente.
pause
