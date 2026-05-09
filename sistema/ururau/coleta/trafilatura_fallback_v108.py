"""
Fallback v108 de extração de texto.

Usa o pacote analisado `google_news_scraper` apenas como inspiração/vendor e
aplica trafilatura/readability como etapa adicional de leitura pública. Não
quebra paywall, não faz login e não tenta acessar conteúdo restrito.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

try:
    from ururau.coleta.http_fetch_v109 import fetch_html_v109
except Exception:
    fetch_html_v109 = None

try:
    from ururau.config.settings import HEADERS, TIMEOUT_PADRAO
except Exception:  # pragma: no cover
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    TIMEOUT_PADRAO = 14

try:
    from ururau.coleta.limpeza_texto_v81 import texto_util_chars
except Exception:
    def texto_util_chars(t: str) -> int:
        return len(str(t or "").strip())

try:
    from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101
except Exception:
    def limpar_texto_artigo_v101(texto: str, titulo: str = "", max_chars: int = 22000) -> str:
        return str(texto or "").strip()[:max_chars]


@dataclass
class ResultadoTrafilaturaV108:
    ok: bool = False
    texto: str = ""
    titulo: str = ""
    imagem: str = ""
    credito_foto: str = ""
    url_final: str = ""
    metodo: str = "v108_trafilatura_failed"
    erro: str = ""
    util_chars: int = 0


def _min_chars() -> int:
    for nome, padrao in [
        ("URURAU_V108_MIN_TEXTO_FONTE_OK", None),
        ("URURAU_V105_MIN_CHARS_FONTE_OK", None),
        ("URURAU_V104_MIN_CHARS_ARTIGO", None),
    ]:
        raw = os.getenv(nome, "")
        if raw:
            try:
                return int(raw)
            except Exception:
                pass
    return 1200


def _fetch_html(url: str) -> tuple[str, str]:
    # v109: usa rotação de User-Agent, retry com backoff e cooldown por domínio.
    if fetch_html_v109 is not None and str(os.getenv("URURAU_V109_HTTP_FETCH", "1")).lower() not in {"0", "false", "nao", "não"}:
        return fetch_html_v109(
            url,
            base_headers=dict(HEADERS or {}),
            timeout=int(os.getenv("URURAU_V108_TRAFILATURA_TIMEOUT", str(TIMEOUT_PADRAO or 14))),
            max_retries=int(os.getenv("URURAU_V109_HTTP_MAX_RETRIES", "3") or "3"),
            backoff=float(str(os.getenv("URURAU_V109_HTTP_BACKOFF", "1.7") or "1.7").replace(",", ".")),
        )

    # Fallback legado, mantido só por segurança.
    import requests
    s = requests.Session()
    h = dict(HEADERS or {})
    h.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36")
    h.setdefault("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8")
    h.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    s.headers.update(h)
    r = s.get(url, timeout=int(os.getenv("URURAU_V108_TRAFILATURA_TIMEOUT", str(TIMEOUT_PADRAO or 14))), allow_redirects=True)
    r.raise_for_status()
    if not r.encoding or str(r.encoding).lower() in {"iso-8859-1", "ascii"}:
        try:
            r.encoding = r.apparent_encoding or "utf-8"
        except Exception:
            pass
    return r.text or "", str(r.url or url)


def _meta(soup: BeautifulSoup, base_url: str) -> dict[str, str]:
    def m(*names: str) -> str:
        for name in names:
            el = soup.find("meta", property=name) or soup.find("meta", attrs={"name": name})
            if el and el.get("content"):
                return " ".join(str(el.get("content", "")).split())
        return ""
    titulo = ""
    h1 = soup.find("h1")
    if h1:
        titulo = h1.get_text(" ", strip=True)
    titulo = titulo or m("og:title", "twitter:title")
    if not titulo and soup.title:
        titulo = soup.title.get_text(" ", strip=True)
    imagem = m("og:image", "og:image:url", "twitter:image", "twitter:image:src")
    if imagem:
        imagem = urljoin(base_url, imagem)
    return {"titulo": titulo, "imagem": imagem}


def _credito(soup: BeautifulSoup) -> str:
    zonas = []
    for sel in ["figcaption", ".caption", ".credito", ".credit", "[class*='credito']", "[class*='credit']"]:
        try:
            for el in soup.select(sel)[:12]:
                zonas.append(el.get_text(" ", strip=True))
        except Exception:
            pass
    for z in zonas:
        z = " ".join((z or "").split())
        m = re.search(r"(?:Foto|Cr[eé]dito|Imagem|Copyright)\s*[:\-]\s*([^|/\n\r]{2,80})", z, flags=re.I)
        if m:
            val = m.group(1).strip(" .,-")
            if 2 <= len(val) <= 60 and not re.search(r"pol[ií]tica de privacidade|termos de uso|compartilhe", val, re.I):
                return val
    return ""


def _preservar_paragrafos(texto: str, titulo: str = "") -> str:
    texto = str(texto or "").replace("\r\n", "\n").replace("\r", "\n")
    blocos = []
    for raw in re.split(r"\n{1,}", texto):
        b = " ".join(raw.split()).strip()
        if len(b) < 35:
            continue
        if re.search(r"pol[ií]tica de privacidade|termos de uso|newsletter|cookies|compartilhe|publicidade", b, re.I) and len(b) < 260:
            continue
        blocos.append(b)
    # Se vier bloco único longo, tenta quebrar em blocos de 2 a 3 frases.
    if len(blocos) <= 1 and len(texto) > 1200:
        frases = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9\"“])", " ".join(texto.split()))
        blocos, atual = [], []
        for f in frases:
            atual.append(f)
            if len(" ".join(atual)) >= 280:
                blocos.append(" ".join(atual).strip())
                atual = []
        if atual:
            blocos.append(" ".join(atual).strip())
    out = "\n\n".join(blocos)
    return limpar_texto_artigo_v101(out, titulo=titulo, max_chars=22000).strip()


def extrair_trafilatura_v108(url: str, titulo: str = "") -> ResultadoTrafilaturaV108:
    if str(os.getenv("URURAU_V108_USAR_TRAFILATURA_FALLBACK", "1")).lower() in {"0", "false", "nao", "não"}:
        return ResultadoTrafilaturaV108(erro="fallback_desativado")
    try:
        html, final = _fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        meta = _meta(soup, final)
        texto = ""
        metodo = "v108_trafilatura"
        try:
            import trafilatura
            texto = trafilatura.extract(
                html,
                url=final,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
                output_format="txt",
            ) or ""
        except Exception as e:
            metodo = f"v108_trafilatura_indisponivel:{type(e).__name__}"
        if texto_util_chars(texto) < _min_chars():
            try:
                from readability import Document
                doc = Document(html)
                summary = doc.summary(html_partial=True)
                rsoup = BeautifulSoup(summary, "html.parser")
                cand = rsoup.get_text("\n", strip=True)
                if texto_util_chars(cand) > texto_util_chars(texto):
                    texto = cand
                    metodo = "v108_readability"
            except Exception as e:
                metodo = metodo if texto else f"v108_readability_error:{type(e).__name__}"
        texto = _preservar_paragrafos(texto, titulo or meta.get("titulo", ""))
        util = texto_util_chars(texto)
        return ResultadoTrafilaturaV108(
            ok=util >= _min_chars(),
            texto=texto[:18000],
            titulo=meta.get("titulo", "") or titulo,
            imagem=meta.get("imagem", ""),
            credito_foto=_credito(soup),
            url_final=final,
            metodo=metodo,
            util_chars=util,
            erro="" if util >= _min_chars() else f"texto_insuficiente:{util}/{_min_chars()}",
        )
    except Exception as e:
        return ResultadoTrafilaturaV108(ok=False, url_final=url, erro=str(e), metodo="v108_trafilatura_error")
