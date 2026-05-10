@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — STATUS NEURAL ENGINE
echo ==========================================
cd /d "%~dp0sistema"
python -c "
from pathlib import Path
root = Path('.')
modelos = root / 'modelos_ml'
dados = root / 'dados_ml'
print('Modelos:', list(modelos.glob('*')) if modelos.exists() else 'Nenhum')
print('Dados:', list(dados.glob('*')) if dados.exists() else 'Nenhum')
print('Neural Engine pronta.' if modelos.exists() else 'Neural Engine não inicializada. Rode 45_TREINAR_MODELOS.bat')
"
pause
