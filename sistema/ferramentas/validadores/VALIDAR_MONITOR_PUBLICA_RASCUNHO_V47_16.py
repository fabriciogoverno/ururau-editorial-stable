# -*- coding: utf-8 -*-
from pathlib import Path
import json, sys
S=Path(__file__).resolve()
for p in S.parents:
    if p.name=='sistema': ROOT=p; break
else: ROOT=Path.cwd()
errors=[]
def ok(c,m):
    print(('OK   ' if c else 'ERRO ') + m)
    if not c: errors.append(m)
cfg=json.loads((ROOT/'config'/'monitor_24h.json').read_text(encoding='utf-8'))
ok(cfg.get('score_minimo_rascunho')==30,'score_minimo_rascunho=30')
ok(cfg.get('texto_minimo_rascunho_chars')==350,'texto_minimo_rascunho_chars=350')
mon=(ROOT/'ururau'/'publisher'/'monitor.py').read_text(encoding='utf-8')
ok('modo_coleta_v47_16' in mon,'monitor usa modo de coleta flexível para rascunho')
ok('rascunho_spool_v47_16' in mon,'monitor salva spool local se CMS falhar')
ok((ROOT/'ururau'/'publisher'/'rascunho_spool_v47_16.py').exists(),'spool de rascunhos existe')
wf=(ROOT/'ururau'/'publisher'/'workflow.py').read_text(encoding='utf-8')
ok('"350"' in wf,'workflow contém threshold 350 para rascunho')
if errors:
    print('\nFALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO MONITOR PUBLICA/RASCUNHO V47.16 OK')
