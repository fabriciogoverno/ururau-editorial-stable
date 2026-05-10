"""
ururau/coleta/fonte_extractor_v104.py

Extrator definitivo v104 para fontes parceiras e públicas.

Objetivo: impedir que o robô redija matéria com snippet/RSS curto quando o
texto completo da notícia existe no site. O módulo tenta, em cascata:
1. URL final/canonical pública;
2. HTML direto com requests;
3. JSON-LD/Article/NewsArticle;
4. JSONs embutidos (__NEXT_DATA__, application/json e scripts com conteúdo);
5. WordPress REST API por slug e por busca de título;
6. densidade textual de containers de artigo;
7. pipeline v90 com adaptadores específicos e densidade textual;
8. Playwright público renderizado, quando habilitado;
9. somente por último avalia texto pré-existente, sem aprovar snippet curto.

Não faz login, não quebra paywall e não tenta acessar conteúdo restrito. Para
fontes parceiras, usa apenas endpoints públicos ou renderização pública do site.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse, quote

import requests
from bs4 import BeautifulSoup

try:
    from ururau.config.settings import HEADERS, TIMEOUT_PADRAO
except Exception:  # pragma: no cover
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    TIMEOUT_PADRAO = 14

from ururau.coleta.limpeza_texto_v81 import limpar_texto_fonte_v81, texto_util_chars
try:
    from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101, score_texto_artigo_v101
except Exception:  # pragma: no cover
    def limpar_texto_artigo_v101(texto: str, titulo: str = "", max_chars: int = 20000) -> str:
        return re.sub(r"\s+", " ", texto or "").strip()[:max_chars]
    def score_texto_artigo_v101(texto: str, titulo: str = "") -> int:
        return len(texto or "")


@dataclass
class ResultadoExtracaoV104:
    ok: bool = False
    url_original: str = ""
    url_final: str = ""
    titulo: str = ""
    texto: str = ""
    imagem: str = ""
    credito_foto: str = ""
    site_name: str = ""
    metodo: str = "failed"
    status: str = "failed"
    score: int = 0
    chars: int = 0
    util_chars: int = 0
    tentativas: list[str] = field(default_factory=list)
    erro: str = ""
    http_status: int = 0


_CACHE: dict[str, tuple[float, ResultadoExtracaoV104]] = {}
_CACHE_TTL = int(os.getenv("URURAU_V104_CACHE_TTL_SEG", "1800"))

_CONTENT_CLASS = re.compile(
    r"(article|artigo|materia|mat[eé]ria|noticia|not[ií]cia|post|entry|content|conteudo|texto|body|"
    r"reportagem|main|story|news|single|publication|page-content)", re.I,
)
_BLACKLIST_CLASS = re.compile(
    r"(ad|ads|advert|banner|menu|nav|header|footer|sidebar|related|share|social|"
    r"comment|newsletter|cookie|modal|promo|ultimas|mais-lidas|leia-tambem|tags|breadcrumb|pagination)", re.I,
)
_JUNK_LINE = re.compile(
    r"(?i)(pol[ií]tica de privacidade|termos de uso|fale conosco|quem somos|publicidade|continua ap[oó]s a publicidade|"
    r"leia tamb[eé]m|mais lidas|[uú]ltimas not[ií]cias|newsletter|cookies|compartilhe|copiar link|salvar para ler|"
    r"assine|fa[cç]a login|todos os direitos reservados|copyright|menu|buscar no site)"
)


def _env_bool(nome: str, padrao: bool = False) -> bool:
    raw = str(os.getenv(nome, "1" if padrao else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _min_chars() -> int:
    return _env_int("URURAU_V104_MIN_CHARS_ARTIGO", _env_int("URURAU_MIN_CHARS_TEXTO_FONTE", 900))


def _normalizar_linha(s: str) -> str:
    s = html_lib.unescape(str(s or "")).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _limpar_publico(texto: str, titulo: str = "") -> str:
    texto = limpar_texto_artigo_v101(texto or "", titulo=titulo or "", max_chars=22000)
    linhas: list[str] = []
    vistos: set[str] = set()
    for raw in re.split(r"\n+", texto):
        l = _normalizar_linha(raw)
        if len(l) < 28:
            continue
        if _JUNK_LINE.search(l) and len(l) < 260:
            continue
        # remove blocos típicos de lista de chamadas internas
        if l.count(" - ") >= 3 and len(l) > 120:
            continue
        key = re.sub(r"[^a-z0-9áéíóúãõâêôç]+", "", l.lower())[:220]
        if key in vistos:
            continue
        vistos.add(key)
        linhas.append(l)
    out = "\n\n".join(linhas)
    out = limpar_texto_fonte_v81(out)
    return out.strip()


def _session() -> requests.Session:
    s = requests.Session()
    h = dict(HEADERS or {})
    h.setdefault("User-Agent", (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ))
    h.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    h.setdefault("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8")
    h.setdefault("Cache-Control", "no-cache")
    h.setdefault("Pragma", "no-cache")
    s.headers.update(h)
    return s


def _fetch(url: str, timeout: int | None = None) -> tuple[str, str, int, str]:
    timeout = timeout or _env_int("URURAU_V104_TIMEOUT", int(TIMEOUT_PADRAO or 14))

    # v110: o extrator principal também passa pelo HTTP resiliente da v109
    # (UA rotativo, retry/backoff, pacing e cooldown 429).
    if _env_bool("URURAU_V109_HTTP_FETCH", True):
        try:
            from ururau.coleta.http_fetch_v109 import fetch_text_v109
            fr = fetch_text_v109(
                url,
                base_headers=dict(HEADERS or {}),
                timeout=timeout,
                max_retries=_env_int("URURAU_V109_HTTP_MAX_RETRIES", 3),
                backoff=float(str(os.getenv("URURAU_V109_HTTP_BACKOFF", "1.7") or "1.7").replace(",", ".")),
                accept="html",
            )
            if not fr.ok:
                raise RuntimeError(fr.erro or "falha_http_v109")
            return fr.text or "", fr.url_final or url, int(fr.status_code or 0), "text/html"
        except Exception as e:
            if _env_bool("URURAU_V110_HTTP_FALLBACK_LEGADO", True):
                print(f"[V110][HTTP] fallback legado para {url[:80]}: {e}")
            else:
                raise

    r = _session().get(url, timeout=timeout, allow_redirects=True)
    status = int(getattr(r, "status_code", 0) or 0)
    r.raise_for_status()
    if not r.encoding or str(r.encoding).lower() in {"iso-8859-1", "ascii"}:
        try:
            r.encoding = r.apparent_encoding or "utf-8"
        except Exception:
            pass
    return r.text or "", str(r.url or url), status, r.headers.get("content-type", "")


def _canonical(soup: BeautifulSoup, base_url: str) -> str:
    for sel, attr in [
        ("link[rel='canonical']", "href"),
        ("meta[property='og:url']", "content"),
        ("meta[name='twitter:url']", "content"),
    ]:
        el = soup.select_one(sel)
        if el and el.get(attr):
            val = urljoin(base_url, str(el.get(attr)).strip())
            if val.startswith("http"):
                return val
    return ""


def _meta(soup: BeautifulSoup, base_url: str) -> dict[str, str]:
    def m(*names: str) -> str:
        for name in names:
            el = soup.find("meta", property=name) or soup.find("meta", attrs={"name": name})
            if el and el.get("content"):
                return _normalizar_linha(el.get("content", ""))
        return ""
    titulo = ""
    h1 = soup.find("h1")
    if h1:
        titulo = h1.get_text(" ", strip=True)
    titulo = titulo or m("og:title", "twitter:title")
    if not titulo and soup.title:
        titulo = soup.title.get_text(" ", strip=True)
    img = m("og:image", "og:image:url", "twitter:image", "twitter:image:src")
    if img:
        img = urljoin(base_url, img)
    return {
        "titulo": _normalizar_linha(titulo),
        "descricao": m("og:description", "twitter:description", "description"),
        "imagem": img,
        "site_name": m("og:site_name", "application-name"),
        "canonical": _canonical(soup, base_url),
    }


def _json_iter(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _json_iter(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _json_iter(it)


def _clean_html_fragment(v: str) -> str:
    if "<" in v and ">" in v:
        return BeautifulSoup(v, "html.parser").get_text("\n", strip=True)
    return v


def _texto_jsonld(soup: BeautifulSoup, titulo_ref: str = "") -> tuple[str, str]:
    titulos: list[str] = []
    textos: list[str] = []
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=False) or ""
        if not raw.strip():
            continue
        # alguns sites publicam vários blocos; tentamos JSON normal e fallback por objetos.
        blobs = [raw]
        if raw.strip().startswith("{") is False and "{" in raw:
            blobs = re.findall(r"\{.*?\}", raw, flags=re.S)[:20] or [raw]
        for blob in blobs:
            try:
                data = json.loads(blob)
            except Exception:
                try:
                    data = json.loads(re.sub(r"\s+", " ", blob).strip())
                except Exception:
                    continue
            for item in _json_iter(data):
                if not isinstance(item, dict):
                    continue
                tipo = item.get("@type") or item.get("type") or ""
                tipo_s = " ".join(tipo) if isinstance(tipo, list) else str(tipo)
                if any(x.lower() in tipo_s.lower() for x in ["NewsArticle", "Article", "ReportageNewsArticle", "BlogPosting"]):
                    headline = item.get("headline") or item.get("name") or ""
                    if headline:
                        titulos.append(str(headline))
                    for key in ("articleBody", "text", "description"):
                        val = item.get(key)
                        if isinstance(val, str) and len(val) > 220:
                            textos.append(_clean_html_fragment(val))
                    # Alguns JSON-LD colocam parágrafos em hasPart.
                    hp = item.get("hasPart") or item.get("articleSection")
                    if isinstance(hp, list):
                        for part in hp:
                            if isinstance(part, dict):
                                val = part.get("text") or part.get("articleBody")
                                if isinstance(val, str) and len(val) > 120:
                                    textos.append(_clean_html_fragment(val))
    return _normalizar_linha(titulos[0] if titulos else titulo_ref), _limpar_publico("\n\n".join(textos), titulo_ref)


def _texto_json_embutido(soup: BeautifulSoup, titulo_ref: str = "") -> str:
    textos: list[str] = []
    scripts = []
    nd = soup.find("script", id="__NEXT_DATA__")
    if nd:
        scripts.append(nd)
    for sc in soup.find_all("script", attrs={"type": re.compile("application/json", re.I)}):
        if sc not in scripts:
            scripts.append(sc)
    # Também vasculha scripts comuns que contêm articleBody/content em string JSON.
    for sc in soup.find_all("script")[:35]:
        txt = sc.string or sc.get_text(" ", strip=False) or ""
        if len(txt) > 600 and any(k in txt for k in ("articleBody", "content", "body", "paragraph")) and sc not in scripts:
            scripts.append(sc)
    for sc in scripts[:12]:
        raw = sc.string or sc.get_text(" ", strip=False) or ""
        if len(raw) < 300:
            continue
        data = None
        try:
            data = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, flags=re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                except Exception:
                    data = None
        if data is None:
            continue
        for item in _json_iter(data):
            if isinstance(item, dict):
                for k, v in item.items():
                    lk = str(k).lower()
                    if isinstance(v, str) and len(v) > 140 and lk in {
                        "text", "texto", "body", "articlebody", "content", "conteudo",
                        "description", "paragraph", "html", "materia", "noticia", "post_content",
                    }:
                        textos.append(_clean_html_fragment(v))
                    elif isinstance(v, list) and lk in {"paragraphs", "paragrafos", "blocks", "content"}:
                        for x in v:
                            if isinstance(x, str) and len(x) > 80:
                                textos.append(_clean_html_fragment(x))
                            elif isinstance(x, dict):
                                val = x.get("text") or x.get("content") or x.get("html")
                                if isinstance(val, str) and len(val) > 80:
                                    textos.append(_clean_html_fragment(val))
            elif isinstance(item, str) and len(item) > 240:
                textos.append(_clean_html_fragment(item))
    return _limpar_publico("\n\n".join(textos), titulo_ref)


def _remover_ruido(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", "form", "button", "nav", "header", "footer", "aside"]):
        tag.decompose()
    for el in list(soup.find_all(True)):
        attrs = " ".join(str(el.get(a, "")) for a in ["id", "class", "role", "aria-label"])
        if _BLACKLIST_CLASS.search(attrs or ""):
            text_len = len(el.get_text(" ", strip=True) or "")
            if text_len < 700 or not _CONTENT_CLASS.search(attrs or ""):
                try:
                    el.decompose()
                except Exception:
                    pass


def _score_container(el: Any, titulo_ref: str = "") -> tuple[int, str]:
    textos: list[str] = []
    for node in el.find_all(["p", "h2", "h3", "blockquote", "li"], recursive=True):
        txt = _normalizar_linha(node.get_text(" ", strip=True))
        if len(txt) >= 35:
            textos.append(txt)
    texto = _limpar_publico("\n\n".join(textos), titulo_ref)
    chars = texto_util_chars(texto)
    attrs = " ".join(str(el.get(a, "")) for a in ["id", "class", "role", "itemprop"])
    bonus = 0
    if getattr(el, "name", "") == "article":
        bonus += 700
    if getattr(el, "name", "") == "main":
        bonus += 300
    if _CONTENT_CLASS.search(attrs or ""):
        bonus += 500
    if "articleBody" in attrs:
        bonus += 600
    # premia parágrafos jornalísticos, penaliza lista de links.
    paragrafos = len([p for p in textos if len(p) > 70])
    lista_links = texto.count(" - ")
    score = chars + paragrafos * 90 + bonus - min(lista_links * 120, 700)
    try:
        score += max(score_texto_artigo_v101(texto, titulo=titulo_ref), 0) // 4
    except Exception:
        pass
    return score, texto


def _texto_por_densidade(soup: BeautifulSoup, titulo_ref: str = "") -> str:
    _remover_ruido(soup)
    seletores = [
        "article", "main", "[role='main']", "div[itemprop='articleBody']", "section[itemprop='articleBody']",
        ".entry-content", ".post-content", ".article-content", ".article-body", ".materia", ".materia-conteudo",
        ".noticia", ".noticia-conteudo", ".texto", ".texto-noticia", ".content", ".conteudo",
        "div[class*='article']", "div[class*='materia']", "div[class*='noticia']", "div[class*='content']",
        "div[class*='texto']", "div[class*='body']", "section[class*='content']", "section[class*='article']",
    ]
    candidatos: list[tuple[int, str]] = []
    vistos: set[int] = set()
    for sel in seletores:
        try:
            elems = soup.select(sel)[:30]
        except Exception:
            elems = []
        for el in elems:
            if id(el) in vistos:
                continue
            vistos.add(id(el))
            candidatos.append(_score_container(el, titulo_ref))
    body = soup.find("body")
    if body:
        candidatos.append(_score_container(body, titulo_ref))
    candidatos.sort(key=lambda x: x[0], reverse=True)
    return candidatos[0][1] if candidatos else ""


def _credito_foto(soup: BeautifulSoup) -> str:
    pads = [
        r"(?:Foto|Cr[eé]dito|Imagem|Reprodu[cç][aã]o|Copyright)\s*[:\-]\s*([^\n\r|/]{2,80})",
        r"(?:por|by)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç .'-]{2,70})",
    ]
    zonas: list[str] = []
    for sel in ["figcaption", ".caption", ".credito", ".credit", "[class*='credito']", "[class*='credit']"]:
        for el in soup.select(sel)[:10]:
            zonas.append(el.get_text(" ", strip=True))
    for img in soup.find_all("img")[:12]:
        for attr in ("alt", "title", "data-credit", "credit"):
            if img.get(attr):
                zonas.append(str(img.get(attr)))
    for z in zonas:
        z = _normalizar_linha(z)
        for pad in pads:
            m = re.search(pad, z, flags=re.I)
            if m:
                val = _normalizar_linha(m.group(1)).strip(" .,-")
                if 2 <= len(val) <= 60 and not _JUNK_LINE.search(val):
                    return val
    return ""


def _from_html(html: str, url: str, titulo_ref: str = "", metodo_base: str = "requests") -> ResultadoExtracaoV104:
    soup = BeautifulSoup(html or "", "html.parser")
    meta = _meta(soup, url)
    titulo_ref = titulo_ref or meta.get("titulo", "")
    titulo_json, texto_jsonld = _texto_jsonld(soup, titulo_ref)
    texto_emb = _texto_json_embutido(soup, titulo_ref)
    texto_dens = _texto_por_densidade(soup, titulo_ref)
    candidatos = [
        ("jsonld_articleBody", texto_jsonld),
        ("embedded_json", texto_emb),
        ("html_density", texto_dens),
    ]
    candidatos.sort(key=lambda it: (texto_util_chars(it[1]), len(it[1])), reverse=True)
    metodo, texto = candidatos[0]
    texto = _limpar_publico(texto, titulo_ref)
    util = texto_util_chars(texto)
    status = "ok" if util >= max(1200, _min_chars()) else ("short_usable" if util >= _min_chars() else "failed")
    score = 96 if util >= 2200 else 88 if util >= 1400 else 78 if util >= _min_chars() else 10
    return ResultadoExtracaoV104(
        ok=util >= _min_chars(),
        url_original=url,
        url_final=meta.get("canonical") or url,
        titulo=titulo_json or meta.get("titulo", "") or titulo_ref,
        texto=texto[:16000],
        imagem=meta.get("imagem", ""),
        credito_foto=_credito_foto(soup),
        site_name=meta.get("site_name", ""),
        metodo=f"v104_{metodo_base}:{metodo}",
        status=status,
        score=score,
        chars=len(texto),
        util_chars=util,
    )


def _url_variantes(url: str) -> list[str]:
    if not url:
        return []
    out: list[str] = []
    def add(u: str):
        if u and u.startswith("http") and u not in out:
            out.append(u)
    add(url)
    p = urlparse(url)
    clean = urlunparse(p._replace(query="", fragment=""))
    add(clean)
    path = p.path.rstrip("/")
    if path:
        add(urlunparse(p._replace(path=path + "/amp/", query="", fragment="")))
        add(urlunparse(p._replace(path="/amp" + path, query="", fragment="")))
        add(urlunparse(p._replace(query="output=amp", fragment="")))
    if p.netloc and not p.netloc.startswith("m."):
        add(urlunparse(p._replace(netloc="m." + p.netloc, fragment="")))
    return out[:_env_int("URURAU_V104_MAX_VARIANTES", 8)]


def _slug_from_url(url: str) -> str:
    p = urlparse(url)
    parts = [x for x in p.path.split("/") if x]
    if not parts:
        return ""
    slug = parts[-1]
    slug = re.sub(r"\.(html?|php|aspx?)$", "", slug, flags=re.I)
    return slug.strip()


def _wp_rest_candidates(url: str, titulo_ref: str = "") -> list[str]:
    p = urlparse(url)
    if not p.netloc:
        return []
    base = f"{p.scheme}://{p.netloc}"
    slug = _slug_from_url(url)
    qs_title = quote(titulo_ref[:120]) if titulo_ref else ""
    urls: list[str] = []
    for typ in ["posts", "pages"]:
        if slug:
            urls.append(f"{base}/wp-json/wp/v2/{typ}?slug={quote(slug)}&_embed=1")
        if qs_title:
            urls.append(f"{base}/wp-json/wp/v2/{typ}?search={qs_title}&per_page=5&_embed=1")
    return urls[:6]


def _text_from_wp_item(item: dict, titulo_ref: str = "") -> tuple[str, str, str, str]:
    title = ""
    try:
        title = BeautifulSoup(str((item.get("title") or {}).get("rendered") or ""), "html.parser").get_text(" ", strip=True)
    except Exception:
        title = ""
    parts: list[str] = []
    for key in ["content", "excerpt"]:
        val = item.get(key)
        if isinstance(val, dict):
            raw = str(val.get("rendered") or "")
        else:
            raw = str(val or "")
        if raw:
            parts.append(BeautifulSoup(raw, "html.parser").get_text("\n", strip=True))
    texto = _limpar_publico("\n\n".join(parts), titulo_ref or title)
    img = ""
    cred = ""
    try:
        emb = item.get("_embedded") or {}
        media = (emb.get("wp:featuredmedia") or [])[0]
        img = media.get("source_url") or media.get("media_details", {}).get("sizes", {}).get("full", {}).get("source_url") or ""
        cred_raw = media.get("caption", {}).get("rendered") or media.get("alt_text") or ""
        cred = BeautifulSoup(str(cred_raw), "html.parser").get_text(" ", strip=True)
        m = re.search(r"(?:Foto|Cr[eé]dito|Imagem|Reprodu[cç][aã]o)\s*[:\-]\s*([^|/\n]{2,80})", cred, flags=re.I)
        if m:
            cred = _normalizar_linha(m.group(1)).strip(" .,-")
    except Exception:
        pass
    return title, texto, img, cred


def _extrair_wordpress(url: str, titulo_ref: str = "") -> ResultadoExtracaoV104:
    melhor = ResultadoExtracaoV104(url_original=url, url_final=url, metodo="v104_wordpress:failed")
    tentativas = []
    for api_url in _wp_rest_candidates(url, titulo_ref):
        tentativas.append(api_url)
        try:
            r = _session().get(api_url, timeout=_env_int("URURAU_V104_TIMEOUT_WP", 12))
            if r.status_code not in (200,):
                continue
            data = r.json()
            itens = data if isinstance(data, list) else [data]
            for item in itens:
                if not isinstance(item, dict):
                    continue
                title, texto, img, cred = _text_from_wp_item(item, titulo_ref)
                util = texto_util_chars(texto)
                if util > melhor.util_chars:
                    melhor = ResultadoExtracaoV104(
                        ok=util >= _min_chars(),
                        url_original=url,
                        url_final=str(item.get("link") or url),
                        titulo=title or titulo_ref,
                        texto=texto[:16000],
                        imagem=img,
                        credito_foto=cred,
                        site_name=urlparse(url).netloc,
                        metodo="v104_wordpress_rest",
                        status="ok" if util >= max(1200, _min_chars()) else "short_usable" if util >= _min_chars() else "failed",
                        score=94 if util >= 1600 else 82 if util >= _min_chars() else 10,
                        chars=len(texto),
                        util_chars=util,
                        tentativas=list(tentativas),
                    )
        except Exception as e:
            melhor.erro = str(e)
            continue
    melhor.tentativas = list(tentativas)
    return melhor


def _extrair_playwright(url: str, titulo_ref: str = "") -> ResultadoExtracaoV104:
    if not _env_bool("URURAU_V104_PLAYWRIGHT_SE_FALHAR", True):
        return ResultadoExtracaoV104(url_original=url, url_final=url, metodo="v104_playwright:desativado", erro="playwright_desativado")
    try:
        from playwright.sync_api import sync_playwright
        timeout_ms = _env_int("URURAU_V104_PLAYWRIGHT_TIMEOUT_MS", 18000)
        wait_ms = _env_int("URURAU_V104_PLAYWRIGHT_WAIT_MS", 1800)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(locale="pt-BR", user_agent=(HEADERS or {}).get("User-Agent"))
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                # dá tempo para JS público montar o article.
                page.wait_for_timeout(wait_ms)
            except Exception:
                pass
            html = page.content()
            final = page.url
            browser.close()
        res = _from_html(html, final or url, titulo_ref, metodo_base="playwright_public")
        res.url_original = url
        res.url_final = final or url
        res.tentativas.append("playwright_public")
        return res
    except Exception as e:
        return ResultadoExtracaoV104(url_original=url, url_final=url, metodo="v104_playwright:error", erro=str(e))



def _extrair_kimi_v110(url: str, titulo_ref: str = "") -> ResultadoExtracaoV104:
    """v110: ArticleExtractor do pacote Kimi como fallback estruturado premium."""
    try:
        from ururau.coleta.kimi_bridge_v110 import extrair_artigo_kimi_v110
        r = extrair_artigo_kimi_v110(url, titulo=titulo_ref)
        texto = (getattr(r, "texto", "") or "").strip()
        util = texto_util_chars(texto)
        return ResultadoExtracaoV104(
            ok=bool(getattr(r, "ok", False)) and util >= _min_chars(),
            url_original=url,
            url_final=getattr(r, "url_final", "") or url,
            titulo=getattr(r, "titulo", "") or titulo_ref,
            texto=texto[:16000],
            imagem=getattr(r, "imagem", "") or "",
            credito_foto="",
            site_name=getattr(r, "dominio", "") or urlparse(getattr(r, "url_final", "") or url).netloc,
            metodo=getattr(r, "metodo", "v110_kimi_article_extractor"),
            status="ok" if util >= max(1200, _min_chars()) else "short_usable" if util >= _min_chars() else "failed",
            score=94 if util >= 1800 else 86 if util >= _min_chars() else 12,
            chars=len(texto),
            util_chars=util,
            tentativas=["v110_kimi_article_extractor"],
            erro=getattr(r, "erro", "") or "",
        )
    except Exception as e:
        return ResultadoExtracaoV104(url_original=url, url_final=url, metodo="v110_kimi_error", erro=str(e))

def _extrair_trafilatura_v108(url: str, titulo_ref: str = "") -> ResultadoExtracaoV104:
    """Fallback v108 com trafilatura/readability preservando parágrafos."""
    try:
        from ururau.coleta.trafilatura_fallback_v108 import extrair_trafilatura_v108
        r = extrair_trafilatura_v108(url, titulo=titulo_ref)
        texto = (getattr(r, "texto", "") or "").strip()
        util = texto_util_chars(texto)
        return ResultadoExtracaoV104(
            ok=bool(getattr(r, "ok", False)) and util >= _min_chars(),
            url_original=url,
            url_final=getattr(r, "url_final", "") or url,
            titulo=getattr(r, "titulo", "") or titulo_ref,
            texto=texto[:16000],
            imagem=getattr(r, "imagem", "") or "",
            credito_foto=getattr(r, "credito_foto", "") or "",
            site_name=urlparse(getattr(r, "url_final", "") or url).netloc,
            metodo=getattr(r, "metodo", "v108_trafilatura"),
            status="ok" if util >= max(1200, _min_chars()) else "short_usable" if util >= _min_chars() else "failed",
            score=90 if util >= 1600 else 82 if util >= _min_chars() else 10,
            chars=len(texto),
            util_chars=util,
            tentativas=["v108_trafilatura_readability"],
            erro=getattr(r, "erro", "") or "",
        )
    except Exception as e:
        return ResultadoExtracaoV104(url_original=url, url_final=url, metodo="v108_trafilatura_error", erro=str(e))


def _extrair_pipeline_v90(url: str, titulo_ref: str = "") -> ResultadoExtracaoV104:
    """Fallback v90: adaptadores específicos, JSON-LD, NEXT_DATA, WP, AMP e densidade."""
    if not _env_bool("URURAU_V104_USAR_V90_PIPELINE", True):
        return ResultadoExtracaoV104(url_original=url, url_final=url, metodo="v90_pipeline:desativado", erro="v90_desativado")
    try:
        from ururau.coleta.extract_pipeline_v90 import extrair_materia_v90
        r = extrair_materia_v90(url, titulo_ref or "", tipo_site="generic")
        texto = _limpar_publico(str((r or {}).get("texto") or ""), titulo_ref)
        util = texto_util_chars(texto)
        metodo = str((r or {}).get("metodo") or "v90_pipeline")
        tent = (r or {}).get("tentativas") or []
        return ResultadoExtracaoV104(
            ok=bool((r or {}).get("aceita")) and util >= _min_chars(),
            url_original=url,
            url_final=str((r or {}).get("url_final") or url),
            titulo=str((r or {}).get("titulo") or titulo_ref),
            texto=texto[:16000],
            imagem=str((r or {}).get("imagem") or ""),
            credito_foto=str((r or {}).get("credito") or ""),
            site_name=urlparse(str((r or {}).get("url_final") or url)).netloc,
            metodo="v104_" + metodo,
            status="ok" if util >= max(1200, _min_chars()) else "short_usable" if util >= _min_chars() else "failed",
            score=90 if util >= 1600 else 82 if util >= _min_chars() else 10,
            chars=len(texto),
            util_chars=util,
            tentativas=["v90_pipeline"] + [str(x)[:200] for x in tent[:12]],
            erro=str((r or {}).get("motivo") or ""),
        )
    except Exception as e:
        return ResultadoExtracaoV104(url_original=url, url_final=url, metodo="v90_pipeline:error", erro=str(e))

def _resolver_publica(url: str) -> str:
    try:
        html, final, _status, _ct = _fetch(url, timeout=_env_int("URURAU_V104_TIMEOUT_RESOLVE", 8))
        soup = BeautifulSoup(html, "html.parser")
        can = _canonical(soup, final or url)
        if can:
            return can
        return final or url
    except Exception:
        return url


def _merge_melhor(a: ResultadoExtracaoV104, b: ResultadoExtracaoV104) -> ResultadoExtracaoV104:
    if b.util_chars > a.util_chars:
        return b
    if b.util_chars == a.util_chars and b.score > a.score:
        return b
    return a


def extrair_artigo_v104(url: str, texto_existente: str = "", titulo: str = "", forcar_refresh: bool = False) -> ResultadoExtracaoV104:
    url = (url or "").strip()
    titulo = _normalizar_linha(titulo or "")
    cache_key = f"{url}|{titulo}"
    now = time.time()
    if not forcar_refresh and cache_key in _CACHE:
        ts, val = _CACHE[cache_key]
        ttl = _CACHE_TTL if getattr(val, "ok", False) else _env_int("URURAU_V104_FAIL_CACHE_TTL_SEG", 180)
        if now - ts < ttl:
            return val

    melhor = ResultadoExtracaoV104(url_original=url, url_final=url, metodo="failed")
    erros: list[str] = []

    # 1) v86 existente, mas sem aceitar snippet curto como final.
    if _env_bool("URURAU_V104_USAR_V86_PRIMEIRO", True):
        try:
            from ururau.coleta.fonte_extractor_v86 import extrair_artigo_v86
            r86 = extrair_artigo_v86(url, texto_existente or "", forcar_refresh=forcar_refresh)
            txt86 = _limpar_publico(getattr(r86, "texto", "") or "", titulo)
            util86 = texto_util_chars(txt86)
            melhor = _merge_melhor(melhor, ResultadoExtracaoV104(
                ok=util86 >= _min_chars(), url_original=url, url_final=getattr(r86, "url_final", "") or url,
                titulo=getattr(r86, "titulo", "") or titulo, texto=txt86[:16000], imagem=getattr(r86, "imagem", "") or "",
                site_name=getattr(r86, "site_name", "") or "", metodo="v104_v86:" + str(getattr(r86, "metodo", "")),
                status="ok" if util86 >= max(1200, _min_chars()) else "short_usable" if util86 >= _min_chars() else "failed",
                score=max(int(getattr(r86, "score", 0) or 0), 80 if util86 >= _min_chars() else 0),
                chars=len(txt86), util_chars=util86, tentativas=list(getattr(r86, "tentativas", []) or []), erro=getattr(r86, "erro", "") or "",
            ))
            if melhor.ok and melhor.util_chars >= max(_min_chars(), _env_int("URURAU_V104_STOP_IF_CHARS", 1800)):
                _CACHE[cache_key] = (now, melhor)
                print(f"[V104][FONTE] OK {melhor.util_chars} chars via {melhor.metodo}: {melhor.url_final[:100]}")
                return melhor
        except Exception as e:
            erros.append(f"v86:{e}")

    resolved = _resolver_publica(url) if url else ""
    for u in _url_variantes(resolved or url):
        try:
            html, final, status, ctype = _fetch(u)
            if "html" not in (ctype or "").lower() and not html.lstrip().startswith("<!") and "<html" not in html[:1000].lower():
                erros.append(f"{u[:70]}:conteudo_nao_html:{ctype}")
                continue
            res_html = _from_html(html, final or u, titulo, metodo_base="requests")
            res_html.http_status = status
            res_html.tentativas.append(u)
            melhor = _merge_melhor(melhor, res_html)
            if melhor.ok and melhor.util_chars >= max(_min_chars(), _env_int("URURAU_V104_STOP_IF_CHARS", 1800)):
                _CACHE[cache_key] = (now, melhor)
                print(f"[V104][FONTE] OK {melhor.util_chars} chars via {melhor.metodo}: {melhor.url_final[:100]}")
                return melhor
        except Exception as e:
            erros.append(f"{u[:70]}:{type(e).__name__}:{e}")

    # 1.5) v110: ArticleExtractor do pacote Kimi (trafilatura + readability + metadados).
    if _env_bool("URURAU_V110_USAR_KIMI_EXTRACTOR", True):
        try:
            km = _extrair_kimi_v110(melhor.url_final or resolved or url, titulo)
            melhor = _merge_melhor(melhor, km)
            if melhor.ok and melhor.util_chars >= max(_min_chars(), _env_int("URURAU_V104_STOP_IF_CHARS", 1800)):
                _CACHE[cache_key] = (now, melhor)
                print(f"[V110][FONTE] OK {melhor.util_chars} chars via {melhor.metodo}: {melhor.url_final[:100]}")
                return melhor
        except Exception as e:
            erros.append(f"kimi_v110:{e}")

    # 1.6) v108: trafilatura/readability como fallback forte antes do WordPress.
    try:
        tr = _extrair_trafilatura_v108(melhor.url_final or resolved or url, titulo)
        melhor = _merge_melhor(melhor, tr)
        if melhor.ok and melhor.util_chars >= max(_min_chars(), _env_int("URURAU_V104_STOP_IF_CHARS", 1800)):
            _CACHE[cache_key] = (now, melhor)
            print(f"[V108][FONTE] OK {melhor.util_chars} chars via {melhor.metodo}: {melhor.url_final[:100]}")
            return melhor
    except Exception as e:
        erros.append(f"trafilatura_v108:{e}")

    # 2) WordPress REST público: muitos parceiros locais usam WordPress.
    try:
        wp = _extrair_wordpress(resolved or url, titulo) if _env_bool("URURAU_V104_USAR_WORDPRESS_REST", True) else ResultadoExtracaoV104(url_original=url, url_final=resolved or url, metodo="v104_wordpress:desativado")
        melhor = _merge_melhor(melhor, wp)
        if melhor.ok and melhor.util_chars >= max(_min_chars(), _env_int("URURAU_V104_STOP_IF_CHARS", 1800)):
            _CACHE[cache_key] = (now, melhor)
            print(f"[V104][FONTE] OK {melhor.util_chars} chars via {melhor.metodo}: {melhor.url_final[:100]}")
            return melhor
    except Exception as e:
        erros.append(f"wp:{e}")

    # 2.5) Pipeline v90/adaptadores legados: soma capacidade sem substituir v104.
    try:
        v90 = _extrair_pipeline_v90(melhor.url_final or resolved or url, titulo)
        melhor = _merge_melhor(melhor, v90)
        if melhor.ok and melhor.util_chars >= max(_min_chars(), _env_int("URURAU_V104_STOP_IF_CHARS", 1800)):
            _CACHE[cache_key] = (now, melhor)
            print(f"[V90][FONTE] OK {melhor.util_chars} chars via {melhor.metodo}: {melhor.url_final[:100]}")
            return melhor
    except Exception as e:
        erros.append(f"v90_pipeline:{e}")

    # 3) Renderização pública JS/Playwright.
    try:
        pw = _extrair_playwright(melhor.url_final or resolved or url, titulo)
        melhor = _merge_melhor(melhor, pw)
    except Exception as e:
        erros.append(f"playwright:{e}")

    # 4) Texto pré-existente só é aceitável se for realmente corpo longo.
    pre = _limpar_publico(texto_existente or "", titulo)
    util_pre = texto_util_chars(pre)
    if _env_bool("URURAU_V104_USAR_PREEXTRAIDO_LONGO", True) and util_pre >= max(_min_chars(), _env_int("URURAU_V104_MIN_PREEXTRAIDO", 1200)):
        melhor = _merge_melhor(melhor, ResultadoExtracaoV104(
            ok=True, url_original=url, url_final=melhor.url_final or url, titulo=titulo or melhor.titulo,
            texto=pre[:16000], imagem=melhor.imagem, credito_foto=melhor.credito_foto,
            site_name=melhor.site_name, metodo="v104_preextraido_longo", status="ok" if util_pre >= 1200 else "short_usable",
            score=78, chars=len(pre), util_chars=util_pre,
        ))

    melhor.ok = melhor.util_chars >= _min_chars()
    if melhor.ok:
        melhor.status = "ok" if melhor.util_chars >= max(1200, _min_chars()) else "short_usable"
        melhor.score = max(melhor.score, 82)
        print(f"[V104][FONTE] OK {melhor.util_chars} chars via {melhor.metodo}: {melhor.url_final[:100]}")
    else:
        melhor.status = "failed"
        melhor.score = min(melhor.score, 20)
        melhor.erro = melhor.erro or "; ".join(erros[-5:]) or "texto útil insuficiente"
        print(f"[V104][FONTE] FAIL {melhor.util_chars} chars | {melhor.metodo} | {melhor.erro[:180]}")
    _CACHE[cache_key] = (now, melhor)
    return melhor


def resultado_v104_para_dossie(res: ResultadoExtracaoV104, url: str = "", texto_existente: str = "") -> dict[str, Any]:
    texto = (res.texto or "").strip()
    util = int(res.util_chars or texto_util_chars(texto))
    return {
        "dossie": texto[:16000],
        "raw_source_text": texto[:16000],
        "cleaned_source_text": texto[:16000],
        "extraction_method": res.metodo or "v104_failed",
        "source_sufficiency_score": int(res.score or (92 if util >= 1600 else 80 if util >= _min_chars() else 5)),
        "extraction_status": "ok" if res.ok and util >= max(1200, _min_chars()) else "short_usable" if res.ok else "failed",
        "metadata": {
            "url": url or res.url_original or "",
            "resolved_url": res.url_final or url or "",
            "rss_chars": len(texto_existente or ""),
            "scraped_chars": len(texto),
            "total_chars": len(texto),
            "util_chars": util,
            "v104_tentativas": list(res.tentativas or []),
            "v104_metodo": res.metodo,
            "v104_erro": res.erro,
            "imagem": res.imagem,
            "credito_foto": res.credito_foto,
            "titulo": res.titulo,
            "site_name": res.site_name,
        },
    }


__all__ = ["ResultadoExtracaoV104", "extrair_artigo_v104", "resultado_v104_para_dossie"]

# PATCH_V47_31_RESULTADO_FONTE_SEGURO_V104
try:
    _v4731_v104_original = extrair_artigo_v104
    def extrair_artigo_v104(url: str, texto_existente: str = '', titulo: str = '', forcar_refresh: bool = False):
        try:
            res = _v4731_v104_original(url, texto_existente=texto_existente, titulo=titulo, forcar_refresh=forcar_refresh)
            if res is None:
                return ResultadoExtracaoV104(ok=False, url_original=url, url_final=url, texto='', metodo='v104_resultado_none_v47_31', status='failed', erro='extrator retornou None')
            erro = getattr(res, 'erro', '') or ''
            if 'NoneType' in erro and 'get' in erro:
                res.erro = 'entrada invalida normalizada pelo resultado seguro v47.31'
            return res
        except Exception as e:
            texto = limpar_texto_fonte_v81(texto_existente or '')
            util = texto_util_chars(texto)
            return ResultadoExtracaoV104(ok=False, url_original=url, url_final=url, texto=texto[:8000], metodo='v104_exception_safe_v47_31', status='failed', score=0, chars=len(texto), util_chars=util, erro=f'{type(e).__name__}: {e}')
except Exception:
    pass
