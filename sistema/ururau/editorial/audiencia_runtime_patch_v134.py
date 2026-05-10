# -*- coding: utf-8 -*-
"""Runtime patch v134 para conectar o trilho de audiência ao scoring.

É tolerante a falhas: se o motor de score mudar de assinatura, não derruba o painel.
"""
from __future__ import annotations

_INSTALADO = False


def instalar_audiencia_runtime_patch_v134() -> bool:
    global _INSTALADO
    if _INSTALADO:
        return True
    try:
        from ururau.coleta import scoring
        from ururau.editorial.audiencia_flow_v134 import aplicar_fluxo_em_score_v134, aplicar_fluxo_em_pauta_v134
    except Exception:
        return False

    # Patch do cálculo principal de score, quando existir.
    for nome in ("calcular_score_completo", "calcular_score", "score_pauta"):
        original = getattr(scoring, nome, None)
        if not callable(original) or getattr(original, "_v134_audiencia", False):
            continue

        def _wrap(*args, __original=original, **kwargs):
            resultado = __original(*args, **kwargs)
            pauta = args[0] if args else kwargs.get("pauta") or kwargs.get("item") or {}
            try:
                aplicar_fluxo_em_pauta_v134(pauta)
                return aplicar_fluxo_em_score_v134(resultado, pauta)
            except Exception:
                return resultado

        _wrap._v134_audiencia = True  # type: ignore[attr-defined]
        setattr(scoring, nome, _wrap)
        _INSTALADO = True

    return _INSTALADO
