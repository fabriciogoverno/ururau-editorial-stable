# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path

def _get(o, k, d=None):
    if isinstance(o, dict): return o.get(k, d)
    return getattr(o, k, d)

def imagem_ok(imagem):
    if not imagem: return False
    path = _get(imagem, 'caminho_imagem') or _get(imagem, 'path') or _get(imagem, 'arquivo') or _get(imagem, 'final')
    url = _get(imagem, 'url_imagem') or _get(imagem, 'url') or _get(imagem, 'src')
    if path and Path(str(path)).exists(): return True
    if url and str(url).startswith(('http://','https://')): return True
    return False

def preflight_publicacao(pauta, materia, imagem, rascunho=True):
    try:
        from ururau.editorial.canal_final_v47_23 import corrigir_canal_materia
        corrigir_canal_materia(materia, pauta)
    except Exception:
        pass
    if not imagem_ok(imagem):
        return False, 'BLOQUEADO: sem imagem valida. Nao envia rascunho nem publicacao ao CMS sem fotografia.'
    return True, 'OK'
