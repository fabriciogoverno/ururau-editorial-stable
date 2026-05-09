# -*- coding: utf-8 -*-
from pathlib import Path
import json, os, sys
S = Path(__file__).resolve()
for p in S.parents:
    if p.name == 'sistema': ROOT=p; break
else: ROOT=Path.cwd()
errors=[]
def ok(c,m):
    print(('OK   ' if c else 'ERRO ') + m)
    if not c: errors.append(m)
cfg=json.loads((ROOT/'config'/'monitor_24h.json').read_text(encoding='utf-8'))
ok(cfg.get('score_minimo_monitor') == 35, 'score_minimo_monitor=35')
ok(cfg.get('score_minimo_rascunho') == 35, 'score_minimo_rascunho=35')
text=(ROOT/'ururau'/'coleta'/'scraper_defaults_v47_10.py').read_text(encoding='utf-8')
ok('forcar=False' in text and '**kwargs' in text, 'aplicar_defaults_scrapers aceita forcar')
mon=(ROOT/'ururau'/'publisher'/'monitor.py').read_text(encoding='utf-8')
ok('score_minimo_monitor' in mon, 'monitor.py lê chave score_minimo_monitor')
ok((ROOT.parent/'10_TESTAR_MONITOR_CICLO_UNICO.bat').exists(), 'BAT de teste ciclo único existe')
if errors:
    print('FALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO MONITOR V47.14 OK')
