@echo off
cd /d "%~dp0sistema"
python -m unittest discover -s tests_contrato -p "test_*.py" -v
pause
