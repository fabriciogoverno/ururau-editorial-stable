"""
scrapling_extractor.py - Extrator principal de matérias via Scrapling.

Substitui a cascata legada v104->v86->v90->trafilatura por uma unica
chamada robusta com StealthyFetcher + AutoExtractor.

Compatível com pipeline existente do Ururau Editorial Stable.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup

from ururau.coleta.limpeza_texto_v81 import limpar_texto_fonte_v81, texto_util_chars

try:
    # API citada no spec original.
    from scrapling import StealthyFetcher  # type: ignore
    SCRAPLING_DISPONIVEL = True
except Exception:
    try:
        # API atual documentada publicamente pelo projeto Scrapling.
        from scrapling.fetchers import StealthyFetcher  # type: ignore
        SCRAPLING_DISPONIVEL = True
    except Exception:
        StealthyFetcher = None  # type: ignore
        SCRAPLING_DISPONIVEL = False


@dataclass
class ScraplingResult:
    """Estrutura de retorno compatível com pipeline v104/v86."""
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


def _texto_de_page(page: Any) -> str:
    """Extrai HTML/texto do objeto Page do Scrapling em diferentes versões da API."""
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


def _limpar_linha(txt: str) -> str:
    return re.sub(r"\s+", " ", str(txt or "")).strip()


def _extrair_basico_html(html: str, url: str = "", titulo_ref: str = "") -> tuple[str, str, str, str, str]:
    """Fallback robusto quando auto_extract_article() não existir na versão instalada."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", "form", "button", "nav", "header", "footer", "aside"]):
        tag.decompose()

    titulo = ""
    h1 = soup.find("h1")
    if h1:
        titulo = _limpar_linha(h1.get_text(" ", strip=True))
    if not titulo and soup.title:
        titulo = _limpar_linha(soup.title.get_text(" ", strip=True))
    titulo = titulo or titulo_ref

    imagem = ""
    for selector in ['meta[property="og:image"]', 'meta[name="twitter:image"]']:
        el = soup.select_one(selector)
        if el and el.get("content"):
            imagem = str(el.get("content") or "").strip()
            break

    site_name = ""
    el_site = soup.select_one('meta[property="og:site_name"]')
    if el_site and el_site.get("content"):
        site_name = str(el_site.get("content") or "").strip()

    candidatos: list[tuple[int, str]] = []
    for sel in ["article", "main", "[role='main']", ".article", ".post", ".content", ".entry-content", ".materia", ".noticia", ".texto", "body"]:
        for el in soup.select(sel)[:12]:
            partes = []
            for node in el.find_all(["p", "h2", "h3", "blockquote", "li"], recursive=True):
                t = _limpar_linha(node.get_text(" ", strip=True))
                if len(t) >= 30:
                    partes.append(t)
            texto = "\n\n".join(partes)
            score = len(texto) + 80 * len([x for x in partes if len(x) > 70])
            candidatos.append((score, texto))
    candidatos.sort(key=lambda x: x[0], reverse=True)
    texto = candidatos[0][1] if candidatos else ""
    return titulo, texto, imagem, "", site_name


class UrurauScraplingExtractor:
    """
    Extrator unico via Scrapling.

    - StealthyFetcher: bypass Cloudflare/DataDome/PerimeterX quando disponível
    - AutoExtractor: extrai artigo, titulo, imagem, autor automaticamente quando disponível
    - Fallback HTML local: tolera versões diferentes da API Scrapling
    """

    def __init__(self):
        self.fetcher = None
        if SCRAPLING_DISPONIVEL and StealthyFetcher:
            try:
                self.fetcher = StealthyFetcher(
                    stealth_mode=True,
                    bypass_cloudflare=True,
                    timeout=_env_int("URURAU_SCRAPLING_TIMEOUT", 18),
                )
            except Exception:
                self.fetcher = StealthyFetcher

    def _fetch(self, url: str) -> Any:
        tentativas = []
        if self.fetcher is None:
            raise RuntimeError("scrapling_fetcher_indisponivel")
        # API de instância usada no spec.
        if hasattr(self.fetcher, "fetch") and not isinstance(self.fetcher, type):
            tentativas.append("instance.fetch")
            try:
                return self.fetcher.fetch(url)
            except TypeError:
                return self.fetcher.fetch(url, headless=True, network_idle=True)
        # API de classe documentada.
        if hasattr(StealthyFetcher, "fetch"):
            tentativas.append("class.fetch")
            try:
                return StealthyFetcher.fetch(url, headless=True, network_idle=True)
            except TypeError:
                try:
                    return StealthyFetcher.fetch(url)
                except TypeError:
                    return StealthyFetcher.fetch(url, stealthy_headers=True, timeout=15000)
        raise RuntimeError("scrapling_fetch_api_nao_suportada")

    def extrair(self, url: str, texto_existente: str = "", titulo: str = "") -> ScraplingResult:
        """
        Extrai matéria completa de uma URL pública.
        """
        url = (url or "").strip()
        if not url:
            return ScraplingResult(ok=False, erro="url_vazia")

        if not SCRAPLING_DISPONIVEL or not self.fetcher:
            return ScraplingResult(
                ok=False, url_original=url, url_final=url,
                metodo="scrapling:nao_instalado", erro="scrapling nao instalado"
            )

        min_chars = _env_int("URURAU_SCRAPLING_MIN_CHARS", _env_int("URURAU_MIN_CHARS_TEXTO_FONTE", 900))
        tentativas: list[str] = []

        try:
            tentativas.append("stealthy_fetch")
            page = self._fetch(url)
            final_url = str(getattr(page, "url", url) or url)

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
            else:
                tentativas.append("html_fallback")
                html_text = _texto_de_page(page)
                titulo_extraido, texto_bruto, imagem, autor, site_name = _extrair_basico_html(html_text, url, titulo)

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
                metodo="scrapling_auto_extract" if article is not None else "scrapling_html_fallback",
                status=status,
                score=score,
                chars=len(texto),
                util_chars=util,
                tentativas=list(tentativas),
            )

        except Exception as e:
            erro_str = f"{type(e).__name__}: {e}"
            return ScraplingResult(
                ok=False, url_original=url, url_final=url, titulo=titulo,
                metodo="scrapling_error", erro=erro_str, tentativas=list(tentativas)
            )


def scrapling_para_dossie(res: ScraplingResult, url: str = "", texto_existente: str = "") -> dict[str, Any]:
    """
    Converte ScraplingResult para o dict padrao do pipeline Ururau.
    """
    texto = (res.texto or "").strip()
    util = int(res.util_chars or texto_util_chars(texto))
    min_chars = _env_int("URURAU_SCRAPLING_MIN_CHARS", _env_int("URURAU_MIN_CHARS_TEXTO_FONTE", 900))

    return {
        "dossie": texto[:16000],
        "raw_source_text": texto[:16000],
        "cleaned_source_text": texto[:16000],
        "extraction_method": res.metodo or "scrapling_failed",
        "source_sufficiency_score": int(res.score or (92 if util >= 1600 else 80 if util >= min_chars else 5)),
        "extraction_status": "ok" if res.ok and util >= max(1200, min_chars) else ("short_usable" if res.ok else "failed"),
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


__all__ = [
    "ScraplingResult",
    "UrurauScraplingExtractor",
    "scrapling_para_dossie",
    "SCRAPLING_DISPONIVEL",
]
