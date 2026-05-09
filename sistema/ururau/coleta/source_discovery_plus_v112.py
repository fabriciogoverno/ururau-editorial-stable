"""
ururau/coleta/source_discovery_plus_v112.py

Ururau Plus v111.2 — descoberta e coleta complementar de fontes publicas.

Objetivo:
- reaproveitar tecnicas observadas em newspaper/newspaper4k:
  descoberta de feeds comuns, descoberta de links por categorias/homepages,
  heuristicas de URL jornalistica, metadados e imagens;
- reaproveitar o desenho do Meridian:
  cooldown por dominio, deduplicacao por URL normalizada, status e fail_reason;
- integrar com a cascata ja existente do google_news_scraper.ArticleExtractor.

Este modulo nao faz login, nao contorna paywall e nao acessa area privada.
Ele opera apenas sobre RSS, homepages, categorias e paginas publicas.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import aiohttp
try:
    import feedparser
except Exception:  # pragma: no cover
    feedparser = None  # type: ignore
from bs4 import BeautifulSoup

try:
    from ururau.coleta.source_policy_v114 import is_feed_url as _v114_is_feed_url, ordenar_fontes as _v114_ordenar_fontes
except Exception:  # pragma: no cover
    _v114_is_feed_url = None  # type: ignore
    _v114_ordenar_fontes = None  # type: ignore

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

try:
    from google_news_scraper.extractor import ArticleExtractor
    from google_news_scraper.models import ScraperConfig
except Exception:  # pragma: no cover
    ArticleExtractor = None  # type: ignore
    ScraperConfig = None  # type: ignore


GOOD_PATHS = {
    "story", "article", "feature", "featured", "news", "noticia", "noticias",
    "materia", "matéria", "politica", "policia", "cidade", "cidades",
    "estado", "rio-de-janeiro", "norte-fluminense", "campos", "macae",
    "sao-joao-da-barra", "economia", "geral", "brasil",
}
BAD_CHUNKS = {
    "careers", "contact", "about", "faq", "terms", "privacy", "advert",
    "preferences", "feedback", "account", "subscribe", "donate", "shop",
    "admin", "login", "cadastro", "newsletter", "tag", "tags", "author",
    "autores", "categoria", "category", "wp-content", "uploads", "assets",
    "politica-de-privacidade", "quem-somos", "fale-conosco",
}
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "fbclid", "gclid", "mc_cid", "mc_eid",
}
DATE_RE = re.compile(
    r"(?<=\W|/)((?:19|20)\d{2})[./\-_]?(?:[01]?\d)[./\-_]?(?:[0-3]?\d)?",
    re.I,
)
POSITIVE_TERMS = {
    "campos", "goytacazes", "norte fluminense", "macae", "macaé",
    "são joão da barra", "sao joao da barra", "porto do açu", "porto do acu",
    "alerj", "governo do rio", "governo rj", "rio de janeiro", "rj",
    "polícia", "policia", "operação", "operacao", "prefeitura", "tce-rj",
    "mprj", "tjrj", "tre-rj", "licitação", "licitacao", "fgts", "anvisa",
}
NEGATIVE_TERMS = {
    "bbb", "horóscopo", "horoscopo", "fofoca", "signo", "cupom",
    "promoção", "promocao", "receita", "loteria", "novela",
}


def _project_root() -> Path:
    candidates: list[Path] = []
    try:
        here = Path(__file__).resolve()
        candidates.extend(here.parents)
    except Exception:
        pass
    try:
        cwd = Path.cwd().resolve()
        candidates.extend([cwd, *cwd.parents])
    except Exception:
        pass
    for base in candidates:
        if (base / "ururau_monitor.py").exists() or (base / "fontes_rss.json").exists():
            return base
    return Path.cwd()


ROOT_DIR = _project_root()


def _env_bool(key: str, default: bool = False) -> bool:
    val = str(os.environ.get(key, "1" if default else "0")).strip().lower()
    return val in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(key: str, default: int) -> int:
    try:
        return int(str(os.environ.get(key, default)).strip())
    except Exception:
        return default


def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _load_json(name: str, default: Any) -> Any:
    candidates = [
        ROOT_DIR / name,
        ROOT_DIR / "config" / name,
        Path.cwd() / name,
        Path.cwd() / "config" / name,
    ]
    for path in candidates:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return default


def clean_url(url: str) -> str:
    """Remove tracking params e normaliza URL para deduplicacao."""
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return url

        query_items = []
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items():
            if key.lower() in TRACKING_PARAMS:
                continue
            for value in values:
                query_items.append((key, value))

        query = "&".join(
            f"{k}={v}" if v != "" else k
            for k, v in query_items
        )
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        netloc = parsed.netloc.lower()
        return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))
    except Exception:
        return url


def normalized_url_key(url: str) -> str:
    try:
        cleaned = clean_url(url)
        parsed = urlparse(cleaned)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = (parsed.path or "/").rstrip("/").lower()
        return f"{netloc}{path}"
    except Exception:
        return (url or "").lower().strip()


def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def looks_like_article_url(url: str) -> bool:
    """Heuristica inspirada em newspaper.urls.valid_url."""
    if not url or not url.startswith(("http://", "https://")):
        return False

    parsed = urlparse(url)
    path = parsed.path or ""
    if not parsed.netloc or path in {"", "/"}:
        return False

    lowered = url.lower()
    if any(ext in lowered for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip", ".mp4", ".mp3"]):
        return False

    chunks = [c for c in path.lower().split("/") if c]
    if any(c in BAD_CHUNKS for c in chunks[:3]):
        return False

    if DATE_RE.search(path):
        return True

    if any(good in chunks for good in GOOD_PATHS):
        return True

    # Slug longo com hifens costuma ser materia.
    last = chunks[-1] if chunks else ""
    if len(last) >= 25 and last.count("-") >= 3:
        return True

    return False


def common_feed_candidates(base_url: str) -> List[str]:
    parsed = urlparse(base_url if base_url.startswith("http") else f"https://{base_url}")
    root = f"{parsed.scheme}://{parsed.netloc}"
    path_base = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))
    suffixes = [
        "/feed/", "/feed", "/feeds", "/rss", "/rss.xml", "/atom.xml",
        "/index.xml", "/noticias/rss", "/noticias/feed/", "/category/noticias/feed/",
        "/?feed=rss2", "/?format=feed&type=rss",
    ]
    out = [urljoin(root, s) for s in suffixes]
    if parsed.path and parsed.path != "/":
        out.extend(urljoin(path_base + "/", s.lstrip("/")) for s in suffixes[:5])
    seen: set[str] = set()
    deduped = []
    for item in out:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


class DomainThrottle:
    """Cooldown simples por dominio, inspirado no DomainRateLimiter do Meridian."""

    def __init__(self, max_concurrent: int = 3, domain_cooldown_ms: int = 1800) -> None:
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.domain_cooldown_ms = domain_cooldown_ms
        self.last_access: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait(self, url: str) -> None:
        domain = extract_domain(url)
        if not domain:
            return
        async with self._lock:
            now = time.monotonic() * 1000
            last = self.last_access.get(domain, 0)
            delta = now - last
            if delta < self.domain_cooldown_ms:
                await asyncio.sleep((self.domain_cooldown_ms - delta) / 1000)
            self.last_access[domain] = time.monotonic() * 1000


async def fetch_text(session: aiohttp.ClientSession, url: str, throttle: DomainThrottle, timeout: int = 15) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        "Referer": "https://news.google.com/",
        "DNT": "1",
    }
    async with throttle.semaphore:
        await throttle.wait(url)
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True) as resp:
                ctype = (resp.headers.get("content-type") or "").lower()
                if resp.status >= 400:
                    return ""
                if not any(t in ctype for t in ["text", "html", "xml", "rss", "atom", "json", ""]):
                    return ""
                return await resp.text(errors="replace")
        except Exception:
            return ""


def parse_feed_items(feed_xml: str, fonte: Dict[str, Any], max_items: int) -> List[Dict[str, Any]]:
    """Parse RSS/Atom. Usa feedparser se existir; caso contrario, BS4 XML."""
    out: List[Dict[str, Any]] = []

    if feedparser is not None:
        parsed = feedparser.parse(feed_xml or "")
        entries = getattr(parsed, "entries", []) or []
        for entry in entries[: max_items * 3]:
            link = clean_url(str(getattr(entry, "link", "") or ""))
            if not looks_like_article_url(link):
                continue
            title = str(getattr(entry, "title", "") or "").strip()
            summary = str(getattr(entry, "summary", "") or getattr(entry, "description", "") or "").strip()
            published = ""
            if getattr(entry, "published_parsed", None):
                try:
                    published = _dt.datetime(*entry.published_parsed[:6], tzinfo=_dt.timezone.utc).isoformat()
                except Exception:
                    published = ""
            elif getattr(entry, "updated_parsed", None):
                try:
                    published = _dt.datetime(*entry.updated_parsed[:6], tzinfo=_dt.timezone.utc).isoformat()
                except Exception:
                    published = ""

            image = ""
            media_content = getattr(entry, "media_content", None) or []
            if media_content and isinstance(media_content, list):
                image = str(media_content[0].get("url", "") or "")
            if not image and getattr(entry, "links", None):
                for item in entry.links:
                    if "image" in str(item.get("type", "")).lower() and item.get("href"):
                        image = str(item.get("href"))
                        break

            out.append(_make_pauta(
                titulo=title,
                url=link,
                descricao=_strip_html(summary),
                fonte=fonte,
                data_publicacao=published,
                imagem=image,
                metodo="rss_feed_plus",
                texto="",
            ))
            if len(out) >= max_items:
                break
        return out

    # Fallback sem feedparser: suficiente para RSS/Atom simples.
    soup = BeautifulSoup(feed_xml or "", "xml")
    entries = soup.find_all(["item", "entry"])[: max_items * 3]
    for entry in entries:
        title_tag = entry.find("title")
        link_tag = entry.find("link")
        guid_tag = entry.find("guid")
        desc_tag = entry.find("description") or entry.find("summary") or entry.find("content")
        pub_tag = entry.find("pubDate") or entry.find("published") or entry.find("updated")

        link = ""
        if link_tag:
            link = link_tag.get("href") or link_tag.get_text(" ", strip=True)
        if not link and guid_tag:
            link = guid_tag.get_text(" ", strip=True)
        link = clean_url(link)
        if not looks_like_article_url(link):
            continue

        title = title_tag.get_text(" ", strip=True) if title_tag else link
        summary = desc_tag.get_text(" ", strip=True) if desc_tag else ""
        published = pub_tag.get_text(" ", strip=True) if pub_tag else ""

        out.append(_make_pauta(
            titulo=title,
            url=link,
            descricao=_strip_html(summary),
            fonte=fonte,
            data_publicacao=published,
            imagem="",
            metodo="rss_feed_plus_bs4",
            texto="",
        ))
        if len(out) >= max_items:
            break
    return out


def discover_article_links_from_html(html: str, base_url: str, max_items: int) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(["script", "style", "noscript", "svg", "form", "button"]):
        tag.decompose()

    links: List[Tuple[str, str, float]] = []
    for a in soup.find_all("a", href=True):
        href = clean_url(urljoin(base_url, str(a.get("href"))))
        if not looks_like_article_url(href):
            continue
        title = a.get_text(" ", strip=True)
        title_attr = str(a.get("title") or "").strip()
        if len(title_attr) > len(title):
            title = title_attr

        score = 0.0
        score += min(len(title), 160)
        path = urlparse(href).path.lower()
        if DATE_RE.search(path):
            score += 70
        if any(term in (title + " " + href).lower() for term in POSITIVE_TERMS):
            score += 100
        if any(term in (title + " " + href).lower() for term in NEGATIVE_TERMS):
            score -= 100
        if len(title) < 10:
            score -= 50

        links.append((href, title, score))

    best: Dict[str, Tuple[str, str, float]] = {}
    for href, title, score in links:
        key = normalized_url_key(href)
        if key not in best or score > best[key][2]:
            best[key] = (href, title, score)

    ordered = sorted(best.values(), key=lambda x: x[2], reverse=True)
    return [(href, title) for href, title, _ in ordered[:max_items]]


def _strip_html(value: str) -> str:
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def _make_pauta(
    *,
    titulo: str,
    url: str,
    descricao: str,
    fonte: Dict[str, Any],
    data_publicacao: str = "",
    imagem: str = "",
    metodo: str = "source_discovery_plus",
    texto: str = "",
) -> Dict[str, Any]:
    dominio = extract_domain(url)
    canal = fonte.get("canal_forcado") or fonte.get("canal_preferencial") or "Cidades"
    nome_fonte = fonte.get("nome") or dominio or "Fonte pública"
    regiao = fonte.get("regiao") or fonte.get("escopo") or ""
    peso = int(fonte.get("peso") or fonte.get("peso_fonte") or fonte.get("prioridade") or 0)
    score = 55 + min(20, max(0, peso))
    if any(t in f"{titulo} {descricao} {url}".lower() for t in POSITIVE_TERMS):
        score += 15
    if imagem:
        score += 5
    if texto and len(texto) >= 1200:
        score += 10

    pauta = {
        "id": f"plus_{abs(hash(normalized_url_key(url))) % 10_000_000}",
        "titulo": titulo or url,
        "descricao": descricao or "",
        "url": url,
        "dominio": dominio,
        "autor": "",
        "data_publicacao": data_publicacao,
        "imagem": imagem or "",
        "imagens": [imagem] if imagem else [],
        "texto_fonte": texto or "",
        "canal_sugerido": canal,
        "score": max(0, min(100, score)),
        "fonte_tipo": "source_discovery_plus",
        "termo_busca": nome_fonte,
        "metodo_extracao": metodo,
        "chars_fonte": len(texto or ""),
        "cidade": "Campos dos Goytacazes" if "campos" in str(regiao).lower() else "",
        "regiao": regiao,
        "coletado_em": _now_iso(),
        "status": "pendente",
        "titulo_origem": titulo or url,
        "link_origem": url,
        "resumo_origem": descricao or "",
        "fonte_nome": nome_fonte,
        "canal_forcado": canal,
        "cleaned_source_text": texto or "",
        "raw_source_text": texto or "",
        "original_source_text": texto or "",
        "dossie": (texto or "")[:14000],
        "source_discovery_plus": True,
    }
    if imagem:
        pauta["imagem_url"] = imagem
        pauta["imagem_status"] = "url_pendente"
        pauta["imagem_credito"] = "Reprodução"
    return pauta


def _iter_fontes_configuradas() -> List[Dict[str, Any]]:
    fontes: List[Dict[str, Any]] = []

    fontes_rss = _load_json("fontes_rss.json", [])
    if isinstance(fontes_rss, list):
        fontes.extend([f for f in fontes_rss if isinstance(f, dict) and f.get("ativo", True)])

    oficiais = _load_json("fontes_oficiais_prioritarias.json", {})
    if isinstance(oficiais, dict):
        fontes.extend([f for f in oficiais.get("fontes", []) if isinstance(f, dict) and f.get("ativo", False)])

    referencias = _load_json("portais_referencia_cobertura.json", {})
    if isinstance(referencias, dict) and _env_bool("URURAU_PLUS_USAR_PORTAIS_REFERENCIA", False):
        fontes.extend([f for f in referencias.get("portais", []) if isinstance(f, dict) and f.get("ativo", False)])

    especiais = _load_json("fontes_source_hunter_especiais_v114.json", {})
    if isinstance(especiais, dict):
        fontes.extend([f for f in especiais.get("fontes", []) if isinstance(f, dict) and f.get("ativo", False)])
    elif isinstance(especiais, list):
        fontes.extend([f for f in especiais if isinstance(f, dict) and f.get("ativo", False)])

    try:
        if _v114_ordenar_fontes is not None:
            # No Source Hunter as fontes especiais forçadas continuam ativas mesmo se estavam em quarentena no RSS rápido.
            for f in fontes:
                if f.get("forcar_source_hunter"):
                    f["source_health_v114"] = "especial_forcada"
            forcar = [f for f in fontes if f.get("forcar_source_hunter")]
            demais = [f for f in fontes if not f.get("forcar_source_hunter")]
            fontes = forcar + _v114_ordenar_fontes(demais, incluir_quarentena=False)
    except Exception:
        pass

    # Dedup por URL/RSS.
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for fonte in fontes:
        key = str(fonte.get("rss") or fonte.get("url") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(fonte)
    return out


async def _coletar_fonte(
    session: aiohttp.ClientSession,
    fonte: Dict[str, Any],
    throttle: DomainThrottle,
    max_por_fonte: int,
    timeout: int,
) -> List[Dict[str, Any]]:
    rss = str(fonte.get("rss") or "").strip()
    url = str(fonte.get("url") or "").strip()
    candidatos: List[str] = []
    for item in fonte.get("feed_candidates") or []:
        if item:
            candidatos.append(str(item).strip())
    if rss:
        candidatos.insert(0, rss)
    if url:
        # v111.4: se a URL cadastrada já é feed (/feed, rss.xml etc.), testa ela diretamente.
        if (_v114_is_feed_url(url) if _v114_is_feed_url else any(x in url.lower() for x in ("/feed", "/rss", "rss.xml", "feed.xml", "?feed="))):
            candidatos.insert(0, url)
            parsed = urlparse(url)
            homepage = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else ""
            if homepage:
                fonte = dict(fonte)
                fonte["homepage_url_v114"] = homepage
        if not candidatos:
            candidatos.extend(common_feed_candidates(url))

    # Dedup candidatos preservando ordem.
    vistos_cand: set[str] = set()
    candidatos = [c for c in candidatos if c and not (c in vistos_cand or vistos_cand.add(c))]

    # 1) RSS/feed direto ou descoberto.
    for feed_url in candidatos[:10]:
        xml = await fetch_text(session, feed_url, throttle, timeout=timeout)
        if not xml:
            continue
        pautas = parse_feed_items(xml, fonte, max_por_fonte)
        if pautas:
            for p in pautas:
                p["feed_origem"] = feed_url
            return pautas

    # 2) Fallback homepage/category link discovery.
    homepage_url = str(fonte.get("homepage_url_v114") or url or "").strip()
    if homepage_url:
        html = await fetch_text(session, homepage_url, throttle, timeout=timeout)
        if html:
            links = discover_article_links_from_html(html, homepage_url, max_por_fonte)
            return [
                _make_pauta(
                    titulo=title,
                    url=href,
                    descricao="",
                    fonte=fonte,
                    metodo="homepage_link_discovery_plus",
                )
                for href, title in links
            ]

    return []


async def hidratar_pautas_source_plus(
    pautas: List[Dict[str, Any]],
    min_chars: int = 1200,
    max_hidratar: int = 12,
) -> List[Dict[str, Any]]:
    if not pautas or ArticleExtractor is None or ScraperConfig is None:
        return pautas

    config = ScraperConfig(
        timeout=_env_int("URURAU_PLUS_FETCH_TIMEOUT", 15),
        concurrency=_env_int("URURAU_PLUS_HIDRATACAO_CONCORRENCIA", 3),
        min_article_chars=min_chars,
    )
    extractor = ArticleExtractor(config)
    semaphore = asyncio.Semaphore(_env_int("URURAU_PLUS_HIDRATACAO_CONCORRENCIA", 3))

    async def _one(pauta: Dict[str, Any]) -> Dict[str, Any]:
        texto = str(pauta.get("texto_fonte") or "")
        if len(texto) >= min_chars:
            return pauta
        url = str(pauta.get("url") or pauta.get("link_origem") or "")
        if not url:
            return pauta
        async with semaphore:
            try:
                res = await extractor.extract(url)
            except Exception as exc:
                pauta["status"] = "erro"
                pauta["fail_reason"] = f"source_plus_hydration_failed: {exc}"
                return pauta

        text = str(res.get("article_text") or "").strip()
        images = res.get("images") or []
        if text:
            pauta["texto_fonte"] = text
            pauta["cleaned_source_text"] = text
            pauta["raw_source_text"] = text
            pauta["original_source_text"] = text
            pauta["dossie"] = text[:14000]
            pauta["chars_fonte"] = len(text)
            pauta["metodo_extracao"] = res.get("method") or pauta.get("metodo_extracao")
            pauta["status"] = "pendente" if len(text) >= min_chars else "hidratacao"
            pauta["score"] = min(100, int(pauta.get("score") or 0) + (10 if len(text) >= min_chars else 4))
        if res.get("author") and not pauta.get("autor"):
            pauta["autor"] = res.get("author")
        if res.get("published_date") and not pauta.get("data_publicacao"):
            dt = res.get("published_date")
            pauta["data_publicacao"] = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
        if images:
            pauta["imagens"] = list(dict.fromkeys(list(pauta.get("imagens") or []) + images))
            if not pauta.get("imagem"):
                pauta["imagem"] = pauta["imagens"][0]
                pauta["imagem_url"] = pauta["imagem"]
                pauta["imagem_status"] = "url_pendente"
                pauta["imagem_credito"] = "Reprodução"
                pauta["score"] = min(100, int(pauta.get("score") or 0) + 5)
        return pauta

    selecionadas = pautas[:max_hidratar]
    hidratadas = await asyncio.gather(*[_one(p) for p in selecionadas])
    return hidratadas + pautas[max_hidratar:]


def deduplicar_pautas_source_plus(pautas: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}
    for pauta in pautas:
        url = str(pauta.get("url") or pauta.get("link_origem") or "")
        key = normalized_url_key(url)
        if not key:
            continue
        if key not in best or int(pauta.get("score") or 0) > int(best[key].get("score") or 0):
            best[key] = pauta
    return sorted(best.values(), key=lambda p: int(p.get("score") or 0), reverse=True)


async def coletar_source_hunter_plus_v112(
    max_fontes: Optional[int] = None,
    max_por_fonte: Optional[int] = None,
    max_total: Optional[int] = None,
    hidratar: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Coleta complementar em RSS, feeds descobertos e homepages publicas."""
    max_fontes = max_fontes or _env_int("URURAU_PLUS_MAX_FONTES", 18)
    max_por_fonte = max_por_fonte or _env_int("URURAU_PLUS_MAX_POR_FONTE", 3)
    max_total = max_total or _env_int("URURAU_PLUS_MAX_TOTAL", 20)
    min_chars = _env_int("URURAU_V111_GNEWS_MIN_CHARS_FONTE", 1200)
    timeout = _env_int("URURAU_PLUS_FETCH_TIMEOUT", 15)
    if hidratar is None:
        hidratar = _env_bool("URURAU_PLUS_HIDRATAR_FONTES", True)

    fontes = _iter_fontes_configuradas()[:max_fontes]
    if not fontes:
        return []

    throttle = DomainThrottle(
        max_concurrent=_env_int("URURAU_PLUS_MAX_CONCORRENCIA", 3),
        domain_cooldown_ms=_env_int("URURAU_PLUS_DOMAIN_COOLDOWN_MS", 1800),
    )
    async with aiohttp.ClientSession() as session:
        tasks = [
            _coletar_fonte(session, fonte, throttle, max_por_fonte=max_por_fonte, timeout=timeout)
            for fonte in fontes
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    pautas: List[Dict[str, Any]] = []
    for result in results:
        if isinstance(result, list):
            pautas.extend(result)

    pautas = deduplicar_pautas_source_plus(pautas)
    if hidratar:
        pautas = await hidratar_pautas_source_plus(
            pautas,
            min_chars=min_chars,
            max_hidratar=_env_int("URURAU_PLUS_MAX_HIDRATAR", 12),
        )
        pautas = deduplicar_pautas_source_plus(pautas)

    return pautas[:max_total]


def coletar_source_hunter_plus_v112_sync(**kwargs: Any) -> List[Dict[str, Any]]:
    """Wrapper sync para uso em monitor legado."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coletar_source_hunter_plus_v112(**kwargs))
    raise RuntimeError("Use await coletar_source_hunter_plus_v112() dentro de event loop ativo")
