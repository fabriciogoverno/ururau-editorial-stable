# -*- coding: utf-8 -*-
from pathlib import Path
import sys
S=Path(__file__).resolve()
for p in S.parents:
    if p.name=='sistema': ROOT=p; break
else: ROOT=Path.cwd()
errors=[]
def ok(c,m):
    print(('OK   ' if c else 'ERRO ') + m)
    if not c: errors.append(m)
patch=ROOT/'ururau'/'ui'/'patch_v47_15_monitor_painel.py'
painel=ROOT/'ururau'/'ui'/'painel.py'
ok(patch.exists(),'patch_v47_15_monitor_painel.py existe')
t=patch.read_text(encoding='utf-8') if patch.exists() else ''
ok('modo_cms=modo_cms' in t,'MonitorRobo recebe modo_cms explícito')
ok('publicar_no_cms=True' in t,'Monitor do painel usa CMS real para rascunho')
ok('RASCUNHO CMS real' in t,'log de rascunho CMS real existe')
p=painel.read_text(encoding='utf-8') if painel.exists() else ''
ok('patch_v47_15_monitor_painel' in p,'painel.py importa patch v47.15')
if errors:
    print('\nFALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO MONITOR PAINEL V47.15 OK')
