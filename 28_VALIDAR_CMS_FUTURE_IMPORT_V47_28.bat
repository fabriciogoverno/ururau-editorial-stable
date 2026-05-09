@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\publisher\cms_playwright_v81.py
python -m py_compile ururau\publisher\workflow.py
python -m py_compile ururau\publisher\monitor.py
echo VALIDACAO CMS FUTURE IMPORT V47.28 OK
pause
