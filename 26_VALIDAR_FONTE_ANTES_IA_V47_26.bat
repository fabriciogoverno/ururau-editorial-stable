@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\editorial\integridade_fonte_v47_26.py
python -m py_compile ururau\editorial\integridade_redacao_v47_25.py
python -m py_compile ururau\ui\patch_v47_26_fonte_antes_ia.py
python -m py_compile ururau\ui\painel.py
echo VALIDACAO FONTE ANTES IA V47.26 OK
pause
