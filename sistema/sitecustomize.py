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

try:
    from ururau.coleta.leitura_fonte_short_ok_v136 import instalar_short_ok_v136
    if instalar_short_ok_v136():
        print("[V136][SHORT_OK] patch de texto curto útil instalado.", flush=True)
except Exception as _e_v136_short:
    try:
        print(f"[V136][SHORT_OK][AVISO] patch não aplicado: {_e_v136_short}", flush=True)
    except Exception:
        pass

try:
    from ururau.ui.fila_visual_fix_v136 import instalar_fila_visual_fix_v136
    if instalar_fila_visual_fix_v136():
        print("[V136][FILA_VISUAL] patch consolidado de fila instalado.", flush=True)
except Exception as _e_v136_fila:
    try:
        print(f"[V136][FILA_VISUAL][AVISO] patch não aplicado: {_e_v136_fila}", flush=True)
    except Exception:
        pass
