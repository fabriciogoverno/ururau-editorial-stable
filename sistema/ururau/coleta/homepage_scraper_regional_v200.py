# -*- coding: utf-8 -*-
"""V200_50: Scraper de homepage para fontes regionais sem RSS valido.

Cada site tem uma funcao especifica que:
  1. Baixa o HTML da homepage (com User-Agent realista + Referer Google)
  2. Aplica regex/seletor especifico pra extrair URLs de materia
  3. Retorna lista de itens no formato compativel com feedparser
     [{titulo, link, published, ...}, ...]

Sites cobertos:
  - folha1.com.br: URLs tipo /<cat>/<ano>/<mes>/<id>-<slug>.html
  - campos24horas.com.br: URLs tipo /noticia/<slug>

Sites SPA (sem links na home, precisam Google News fallback):
  - nfnoticias.com.br
  - clickcampos.com.br
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)
PREFIX = "[HOMEPAGE_SCRAPER_V200]"

UA_REAL = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA_REAL,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
    "Referer": "https://www.google.com/",
}


def _baixar_html(url: str, timeout: int = 15) -> str:
    """Baixa HTML com User-Agent realista. Retorna "" em falha."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            logger.warning("%s HTTP %s em %s", PREFIX, r.status_code, url[:80])
            return ""
        return r.text or ""
    except Exception as e:
        logger.warning("%s baixar %s falhou: %s", PREFIX, url[:80], e)
        return ""


def _scraping_folha1(homepage_url: str = "https://www.folha1.com.br/") -> list[dict]:
    """Folha 1: URLs padrao /<cat>/<ano>/<mes>/<id>-<slug>.html"""
    html = _baixar_html(homepage_url)
    if not html:
        return []
    # Regex captura caminho relativo OU absoluto
    pad = re.compile(
        r'href="((?:https?://(?:www\.)?folha1\.com\.br)?'
        r'/(?:geral|politica|esportes|cidades|economia|brasil|mundo|'
        r'cultura|opiniao|esporte|saude|tecnologia|blogs|artigos)'
        r'/\d{4}/\d{2}/\d{6,}-[a-z0-9\-]+\.html)"',
        re.IGNORECASE,
    )
    vistos = set()
    itens = []
    for m in pad.finditer(html):
        href = m.group(1)
        if href.startswith("/"):
            href = "https://www.folha1.com.br" + href
        href = href.replace("//geral", "/geral")  # corrige duplos slashes
        if href in vistos:
            continue
        vistos.add(href)
        # Extrai titulo aproximado do slug
        try:
            slug = href.split("/")[-1].rsplit(".html", 1)[0]
            # remove id numerico no inicio
            titulo_partes = slug.split("-", 1)
            titulo = titulo_partes[1] if len(titulo_partes) > 1 else slug
            titulo = titulo.replace("-", " ").strip().capitalize()
        except Exception:
            titulo = href
        itens.append({
            "titulo": titulo,
            "link": href,
            "published": datetime.now().strftime("%a, %d %b %Y %H:%M:%S -0300"),
            "fonte": "Folha 1",
        })
        if len(itens) >= 30:
            break
    logger.info("%s folha1 extraiu %d itens", PREFIX, len(itens))
    return itens


def _scraping_campos24h(homepage_url: str = "https://campos24horas.com.br/") -> list[dict]:
    """Campos 24 Horas: URLs /noticia/<slug>"""
    html = _baixar_html(homepage_url)
    if not html:
        return []
    pad = re.compile(
        r'href="(?:\.\.)?((?:https?://(?:www\.)?campos24horas\.com\.br)?'
        r'/noticia/([a-z0-9\-]+))"',
        re.IGNORECASE,
    )
    vistos = set()
    itens = []
    for m in pad.finditer(html):
        href = m.group(1)
        slug = m.group(2)
        if href.startswith("/"):
            href = "https://campos24horas.com.br" + href
        elif not href.startswith("http"):
            href = "https://campos24horas.com.br/" + href.lstrip("/")
        if href in vistos:
            continue
        vistos.add(href)
        titulo = slug.replace("-", " ").strip().capitalize()
        itens.append({
            "titulo": titulo,
            "link": href,
            "published": datetime.now().strftime("%a, %d %b %Y %H:%M:%S -0300"),
            "fonte": "Campos 24 Horas",
        })
        if len(itens) >= 30:
            break
    logger.info("%s campos24horas extraiu %d itens", PREFIX, len(itens))
    return itens


# Tabela de scrapers por dominio
_SCRAPERS_POR_DOMINIO = {
    "folha1.com.br":          _scraping_folha1,
    "www.folha1.com.br":      _scraping_folha1,
    "campos24horas.com.br":   _scraping_campos24h,
    "www.campos24horas.com.br": _scraping_campos24h,
}


def scrape_fonte_regional(url_homepage: str) -> list[dict]:
    """Roteador principal: detecta dominio e chama o scraper apropriado.
    Retorna lista de itens no formato {titulo, link, published, fonte}.
    Lista vazia se dominio nao mapeado ou erro.
    """
    if not url_homepage:
        return []
    try:
        dom = urlparse(url_homepage).netloc.lower()
    except Exception:
        return []
    fn = _SCRAPERS_POR_DOMINIO.get(dom)
    if not fn:
        return []
    try:
        return fn(url_homepage)
    except Exception as e:
        logger.warning("%s scraper %s falhou: %s", PREFIX, dom, e)
        return []


__all__ = ["scrape_fonte_regional"]
