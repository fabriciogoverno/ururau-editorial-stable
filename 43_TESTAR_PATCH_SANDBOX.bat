@echo off
cd /d "%~dp0sistema"
if "%~1"=="" (
  echo Uso: 43_TESTAR_PATCH_SANDBOX.bat caminho_do_script_patch
  echo Exemplo: 43_TESTAR_PATCH_SANDBOX.bat ..\scripts\MEU_PATCH.py
  pause
  exit /b 2
)
python -m ururau_ai_auditor.sandbox_patch_runner --script "%~1"
pause
