@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\editorial\integridade_redacao_v47_25.py
python -m py_compile ururau\ui\patch_v47_25_integridade_redacao.py
python -m py_compile ururau\ui\painel.py
echo VALIDACAO INTEGRIDADE REDACAO V47.25 OK
pause
