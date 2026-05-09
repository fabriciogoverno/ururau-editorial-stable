"""Detecção de duplicidade semântica local — v74."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from ururau.editorial.memoria_editorial import carregar_memoria, tokens, jaccard, _norm


@dataclass
class DuplicateCheck:
    is_duplicate: bool
    score: float
    reason: str = ""
    matched_title: str = ""
    matched_link: str = ""


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def verificar_duplicidade_semantica(pauta: dict[str, Any], candidatos: list[dict[str, Any]] | None = None, threshold: float = 0.72) -> DuplicateCheck:
    titulo = pauta.get("titulo_origem") or pauta.get("titulo") or ""
    texto = " ".join([titulo, pauta.get("resumo_origem", "") or "", pauta.get("texto_fonte", "") or pauta.get("dossie", "") or ""])
    link = pauta.get("link_origem") or ""

    # 1) Link idêntico entre candidatos
    if candidatos:
        for c in candidatos:
            if c is pauta:
                continue
            if link and link == (c.get("link_origem") or ""):
                return DuplicateCheck(True, 1.0, "link_origem idêntico no mesmo ciclo", c.get("titulo_origem", ""), link)

    # 2) Memória editorial recente
    mem = carregar_memoria()
    score, item = mem.similaridade_recente(titulo, texto)
    if item and score >= threshold:
        return DuplicateCheck(True, score, "similaridade alta com memória editorial recente", item.get("titulo", ""), item.get("link", ""))

    # 3) Comparação no ciclo atual
    tks = tokens(texto)
    best = 0.0
    best_title = ""
    best_link = ""
    if candidatos:
        for c in candidatos:
            if c is pauta:
                continue
            ctitulo = c.get("titulo_origem") or ""
            ctexto = " ".join([ctitulo, c.get("resumo_origem", "") or "", c.get("texto_fonte", "") or c.get("dossie", "") or ""])
            s = max(jaccard(tks, tokens(ctexto)), _sim(titulo, ctitulo))
            if s > best:
                best = s
                best_title = ctitulo
                best_link = c.get("link_origem", "") or ""
    if best >= threshold:
        return DuplicateCheck(True, best, "similaridade alta no ciclo atual", best_title, best_link)
    return DuplicateCheck(False, max(best, score), "sem duplicidade semântica relevante")
