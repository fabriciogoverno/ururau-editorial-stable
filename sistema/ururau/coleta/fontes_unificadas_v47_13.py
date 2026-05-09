
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import json, re
from urllib.parse import urlparse

def _root():
    p = Path(__file__).resolve()
    for parent in p.parents:
        if parent.name == 'sistema': return parent
    return Path.cwd()

def _urls_from_obj(obj):
    found=[]
    def walk(x):
        if isinstance(x, str):
            if x.startswith('http://') or x.startswith('https://'): found.append(x.strip())
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(obj); return found

def carregar_fontes_unificadas(limit=None):
    s=_root(); paths=[
      s/'fontes_rss.json', s/'config'/'fontes_rss.json', s/'configuracoes'/'fontes_rss.json',
      s/'config'/'perfis_fontes_v131.json', s/'configuracoes'/'perfis_fontes_v131.json',
      s/'config'/'fontes_especiais_v129.json', s/'configuracoes'/'fontes_especiais_v129.json',
      s/'fontes_especiais_v129.json'
    ]
    urls=[]
    for p in paths:
        try:
            if p.exists(): urls.extend(_urls_from_obj(json.loads(p.read_text(encoding='utf-8'))))
        except Exception: pass
    seen=set(); out=[]
    for u in urls:
        key=u.split('#')[0].rstrip('/')
        if key in seen: continue
        seen.add(key); out.append({'url':u, 'dominio':urlparse(u).netloc, 'origem':'fontes_unificadas_v47_13'})
    return out[:limit] if limit else out
