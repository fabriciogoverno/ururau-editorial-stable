"""
coleta/scraping.py — Extração de conteúdo web para apuração.
Extrai texto principal, meta tags og: e monta dossiê da pauta.
"""
from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ururau.config.settings import HEADERS, TIMEOUT_PADRAO
from ururau.coleta.limpeza_texto_v81 import limpar_texto_fonte_v81, texto_util_chars


# ── Seletores de container de artigo (CSS classes/IDs comuns) ─────────────────
_ARTICLE_SELETORES = [
    "article",
    '[class*="article"]',
    '[class*="content"]',
    '[class*="materia"]',
    '[class*="noticia"]',
    '[class*="post-body"]',
    '[class*="entry-content"]',
    '[class*="news-body"]',
    "main",
]

# Elementos a remover antes de extrair texto
_REMOVER_TAGS = [
    "script", "style", "nav", "header", "footer", "aside",
    "form", "noscript", "iframe", "button", "figure[class*='ad']",
]


def _criar_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _limpar_texto(texto: str) -> str:
    """v81: remove metadados/paywall e normaliza espaços."""
    return limpar_texto_fonte_v81(texto)



def _parece_google_news(url: str) -> bool:
    try:
        return "news.google.com" in (url or "").lower()
    except Exception:
        return False


def _resolver_google_news_url(url: str) -> str:
    """Tenta resolver link do Google News para a URL final da fonte.

    O RSS do Google News frequentemente entrega URL intermediária. Quando não
    for possível resolver com segurança, retorna a URL original e o gate de
    suficiência bloqueia a autopublicação se o texto ficar curto.
    """
    if not _parece_google_news(url):
        return url
    try:
        sess = _criar_session()
        resp = sess.get(url, timeout=TIMEOUT_PADRAO, allow_redirects=True)
        final = str(resp.url or "")
        if final and "news.google.com" not in final.lower():
            print(f"[SCRAPING] Google News resolvido: {final[:100]}")
            return final
        # tenta achar canonical/og:url no HTML intermediário
        soup = BeautifulSoup(resp.text or "", "html.parser")
        for sel in ["link[rel='canonical']", "meta[property='og:url']", "a[href]"]:
            el = soup.select_one(sel)
            val = ""
            if el:
                val = el.get("href") or el.get("content") or ""
            if val and val.startswith("http") and "news.google.com" not in val.lower():
                print(f"[SCRAPING] Google News canonical: {val[:100]}")
                return val
    except Exception as e:
        print(f"[SCRAPING] Não foi possível resolver Google News: {e}")
    return url


def _texto_rss_eh_snippet_google(texto: str) -> bool:
    t = re.sub(r"\s+", " ", texto or "").strip().lower()
    if not t:
        return True
    sinais = ["notícia no detalhe", "o projeto...", "&nbsp", " jornal ", " - "]
    if len(t) < 900 and any(s in t for s in sinais):
        return True
    if len(t) < 700:
        return True
    return False

