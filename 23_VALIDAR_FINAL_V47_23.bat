@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau/editorial/canal_final_v47_23.py
python -m py_compile ururau/publisher/preflight_publicacao_v47_23.py
python -m py_compile ururau/publisher/monitor_stop_v47_23.py
python -m py_compile ururau/publisher/monitor.py
python -m py_compile ururau/publisher/workflow.py
python -m py_compile ururau/ui/patch_v47_23_monitor_stop_painel.py
python -m py_compile ururau/ui/painel.py
echo VALIDACAO FINAL V47.23 OK
pause
