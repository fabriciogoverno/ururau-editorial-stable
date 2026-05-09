@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\publisher\monitor.py
python -m py_compile ururau\coleta\scraper_defaults_v47_10.py
echo VALIDACAO MONITOR BUSCA CONTINUA V47.17 OK
pause
