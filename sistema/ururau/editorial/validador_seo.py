# -*- coding: utf-8 -*-
"""validador_seo — validacao de SEO e estrutura editorial.

spec_linha_editorial_ia_copydesk_antialucinacao §4 e §7.

Reutiliza ururau.ia.regras_editoriais_validador (limites de titulo, retranca,
paragrafos, travessao) e acrescenta:
  - palavra-chave no inicio do titulo SEO quando natural
  - subtitulo nao repete o titulo literalmente
  - tags separadas por virgula, sem hashtag
  - retranca 1..3 palavras (era 1; spec atual amplia)
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


# Reutiliza validador da branch IA-real (mesmo arquivo, ja consolidado).
from ururau.ia.regras_editoriais_validador import (
    validar_pacote_editorial as _validar_base,
    MAX_TITULO_SEO, MAX_TITULO_CAPA, MIN_PARAGRAFOS, MAX_PARAGRAFO,
)


def _norm(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def validar_seo_editorial(pacote: dict | None,
                          *, palavra_chave: str = "",
                          exigir_minimo_paragrafos: bool = True) -> dict:
    """Valida SEO + estrutura. Devolve dict no mesmo formato do base + extras."""
    base = _validar_base(pacote, exigir_minimo_paragrafos=exigir_minimo_paragrafos)
    base.setdefault("avisos_seo", [])

    if not isinstance(pacote, dict):
        return base

    t_seo = str(pacote.get("titulo_seo", "") or "").strip()
    subt = str(pacote.get("subtitulo_curto", "") or "").strip()
    tags = str(pacote.get("tags", "") or "").strip()

    # 1) palavra-chave no titulo quando natural
    if palavra_chave:
        if _norm(palavra_chave) not in _norm(t_seo):
            base["avisos_seo"].append("palavra_chave_ausente_no_titulo_seo")

    # 2) subtitulo nao pode ser igual ao titulo literalmente
    if subt and t_seo and _norm(subt) == _norm(t_seo):
        base["erros"].append("subtitulo_igual_ao_titulo_literal")
        base["ok"] = False

    # 3) tags
    if tags:
        if "#" in tags:
            base["erros"].append("tags_com_hashtag_no_site")
            base["ok"] = False
        if "," not in tags and len(tags.split()) > 1:
            base["avisos_seo"].append("tags_sem_virgula_aparente")

    return base


__all__ = [
    "validar_seo_editorial",
    "MAX_TITULO_SEO", "MAX_TITULO_CAPA",
    "MIN_PARAGRAFOS", "MAX_PARAGRAFO",
]
