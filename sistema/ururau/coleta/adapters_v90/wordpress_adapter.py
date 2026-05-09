"""wordpress_adapter.py - Extração para sites WordPress."""
import re
import logging
from .helpers_v90 import (
    safe_get, get_soup, get_json_ld, find_json_ld_newsarticle,
    extract_paragraphs_from_soup, all_meaningful_paragraphs,
    titulo_from_soup, imagem_from_soup, legenda_from_soup,
    credito_from_soup, strip_url_to_slug, fallback_result, build_result,
)

logger = logging.getLogger(__name__)
PREFIX = "[v90][ADAPTER][WORDPRESS]"


def _detect_wordpress(soup, html):
    """Detecta se é um site WordPress por meta generator ou /wp-content/."""
    if not html or not isinstance(html, str):
        return False
    if "/wp-content/" in html or "wp-includes" in html:
        return True
    if not soup:
        return False
    meta = soup.find("meta", attrs={"name": "generator"})
    if meta and "WordPress" in (meta.get("content", "") or ""):
        return True
    # classes típicas do WordPress
    wp_classes = ["entry-content", "post-content", "wp-post", "wp-block"]
    for cls in wp_classes:
        if soup.find(class_=lambda x: x and cls in x):
            return True
    return False


def extract(url: str, html: str = "") -> dict:
    result = fallback_result()
    result["metodo"] = "wordpress"
    result["motivo"] = "extração WordPress"

    soup = get_soup(html)
    if not soup:
        result["motivo"] = "HTML vazio ou inválido"
        return result

    is_wp = _detect_wordpress(soup, html)
    if not is_wp:
        logger.warning(f"{PREFIX} Site não parece WordPress: {url}")
        # Continua mesmo assim; pode ser um WordPress escondido

    titulo = ""
    texto = ""
    paragrafos = []
    imagem = None
    legenda = None
    credito = None
    metodo = "wordpress/desconhecido"
    aceito = False

    # 1. JSON-LD
    try:
        from .helpers_v90 import get_json_ld, find_json_ld_newsarticle
        scripts = get_json_ld(soup)
        article = find_json_ld_newsarticle(scripts)
        if article:
            titulo = safe_get(article, "headline", "")
            texto = safe_get(article, "articleBody", "")
            img_data = safe_get(article, "image", {})
            imagem = safe_get(img_data, "url", None) if isinstance(img_data, dict) else (img_data if isinstance(img_data, str) else None)
            if titulo and texto:
                paragrafos = [p.strip() for p in texto.split("\n") if len(p.strip()) > 20]
                if not paragrafos:
                    paragrafos = [texto]
                aceito = True
                metodo = "wordpress/json-ld"
                logger.info(f"{PREFIX} JSON-LD ok")
    except Exception as e:
        logger.warning(f"{PREFIX} JSON-LD falhou: {e}")

    # 2. articleBody em div/itemprop
    if not aceito:
        try:
            body_el = soup.find(attrs={"itemprop": "articleBody"})
            if body_el:
                paragrafos = extract_paragraphs_from_soup(body_el, None, min_len=30)
                if paragrafos:
                    texto = "\n\n".join(paragrafos)
                    aceito = True
                    metodo = "wordpress/articleBody"
                    logger.info(f"{PREFIX} articleBody ok")
        except Exception as e:
            logger.warning(f"{PREFIX} articleBody falhou: {e}")

    # 3. WordPress REST API hint (não fazemos requisição real, apenas registro)
    if not aceito:
        try:
            slug = strip_url_to_slug(url)
            if "/wp-json/" in html or "wp-json/wp/v2/posts" in html:
                metodo = "wordpress/rest-api-hint"
                logger.info(f"{PREFIX} REST API hint detectado slug={slug}")
        except Exception as e:
            logger.warning(f"{PREFIX} REST API hint falhou: {e}")

    # 4. Divs com classe .entry-content, .post-content
    if not aceito:
        for cls in ("entry-content", "post-content", "wp-post", "article-content", "td-post-content"):
            try:
                divs = soup.find_all(class_=re.compile(cls))
                for div in divs:
                    pars = extract_paragraphs_from_soup(div, None, min_len=30)
                    if len(pars) >= 2:
                        paragrafos = pars
                        texto = "\n\n".join(paragrafos)
                        aceito = True
                        metodo = f"wordpress/{cls}"
                        logger.info(f"{PREFIX} {cls} ok")
                        break
                if aceito:
                    break
            except Exception as e:
                logger.warning(f"{PREFIX} {cls} falhou: {e}")

    # 5. Fallback genérico de parágrafos
    if not aceito:
        try:
            paragrafos = all_meaningful_paragraphs(soup, min_len=40)
            if paragrafos:
                texto = "\n\n".join(paragrafos)
                aceito = True
                metodo = "wordpress/fallback-p"
                logger.info(f"{PREFIX} fallback-p ok")
        except Exception as e:
            logger.warning(f"{PREFIX} fallback-p falhou: {e}")

    if not aceito or not paragrafos:
        result["motivo"] = "Não foi possível extrair conteúdo útil do WordPress"
        logger.warning(f"{PREFIX} Rejeitado: {url}")
        return result

    if not titulo:
        titulo = titulo_from_soup(soup, prefer_h1=True)
    if not imagem:
        imagem = imagem_from_soup(soup)
    if not legenda:
        legenda = legenda_from_soup(soup)
    if not credito:
        credito = credito_from_soup(soup)

    if len(texto) < 150:
        result["motivo"] = f"Texto muito curto ({len(texto)} chars)"
        return result

    logger.info(f"{PREFIX} Aceito paragrafos={len(paragrafos)} metodo={metodo}")
    return build_result(
        True, titulo, texto, paragrafos,
        imagem, legenda, credito,
        metodo, "extraído via WordPress adapter"
    )
