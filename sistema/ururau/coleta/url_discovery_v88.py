from __future__ import annotations
import os, re, time
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urljoin, urlparse, quote_plus
import feedparser, requests
from bs4 import BeautifulSoup
try:
    from ururau.config.settings import HEADERS, TIMEOUT_PADRAO
except Exception:
    HEADERS = {"User-Agent":"Mozilla/5.0"}; TIMEOUT_PADRAO = 10

@dataclass
class UrlCandidataV88:
    url: str
    titulo: str = ""
    fonte_nome: str = ""
    canal_forcado: str = ""
    origem: str = ""
    published: str = ""
    score_descoberta: int = 0
    metadata: dict = field(default_factory=dict)

def normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url: return ""
    url = re.sub(r"([?&])(utm_[^=&]+|fbclid|gclid|mc_cid|mc_eid)=[^&#]+", r"\1", url)
    return re.sub(r"[?&]+$", "", url)

def dominio(url: str) -> str:
    try:
        h = urlparse(url).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""

def fetch_text(url: str, timeout: int | None = None) -> tuple[str, str, int]:
    timeout = timeout or int(os.getenv("URURAU_V88_TIMEOUT_DISCOVERY", str(TIMEOUT_PADRAO or 10)))
    h = dict(HEADERS or {})
    h.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")
    h.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    r = requests.get(url, headers=h, timeout=timeout, allow_redirects=True)
    status = int(getattr(r, "status_code", 0) or 0)
    r.raise_for_status()
    return r.text, str(getattr(r, "url", url)), status

def _titulo_de_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    last = path.split("/")[-1] if path else dominio(url)
    last = re.sub(r"[-_]+", " ", last)
    last = re.sub(r"\.(ghtml|html|shtml|amp)$", "", last)
    return last[:120].strip().title()

def descobrir_por_pagina(fonte: dict, max_urls: int = 30) -> list[UrlCandidataV88]:
    saida, vistos = [], set()
    dominios_ok = {d.lower().replace("www.", "") for d in fonte.get("dominios", [])}
    for page_url in fonte.get("homepages", [])[: int(os.getenv("URURAU_V88_MAX_PAGES_POR_FONTE", "5"))]:
        try:
            html, final_url, status = fetch_text(page_url)
            soup = BeautifulSoup(html or "", "html.parser")
            for a in soup.find_all("a", href=True):
                href = normalizar_url(urljoin(final_url, a.get("href", "")))
                if not href or href in vistos: continue
                host = dominio(href)
                if dominios_ok and not any(host == d or host.endswith("." + d) for d in dominios_ok): continue
                if any(x in href.lower() for x in ("/tag/","/tags/","/autor/","/author/","/category/","/categoria/","/video/","/videos/","/podcast","#")): continue
                titulo = " ".join(a.get_text(" ", strip=True).split()) or _titulo_de_url(href)
                if len(titulo) < 18: continue
                vistos.add(href)
                saida.append(UrlCandidataV88(href, titulo[:180], fonte.get("nome", host), fonte.get("canal_preferencial", ""), "source_page_v88", "", int(fonte.get("prioridade", 50)), {"pagina_origem": page_url, "status_http": status}))
                if len(saida) >= max_urls: return saida
        except Exception as e:
            print(f"[v88][PAGE] {fonte.get('nome','fonte')} falhou em {page_url}: {str(e)[:150]}")
        time.sleep(float(os.getenv("URURAU_V88_SLEEP_DISCOVERY", "0.2")))
    return saida

def descobrir_por_sitemap(fonte: dict, max_urls: int = 40) -> list[UrlCandidataV88]:
    saida, vistos = [], set()
    max_depth = int(os.getenv("URURAU_V88_SITEMAP_DEPTH", "1"))
    fila = [(u, 0) for u in fonte.get("sitemaps", [])]
    dominios_ok = {d.lower().replace("www.", "") for d in fonte.get("dominios", [])}
    while fila and len(saida) < max_urls:
        sm_url, depth = fila.pop(0)
        try:
            xml, final_url, status = fetch_text(sm_url)
            soup = BeautifulSoup(xml or "", "xml")
            if depth < max_depth:
                for loc in soup.find_all("loc")[:80]:
                    loc_text = loc.get_text(strip=True)
                    if loc_text and ("sitemap" in loc_text.lower() or loc_text.endswith(".xml")):
                        fila.append((loc_text, depth + 1))
            for url_tag in soup.find_all("url")[:300]:
                loc = url_tag.find("loc")
                if not loc: continue
                href = normalizar_url(loc.get_text(strip=True))
                if not href or href in vistos: continue
                host = dominio(href)
                if dominios_ok and not any(host == d or host.endswith("." + d) for d in dominios_ok): continue
                lm = url_tag.find("lastmod")
                lastmod = lm.get_text(strip=True) if lm else ""
                vistos.add(href)
                saida.append(UrlCandidataV88(href, _titulo_de_url(href), fonte.get("nome", host), fonte.get("canal_preferencial", ""), "sitemap_v88", lastmod, int(fonte.get("prioridade", 50)) + 5, {"sitemap": sm_url, "lastmod": lastmod}))
                if len(saida) >= max_urls: break
        except Exception as e:
            print(f"[v88][SITEMAP] {fonte.get('nome','fonte')} falhou em {sm_url}: {str(e)[:150]}")
        time.sleep(float(os.getenv("URURAU_V88_SLEEP_DISCOVERY", "0.2")))
    return saida

def descobrir_por_google_news_terms(fonte: dict, max_por_termo: int = 5) -> list[UrlCandidataV88]:
    saida = []
    base = "https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    for termo in fonte.get("google_news_terms", [])[: int(os.getenv("URURAU_V88_MAX_TERMOS_POR_FONTE", "6"))]:
        try:
            # V200_3: feedparser.parse(url) faz fetch SEM timeout e trava o
            # ciclo. Roteia pelo HTTP resiliente com timeout duro.
            _url_gn = base.format(query=quote_plus(termo))
            try:
                from ururau.coleta.http_fetch_v109 import fetch_rss_v109 as _frss_v88
                _r88 = _frss_v88(_url_gn, timeout=12, max_retries=2,
                                 referer="https://news.google.com/")
                feed = feedparser.parse(_r88.text) if (_r88.ok and _r88.text) else feedparser.parse("")
            except Exception:
                feed = feedparser.parse("")
            for entry in feed.get("entries", [])[:max_por_termo]:
                titulo = (entry.get("title") or "").strip(); link = (entry.get("link") or "").strip()
                if " - " in titulo: titulo = titulo.rsplit(" - ", 1)[0].strip()
                if titulo and link:
                    saida.append(UrlCandidataV88(normalizar_url(link), titulo[:180], fonte.get("nome", "Fonte Premium"), fonte.get("canal_preferencial", ""), "google_news_domain_v88", str(entry.get("published") or ""), int(fonte.get("prioridade", 50)) + 8, {"termo": termo, "link_google_news": link}))
        except Exception as e:
            print(f"[v88][GNEWS-DOMAIN] {termo}: {str(e)[:150]}")
        time.sleep(float(os.getenv("URURAU_V88_SLEEP_DISCOVERY", "0.25")))
    return saida

def dedup_urls(candidatas: Iterable[UrlCandidataV88]) -> list[UrlCandidataV88]:
    best = {}
    for c in candidatas:
        u = normalizar_url(c.url)
        if not u: continue
        c.url = u
        old = best.get(u)
        if old is None or c.score_descoberta > old.score_descoberta:
            best[u] = c
    return list(best.values())
