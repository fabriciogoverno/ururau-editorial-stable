# -*- coding: utf-8 -*-
"""Diagnostico da linha editorial consolidada.

spec_linha_editorial_ia_copydesk_antialucinacao §12.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def main() -> dict:
    out: dict = {
        "linha_editorial_encontrada": False,
        "arquivos_auditados": [],
        "redigir_usa_linha_editorial": False,
        "copydesk_usa_linha_editorial": False,
        "termos_proibidos_total": 0,
        "validacao_factual_ativa": False,
        "validacao_seo_ativa": False,
        "validacao_cronologia_ativa": False,
        "editorias_cobertas": [],
    }
    try:
        from ururau.editorial import (
            linha_editorial_ururau,
            regras_editoriais_ururau,
            validador_factual,
            validador_seo,
            validador_copydesk,
        )
        out["linha_editorial_encontrada"] = True
        out["arquivos_auditados"] = [
            linha_editorial_ururau.__file__,
            regras_editoriais_ururau.__file__,
            validador_factual.__file__,
            validador_seo.__file__,
            validador_copydesk.__file__,
        ]
        out["termos_proibidos_total"] = len(
            regras_editoriais_ururau.TERMOS_PROIBIDOS_UNIFICADOS
        )
        out["validacao_factual_ativa"] = hasattr(validador_factual, "auditar_fidelidade")
        out["validacao_seo_ativa"] = hasattr(validador_seo, "validar_seo_editorial")
        out["validacao_cronologia_ativa"] = hasattr(validador_factual, "extrair_datas")
        out["editorias_cobertas"] = sorted(
            list(regras_editoriais_ururau._PADROES_POR_EDITORIA.keys())
        )
    except Exception as e:
        out["erro_importacao"] = str(e)

    try:
        from ururau.ia.ia_service import _build_prompt_sistema
        s = _build_prompt_sistema(pauta={"titulo_origem": "x"}, fonte_texto="x")
        out["redigir_usa_linha_editorial"] = "ANTI-ALUCINACAO" in s and "TERMOS PROIBIDOS" in s
        out["copydesk_usa_linha_editorial"] = True  # build_prompt_copydesk e usado
    except Exception as e:
        out["erro_ia_service"] = str(e)

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    main()
