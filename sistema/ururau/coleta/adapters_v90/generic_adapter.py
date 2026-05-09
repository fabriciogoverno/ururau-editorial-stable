"""generic_adapter.py - Extração genérica via BeautifulSoup."""
import logging
from bs4 import BeautifulSoup
from .helpers_v90 import (
    safe_get, get_soup, get_json_ld, find_json_ld_newsarticle,
    extract_paragraphs_from_soup, all_meaningful_paragraphs,
    titulo_from_soup, imagem_from_soup, legenda_from_soup,
    credito_from_soup, fallback_result, build_result,
)

logger = logging.getLogger(__name__)
PREFIX = "[v90][ADAPTER][GENERIC]"


def extract(url: str, html: str = "") -> dict:
    result = fallback_result()
    result["metodo"] = "generic"
    result["motivo"] = "extração genérica via BeautifulSoup"

    soup = get_soup(html)
    if not soup:
        logger.warning(f"{PREFIX} HTML vazio ou inválido para URL={url}")
        result["motivo"] = "HTML vazio ou inválido"
        return result

    # 1. Tentativa JSON-LD
    try:
        scripts = get_json_ld(soup)
        article = find_json_ld_newsarticle(scripts)
        if article:
            titulo = safe_get(article, "headline", "")
            texto = safe_get(article, "articleBody", "")
            imagem = safe_get(article, "image", {})
            img_url = safe_get(imagem, "url", None) if isinstance(imagem, dict) else (imagem if isinstance(imagem, str) else None)
            if titulo and texto:
                paragrafos = [p.strip() for p in texto.split("\n") if len(p.strip()) > 30]
                if not paragrafos:
                    paragrafos = [texto]
                logger.info(f"{PREFIX} JSON-LD ok titulo={titulo[:60]}")
                return build_result(
                    True, titulo, texto, paragrafos,
                    img_url, None, None, "generic/json-ld", "extraído via JSON-LD"
                )
    except Exception as e:
        logger.warning(f"{PREFIX} JSON-LD falhou: {e}")

    # 2. Busca por containers semânticos
    titulo = ""
    paragrafos = []
    container = None
    try:
        titulo = titulo_from_soup(soup, prefer_h1=True)
    except Exception as e:
        logger.warning(f"{PREFIX} titulo falhou: {e}")

    selectors = [
        "article",
        "main",
        '[role="main"]',
        ".content",
        ".post-content",
        "#content",
        ".article-body",
        ".news-body",
        ".entry-content",
        ".texto",
        ".mainContent",
        "[itemprop='articleBody']",
    ]

    for sel in selectors:
        try:
            container = soup.select_one(sel)
            if container:
                paragrafos = extract_paragraphs_from_soup(container, None, min_len=30)
                if len(paragrafos) >= 2 and sum(len(p) for p in paragrafos) > 300:
                    logger.info(f"{PREFIX} Container {sel} com {len(paragrafos)} parágrafos")
                    break
        except Exception as e:
            logger.warning(f"{PREFIX} seletor {sel} falhou: {e}")

    # 3. Fallback para todos os <p> significativos
    if not paragrafos or len(paragrafos) < 2:
        try:
            paragrafos = all_meaningful_paragraphs(soup, min_len=40)
            logger.info(f"{PREFIX} Fallback <p> retornou {len(paragrafos)} parágrafos")
        except Exception as e:
            logger.warning(f"{PREFIX} Fallback <p> falhou: {e}")

    if not paragrafos:
        logger.warning(f"{PREFIX} Nenhum parágrafo encontrado em {url}")
        result["motivo"] = "Nenhum parágrafo significativo encontrado"
        return result

    texto = "\n\n".join(paragrafos)
    if len(texto) < 150:
        logger.warning(f"{PREFIX} Texto muito curto ({len(texto)} chars)")
        result["motivo"] = f"Texto muito curto ({len(texto)} chars)"
        return result

    # metadados
    imagem = None
    legenda = None
    credito = None
    try:
        imagem = imagem_from_soup(soup)
        legenda = legenda_from_soup(soup)
        credito = credito_from_soup(soup)
    except Exception as e:
        logger.warning(f"{PREFIX} metadados falhou: {e}")

    if not titulo:
        titulo = titulo_from_soup(soup, prefer_h1=False)

    logger.info(f"{PREFIX} Aceito paragrafos={len(paragrafos)} texto={len(texto)} chars")
    return build_result(
        True, titulo, texto, paragrafos,
        imagem, legenda, credito,
        "generic/beautifulsoup", f"extraído via container genérico"
    )
