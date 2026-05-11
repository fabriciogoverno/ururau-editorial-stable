"""
scrapling_extractor.py - Extrator principal de matérias via Scrapling.

Integra Scrapling como primeira tentativa de extração, mantendo o fallback legado
v104/v86/v90 intacto em scraping.py.

Compatível com versões diferentes da API do Scrapling: tenta StealthyFetcher,
seletores nativos, extração de containers e fallback BeautifulSoup.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ururau.coleta.limpeza_texto_v81 import limpar_texto_fonte_v81, texto_util_chars

try:
    from scrapling import StealthyFetcher  # type: ignore
    SCRAPLING_DISPONIVEL = True
except Exception:
    try:
        from scrapling.fetchers import StealthyFetcher  # type: ignore
        SCRAPLING_DISPONIVEL = True
    except Exception:
        StealthyFetcher = None  # type: ignore
        SCRAPLING_DISPONIVEL = False


@dataclass
class ScraplingResult:
    ok: bool = False
    url_original: str = ""
    url_final: str = ""
    titulo: str = ""
    texto: str = ""
    imagem: str = ""
    credito_foto: str = ""
    site_name: str = ""
    metodo: str = "scrapling_failed"
    status: str = "failed"
    score: int = 0
    chars: int = 0
    util_chars: int = 0
    tentativas: list[str] = field(default_factory=list)
    erro: str = ""


def _env_bool(nome: str, padrao: bool = False) -> bool:
    raw = str(os.getenv(nome, "1" if padrao else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _limpar_linha(txt: str) -> str:
    return re.sub(r"\s+", " ", str(txt or "")).strip()


def _normalizar_texto_partes(partes: list[str]) -> str:
    vistos: set[str] = set()
    linhas: list[str] = []
    junk = re.compile(
        r"(?i)(cookies|newsletter|assine|login|publicidade|compartilhe|termos de uso|"
        r"política de privacidade|mais lidas|últimas notícias|continua após a publicidade|"
        r"receba gratuitamente|siga-nos|redes sociais)"
    )
    for raw in partes:
        linha = _limpar_linha(raw)
        if len(linha) < 30:
            continue
        if junk.search(linha) and len(linha) < 260:
            continue
        chave = re.sub(r"[^a-z0-9áéíóúãõâêôç]+", "", linha.lower())[:220]
        if chave in vistos:
            continue
        vistos.add(chave)
        linhas.append(linha)
    return "\n\n".join(linhas).strip()


def _get_first(page: Any, selectors: list[str]) -> str:
    for sel in selectors:
        try:
            obj = page.css(sel)
            if hasattr(obj, "get"):
                val = obj.get()
            elif hasattr(obj, "first"):
                val = obj.first()
            else:
                val = None
            if val:
                return _limpar_linha(str(val))
        except Exception:
            pass
        try:
            obj = page.css_first(sel)
            if obj:
                if hasattr(obj, "get_all_text"):
                    val = obj.get_all_text(strip=True)
                elif hasattr(obj, "get"):
                    val = obj.get()
                else:
                    val = str(obj)
                if val:
                    return _limpar_linha(str(val))
        except Exception:
            pass
    return ""


def _get_all(page: Any, selector: str) -> list[str]:
    try:
        obj = page.css(selector)
        if hasattr(obj, "getall"):
            vals = obj.getall()
        elif hasattr(obj, "get_all"):
            vals = obj.get_all()
        else:
            vals = list(obj) if obj is not None else []
        return [_limpar_linha(str(v)) for v in vals if _limpar_linha(str(v))]
    except Exception:
        return []


def _container_text(page: Any, selector: str) -> str:
    try:
        obj = page.css_first(selector)
        if obj and hasattr(obj, "get_all_text"):
            return _limpar_linha(obj.get_all_text(separator="\n", strip=True))
        if obj and hasattr(obj, "css"):
            vals = obj.css("p::text").getall()
            return _normalizar_texto_partes([str(v) for v in vals])
    except Exception:
        pass
    return ""


def _texto_de_page(page: Any) -> str:
    for attr in ("html", "body", "content"):
        try:
            value = getattr(page, attr)
            if callable(value):
                value = value()
            if isinstance(value, str) and len(value) > 100:
                return value
        except Exception:
            pass
    try:
        body = page.css("body").get()
        if body:
            return str(body)
    except Exception:
        pass
    return str(page or "")


def _extrair_scrapling_selectors(page: Any, url: str = "", titulo_ref: str = "") -> tuple[str, str, str, str, str]:
    titulo = _get_first(page, [
        "h1::text",
        "article h1::text",
        "main h1::text",
        "title::text",
        "meta[property='og:title']::attr(content)",
        "meta[name='twitter:title']::attr(content)",
    ]) or titulo_ref

    imagem = _get_first(page, [
        "meta[property='og:image']::attr(content)",
        "meta[property='og:image:url']::attr(content)",
        "meta[name='twitter:image']::attr(content)",
        "article img::attr(src)",
        "main img::attr(src)",
        "img::attr(src)",
    ])
    if imagem and url:
        imagem = urljoin(url, imagem)

    site_name = _get_first(page, ["meta[property='og:site_name']::attr(content)"])

    candidatos: list[tuple[int, str]] = []

    # 1) Containers nativos inteiros
    for sel in ["article", "main", "[role='main']", ".content", ".entry-content", ".article", ".materia", ".noticia", ".texto", "body"]:
        texto = _container_text(page, sel)
        if texto:
            candidatos.append((texto_util_chars(texto), texto))

    # 2) Parágrafos por seletor
    for sel in [
        "article p::text",
        "main p::text",
        "[role='main'] p::text",
        ".content p::text",
        ".entry-content p::text",
        ".article p::text",
        ".materia p::text",
        ".noticia p::text",
        "p::text",
    ]:
        partes = _get_all(page, sel)
        texto = _normalizar_texto_partes(partes)
        if texto:
            candidatos.append((texto_util_chars(texto), texto))

    candidatos.sort(key=lambda item: item[0], reverse=True)
    texto = candidatos[0][1] if candidatos else ""
    return titulo, texto, imagem, "", site_name


def _extrair_basico_html(html: str, url: str = "", titulo_ref: str = "") -> tuple[str, str, str, str, str]:
    soup = BeautifulSoup(html or "", "html.parser")

    # JSON-LD primeiro: comum em sites jornalísticos
    jsonld_textos: list[str] = []
    jsonld_titulo = ""
    jsonld_img = ""
    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = script.string or script.get_text(" ", strip=False) or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop(0)
            if isinstance(item, dict):
                tipo = item.get("@type") or item.get("type") or ""
                tipo_s = " ".join(tipo) if isinstance(tipo, list) else str(tipo)
                if any(x in tipo_s.lower() for x in ("article", "newsarticle", "blogposting")):
                    jsonld_titulo = str(item.get("headline") or item.get("name") or jsonld_titulo or "")
                    img = item.get("image")
                    if isinstance(img, str):
                        jsonld_img = img
                    elif isinstance(img, list) and img:
                        jsonld_img = str(img[0])
                    body = item.get("articleBody") or item.get("text") or item.get("description")
                    if isinstance(body, str) and len(body) > 100:
                        jsonld_textos.append(body)
                stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
            elif isinstance(item, list):
                stack.extend(item)

    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", "form", "button", "nav", "header", "footer", "aside"]):
        tag.decompose()

    titulo = jsonld_titulo
    h1 = soup.find("h1")
    if h1:
        titulo = _limpar_linha(h1.get_text(" ", strip=True)) or titulo
    if not titulo and soup.title:
        titulo = _limpar_linha(soup.title.get_text(" ", strip=True))
    titulo = titulo or titulo_ref

    imagem = jsonld_img
    for selector in ['meta[property="og:image"]', 'meta[name="twitter:image"]']:
        el = soup.select_one(selector)
        if el and el.get("content"):
            imagem = str(el.get("content") or "").strip()
            break
    if imagem and url:
        imagem = urljoin(url, imagem)

    site_name = ""
    el_site = soup.select_one('meta[property="og:site_name"]')
    if el_site and el_site.get("content"):
        site_name = str(el_site.get("content") or "").strip()

    candidatos: list[tuple[int, str]] = []
    if jsonld_textos:
        texto_jsonld = _normalizar_texto_partes(jsonld_textos)
        candidatos.append((texto_util_chars(texto_jsonld) + 500, texto_jsonld))

    for sel in ["article", "main", "[role='main']", ".article", ".post", ".content", ".entry-content", ".materia", ".noticia", ".texto", "body"]:
        for el in soup.select(sel)[:12]:
            partes = []
            for node in el.find_all(["p", "h2", "h3", "blockquote", "li"], recursive=True):
                t = _limpar_linha(node.get_text(" ", strip=True))
                if len(t) >= 30:
                    partes.append(t)
            texto = _normalizar_texto_partes(partes)
            candidatos.append((texto_util_chars(texto), texto))
    candidatos.sort(key=lambda x: x[0], reverse=True)
    texto = candidatos[0][1] if candidatos else ""
    return titulo, texto, imagem, "", site_name


class UrurauScraplingExtractor:
    def __init__(self):
        self.fetcher = None
        if SCRAPLING_DISPONIVEL and StealthyFetcher:
            try:
                # API recomendada pela própria lib v0.4.x
                StealthyFetcher.configure(
                    stealth_mode=True,
                    bypass_cloudflare=True,
                    timeout=_env_int("URURAU_SCRAPLING_TIMEOUT", 18),
                )
            except Exception:
                pass
            self.fetcher = StealthyFetcher

    def _fetch(self, url: str) -> Any:
        if self.fetcher is None:
            raise RuntimeError("scrapling_fetcher_indisponivel")
        try:
            return StealthyFetcher.fetch(url, headless=True, network_idle=True, timeout=_env_int("URURAU_SCRAPLING_TIMEOUT", 18) * 1000)
        except TypeError:
            try:
                return StealthyFetcher.fetch(url, headless=True, network_idle=True)
            except TypeError:
                return StealthyFetcher.fetch(url)

    def extrair(self, url: str, texto_existente: str = "", titulo: str = "") -> ScraplingResult:
        url = (url or "").strip()
        if not url:
            return ScraplingResult(ok=False, erro="url_vazia")

        if not SCRAPLING_DISPONIVEL or not self.fetcher:
            return ScraplingResult(ok=False, url_original=url, url_final=url, metodo="scrapling:nao_instalado", erro="scrapling nao instalado")

        min_chars = _env_int("URURAU_SCRAPLING_MIN_CHARS", _env_int("URURAU_MIN_CHARS_TEXTO_FONTE", 900))
        tentativas: list[str] = []

        try:
            tentativas.append("stealthy_fetch")
            page = self._fetch(url)
            final_url = str(getattr(page, "url", url) or url)

            # Primeiro: auto_extract_article se disponível
            article = None
            try:
                if hasattr(page, "auto_extract_article"):
                    article = page.auto_extract_article()
            except Exception:
                article = None

            if article is not None:
                texto_bruto = str(getattr(article, "text", "") or "").strip()
                titulo_extraido = str(getattr(article, "title", "") or titulo or "").strip()
                imagem = str(getattr(article, "image", "") or "").strip()
                site_name = str(getattr(article, "site_name", "") or "").strip()
                autor = str(getattr(article, "author", "") or "").strip()
                tentativas.append("auto_extract_article")
            else:
                texto_bruto = ""
                titulo_extraido = titulo
                imagem = ""
                autor = ""
                site_name = ""

            # Segundo: seletores nativos do Scrapling
            if texto_util_chars(limpar_texto_fonte_v81(texto_bruto)) < min_chars:
                tentativas.append("scrapling_selectors")
                t2, tx2, img2, aut2, site2 = _extrair_scrapling_selectors(page, final_url or url, titulo)
                if texto_util_chars(limpar_texto_fonte_v81(tx2)) > texto_util_chars(limpar_texto_fonte_v81(texto_bruto)):
                    titulo_extraido = t2 or titulo_extraido
                    texto_bruto = tx2
                    imagem = img2 or imagem
                    autor = aut2 or autor
                    site_name = site2 or site_name

            # Terceiro: HTML bruto + BeautifulSoup/JSON-LD
            if texto_util_chars(limpar_texto_fonte_v81(texto_bruto)) < min_chars:
                tentativas.append("html_fallback")
                html_text = _texto_de_page(page)
                t3, tx3, img3, aut3, site3 = _extrair_basico_html(html_text, final_url or url, titulo)
                if texto_util_chars(limpar_texto_fonte_v81(tx3)) > texto_util_chars(limpar_texto_fonte_v81(texto_bruto)):
                    titulo_extraido = t3 or titulo_extraido
                    texto_bruto = tx3
                    imagem = img3 or imagem
                    autor = aut3 or autor
                    site_name = site3 or site_name

            texto = limpar_texto_fonte_v81(texto_bruto)
            util = texto_util_chars(texto)

            ok = util >= min_chars
            status = "ok" if util >= max(1200, min_chars) else ("short_usable" if ok else "failed")
            score = 96 if util >= 2200 else 88 if util >= 1400 else 78 if ok else 10

            return ScraplingResult(
                ok=ok,
                url_original=url,
                url_final=final_url,
                titulo=titulo_extraido,
                texto=texto[:16000],
                imagem=imagem,
                credito_foto=autor,
                site_name=site_name,
                metodo="scrapling_auto_extract" if article is not None and ok else ("scrapling_selectors" if "scrapling_selectors" in tentativas and ok else "scrapling_html_fallback"),
                status=status,
                score=score,
                chars=len(texto),
                util_chars=util,
                tentativas=list(tentativas),
            )

        except Exception as e:
            return ScraplingResult(ok=False, url_original=url, url_final=url, titulo=titulo, metodo="scrapling_error", erro=f"{type(e).__name__}: {e}", tentativas=list(tentativas))


def scrapling_para_dossie(res: ScraplingResult, url: str = "", texto_existente: str = "") -> dict[str, Any]:
    texto = (res.texto or "").strip()
    util = int(res.util_chars or texto_util_chars(texto))
    return {
        "dossie": texto[:16000],
        "raw_source_text": texto[:16000],
        "cleaned_source_text": texto[:16000],
        "extraction_method": res.metodo or "scrapling_failed",
        "source_sufficiency_score": int(res.score or (92 if util >= 1600 else 80 if util >= 500 else 5)),
        "extraction_status": res.status or ("ok" if res.ok else "failed"),
        "metadata": {
            "url": url or res.url_original or "",
            "resolved_url": res.url_final or url or "",
            "rss_chars": len(texto_existente or ""),
            "scraped_chars": len(texto),
            "total_chars": len(texto),
            "util_chars": util,
            "scrapling_tentativas": list(res.tentativas or []),
            "scrapling_metodo": res.metodo,
            "scrapling_erro": res.erro,
            "imagem": res.imagem,
            "credito_foto": res.credito_foto,
            "titulo": res.titulo,
            "site_name": res.site_name,
        },
    }


__all__ = ["ScraplingResult", "UrurauScraplingExtractor", "scrapling_para_dossie", "SCRAPLING_DISPONIVEL"]
