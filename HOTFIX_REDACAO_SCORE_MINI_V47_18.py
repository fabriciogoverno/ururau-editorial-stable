# -*- coding: utf-8 -*-
from pathlib import Path
import shutil, subprocess, sys, re

def base():
    p=Path.cwd().resolve()
    if (p/'sistema').is_dir(): return p
    for x in [p]+list(p.parents):
        if (x/'sistema').is_dir(): return x
    raise SystemExit('Rode na raiz do projeto, acima da pasta sistema.')
B=base(); S=B/'sistema'
print('[V47.18] base', B)

def bk(p):
    if p.exists():
        b=p.with_suffix(p.suffix+'.bak_v47_18')
        if not b.exists(): shutil.copy2(p,b)

def wr(p,c):
    p.parent.mkdir(parents=True,exist_ok=True); bk(p); p.write_text(c,encoding='utf-8'); print('[OK]',p.relative_to(B))

def rd(p): return p.read_text(encoding='utf-8',errors='ignore') if p.exists() else ''

compat=S/'ururau'/'editorial'/'compat_resultado_v47_18.py'
wr(compat,'''# -*- coding: utf-8 -*-\nclass AttrDict(dict):\n    def __getattr__(self,k):\n        try: return self[k]\n        except KeyError as e: raise AttributeError(k) from e\n    def __setattr__(self,k,v): self[k]=v\n\ndef compat_obj(v):\n    if isinstance(v,dict): return AttrDict({k:compat_obj(x) for k,x in v.items()})\n    if isinstance(v,list): return [compat_obj(x) for x in v]\n    return v\n\ndef getv(o,k,d=None):\n    if isinstance(o,dict): return o.get(k,d)\n    return getattr(o,k,d)\n\ndef get_score(o,d=0):\n    for k in (\'score\',\'score_total\',\'score_qualidade\',\'qualidade\',\'seo_score\',\'score_editorial\',\'nota\'):\n        v=getv(o,k,None)\n        if v not in (None,\'\'):\n            try: return int(float(v))\n            except Exception: pass\n    return int(d)\n''')

helper="""\n# PATCH_V47_18_DICT_SCORE_COMPAT\ntry:\n    from ururau.editorial.compat_resultado_v47_18 import compat_obj as _v4718_compat_obj, getv as _v4718_getv, get_score as _v4718_get_score\nexcept Exception:\n    def _v4718_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)\n    def _v4718_get_score(o,d=0):\n        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):\n            v=_v4718_getv(o,k,None)\n            if v not in (None,''):\n                try: return int(float(v))\n                except Exception: pass\n        return int(d)\n    def _v4718_compat_obj(o): return o\n"""
vars=['resultado','result','res','ret','saida','out','resp','auditoria','validacao','avaliacao','qualidade','gate','diagnostico','analise','seo','quality_result','seo_result']
for p in [S/'ururau'/'editorial'/'redacao.py',S/'ururau'/'editorial'/'engine.py',S/'ururau'/'publisher'/'workflow.py',S/'ururau'/'ui'/'painel.py',S/'ururau'/'editorial'/'quality_gate_v103.py']:
    if not p.exists(): continue
    t=rd(p); bk(p); changed=False
    if 'PATCH_V47_18_DICT_SCORE_COMPAT' not in t:
        t=helper+'\n'+t; changed=True
    for v in vars:
        nt=re.sub(r'\b'+re.escape(v)+r'\.score\b', '_v4718_get_score('+v+', 0)', t)
        if nt!=t: t=nt; changed=True
    nt=re.sub(r'getattr\(([^,\)]+),\s*[\'\"]score[\'\"]\s*,\s*([^\)]+)\)', r'_v4718_get_score(\1, \2)', t)
    if nt!=t: t=nt; changed=True
    if changed: p.write_text(t,encoding='utf-8'); print('[OK] patched',p.relative_to(B))

val=S/'ferramentas'/'validadores'/'VALIDAR_REDACAO_SCORE_V47_18.py'
wr(val,"""from pathlib import Path\nimport sys\nS=Path(__file__).resolve()\nfor p in S.parents:\n    if p.name=='sistema': ROOT=p; break\nelse: ROOT=Path.cwd()\nns={}\nexec((ROOT/'ururau'/'editorial'/'compat_resultado_v47_18.py').read_text(encoding='utf-8'),ns)\nassert ns['get_score']({'score':88})==88\nprint('VALIDACAO REDACAO SCORE V47.18 OK')\n""")
wr(B/'16_VALIDAR_REDACAO_SCORE_V47_18.bat','@echo off\r\ncd /d "%~dp0sistema"\r\npython ferramentas\\validadores\\VALIDAR_REDACAO_SCORE_V47_18.py\r\npause\r\n')
for p in [compat,val]: subprocess.run([sys.executable,'-m','py_compile',str(p)],check=False)
print('\n[V47.18] aplicado. Rode .\\16_VALIDAR_REDACAO_SCORE_V47_18.bat e depois abra o painel.')
