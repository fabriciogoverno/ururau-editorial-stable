# -*- coding: utf-8 -*-
"""Scrapling Source Discovery v136.

Descobre links de matérias usando recursos centrais do Scrapling:
- Fetcher rápido para RSS/Atom/Sitemap/XML, sem navegador;
- Fetcher/Stealthy/Dynamic apenas para homepage/listagem HTML;
- CSS-like link extraction;
- diagnóstico por domínio;
- saída JSON/JSONL para workers/painel.

Regra central: XML/feed/sitemap não deve ir para browser nem esperar <body>.
"""
from __future__ import annotations

import json
import re
import time
import hashlib
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ururau.coleta.scrapling_engine_v136 import ScraplingEngineV136

ROOT = Path(__file__).resolve().parents[3]
SISTEMA = ROOT / "sistema"
OUT_DIR = SISTEMA / "relatorios_scrapling_v136"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ARTICLE_HINTS = re.compile(
    r"(?i)(/noticia/|/noticias/|/politica/|/policia/|/cidade/|/cidades/|/rio/|/estado/|"
    r"/brasil/|/mundo/|/economia/|/saude/|/educacao/|/esportes/|/entretenimento/|"
    r"/colunas/|/portal/|/20\d{2}/|\.ghtml|\.html|/\d{4,})"
)
NOISE_HINTS = re.compile(
    r"(?i)(/tag/|/tags/|/author/|/categoria/|/category/|/login|/cadastro|/newsletter|"
    r"/wp-admin|/wp-content|/feed/?$|/rss/?$|#|javascript:|mailto:|whatsapp:)"
)
XML_HINTS = re.compile(r"(?i)(feed/?$|rss/?$|atom\.xml|rss\.xml|sitemap|news-sitemap|\.xml(?:\?|$))")


@dataclass
class LinkCandidatoV136:
    url: str
    titulo: str = ""
    fonte: str = ""
    origem: str = ""
    dominio: str = ""
    score: int = 0
    metodo: str = "scrapling_discovery_v136"


@dataclass
class DiagnosticoFonteV136:
    fonte: str
    url_base: str
    dominio: str = ""
    started_at: str = ""
    ok: bool = False
    estrategia: str = ""
    tentativas: list[str] = field(default_factory=list)
    candidatos_total: int = 0
    candidatos: list[dict[str, Any]] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)


def _hash(url: str) -> str:
    return hashlib.sha1(str(url or "").encode("utf-8", errors="ignore")).hexdigest()


def _clean(txt: str) -> str:
    return re.sub(r"\s+", " ", str(txt or "")).strip()[:220]


def _is_xml_like_url(url: str) -> bool:
    return bool(XML_HINTS.search(str(url or "")))


def urls_candidatas_para_fonte(url_base: str) -> list[str]:
    engine = ScraplingEngineV136()
    base = engine.normalize_url(url_base)
    p = urlparse(base)
    root = f"{p.scheme}://{p.netloc}/"

    # Se a fonte já é feed/sitemap, testa ela primeiro e evita duplicações inúteis.
    paths = ["", "feed/", "rss/", "atom.xml", "rss.xml", "sitemap.xml", "sitemap_index.xml", "news-sitemap.xml"]
    out: list[str] = []
    seen: set[str] = set()
    for path in paths:
        u = base if not path else urljoin(root, path)
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out


def _same_domain(engine: ScraplingEngineV136, url: str, domain: str) -> bool:
    d = engine.domain(url)
    domain = (domain or "").lower().removeprefix("www.")
    return bool(d and domain and (d == domain or d.endswith("." + domain)))


