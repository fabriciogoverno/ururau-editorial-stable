@echo off
chcp 65001 >nul
cd /d "%~dp0sistema"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
python "ferramentas\validadores\AUDITAR_REGRAS_EDITORIAIS.py"
pause
