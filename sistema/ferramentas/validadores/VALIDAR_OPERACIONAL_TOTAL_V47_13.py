
# -*- coding: utf-8 -*-
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve()
for p in ROOT.parents:
    if p.name=='sistema': S=p; break
else: S=Path.cwd()
errors=[]
def ok(cond,msg):
    print(('OK   ' if cond else 'ERRO ') + msg)
    if not cond: errors.append(msg)
cfg=S/'config'/'monitor_24h.json'
ok(cfg.exists(),'config/monitor_24h.json existe')
if cfg.exists():
    data=json.loads(cfg.read_text(encoding='utf-8'))
    ok(data.get('score_minimo_monitor',99)<=45,'score mínimo flexível para rascunho')
    ok(data.get('coleta',{}).get('google_news_integrado_v111') is True,'Google News v111 ativo')
    ok(data.get('coleta',{}).get('fila_painel_monitor') is True,'fila do painel entra no monitor')
    ok(data.get('extracao',{}).get('playwright_publico_se_falhar') is True,'Playwright público fallback ativo')
ok((S/'ururau'/'coleta'/'scraper_defaults_v47_10.py').exists(),'scraper defaults existe')
ok((S/'ururau'/'coleta'/'fontes_unificadas_v47_13.py').exists(),'fontes unificadas existe')
ok((S/'ururau'/'editorial'/'seo_premium_v47_12.py').exists(),'SEO premium existe')
ok((S/'ururau'/'editorial'/'risco.py').exists(),'risco detalhado existe')
if errors:
    print('\nFALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO V47.13 OK')
