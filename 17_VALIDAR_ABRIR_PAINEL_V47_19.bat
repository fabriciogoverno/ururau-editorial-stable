@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\ui\painel.py
python -m py_compile ururau\editorial\redacao.py
python -m py_compile ururau\editorial\engine.py
echo VALIDACAO V47.19 OK
pause
