"""
ururau/coleta/fonte_extractor_v86.py

Extrator multiestratégia v86 para capturar o texto real da matéria antes da
redação. O objetivo é aumentar a taxa de captura sem burlar paywall, login,
restrições técnicas ou bloqueios de acesso.

Estratégias seguras:
- requests com headers realistas, retries e cache simples;
- resolução de redirect/canonical/og:url, inclusive Google News quando possível;
- leitura de JSON-LD: NewsArticle/Article/articleBody;
- leitura de __NEXT_DATA__ e scripts JSON embutidos quando contêm parágrafos;
- heurística de contêiner principal por densidade textual;
- variantes públicas AMP/mobile/canonical;
- fallback opcional por Playwright apenas para página pública renderizada por JS.

Não faz login, não contorna paywall e não acessa conteúdo não público.
"""
from __future__ import annotations

import html as html_lib
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
    }
    TIMEOUT_PADRAO = 12

from ururau.coleta.limpeza_texto_v81 import limpar_texto_fonte_v81, texto_util_chars


@dataclass
class ResultadoExtracaoV86:
    ok: bool = False
    url_original: str = ""
    url_final: str = ""
    titulo: str = ""
    texto: str = ""
    imagem: str = ""
    site_name: str = ""
    metodo: str = "failed"
    status: str = "failed"
    score: int = 0
    chars: int = 0
    util_chars: int = 0
    tentativas: list[str] = field(default_factory=list)
    erro: str = ""
    html_chars: int = 0
    http_status: int = 0
    paywall_detectado: bool = False


_CACHE: dict[str, tuple[float, ResultadoExtracaoV86]] = {}
_CACHE_TTL = int(os.getenv("URURAU_V86_CACHE_TTL_SEG", "1800"))

_BLACKLIST_TEXT = [
    "benefício do assinante", "beneficio do assinante", "assine a folha",
    "assine para continuar", "conteúdo exclusivo para assinantes",
    "conteudo exclusivo para assinantes", "já é assinante", "ja e assinante",
    "faça seu login", "faca seu login", "copiar link", "salvar para ler depois",
    "publicidade", "continua após a publicidade", "continua apos a publicidade",
]
_BLACKLIST_CLASS = re.compile(
    r"(ad|ads|advert|banner|menu|nav|header|footer|sidebar|related|share|social|"
    r"comment|newsletter|paywall|subscribe|assinante|login|cookie|modal|promo)",
    re.I,
)
_CONTENT_CLASS = re.compile(
    r"(article|materia|mat[eé]ria|noticia|not[ií]cia|post|entry|content|texto|body|"
    r"reportagem|main|story|news)",
    re.I,
)


