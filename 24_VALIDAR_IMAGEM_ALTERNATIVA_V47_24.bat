@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\imaging\busca.py
python -m py_compile ururau\imaging\processamento.py
python -m py_compile ururau\publisher\workflow.py
echo VALIDACAO IMAGEM ALTERNATIVA V47.24 OK
pause
