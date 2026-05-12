@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM ── fix/auditoria-fila-scrapling-v136: flags canonicas obrigatorias ──
REM Decisao §4 do spec_autorizacao_claudio:
REM  - desliga patches runtime de FilaPautas.popular (V136/V137/V138)
REM  - cleaned_source_text e canonico; MIN_VALID=550
REM  - Scrapling v136 segue como motor principal
REM Para rollback rapido, comente as 4 linhas abaixo ou exporte =0.
set URURAU_DISABLE_FILA_RUNTIME_PATCHES=1
set URURAU_USE_CANONICAL_QUEUE=1
set URURAU_USE_SCRAPLING_V136=1
set URURAU_MIN_VALID=550


echo ==========================================
echo  URURAU — ABRIR PAINEL EDITORIAL
echo ==========================================

if exist "sistema\ururau_autopilot_service.py" (
    echo [AUTOPILOT] Iniciando junto com o painel editorial...
    start "Ururau Autopilot" /min cmd /c "cd /d "%~dp0sistema" && python ururau_autopilot_service.py --interval=300"
) else (
    echo [AUTOPILOT][AVISO] ururau_autopilot_service.py nao encontrado. Abrindo painel sem Autopilot.
)

cd /d "%~dp0sistema"
set PYTHONPATH=%CD%;%PYTHONPATH%
python -c "import sitecustomize; import ururau_painel; ururau_painel.main()"

pause
