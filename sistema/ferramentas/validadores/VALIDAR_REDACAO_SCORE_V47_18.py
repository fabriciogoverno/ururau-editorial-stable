from pathlib import Path
import sys
S=Path(__file__).resolve()
for p in S.parents:
    if p.name=='sistema': ROOT=p; break
else: ROOT=Path.cwd()
ns={}
exec((ROOT/'ururau'/'editorial'/'compat_resultado_v47_18.py').read_text(encoding='utf-8'),ns)
assert ns['get_score']({'score':88})==88
print('VALIDACAO REDACAO SCORE V47.18 OK')