def extrair_texto_pagina(url: str) -> str:
    """
    Extrai o texto principal do artigo de uma URL.
    Usa heurística de containers de conteúdo.
    Retorna string com o texto ou string vazia em caso de falha.
    """
    url = _resolver_google_news_url(url)
    sess = _criar_session()
    try:
        resp = sess.get(url, timeout=TIMEOUT_PADRAO, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove elementos indesejados
        for tag in _REMOVER_TAGS:
            for el in soup.select(tag):
                el.decompose()

        # Tenta encontrar container de artigo
        container = None
        for seletor in _ARTICLE_SELETORES:
            container = soup.select_one(seletor)
            if container:
                break

        alvo = container if container else soup.body
        if not alvo:
            return ""

        # Extrai parágrafos
        paragrafos = []
        for p in alvo.find_all(["p", "h2", "h3", "blockquote"], limit=60):
            texto = p.get_text(separator=" ", strip=True)
            if len(texto) > 30:
                paragrafos.append(texto)

        return _limpar_texto("\n\n".join(paragrafos))

    except Exception as e:
        print(f"[SCRAPING] Falha ao extrair texto de {url}: {e}")
        return ""


def extrair_meta_og(url: str) -> dict:
    """
    Extrai meta tags og: e twitter: de uma URL.

    Retorna dict com:
      - titulo: str
      - descricao: str
      - imagem: str
      - tipo: str
      - site_name: str
      - url_canonical: str
    """
    url = _resolver_google_news_url(url)
    sess = _criar_session()
    resultado = {
        "titulo": "",
        "descricao": "",
        "imagem": "",
        "tipo": "",
        "site_name": "",
        "url_canonical": url,
    }

    try:
        resp = sess.get(url, timeout=TIMEOUT_PADRAO, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        mapeamento = {
            "titulo":       [("og:title",), ("twitter:title",)],
            "descricao":    [("og:description",), ("twitter:description",), ("description",)],
            "imagem":       [("og:image",), ("og:image:url",), ("twitter:image",), ("twitter:image:src",)],
            "tipo":         [("og:type",)],
            "site_name":    [("og:site_name",)],
            "url_canonical":[("og:url",)],
        }

        for campo, opcoes in mapeamento.items():
            for (nome,) in opcoes:
                # Tenta property= (og:) e name= (twitter:/description)
                el = soup.find("meta", property=nome) or soup.find("meta", attrs={"name": nome})
                if el and el.get("content", "").strip():
                    resultado[campo] = el["content"].strip()
                    break

        # Fallback para <title>
        if not resultado["titulo"]:
            title_tag = soup.find("title")
            if title_tag:
                resultado["titulo"] = title_tag.get_text(strip=True)

    except Exception as e:
        print(f"[SCRAPING] Falha ao extrair og: de {url}: {e}")

    return resultado


def extrair_dossie(url: str, texto_existente: str = "") -> str:
    """
    v68: SEMPRE tenta abrir URL quando disponivel.
    RSS texto >=500 chars NAO eh aceito como fonte completa.
    """
    MAX_DOSSIE = 8000
    if not url:
        return (texto_existente or "")[:MAX_DOSSIE]
    texto_scraped = extrair_texto_pagina(url) or ""
    partes = []
    if texto_existente:
        partes.append(texto_existente)
    if texto_scraped:
        partes.append(texto_scraped)
    dossie = "\n\n".join(partes)
    if not dossie:
        dossie = texto_existente or ""
    return dossie[:MAX_DOSSIE]



def _env_bool_v86(nome: str, padrao: bool = False) -> bool:
    raw = str(os.getenv(nome, "1" if padrao else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}



def _dossie_v104_para_dict(url: str, texto_existente: str = "", titulo: str = "") -> dict | None:
    """v104: extrator definitivo antes dos caminhos antigos.

    Só retorna quando encontrou texto útil real acima do mínimo configurado.
    Snippet/RSS curto não é promovido a fonte completa.
    """
    if not _env_bool_v86("URURAU_V104_EXTRATOR_DEFINITIVO", True):
        return None
    try:
        from ururau.coleta.fonte_extractor_v104 import extrair_artigo_v104, resultado_v104_para_dossie
        from ururau.coleta.limpeza_texto_v81 import texto_util_chars
        res = extrair_artigo_v104(url or "", texto_existente or "", titulo=titulo or "")
        texto = (getattr(res, "texto", "") or "").strip()
        util = int(getattr(res, "util_chars", 0) or texto_util_chars(texto))
        min_chars = int(os.getenv("URURAU_V104_MIN_CHARS_ARTIGO", os.getenv("URURAU_MIN_CHARS_TEXTO_FONTE", "900")) or "900")
        if util >= min_chars:
            return resultado_v104_para_dossie(res, url=url or "", texto_existente=texto_existente or "")
        print(f"[V104][FONTE] Sem texto suficiente após cascata: {util} chars | metodo={getattr(res, 'metodo', '')}")
        return None
    except Exception as e:
        print(f"[V104][FONTE] erro interno no extrator definitivo: {e}")
        return None

def _dossie_v86_para_dict(url: str, texto_existente: str = "") -> dict | None:
    """Executa o extrator multiestratégia v86 antes do bloqueio antigo.

    Esta função é propositalmente chamada antes do fail-closed v84/v83.
    Assim, a pauta só é bloqueada depois que o robô tentou HTML, canonical,
    JSON-LD, __NEXT_DATA__, densidade, AMP/mobile e Playwright opcional.
    """
    if not _env_bool_v86("URURAU_V86_EXTRATOR_MULTIESTRATEGIA", True):
        return None

    try:
        from ururau.coleta.fonte_extractor_v86 import extrair_artigo_v86
        from ururau.coleta.limpeza_texto_v81 import texto_util_chars

        res = extrair_artigo_v86(url or "", texto_existente or "")
        texto = (getattr(res, "texto", "") or "").strip()
        util = int(getattr(res, "util_chars", 0) or texto_util_chars(texto))
        min_chars = int(os.getenv("URURAU_V86_MIN_CHARS_ACEITAR", os.getenv("URURAU_V84_MIN_CHARS_CAPTURA", "500")) or "500")

        # Se o v86 achou texto útil, retorna imediatamente. A partir daqui o
        # fail-closed decide se o texto é "ok" ou "short_usable", mas sem
        # bloquear antes das tentativas novas.
        if util >= min_chars:
            status = str(getattr(res, "status", "") or ("ok" if util >= 1200 else "short_usable"))
            metodo = str(getattr(res, "metodo", "") or "v86_multiestrategia")
            if not metodo.startswith("v86_") and not metodo.startswith("requests:") and not metodo.startswith("playwright"):
                metodo = "v86_" + metodo
            return {
                "dossie": texto[:12000],
                "raw_source_text": texto[:12000],
                "cleaned_source_text": texto[:12000],
                "extraction_method": metodo,
                "source_sufficiency_score": int(getattr(res, "score", 0) or (95 if util >= 1500 else 75)),
                "extraction_status": status,
                "metadata": {
                    "url": url or "",
                    "resolved_url": getattr(res, "url_final", "") or url or "",
                    "rss_chars": len(texto_existente or ""),
                    "scraped_chars": len(texto),
                    "total_chars": len(texto),
                    "util_chars": util,
                    "v86_tentativas": list(getattr(res, "tentativas", []) or []),
                    "v86_metodo": metodo,
                    "v86_erro": getattr(res, "erro", "") or "",
                    "v86_paywall_detectado": bool(getattr(res, "paywall_detectado", False)),
                    "imagem": getattr(res, "imagem", "") or "",
                    "titulo": getattr(res, "titulo", "") or "",
                    "site_name": getattr(res, "site_name", "") or "",
                },
            }

        print(
            f"[V86][FONTE] Sem texto útil após multiestratégia: "
            f"{util} chars | metodo={getattr(res, 'metodo', '')} | "
            f"erro={str(getattr(res, 'erro', ''))[:160]}"
        )
        return None
    except Exception as e:
        print(f"[V86][FONTE] erro interno no extrator multiestratégia: {e}")
        return None

def extrair_dossie_completo(url: str, texto_existente: str = "") -> dict:
    """
    v68: versao estruturada que retorna metadados de extracao.

    Retorna:
      {
        "dossie": str,
        "raw_source_text": str,
        "cleaned_source_text": str,
        "extraction_method": "url_scraping | rss_only | failed",
        "source_sufficiency_score": int 0..100,
        "extraction_status": "ok | short_usable | failed",
        "metadata": {url, rss_chars, scraped_chars, total_chars},
      }
    """
    MAX_DOSSIE = 8000
    rss_chars = len(texto_existente or "")
    out = {
        "dossie": "",
        "raw_source_text": "",
        "cleaned_source_text": "",
        "extraction_method": "failed",
        "source_sufficiency_score": 0,
        "extraction_status": "failed",
        "metadata": {
            "url": url or "",
            "resolved_url": url or "",
            "rss_chars": rss_chars,
            "scraped_chars": 0,
            "total_chars": 0,
        },
    }

    # v104: tenta extrator definitivo antes de qualquer fallback antigo.
    dossie_v104 = _dossie_v104_para_dict(url, texto_existente)
    if dossie_v104:
        return dossie_v104

    # v86C: tenta o extrator multiestratégia ANTES de qualquer bloqueio antigo.
    # O bloqueio fail-closed só pode acontecer depois dessas tentativas.
    dossie_v86 = _dossie_v86_para_dict(url, texto_existente)
    if dossie_v86:
        return dossie_v86

    if not url:
        d = (texto_existente or "")[:MAX_DOSSIE]
        out["dossie"] = d
        out["raw_source_text"] = d
        out["cleaned_source_text"] = d
        out["extraction_method"] = "rss_only" if d else "failed"
        out["metadata"]["total_chars"] = len(d)
        if len(d) >= 1500:
            out["extraction_status"] = "ok"
            out["source_sufficiency_score"] = 80
        elif len(d) >= 500:
            out["extraction_status"] = "short_usable"
            out["source_sufficiency_score"] = 50
        else:
            out["extraction_status"] = "failed"
            out["source_sufficiency_score"] = 10
        return out

    url_resolvida = _resolver_google_news_url(url)
    out["metadata"]["resolved_url"] = url_resolvida
    texto_scraped = extrair_texto_pagina(url_resolvida) or ""
    scraped_chars = len(texto_scraped)
    out["metadata"]["scraped_chars"] = scraped_chars
    out["raw_source_text"] = texto_scraped

    partes = []
    if texto_existente:
        partes.append(texto_existente)
    if texto_scraped:
        partes.append(texto_scraped)
    dossie_raw = "\n\n".join(partes)[:MAX_DOSSIE]
    dossie = limpar_texto_fonte_v81(dossie_raw)[:MAX_DOSSIE]
    util_chars = texto_util_chars(dossie)

    out["dossie"] = dossie
    out["cleaned_source_text"] = dossie
    out["metadata"]["total_chars"] = len(dossie)
    out["metadata"]["util_chars"] = util_chars

    if util_chars < 500:
        out["extraction_method"] = "source_too_short_v81"
        out["extraction_status"] = "failed"
        out["source_sufficiency_score"] = 5
    elif scraped_chars >= 1500:
        out["extraction_method"] = "url_scraping"
        out["extraction_status"] = "ok"
        out["source_sufficiency_score"] = 90
    elif scraped_chars >= 500:
        out["extraction_method"] = "url_scraping"
        out["extraction_status"] = "short_usable"
        out["source_sufficiency_score"] = 70
    elif rss_chars >= 1500:
        out["extraction_method"] = "rss_only"
        out["extraction_status"] = "short_usable"
        out["source_sufficiency_score"] = 50
    elif rss_chars >= 300 and not _parece_google_news(url) and not _texto_rss_eh_snippet_google(texto_existente):
        out["extraction_method"] = "rss_only"
        out["extraction_status"] = "short_usable"
        out["source_sufficiency_score"] = 30
    elif _parece_google_news(url):
        out["extraction_method"] = "google_news_unresolved"
        out["extraction_status"] = "failed"
        out["source_sufficiency_score"] = 5
    else:
        out["extraction_method"] = "failed"
        out["extraction_status"] = "failed"
        out["source_sufficiency_score"] = 10

    return out
