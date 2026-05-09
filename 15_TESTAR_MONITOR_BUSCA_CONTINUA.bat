@echo off
cd /d "%~dp0sistema"
set URURAU_MONITOR_MODO_CMS=rascunho
set URURAU_PUBLICAR_DIRETO=0
set URURAU_CMS_PUBLICACAO_DIRETA=0
set SCORE_MIN_MONITOR=30
set URURAU_SCORE_MINIMO_RASCUNHO=30
set URURAU_V110_KIMI_TIMEOUT_SEG=25
set URURAU_V111_TIMEOUT_SEG=35
set URURAU_SOURCE_HUNTER_TIMEOUT_SEG=20
python ururau_monitor.py --modo-cms rascunho --ciclo-unico --intervalo 90 --max-hora 24
pause


