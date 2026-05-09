"""helpers_v90.py - Utilitários compartilhados entre adaptadores v90."""
import re
import json
import logging
from bs4 import BeautifulSoup


def safe_get(obj, key, default=None):
    """Retorna obj.get(key, default) se obj for dict; senão retorna default."""
    return obj.get(key, default) if isinstance(obj, dict) else default


def get_soup(html: str):
    """Retorna BeautifulSoup parsing com html.parser."""
    if not html or not isinstance(html, str):
        return None
    return BeautifulSoup(html, "html.parser")


def get_json_ld(soup):
    """Extrai e retorna todos os objetos JSON-LD do HTML."""
    scripts = []
    if not soup:
        return scripts
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = (script.string or "").strip()
            if not raw:
                continue
            data = json.loads(raw, strict=False)
            if isinstance(data, list):
                scripts.extend(data)
            elif isinstance(data, dict):
                scripts.append(data)
        except Exception:
            continue
    return scripts


def find_json_ld_by_type(scripts, types):
    """Encontra o primeiro JSON-LD cujo @type está em types (lista/tupla de strings)."""
    for entry in scripts:
        entry_type = safe_get(entry, "@type", "")
        if isinstance(entry_type, list):
            for t in entry_type:
                if t in types:
                    return entry
        elif entry_type in types:
            return entry
    return {}


def find_json_ld_newsarticle(scripts):
    """Encontra o primeiro JSON-LD NewsArticle ou Article."""
    return find_json_ld_by_type(scripts, ("NewsArticle", "Article", "ReportageNewsArticle", "WebPage"))


def extract_paragraphs_from_soup(soup, selector, min_len=30):
    """Extrai parágrafos a partir de um seletor CSS; retorna lista de strings."""
    if not soup:
        return []
    container = soup.select_one(selector) if selector else soup
    if not container:
        return []
    paras = []
    for p in container.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) >= min_len:
            paras.append(text)
    return paras


def all_meaningful_paragraphs(soup, min_len=40):
    """Retorna todos os <p> com texto significativo do body."""
    if not soup:
        return []
    body = soup.find("body") or soup
    texts = []
    for p in body.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) >= min_len:
            texts.append(text)
    return texts


def og_meta(soup, prop):
    """Retorna o conteúdo de uma meta tag Open Graph."""
    if not soup:
        return None
    tag = soup.find("meta", property=f"og:{prop}") or soup.find("meta", attrs={"name": f"og:{prop}"})
    if tag:
        return tag.get("content", "")
    return None


def meta_tag(soup, name):
    """Retorna o conteúdo de uma meta tag por name."""
    if not soup:
        return None
    tag = soup.find("meta", attrs={"name": name})
    if tag:
        return tag.get("content", "")
    return None


def titulo_from_soup(soup, prefer_h1=True):
    """Extrai título do soup via h1, og:title ou title."""
    if not soup:
        return ""
    if prefer_h1:
        h1 = soup.find("h1")
        if h1:
            txt = h1.get_text(strip=True)
            if txt:
                return txt
    og = og_meta(soup, "title")
    if og:
        return og
    t = soup.find("title")
    if t:
        return t.get_text(strip=True)
    return ""


def imagem_from_soup(soup):
    """Tenta extrair URL da imagem principal."""
    if not soup:
        return None
    # og:image
    img = og_meta(soup, "image")
    if img:
        return img
    # primeiro img grande dentro de article/main
    for container in soup.find_all(["article", "main", "div", "section"]):
        if container.get("class") and any(c in ("content", "post-content", "entry-content", "mainContent", "texto", "article-body") for c in container.get("class", [])):
            for img_tag in container.find_all("img"):
                src = img_tag.get("src", "") or img_tag.get("data-src", "")
                if src and not src.startswith("data:"):
                    return src
    # primeiro img com src absoluto
    for img_tag in soup.find_all("img"):
        src = img_tag.get("src", "") or img_tag.get("data-src", "") or img_tag.get("data-lazy-src", "")
        if src and src.startswith("http"):
            return src
    return None


def legenda_from_soup(soup):
    """Tenta extrair legenda da imagem principal."""
    if not soup:
        return None
    for fig in soup.find_all("figure"):
        cap = fig.find("figcaption")
        if cap:
            txt = cap.get_text(strip=True)
            if txt:
                return txt
    # classes comuns de legenda
    for cls in ("legenda", "caption", "image-caption", "wp-caption-text"):
        el = soup.find(class_=lambda x: x and cls in x)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return txt
    return None


def credito_from_soup(soup):
    """Tenta extrair crédito da imagem/foto."""
    if not soup:
        return None
    for cls in ("credito", "credit", "photo-credit", "image-credit", "autor"):
        el = soup.find(class_=lambda x: x and cls in x)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return txt
    # meta tag author
    auth = meta_tag(soup, "author")
    if auth:
        return auth
    return None


def strip_url_to_slug(url):
    """Retorna o último slug da URL."""
    if not url:
        return ""
    clean = url.rstrip("/")
    return clean.split("/")[-1].split("?")[0].split("#")[0]


def fallback_result():
    """Retorna dict base para rejeição."""
    return {
        "aceita": False,
        "titulo": "",
        "texto": "",
        "paragrafos": [],
        "imagem": None,
        "legenda": None,
        "credito": None,
        "metodo": "",
        "motivo": "",
    }


def build_result(aceita, titulo, texto, paragrafos, imagem, legenda, credito, metodo, motivo):
    """Monta o dict de resultado padronizado."""
    return {
        "aceita": aceita,
        "titulo": str(titulo or ""),
        "texto": str(texto or ""),
        "paragrafos": paragrafos if isinstance(paragrafos, list) else [],
        "imagem": imagem if imagem else None,
        "legenda": legenda if legenda else None,
        "credito": credito if credito else None,
        "metodo": str(metodo or ""),
        "motivo": str(motivo or ""),
    }
