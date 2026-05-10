@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — FECHAMENTO DE PATCHES (24h)
echo ==========================================
cd /d "%~dp0sistema"
python -c "
from pathlib import Path
import sys
base = Path('..').resolve()
sys.path.insert(0, str(base / 'sistema'))
from ururau_ai_auditor.nn_engine.rollback_guard import RollbackGuard
from ururau_ai_auditor.nn_engine.impact_tracker import ImpactTracker
import json
g = RollbackGuard(base)
t = ImpactTracker(base)
for r in t.get_historico():
    if r.get('fase') == 'baseline' and not any(x.get('fase')=='fechamento' and x.get('patch_id')==r['patch_id'] for x in t.get_historico()):
        print(f'Fechando: {r["patch_id"]}')
        res = g.fechar(r['patch_id'])
        print(json.dumps(res, ensure_ascii=False, indent=2))
print('Fechamento concluido.')
"
pause
