# -*- coding: utf-8 -*-
from pathlib import Path
import json, py_compile, sys
S=Path(__file__).resolve()
for p in S.parents:
    if p.name=='sistema': ROOT=p; break
else: ROOT=Path.cwd()
errors=[]
def ok(c,m):
    print(('OK   ' if c else 'ERRO ') + m)
    if not c: errors.append(m)
for rel in ['ururau/ui/painel.py','ururau/editorial/redacao.py','ururau/editorial/engine.py','ururau/publisher/workflow.py']:
    f=ROOT/rel
    py_compile.compile(str(f), doraise=True)
    t=f.read_text(encoding='utf-8',errors='ignore')
    ok('PATCH_V47_20_DICT_ATTR_COMPAT' in t, rel+' com compat dict/obj')
cfg=json.loads((ROOT/'config'/'monitor_24h.json').read_text(encoding='utf-8'))
coleta=cfg.get('coleta',{})
ok(coleta.get('google_news_integrado_v111') is False, 'Google News v111 desligado no monitor')
ok(coleta.get('google_news_fallback_v110') is False, 'Kimi/Google legado desligado no monitor')
ok(coleta.get('source_hunter') is False, 'Source Hunter desligado no monitor')
pp=(ROOT/'ururau/ui/patch_v47_15_monitor_painel.py').read_text(encoding='utf-8',errors='ignore')
ok('URURAU_GNEWS_DESLIGADO_NO_MONITOR' in pp, 'painel força GNEWS off no monitor')
if errors:
    print('\nFALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO REPARO FINAL V47.20 OK')
