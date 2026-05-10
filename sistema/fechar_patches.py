# -*- coding: utf-8 -*-
from pathlib import Path
import sys
import json

base = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(base / "sistema"))

from ururau_ai_auditor.nn_engine.rollback_guard import RollbackGuard
from ururau_ai_auditor.nn_engine.impact_tracker import ImpactTracker

g = RollbackGuard(base)
t = ImpactTracker(base)

historico = t.get_historico()
fechados = 0
for r in historico:
    if r.get("fase") == "baseline":
        ja_fechado = any(x.get("fase") == "fechamento" and x.get("patch_id") == r["patch_id"] for x in historico)
        if not ja_fechado:
            print(f"Fechando: {r['patch_id']}")
            res = g.fechar(r["patch_id"])
            print(json.dumps(res, ensure_ascii=False, indent=2))
            fechados += 1

if fechados == 0:
    print("Nenhum patch pendente de fechamento.")
else:
    print(f"Fechamento concluido. {fechados} patch(s) processado(s).")
