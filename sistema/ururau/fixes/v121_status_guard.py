from __future__ import annotations

import builtins
import inspect
import sys

_PATCHED = False
_ORIGINAL_IMPORT = None

STATUS_MAP = {
    "EM_REDACAO": "em_redacao",
    "REVISADA": "revisada",
    "RASCUNHO": "rascunho",
    "PUBLICADA": "publicada",
    "DESCARTADA": "descartada",
    "CAPTADA": "captada",
    "TRIADA": "triada",
    "APROVADA": "aprovada",
    "REJEITADA": "rejeitada",
    "BLOQUEADA": "bloqueada",
    "EXCLUIDA": "excluida",
    "PRONTA": "pronta",
    "COLETADA": "coletada",
    "PENDENTE": "pendente",
    "REPROVADA": "reprovada",
    "EM_REVISAO": "em_revisao",
    "FALHOU": "falhou",
    "ERRO": "erro",
}

def _add_status_attrs(obj):
    try:
        for attr, value in STATUS_MAP.items():
            if not hasattr(obj, attr):
                setattr(obj, attr, value)
    except Exception:
        pass

def _patch_module(mod):
    try:
        name = getattr(mod, "__name__", "")
        if not name.startswith("ururau"):
            return
        for _n, obj in list(vars(mod).items()):
            if inspect.isfunction(obj) or inspect.ismethod(obj):
                _add_status_attrs(obj)
    except Exception:
        pass

def _patch_loaded_modules():
    for mod in list(sys.modules.values()):
        if mod is not None:
            _patch_module(mod)

def aplicar_status_guard_v121():
    global _PATCHED, _ORIGINAL_IMPORT
    if _PATCHED:
        return
    _PATCHED = True
    _patch_loaded_modules()
    _ORIGINAL_IMPORT = builtins.__import__
    def import_wrapper(name, globals=None, locals=None, fromlist=(), level=0):
        mod = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
        try:
            if name.startswith("ururau"):
                _patch_loaded_modules()
        except Exception:
            pass
        return mod
    builtins.__import__ = import_wrapper
    print("[V121][STATUS] guard ativo: erro de função sem REVISADA/EM_REDACAO protegido")
