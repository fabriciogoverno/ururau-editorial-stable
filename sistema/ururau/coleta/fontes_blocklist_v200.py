# -*- coding: utf-8 -*-
"""fontes_blocklist_v200 — bloqueia URLs/dominios em cooldown cronico.

Spec V200_2 (14/05/2026): durante a coleta observamos URLs que SEMPRE
falham e congelam a captacao por minutos a fio (DNS, 404, timeout
gigante). Em vez de tentar e fracassar, listamos aqui e o coletor
pula imediatamente.

Politica:
  - Apenas URLs/padroes COMPROVADAMENTE quebrados em prod (>=3 falhas).
  - Configuravel por ENV: URURAU_V200_BLOCKLIST_ATIVA=1 (default).
  - URURAU_V200_BLOCKLIST_EXTRA=<padrao1>;<padrao2> permite adicionar
    sem editar o codigo.

API:
  - eh_url_bloqueada(url) -> tuple[bool, str]
  - filtrar_urls_bloqueadas(urls) -> tuple[list_ok, list_bloqueadas]
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse


# Padroes literais (substring case-insensitive) que sempre falham
_PADROES_LITERAIS: tuple[str, ...] = (
    # Tira-Teima / Charge / Quizzes — paginas estaticas sem RSS
    "charge-do-aroeira",
    "cpi-do-banco-master",
    "frase-do-dia",
    # campos.rj.gov.br: o endpoint exibirNoticia.php esta 100% morto
    # (todos os id_noticia retornam 404). Log da Coleta 82-83: 188 retries.
    "campos.rj.gov.br/exibirnoticia.php",
    "campos.rj.gov.br/exibirnoticia",
)

# Regex (case-insensitive) — para padroes mais sofisticados
_PADROES_REGEX: tuple[re.Pattern, ...] = (
    # V200_2: band.com.br/esportes/... — a secao de esportes inteira
    # devolve 404 nas URLs vindas do feed (estrutura de URL mudou no
    # site). Log da Coleta 82-83: 76 retries em al-ittihad, mls-*,
    # new-england, bastidores, charlotte, melhores-momentos etc.
    re.compile(r"band\.com\.br/esportes/", re.I),
    # V200_2: subdominios 'm.' (mobile) — sempre dao DNS NameResolutionError
    # (m.www.band.com.br, m.campos.rj.gov.br, m.agendadopoder.com.br...).
    re.compile(r"https?://m\.[a-z0-9.-]+", re.I),
    # campos.rj.gov.br exibirNoticia em qualquer variante de querystring
    re.compile(r"campos\.rj\.gov\.br/(?:amp/)?exibirnoticia", re.I),
    # jogos especificos antigos (al-ittihad, etc)
    re.compile(r"/al-ittihad-(?:damac|hilal)-\d{4}", re.I),
)


def _env_bool(k: str, d: bool = True) -> bool:
    v = os.getenv(k)
    if v is None:
        return d
    return str(v).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _padroes_extras() -> list[str]:
    raw = os.getenv("URURAU_V200_BLOCKLIST_EXTRA", "") or ""
    return [p.strip() for p in raw.replace(",", ";").split(";") if p.strip()]


def eh_url_bloqueada(url: str) -> tuple[bool, str]:
    """Devolve (bloqueada?, motivo). Motivo vazio quando nao bloqueada."""
    if not _env_bool("URURAU_V200_BLOCKLIST_ATIVA", True):
        return False, ""
    if not url:
        return False, ""
    u = str(url).lower()
    for pat in _PADROES_LITERAIS:
        if pat.lower() in u:
            return True, f"literal:{pat}"
    for rx in _PADROES_REGEX:
        if rx.search(u):
            return True, f"regex:{rx.pattern[:60]}"
    for extra in _padroes_extras():
        if extra.lower() in u:
            return True, f"env_extra:{extra}"
    return False, ""


def filtrar_urls_bloqueadas(urls):
    """Recebe iteravel de URLs (strings ou dicts com 'url'/'rss').

    Retorna (urls_ok, urls_bloqueadas) preservando o tipo de entrada.
    """
    if not _env_bool("URURAU_V200_BLOCKLIST_ATIVA", True):
        return list(urls or []), []
    ok: list = []
    blk: list = []
    for item in urls or []:
        if isinstance(item, dict):
            u = item.get("rss") or item.get("url") or item.get("feed") or ""
        else:
            u = str(item or "")
        bloq, motivo = eh_url_bloqueada(u)
        if bloq:
            if isinstance(item, dict):
                item = dict(item)
                item["_blocklist_motivo_v200"] = motivo
            blk.append(item)
        else:
            ok.append(item)
    return ok, blk


# Dominios com timeout cronico (reduzir timeout para ~8s antes de skip)
DOMINIOS_TIMEOUT_REDUZIDO: dict[str, int] = {
    "www12.senado.leg.br": 8,
    "girorj.com.br": 12,
    "campos24h.com.br": 10,
}


def timeout_recomendado_para_dominio(url: str, default: int = 30) -> int:
    """Devolve timeout sugerido (segundos) para o dominio.

    Usa lista DOMINIOS_TIMEOUT_REDUZIDO; cai no default caso nao mapeado.
    """
    try:
        host = urlparse(str(url or "")).netloc.lower()
    except Exception:
        return default
    if not host:
        return default
    return DOMINIOS_TIMEOUT_REDUZIDO.get(host, default)


__all__ = [
    "eh_url_bloqueada",
    "filtrar_urls_bloqueadas",
    "timeout_recomendado_para_dominio",
    "DOMINIOS_TIMEOUT_REDUZIDO",
]
