# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, asdict
from urllib.parse import urlparse


@dataclass(frozen=True)
class PoliticaDominioFonte:
    dominio: str
    min_chars_redacao: int = 900
    aceita_rss_fallback_sem_integridade: bool = False
    exige_fonte_validada: bool = True
    prioridade_extracao: tuple[str, ...] = (
        "v104",
        "wordpress_rest",
        "json_ld",
        "html_density",
        "playwright_publico",
    )
    observacao: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["prioridade_extracao"] = list(self.prioridade_extracao)
        return d


POLITICAS: dict[str, PoliticaDominioFonte] = {
    "campos24horas.com.br": PoliticaDominioFonte(
        dominio="campos24horas.com.br",
        min_chars_redacao=900,
        aceita_rss_fallback_sem_integridade=False,
        prioridade_extracao=("adapter_campos24", "v104", "html_density", "playwright_publico"),
        observacao="Maior reincidente em NoneType/rss_fallback; nunca redigir sem FonteValidada.",
    ),
    "metropoles.com": PoliticaDominioFonte(
        dominio="metropoles.com",
        min_chars_redacao=900,
        aceita_rss_fallback_sem_integridade=False,
        prioridade_extracao=("v104", "json_ld", "html_density", "playwright_publico"),
        observacao="Reincidente em rss_fallback curto.",
    ),
    "g1.globo.com": PoliticaDominioFonte(
        dominio="g1.globo.com",
        min_chars_redacao=900,
        aceita_rss_fallback_sem_integridade=False,
        prioridade_extracao=("v104", "json_ld", "html_density"),
        observacao="Usar somente texto validado; evitar snippet de chamada.",
    ),
    "cnnbrasil.com.br": PoliticaDominioFonte(
        dominio="cnnbrasil.com.br",
        min_chars_redacao=900,
        aceita_rss_fallback_sem_integridade=False,
        prioridade_extracao=("wordpress_rest", "v104", "json_ld", "html_density"),
        observacao="WordPress REST costuma ser produtivo.",
    ),
    "jornaldesabado.com.br": PoliticaDominioFonte(
        dominio="jornaldesabado.com.br",
        min_chars_redacao=900,
        aceita_rss_fallback_sem_integridade=False,
        prioridade_extracao=("v104", "html_density", "playwright_publico"),
        observacao="Reincidente em 404/amp e rss_fallback.",
    ),
    "agenciabrasil.ebc.com.br": PoliticaDominioFonte(
        dominio="agenciabrasil.ebc.com.br",
        min_chars_redacao=900,
        aceita_rss_fallback_sem_integridade=False,
        prioridade_extracao=("v104", "json_ld", "html_density"),
        observacao="Fonte pública confiável; exigir corpo completo.",
    ),
}

POLITICA_PADRAO = PoliticaDominioFonte(dominio="*")


def normalizar_dominio(url_ou_host: str) -> str:
    raw = (url_ou_host or "").strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        host = urlparse(raw).netloc.lower()
    else:
        host = raw.split("/", 1)[0]
    return host[4:] if host.startswith("www.") else host


def politica_para_url(url_ou_host: str) -> PoliticaDominioFonte:
    dom = normalizar_dominio(url_ou_host)
    return POLITICAS.get(dom, POLITICA_PADRAO)


def aceita_rss_fallback_sem_integridade(url_ou_host: str) -> bool:
    return politica_para_url(url_ou_host).aceita_rss_fallback_sem_integridade


def min_chars_redacao(url_ou_host: str, padrao: int = 900) -> int:
    pol = politica_para_url(url_ou_host)
    return int(pol.min_chars_redacao or padrao)


def exportar_politicas() -> dict:
    return {k: v.to_dict() for k, v in POLITICAS.items()}
