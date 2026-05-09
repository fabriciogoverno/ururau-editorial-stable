@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\publisher\monitor_stop_v47_22.py
python -m py_compile ururau\publisher\monitor.py
python -m py_compile ururau\ui\patch_v47_22_monitor_stop_painel.py
python -m py_compile ururau\ui\painel.py
echo VALIDACAO MONITOR PARAR V47.22 OK
pause
