@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\editorial\limpar_contaminadas_v47_27.py
python -m py_compile ururau\ui\patch_v47_27_preview_guard.py
python -m py_compile LIMPAR_MATERIAS_CONTAMINADAS_V47_27.py
python -m py_compile ururau\ui\painel.py
echo VALIDACAO LIMPEZA CONTAMINADAS V47.27 OK
pause
