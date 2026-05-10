# -*- coding: utf-8 -*-
"""Patches automáticos leves carregados no startup do Python.

Python importa sitecustomize automaticamente quando o arquivo está no sys.path.
Como o painel roda dentro da pasta sistema, este arquivo ativa patches de runtime
sem exigir alteração direta no ururau_painel.py.
"""
from __future__ import annotations

try:
    from ururau.editorial.audiencia_runtime_patch_v134 import instalar_audiencia_runtime_patch_v134
    if instalar_audiencia_runtime_patch_v134():
        print("[V134][AUDIENCIA] trilho de alcance/audiência ativo.", flush=True)
except Exception as _e_v134:
    try:
        print(f"[V134][AUDIENCIA][AVISO] patch não aplicado: {_e_v134}", flush=True)
    except Exception:
        pass
