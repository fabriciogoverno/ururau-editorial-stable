# -*- coding: utf-8 -*-
"""Patches automaticos leves carregados no startup do Python.

Python importa sitecustomize automaticamente quando o arquivo esta no sys.path.
Como o painel roda dentro da pasta sistema, este arquivo ativa patches de runtime
sem exigir alteracao direta no ururau_painel.py.

NOTA fix/auditoria-fila-scrapling-v136:
    A partir desta branch, os patches que interceptavam ``FilaPautas.popular``
    em runtime (V136 FILA_VISUAL e variantes locais V137/V138) ficam
    DESLIGADOS por padrao. A logica oficial vive em
    ``ururau.ui.painel.FilaPautas.popular`` + ``Database.query_fila_ativa``.

    Para reativar o patch antigo da fila (rollback rapido), basta exportar:

        URURAU_DISABLE_FILA_RUNTIME_PATCHES=0

    Patches que NAO mexem na fila (audiencia v134, short_ok v136) continuam
    ativos normalmente.
"""
from __future__ import annotations

import os


def _flag(name: str, default: str) -> bool:
    raw = str(os.getenv(name, default)).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


# Patches que NAO sao monkey-patches da fila — permanecem ativos por padrao.
try:
    from ururau.editorial.audiencia_runtime_patch_v134 import instalar_audiencia_runtime_patch_v134
    if instalar_audiencia_runtime_patch_v134():
        print("[V134][AUDIENCIA] trilho de alcance/audiencia ativo.", flush=True)
except Exception as _e_v134:
    try:
        print(f"[V134][AUDIENCIA][AVISO] patch nao aplicado: {_e_v134}", flush=True)
    except Exception:
        pass

try:
    from ururau.coleta.leitura_fonte_short_ok_v136 import instalar_short_ok_v136
    if instalar_short_ok_v136():
        print("[V136][SHORT_OK] patch de texto curto util instalado.", flush=True)
except Exception as _e_v136_short:
    try:
        print(f"[V136][SHORT_OK][AVISO] patch nao aplicado: {_e_v136_short}", flush=True)
    except Exception:
        pass

# Gate oficial — desliga monkey-patches que interceptam FilaPautas.popular.
# Default = desligado. Para reativar (rollback): URURAU_DISABLE_FILA_RUNTIME_PATCHES=0.
if _flag("URURAU_DISABLE_FILA_RUNTIME_PATCHES", "1"):
    print("[FILA][CANONICO] patches runtime de FilaPautas.popular desligados (URURAU_DISABLE_FILA_RUNTIME_PATCHES=1).", flush=True)
else:
    try:
        from ururau.ui.fila_visual_fix_v136 import instalar_fila_visual_fix_v136
        if instalar_fila_visual_fix_v136():
            print("[V136][FILA_VISUAL] patch consolidado de fila instalado.", flush=True)
    except Exception as _e_v136_fila:
        try:
            print(f"[V136][FILA_VISUAL][AVISO] patch nao aplicado: {_e_v136_fila}", flush=True)
        except Exception:
            pass
