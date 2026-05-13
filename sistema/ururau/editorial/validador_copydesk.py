# -*- coding: utf-8 -*-
"""validador_copydesk — auditoria editorial + factual + SEO consolidada.

spec_linha_editorial_ia_copydesk_antialucinacao §9.

Entrada: pacote_editorial (dict) + fonte_texto (str).
Saida:
    {
      "copydesk_ok": bool,
      "problemas": list[str],
      "correcao_feita": bool,         # heuristica; main fica em ia_service
      "motivo_bloqueio": str,
      "subauditorias": {
          "factual":  { ... validador_factual.auditar_fidelidade ... },
          "seo":      { ... validador_seo.validar_seo_editorial ... },
          "termos":   { "encontrados": [...] }
      }
    }

Nao chama IA. So combina os tres validadores. ia_service decide regenerar.
"""
from __future__ import annotations

from typing import Any

from .regras_editoriais_ururau import detectar_termos_proibidos
from .validador_factual import auditar_fidelidade
from .validador_seo import validar_seo_editorial


def auditar_copydesk(pacote: dict | None, fonte_texto: str,
                     *, modo_estrito_factual: bool = True,
                     palavra_chave: str = "") -> dict:
    if not isinstance(pacote, dict):
        return {
            "copydesk_ok": False,
            "problemas": ["pacote_nao_e_dict"],
            "correcao_feita": False,
            "motivo_bloqueio": "pacote_invalido",
            "subauditorias": {},
        }

    corpo = " ".join(str(pacote.get(k, "") or "") for k in (
        "titulo_seo", "subtitulo_curto", "titulo_capa",
        "legenda_curta", "retranca", "corpo_materia",
    ))

    factual = auditar_fidelidade(corpo, fonte_texto or "",
                                 modo_estrito=modo_estrito_factual)
    seo = validar_seo_editorial(pacote, palavra_chave=palavra_chave)
    termos_achados = detectar_termos_proibidos(corpo)

    problemas: list[str] = []
    if not factual["ok"]:
        problemas.extend(factual["problemas"])
    if not seo["ok"]:
        problemas.extend(seo["erros"])
    if termos_achados:
        problemas.append("termos_proibidos:" + ",".join(termos_achados[:8]))

    erros_graves = (
        bool(factual["erro_tipos"])
        or any(e for e in seo["erros"] if "titulo_seo_excede" in e
                                  or "titulo_capa_excede" in e
                                  or "paragrafo_unico" in e
                                  or "abaixo_de_4_paragrafos" in e
                                  or "travessao_no_corpo" in e
                                  or "retranca_fora" in e
                                  or "subtitulo_igual_ao_titulo_literal" in e)
        or bool(termos_achados)
    )

    motivo = ""
    if erros_graves:
        if factual["erro_tipos"]:
            motivo = factual["erro_tipos"][0]
        elif termos_achados:
            motivo = "TERMOS_PROIBIDOS"
        else:
            motivo = "VIOLACAO_LIMITES_EDITORIAIS"

    return {
        "copydesk_ok": not erros_graves,
        "problemas": problemas,
        "correcao_feita": False,
        "motivo_bloqueio": motivo,
        "subauditorias": {
            "factual": factual,
            "seo": seo,
            "termos": {"encontrados": termos_achados},
        },
    }


__all__ = ["auditar_copydesk"]