def _env_bool(nome: str, padrao: bool = False) -> bool:
    raw = str(os.getenv(nome, "1" if padrao else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _normalizar_linha(s: str) -> str:
    s = html_lib.unescape(s or "")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _dedup_linhas(linhas: Iterable[str]) -> list[str]:
    out: list[str] = []
    vistos: set[str] = set()
    for linha in linhas:
        l = _normalizar_linha(linha)
        if len(l) < 25:
            continue
        chave = re.sub(r"[^a-z0-9áéíóúãõâêôç]+", "", l.lower())[:180]
        if not chave or chave in vistos:
            continue
        if any(x in l.lower() for x in _BLACKLIST_TEXT) and len(l) < 250:
            continue
        vistos.add(chave)
        out.append(l)
    return out


def _texto_de_linhas(linhas: Iterable[str], limite: int = 10000) -> str:
    texto = "\n\n".join(_dedup_linhas(linhas))
    texto = limpar_texto_fonte_v81(texto)
    return texto[:limite].strip()


def _session() -> requests.Session:
    s = requests.Session()
    h = dict(HEADERS or {})
    h.setdefault("User-Agent", (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ))
    h.setdefault("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8")
    h.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    h.setdefault("Cache-Control", "no-cache")
    h.setdefault("Pragma", "no-cache")
    s.headers.update(h)
    return s


def _fetch(url: str, timeout: int | None = None) -> tuple[str, str, int, str]:
    timeout = timeout or _env_int("TIMEOUT_PADRAO", int(TIMEOUT_PADRAO or 12))
    sess = _session()
    r = sess.get(url, timeout=timeout, allow_redirects=True)
    status = int(getattr(r, "status_code", 0) or 0)
    r.raise_for_status()
    # força requests a respeitar encoding aparente quando o servidor omite charset
    if not r.encoding or r.encoding.lower() in {"iso-8859-1", "ascii"}:
        try:
            r.encoding = r.apparent_encoding or "utf-8"
        except Exception:
            pass
    return r.text or "", str(r.url or url), status, r.headers.get("content-type", "")


def _parece_google_news(url: str) -> bool:
    return "news.google.com" in (url or "").lower()


def _canonical_ou_og_url(soup: BeautifulSoup, base_url: str) -> str:
    candidatos: list[str] = []
    for sel, attr in [
        ("link[rel='canonical']", "href"),
        ("meta[property='og:url']", "content"),
        ("meta[name='twitter:url']", "content"),
    ]:
        el = soup.select_one(sel)
        if el and el.get(attr):
            candidatos.append(urljoin(base_url, el.get(attr, "").strip()))
    for href in candidatos:
        if href.startswith("http") and not _parece_google_news(href):
            return href
    return ""


def resolver_url_publica_v86(url: str) -> str:
    """Resolve redirects públicos/canonical. Não quebra paywall nem login."""
    if not url:
        return ""
    try:
        html, final, _status, _ct = _fetch(url, timeout=_env_int("URURAU_V86_TIMEOUT_RESOLVE", 8))
        if final and not _parece_google_news(final):
            return final
        soup = BeautifulSoup(html, "html.parser")
        can = _canonical_ou_og_url(soup, final or url)
        if can:
            return can
        # fallback seguro: primeiro link externo real em Google News
        if _parece_google_news(url):
            for a in soup.find_all("a", href=True):
                href = urljoin(final or url, a.get("href", ""))
                if href.startswith("http") and not _parece_google_news(href) and "google.com" not in href.lower():
                    return href
    except Exception:
        pass
    return url


def _url_variantes(url: str) -> list[str]:
    """Gera variantes públicas que frequentemente expõem a mesma matéria."""
    url = resolver_url_publica_v86(url)
    if not url:
        return []
    parsed = urlparse(url)
    variantes = [url]

    # canonical sem query longa/tracking
    clean_qs = []
    for part in (parsed.query or "").split("&"):
        if not part:
            continue
        k = part.split("=", 1)[0].lower()
        if k.startswith("utm_") or k in {"fbclid", "gclid", "output"}:
            continue
        clean_qs.append(part)
    clean = urlunparse(parsed._replace(query="&".join(clean_qs), fragment=""))
    if clean not in variantes:
        variantes.append(clean)

    # AMP: não contorna paywall; só tenta endpoint público AMP quando existe.
    path = parsed.path.rstrip("/")
    amp_candidates = []
    if not path.endswith("/amp") and not path.endswith("/amp/"):
        amp_candidates.append(urlunparse(parsed._replace(path=path + "/amp/", query="", fragment="")))
    if not path.startswith("/amp/"):
        amp_candidates.append(urlunparse(parsed._replace(path="/amp" + path, query="", fragment="")))
    # Algumas fontes usam ?output=amp
    amp_candidates.append(urlunparse(parsed._replace(query="output=amp", fragment="")))
    for v in amp_candidates:
        if v not in variantes:
            variantes.append(v)

    # v111.4: mobile automático foi desativado por padrão.
    # Os logs mostraram domínios inexistentes como m.j3news.com, m.girorj.com.br
    # e m.www.portalviu.com.br. Só tente mobile se o domínio estiver liberado.
    if _env_bool("URURAU_V86_TENTAR_MOBILE_AUTOMATICO", False):
        try:
            from ururau.coleta.source_policy_v114 import mobile_variant_allowed
            host = parsed.netloc
            if host and not host.startswith("m.") and mobile_variant_allowed(url):
                host_base = host[4:] if host.startswith("www.") else host
                mobile = urlunparse(parsed._replace(netloc="m." + host_base, fragment=""))
                if mobile not in variantes:
                    variantes.append(mobile)
        except Exception:
            pass

    return variantes[: _env_int("URURAU_V86_MAX_VARIANTES", 5)]


def _extrair_meta(soup: BeautifulSoup, base_url: str) -> dict[str, str]:
    def meta(*names: str) -> str:
        for name in names:
            el = soup.find("meta", property=name) or soup.find("meta", attrs={"name": name})
            if el and el.get("content"):
                return _normalizar_linha(el.get("content", ""))
        return ""

    titulo = ""
    h1 = soup.find("h1")
    if h1:
        titulo = h1.get_text(" ", strip=True)
    titulo = titulo or meta("og:title", "twitter:title")
    if not titulo and soup.title:
        titulo = soup.title.get_text(" ", strip=True)

    imagem = meta("og:image", "og:image:url", "twitter:image", "twitter:image:src")
    if imagem:
        imagem = urljoin(base_url, imagem)

    return {
        "titulo": _normalizar_linha(titulo),
        "descricao": meta("og:description", "twitter:description", "description"),
        "imagem": imagem,
        "site_name": meta("og:site_name", "application-name"),
        "canonical": _canonical_ou_og_url(soup, base_url),
    }


def _json_iter(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _json_iter(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _json_iter(it)


def _extrair_jsonld(soup: BeautifulSoup) -> tuple[str, str]:
    titulos: list[str] = []
    corpos: list[str] = []
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=False) or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            # tenta limpar blocos com múltiplos JSONs mal formatados
            try:
                data = json.loads(re.sub(r"\s+", " ", raw).strip())
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
                body = item.get("articleBody") or item.get("description") or ""
                if body and len(str(body)) > 300:
                    corpos.append(str(body))
    return _normalizar_linha(titulos[0] if titulos else ""), _texto_de_linhas(corpos)


def _extrair_next_data(soup: BeautifulSoup) -> str:
    """Extrai parágrafos de JSONs embutidos, especialmente Next.js/React."""
    textos: list[str] = []
    scripts = []
    nd = soup.find("script", id="__NEXT_DATA__")
    if nd:
        scripts.append(nd)
    for sc in soup.find_all("script", attrs={"type": re.compile("application/json", re.I)}):
        if sc not in scripts:
            scripts.append(sc)
    for sc in scripts[:6]:
        raw = sc.string or sc.get_text(" ", strip=False) or ""
        if len(raw) < 300:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for item in _json_iter(data):
            if isinstance(item, dict):
                for k, v in item.items():
                    if isinstance(v, str) and len(v) > 120 and k.lower() in {
                        "text", "texto", "body", "articlebody", "content", "description",
                        "paragraph", "paragraphs", "materia", "noticia", "html"
                    }:
                        clean = BeautifulSoup(v, "html.parser").get_text(" ", strip=True)
                        textos.append(clean)
            elif isinstance(item, str) and len(item) > 200:
                textos.append(item)
    return _texto_de_linhas(textos)


def _remover_ruido(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", "form", "button", "nav", "header", "footer", "aside"]):
        tag.decompose()
    for el in soup.find_all(True):
        attrs = " ".join(str(el.get(a, "")) for a in ["id", "class", "role", "aria-label"])
        if _BLACKLIST_CLASS.search(attrs or ""):
            # não remove article/paywall inteiro se também tem sinal de conteúdo forte
            text_len = len(el.get_text(" ", strip=True) or "")
            if text_len < 500 or not _CONTENT_CLASS.search(attrs or ""):
                try:
                    el.decompose()
                except Exception:
                    pass


def _score_container(el: Any) -> tuple[int, str]:
    textos: list[str] = []
    for node in el.find_all(["p", "h2", "h3", "li", "blockquote"], recursive=True):
        txt = node.get_text(" ", strip=True)
        if len(txt) >= 30:
            textos.append(txt)
    texto = _texto_de_linhas(textos)
    chars = texto_util_chars(texto)
    parag = len(textos)
    attrs = " ".join(str(el.get(a, "")) for a in ["id", "class", "role"])
    bonus = 120 if _CONTENT_CLASS.search(attrs or "") else 0
    if getattr(el, "name", "") == "article":
        bonus += 150
    if getattr(el, "name", "") == "main":
        bonus += 80
    pontuacao = chars + parag * 45 + bonus
    return pontuacao, texto


def _extrair_por_densidade(soup: BeautifulSoup) -> str:
    _remover_ruido(soup)
    candidatos: list[tuple[int, str]] = []
    seletores = [
        "article", "main", "[role='main']", "div[itemprop='articleBody']",
        "section[itemprop='articleBody']", "div[class*='article']", "div[class*='materia']",
        "div[class*='noticia']", "div[class*='content']", "div[class*='texto']",
        "div[class*='body']", "section[class*='content']", "section[class*='article']",
    ]
    vistos_ids: set[int] = set()
    for sel in seletores:
        for el in soup.select(sel)[:20]:
            if id(el) in vistos_ids:
                continue
            vistos_ids.add(id(el))
            candidatos.append(_score_container(el))
    body = soup.find("body")
    if body:
        candidatos.append(_score_container(body))
    candidatos.sort(key=lambda x: x[0], reverse=True)
    for score, texto in candidatos[:5]:
        if texto_util_chars(texto) >= _env_int("URURAU_V86_MIN_CHARS_ACEITAR", 500):
            return texto
    return candidatos[0][1] if candidatos else ""


def _paywall_detectado(texto: str, html: str = "") -> bool:
    t = ((texto or "") + " " + (html or "")[:5000]).lower()
    sinais = [
        "conteúdo exclusivo para assinantes", "conteudo exclusivo para assinantes",
        "assine para continuar", "assine a folha", "benefício do assinante",
        "recurso exclusivo para assinantes", "já é assinante", "faça seu login",
    ]
    return any(s in t for s in sinais)


def _extrair_de_html(html: str, url: str, metodo_base: str) -> ResultadoExtracaoV86:
    soup = BeautifulSoup(html or "", "html.parser")
    meta = _extrair_meta(soup, url)
    titulo_json, texto_jsonld = _extrair_jsonld(soup)
    texto_next = _extrair_next_data(soup)
    texto_densidade = _extrair_por_densidade(soup)

    candidatos = [
        ("jsonld_articleBody", texto_jsonld),
        ("embedded_json", texto_next),
        ("html_density", texto_densidade),
    ]
    candidatos.sort(key=lambda it: texto_util_chars(it[1]), reverse=True)
    metodo, texto = candidatos[0]
    texto = limpar_texto_fonte_v81(texto)
    util = texto_util_chars(texto)

    res = ResultadoExtracaoV86(
        ok=util >= _env_int("URURAU_V86_MIN_CHARS_ACEITAR", 500),
        url_original=url,
        url_final=meta.get("canonical") or url,
        titulo=titulo_json or meta.get("titulo", ""),
        texto=texto[:12000],
        imagem=meta.get("imagem", ""),
        site_name=meta.get("site_name", ""),
        metodo=f"{metodo_base}:{metodo}",
        status="ok" if util >= 1200 else ("short_usable" if util >= 500 else "failed"),
        score=95 if util >= 1500 else (75 if util >= 800 else (55 if util >= 500 else 5)),
        chars=len(texto),
        util_chars=util,
        html_chars=len(html or ""),
        paywall_detectado=_paywall_detectado(texto, html),
    )
    if res.paywall_detectado and util < 1200:
        res.ok = False
        res.status = "failed"
        res.metodo = f"{metodo_base}:paywall_or_login"
        res.score = 5
    return res


def _extrair_com_playwright(url: str) -> ResultadoExtracaoV86:
    """Renderiza página pública com Playwright, sem login e sem burlar restrição."""
    if not _env_bool("URURAU_V86_PLAYWRIGHT_SE_FALHAR", False):
        return ResultadoExtracaoV86(url_original=url, url_final=url, erro="playwright_desativado")
    try:
        from playwright.sync_api import sync_playwright
        timeout_ms = _env_int("URURAU_V86_PLAYWRIGHT_TIMEOUT_MS", 15000)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(locale="pt-BR", user_agent=HEADERS.get("User-Agent"))
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_timeout(_env_int("URURAU_V86_PLAYWRIGHT_WAIT_MS", 1200))
            except Exception:
                pass
            html = page.content()
            final = page.url
            browser.close()
        res = _extrair_de_html(html, final or url, "playwright_public")
        res.url_original = url
        res.url_final = final or url
        res.tentativas.append("playwright_public")
        return res
    except Exception as e:
        return ResultadoExtracaoV86(url_original=url, url_final=url, metodo="playwright_error", erro=str(e))


def extrair_artigo_v86(url: str, texto_existente: str = "", forcar_refresh: bool = False) -> ResultadoExtracaoV86:
    """Extrai artigo com cascata segura. Não levanta exceção."""
    url = (url or "").strip()
    if not url:
        texto = limpar_texto_fonte_v81(texto_existente or "")
        util = texto_util_chars(texto)
        return ResultadoExtracaoV86(
            ok=util >= 500, texto=texto, chars=len(texto), util_chars=util,
            metodo="rss_only_no_url", status="ok" if util >= 1500 else "short_usable" if util >= 500 else "failed",
            score=50 if util >= 500 else 0,
        )

    now = time.time()
    if not forcar_refresh and url in _CACHE:
        ts, val = _CACHE[url]
        if now - ts < _CACHE_TTL:
            return val

    tentativas: list[str] = []
    melhor = ResultadoExtracaoV86(url_original=url, url_final=url, texto="", metodo="failed")
    erros: list[str] = []

    for u in _url_variantes(url):
        if not u or u in tentativas:
            continue
        tentativas.append(u)
        try:
            html, final, status, ctype = _fetch(u)
            if "text/html" not in (ctype or "").lower() and "application/xhtml" not in (ctype or "").lower() and html.lstrip().startswith("%PDF"):
                erros.append(f"{u[:80]}: conteudo nao HTML")
                continue
            res = _extrair_de_html(html, final or u, "requests")
            res.url_original = url
            res.http_status = status
            res.tentativas = list(tentativas)
            if res.util_chars > melhor.util_chars:
                melhor = res
            if res.ok and res.util_chars >= _env_int("URURAU_V86_MIN_CHARS_ACEITAR", 500):
                _CACHE[url] = (now, res)
                print(f"[V86][FONTE] OK {res.util_chars} chars via {res.metodo}: {res.url_final[:100]}")
                return res
        except Exception as e:
            erros.append(f"{u[:80]}: {type(e).__name__}: {e}")
            continue

    # fallback público renderizado por JS, opcional e controlado por env
    pw = _extrair_com_playwright(melhor.url_final or resolver_url_publica_v86(url) or url)
    if pw.util_chars > melhor.util_chars:
        melhor = pw
    if melhor.ok:
        _CACHE[url] = (now, melhor)
        print(f"[V86][FONTE] OK {melhor.util_chars} chars via {melhor.metodo}: {melhor.url_final[:100]}")
        return melhor

    # último recurso: texto_existente só como short_usable, nunca como texto completo se for pequeno
    rss = limpar_texto_fonte_v81(texto_existente or "")
    util_rss = texto_util_chars(rss)
    if util_rss > melhor.util_chars:
        melhor.texto = rss[:8000]
        melhor.chars = len(rss)
        melhor.util_chars = util_rss
        melhor.metodo = "rss_fallback"
        melhor.status = "short_usable" if util_rss >= 500 else "failed"
        melhor.score = 45 if util_rss >= 500 else 5
        melhor.ok = util_rss >= 500 and _env_bool("URURAU_V86_ACEITAR_RSS_FALLBACK", False)

    melhor.tentativas = list(tentativas)
    melhor.erro = "; ".join(erros[-4:]) or melhor.erro or "extração sem texto útil"
    if not melhor.status or melhor.status == "ok":
        melhor.status = "failed"
    _CACHE[url] = (now, melhor)
    print(f"[V86][FONTE] FAIL {melhor.util_chars} chars | {melhor.metodo} | {melhor.erro[:180]}")
    return melhor


__all__ = [
    "ResultadoExtracaoV86",
    "extrair_artigo_v86",
    "resolver_url_publica_v86",
]
