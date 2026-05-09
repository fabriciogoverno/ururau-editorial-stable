# -*- coding: utf-8 -*-
from pathlib import Path
import shutil, subprocess, sys

cwd = Path.cwd().resolve()
base = cwd if (cwd / 'sistema').is_dir() else None
if base is None:
    for p in [cwd] + list(cwd.parents):
        if (p / 'sistema').is_dir():
            base = p
            break
if base is None:
    raise SystemExit('Rode na raiz do projeto, acima da pasta sistema.')

sistema = base / 'sistema'
print('[V47.19] base:', base)

helper = """# PATCH_V47_18_DICT_SCORE_COMPAT
try:
    from ururau.editorial.compat_resultado_v47_18 import compat_obj as _v4718_compat_obj, getv as _v4718_getv, get_score as _v4718_get_score
except Exception:
    def _v4718_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4718_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4718_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4718_compat_obj(o): return o

"""

def backup(p):
    if p.exists():
        b = p.with_suffix(p.suffix + '.bak_v47_19')
        if not b.exists(): shutil.copy2(p, b)

def fix_file(p):
    if not p.exists(): return
    txt = p.read_text(encoding='utf-8', errors='ignore')
    if 'PATCH_V47_18_DICT_SCORE_COMPAT' not in txt:
        return
    backup(p)
    # Remove bloco de compatibilidade do topo até o início real do arquivo original.
    start = txt.find('# -*- coding', 5)
    if start < 0:
        start = txt.find('from __future__ import')
    if start < 0:
        return
    body = txt[start:]
    # Insere o helper depois do último import __future__, que é onde Python permite código normal.
    lines = body.splitlines(True)
    insert = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('#') or s == '' or s.startswith('"""') or s.startswith("'''"):
            insert = i + 1
            continue
        if s.startswith('from __future__ import'):
            insert = i + 1
            continue
        break
    new = ''.join(lines[:insert]) + helper + ''.join(lines[insert:])
    p.write_text(new, encoding='utf-8')
    print('[OK] corrigido', p.relative_to(base))

for rel in [
    'ururau/ui/painel.py',
    'ururau/editorial/redacao.py',
    'ururau/editorial/engine.py',
    'ururau/publisher/workflow.py',
    'ururau/editorial/quality_gate_v103.py',
]:
    fix_file(sistema / rel)

bat = base / '17_VALIDAR_ABRIR_PAINEL_V47_19.bat'
bat.write_text('@echo off\r\ncd /d "%~dp0sistema"\r\npython -m py_compile ururau\\ui\\painel.py\r\npython -m py_compile ururau\\editorial\\redacao.py\r\npython -m py_compile ururau\\editorial\\engine.py\r\necho VALIDACAO V47.19 OK\r\npause\r\n', encoding='ascii')

for rel in ['ururau/ui/painel.py','ururau/editorial/redacao.py','ururau/editorial/engine.py','ururau/publisher/workflow.py','ururau/editorial/quality_gate_v103.py']:
    p = sistema / rel
    if p.exists(): subprocess.run([sys.executable, '-m', 'py_compile', str(p)], check=False)
print('[V47.19] pronto. Rode .\\17_VALIDAR_ABRIR_PAINEL_V47_19.bat e depois .\\02_ABRIR_PAINEL.bat')
