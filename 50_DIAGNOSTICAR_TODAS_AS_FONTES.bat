@echo off
chcp 65001 >nul
title Ururau - Diagnostico de TODAS as fontes (v200)
cd /d "%~dp0"

echo ============================================================
echo  DIAGNOSTICO DE FONTE EM LOTE - URURAU v200
echo ------------------------------------------------------------
echo  Roda o diagnostico completo de TODAS as fontes configuradas,
echo  descobre a melhor estrategia de captacao de cada link e
echo  aplica o perfil operacional. Fontes que falharem em tudo
echo  sao apenas SINALIZADAS (nada e desativado).
echo ============================================================
echo.

python sistema\diagnosticar_todas_fontes_v200.py %*

echo.
echo ============================================================
echo  Concluido. Veja o relatorio em:
echo  sistema\relatorios_diagnostico_fontes\lote_v200\
echo ============================================================
pause
