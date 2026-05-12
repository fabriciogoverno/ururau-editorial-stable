# -*- coding: utf-8 -*-
"""Contrato oficial de texto da fonte — fix/auditoria-fila-scrapling-v136.

Consolida os aliases de texto da fonte que estavam dispersos e em conflito:
``cleaned_source_text`` (canônico) e a cadeia de fallback v134/v105/raw/dossie.

Resolve o problema documentado em ``spec_autorizacao_claudio.md`` §4.1:

- nenhum processo sobrescreve texto válido por vazio, erro ou snippet curto;
- V134 (READER_PROXY) e v105 (bing/fonte) usam um único contrato de leitura
  e escrita;
- o limite mínimo de texto útil é ``MIN_VALID = 550`` (overridável via env
  ``URURAU_MIN_VALID``, mas o default oficial fica em 550).

Este módulo é stateless e síncrono. Funciona em cima do dicionário de pauta
(modelo de domínio leve do projeto) e nunca toca em SQLite, IA ou rede.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

# Alias canônico (Decisão §4.1)
CANONICAL_ALIAS = "cleaned_source_text"

# Cadeia oficial de leitura, em ordem de preferência (mais limpo → mais cru).
SOURCE_TEXT_ALIASES: tuple[str, ...] = (
    "cleaned_source_text",
    "texto_fonte_v134",
    "texto_fonte",
    "texto_fonte_v105",
    "raw_source_text",
    "dossie",
)

# Ordem de confiabilidade das origens. Origem mais confiável pode substituir
# texto vindo de origem menos confiável, contanto que não reduza o tamanho útil.
ORIGEM_PRIORIDADE: dict[str, int] = {
    "unknown": 0,
    "snippet": 1,
    "rss": 1,
    "dossie": 1,
    "raw": 2,
    "v105": 3,
    "v107": 4,
    "v134": 5,
    "reader_proxy": 5,
    "cleaned": 6,
    "manual": 9,  # injeção explícita do usuário (aba Fonte) tem prioridade máxima
}

_DEFAULT_MIN_VALID = 550


def min_valid() -> int:
    """Retorna o mínimo de chars úteis para texto da fonte ser ``válido``.

    Default oficial: 550 (Decisão §4.2). Sobrescritível por
    ``URURAU_MIN_VALID``. Valores inválidos caem para 550.
    """
    raw = os.getenv("URURAU_MIN_VALID", "").strip()
    if not raw:
        return _DEFAULT_MIN_VALID
    try:
        v = int(raw)
        return v if v > 0 else _DEFAULT_MIN_VALID
    except Exception:
        return _DEFAULT_MIN_VALID


def _normalizar(texto: Any) -> str:
    if texto is None:
        return ""
    s = str(texto)
    # remove caracteres invisíveis comuns e normaliza espaços
    s = s.replace("\xa0", " ").replace("​", "")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def texto_util_chars(texto: Any) -> int:
    """Quantidade de caracteres úteis (sem espaços excedentes e sem só pontuação).

    Usa o mesmo princípio de ``ururau.coleta.limpeza_texto_v81.texto_util_chars``
    mas sem depender dele para que o contrato possa ser importado em tests
    isolados sem trazer toda a coleta.
    """
    s = _normalizar(texto)
    if not s:
        return 0
    # tira pontuação solta e símbolos
    util = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    util = re.sub(r"\s+", " ", util).strip()
    return len(util)


def get_source_text(pauta: dict | None) -> str:
    """Retorna o texto da fonte usando a cadeia oficial de aliases.

    Retorna o primeiro alias com chars úteis ≥ ``min_valid()``. Se nenhum
    atinge o mínimo, retorna o **maior** texto entre os aliases (ou string
    vazia se nenhum tiver conteúdo). Isso garante que a aba Fonte sempre
    mostre o melhor texto disponível, sem que o Redigir libere automático.
    """
    if not pauta:
        return ""
    minimo = min_valid()
    melhor = ""
    melhor_chars = 0
    for alias in SOURCE_TEXT_ALIASES:
        bruto = pauta.get(alias)
        if not bruto:
            continue
        s = _normalizar(bruto)
        chars = texto_util_chars(s)
        if chars >= minimo:
            return s
        if chars > melhor_chars:
            melhor = s
            melhor_chars = chars
    return melhor


def source_text_len(pauta: dict | None) -> int:
    """Quantidade de caracteres úteis do texto canônico da pauta."""
    return texto_util_chars(get_source_text(pauta))


def source_text_is_valid(pauta: dict | None) -> bool:
    """True se o texto da fonte tem chars úteis ≥ ``MIN_VALID``."""
    return source_text_len(pauta) >= min_valid()


def _prioridade(origem: str) -> int:
    return ORIGEM_PRIORIDADE.get((origem or "").lower(), 0)


def set_source_text(pauta: dict, texto: Any, origem: str = "unknown",
                    *, force: bool = False) -> bool:
    """Grava texto da fonte no alias canônico (``cleaned_source_text``).

    Regras (Decisão §4.1):

    1. Nunca grava vazio sobre texto válido.
    2. Só substitui texto existente quando:
       * o novo texto é maior (em chars úteis); **ou**
       * o texto antigo está abaixo do mínimo e o novo é >= mínimo; **ou**
       * a origem nova tem prioridade maior **e** o novo texto não reduz os
         chars úteis em mais de 5%.
    3. ``force=True`` ignora a regra (usado por testes e por injeção manual
       explícita da aba Fonte).

    Atualiza simultaneamente o alias canônico e a aba ``fonte_aba_texto``.
    Não toca em ``texto_fonte_v134`` / ``texto_fonte_v105`` para preservar
    o histórico de cada extrator.

    Retorna True se o campo foi atualizado.
    """
    if pauta is None:
        return False
    novo = _normalizar(texto)
    novo_chars = texto_util_chars(novo)
    antigo = _normalizar(pauta.get(CANONICAL_ALIAS) or "")
    antigo_chars = texto_util_chars(antigo)
    minimo = min_valid()

    if force:
        pauta[CANONICAL_ALIAS] = novo
        pauta["_source_text_origem"] = origem
        return True

    # Regra 1: nunca apagar texto válido.
    if novo_chars == 0 and antigo_chars > 0:
        return False

    if antigo_chars == 0:
        pauta[CANONICAL_ALIAS] = novo
        pauta["_source_text_origem"] = origem
        return True

    # Regra 2a: texto maior sempre ganha.
    if novo_chars > antigo_chars:
        pauta[CANONICAL_ALIAS] = novo
        pauta["_source_text_origem"] = origem
        return True

    # Regra 2b: antigo abaixo do mínimo e novo >= mínimo.
    if antigo_chars < minimo <= novo_chars:
        pauta[CANONICAL_ALIAS] = novo
        pauta["_source_text_origem"] = origem
        return True

    # Regra 2c: origem mais confiável e perda de no máximo 5%.
    origem_antiga = str(pauta.get("_source_text_origem") or "").lower()
    if _prioridade(origem) > _prioridade(origem_antiga):
        if novo_chars >= int(antigo_chars * 0.95):
            pauta[CANONICAL_ALIAS] = novo
            pauta["_source_text_origem"] = origem
            return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Filtros editoriais (Fase F)
#
# Estes padrões marcam itens como "baixo score" para ir ao final da fila.
# Não removem nada do banco e não bloqueiam Aprovar/Reprovar — apenas
# classificam visualmente e bloqueiam Redigir automático.
# ─────────────────────────────────────────────────────────────────────────────

_PADROES_LIXO_TITULO: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bmelhores\s+gols\b", re.I),     "esporte_melhores_gols"),
    (re.compile(r"\bmelhores\s+momentos\b", re.I), "esporte_melhores_momentos"),
    (re.compile(r"\bmelhores\s+defesas\b", re.I),  "esporte_melhores_defesas"),
    (re.compile(r"\bgol(?:s)?\s*[:\-–—]", re.I),   "esporte_gols"),
    (re.compile(r"\bcharge(?:s)?\b", re.I),        "charge"),
    (re.compile(r"\bfrase\s+do\s+dia\b", re.I),    "frase_do_dia"),
    (re.compile(r"\benquete(?:s)?\b", re.I),       "enquete"),
    (re.compile(r"\bvídeo\b.*\b(curto|short|reels)\b", re.I), "video_curto"),
)

_PADROES_LIXO_LINK: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"/charge[s]?/", re.I),        "charge_url"),
    (re.compile(r"/melhores[-_]?gols", re.I),  "esporte_melhores_gols_url"),
    (re.compile(r"/shorts?/", re.I),           "video_curto_url"),
    (re.compile(r"/reels?/", re.I),            "video_curto_url"),
)


def _normalizar_titulo(t: Any) -> str:
    s = unicodedata.normalize("NFKD", str(t or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def eh_lixo_editorial(pauta: dict | None) -> tuple[bool, str]:
    """Classifica pauta como lixo editorial (vai para baixo score/quarentena).

    Retorna ``(True, motivo)`` se for lixo, ``(False, '')`` caso contrário.
    Os motivos são auditáveis e estáveis para teste.
    """
    if not pauta:
        return False, ""
    titulo = _normalizar_titulo(pauta.get("titulo_origem") or pauta.get("titulo") or "")
    link = str(pauta.get("link_origem") or pauta.get("url") or "").lower()
    if not titulo and not link:
        return True, "sem_titulo_e_link"
    for rx, motivo in _PADROES_LIXO_TITULO:
        if rx.search(titulo):
            return True, motivo
    for rx, motivo in _PADROES_LIXO_LINK:
        if rx.search(link):
            return True, motivo
    # Texto insuficiente também é lixo editorial para o Redigir.
    if source_text_len(pauta) < min_valid():
        # Mas só marca como lixo se NÃO houver indicação de matéria com corpo.
        # (Pautas recém-coletadas sem hidratar não são lixo; são "pendentes".)
        # Convenção: se o status já é baixo_score ou pendente, mantemos.
        st = str(pauta.get("status") or "").lower()
        if st in {"baixo_score", "quarentena"}:
            return True, st
    return False, ""


__all__ = [
    "CANONICAL_ALIAS",
    "SOURCE_TEXT_ALIASES",
    "ORIGEM_PRIORIDADE",
    "min_valid",
    "get_source_text",
    "set_source_text",
    "source_text_len",
    "source_text_is_valid",
    "eh_lixo_editorial",
    "texto_util_chars",
]