def _extract_links(html: str, base_url: str, fonte: str, origem: str, metodo: str) -> list[LinkCandidatoV136]:
    engine = ScraplingEngineV136()
    soup_xml = BeautifulSoup(html or "", "xml")
    soup_html = BeautifulSoup(html or "", "html.parser")
    domain = engine.domain(base_url)
    seen: set[str] = set()
    out: list[LinkCandidatoV136] = []

    # RSS/Atom/Sitemap nodes.
    for item in soup_xml.find_all(["item", "entry", "url"]):
        loc = item.find("link") or item.find("loc")
        href = loc.get("href") if loc else ""
        href = href or (loc.get_text(" ", strip=True) if loc else "")
        if not href:
            continue
        u = engine.normalize_url(href, base_url)
        if not u or not _same_domain(engine, u, domain) or NOISE_HINTS.search(u):
            continue
        if not ARTICLE_HINTS.search(u):
            continue
        title_tag = item.find("title") or item.find("news:title")
        titulo = _clean(title_tag.get_text(" ", strip=True) if title_tag else "")
        k = _hash(u)
        if k in seen:
            continue
        seen.add(k)
        out.append(LinkCandidatoV136(url=u, titulo=titulo, fonte=fonte, origem=origem, dominio=domain, score=90 if titulo else 70, metodo=metodo))

    # HTML anchors.
    for a in soup_html.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        if not href or NOISE_HINTS.search(href):
            continue
        u = engine.normalize_url(href, base_url)
        if not u or not _same_domain(engine, u, domain):
            continue
        if not ARTICLE_HINTS.search(u):
            continue
        k = _hash(u)
        if k in seen:
            continue
        seen.add(k)
        titulo = _clean(a.get_text(" ", strip=True))
        score = 45
        if len(titulo) >= 25:
            score += 25
        if re.search(r"/20\d{2}/|/noticia/|/noticias/|\.ghtml|\.html", u):
            score += 20
        out.append(LinkCandidatoV136(url=u, titulo=titulo, fonte=fonte, origem=origem, dominio=domain, score=score, metodo=metodo))

    out.sort(key=lambda x: x.score, reverse=True)
    return out


def _fetch_fast_only(engine: ScraplingEngineV136, url: str):
    # Para XML/feed/sitemap, nunca usar browser, pois não há <body> e gera timeout.
    return engine.fetch(url, mode="fast")


def diagnosticar_fonte_scrapling_v136(fonte: str, url_base: str, limite: int = 40) -> DiagnosticoFonteV136:
    engine = ScraplingEngineV136()
    diag = DiagnosticoFonteV136(
        fonte=fonte or engine.domain(url_base),
        url_base=url_base,
        dominio=engine.domain(url_base),
        started_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    todos: list[LinkCandidatoV136] = []
    seen: set[str] = set()

    for u in urls_candidatas_para_fonte(url_base):
        diag.tentativas.append(u)
        try:
            if _is_xml_like_url(u):
                modes = ["fast"]
            else:
                modes = ["fast", "stealth", "dynamic"]

            for mode in modes:
                result = _fetch_fast_only(engine, u) if mode == "fast" else engine.fetch(u, mode=mode)
                if not result.ok:
                    diag.erros.append(f"{u} [{mode}]: {result.error}")
                    continue

                links = _extract_links(result.html or result.text, result.final_url or u, fonte, origem=u, metodo=result.method or mode)
                for link in links:
                    h = _hash(link.url)
                    if h not in seen:
                        seen.add(h)
                        todos.append(link)
                if links or _is_xml_like_url(u):
                    # Feed/sitemap já foi processado; não há razão para tentar browser.
                    break
        except Exception as exc:
            diag.erros.append(f"{u}: {type(exc).__name__}: {exc}")

        if len(todos) >= limite:
            break

    todos.sort(key=lambda x: x.score, reverse=True)
    diag.candidatos_total = len(todos)
    diag.candidatos = [asdict(x) for x in todos[:limite]]
    diag.ok = bool(diag.candidatos)
    diag.estrategia = "scrapling_discovery_v136" if diag.ok else "sem_links_uteis"
    return diag


def salvar_diagnostico_v136(diag: DiagnosticoFonteV136) -> dict[str, str]:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", diag.dominio or diag.fonte or "fonte")[:80]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = OUT_DIR / f"discovery_v136_{safe}_{stamp}.json"
    jsonl_path = OUT_DIR / f"discovery_v136_{safe}_{stamp}.jsonl"
    json_path.write_text(json.dumps(asdict(diag), ensure_ascii=False, indent=2), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in diag.candidatos:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return {"json": str(json_path), "jsonl": str(jsonl_path)}


__all__ = ["LinkCandidatoV136", "DiagnosticoFonteV136", "diagnosticar_fonte_scrapling_v136", "salvar_diagnostico_v136", "urls_candidatas_para_fonte"]
