"""globo_adapter.py - Extração para sites Globo (G1, Globo.com etc)."""
import re
import json
import logging
from .helpers_v90 import (
    safe_get, get_soup, get_json_ld, find_json_ld_newsarticle,
    extract_paragraphs_from_soup, all_meaningful_paragraphs,
    titulo_from_soup, imagem_from_soup, legenda_from_soup,
    credito_from_soup, og_meta, fallback_result, build_result,
)

logger = logging.getLogger(__name__)
PREFIX = "[v90][ADAPTER][GLOBO]"


def extract(url: str, html: str = "") -> dict:
    result = fallback_result()
    result["metodo"] = "globo"
    result["motivo"] = "extração G1/Globo"

    soup = get_soup(html)
    if not soup:
        result["motivo"] = "HTML vazio ou inválido"
        return result

    titulo = ""
    texto = ""
    paragrafos = []
    imagem = None
    legenda = None
    credito = None
    metodo = "globo/desconhecido"
    aceito = False

    # 1. JSON-LD (Globo usa muito)
    try:
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
                metodo = "globo/json-ld"
                logger.info(f"{PREFIX} JSON-LD ok titulo={titulo[:60]}")
    except Exception as e:
        logger.warning(f"{PREFIX} JSON-LD falhou: {e}")

    # 2. __NEXT_DATA__ script (Next.js do Globo)
    if not aceito:
        try:
            for script in soup.find_all("script"):
                txt = script.string or ""
                if "__NEXT_DATA__" in txt and "props" in txt:
                    # Extrai JSON do window.__NEXT_DATA__ = {...}
                    match = re.search(r'window\.__NEXT_DATA__\s*=\s*({.*?});?\s*$', txt, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                        page_props = safe_get(data, "props", {})
                        page_props = safe_get(page_props, "pageProps", page_props)
                        # Busca por artigo
                        art = safe_get(page_props, "article", {})
                        if not art:
                            # busca recursivamente
                            def _find_article(d):
                                if isinstance(d, dict):
                                    if "headline" in d and "body" in d:
                                        return d
                                    for v in d.values():
                                        r = _find_article(v)
                                        if r:
                                            return r
                                elif isinstance(d, list):
                                    for item in d:
                                        r = _find_article(item)
                                        if r:
                                            return r
                                return None
                            art = _find_article(page_props) or {}
                        if art:
                            titulo = titulo or safe_get(art, "headline", "")
                            body = safe_get(art, "body", "")
                            if body:
                                paragrafos = [p.strip() for p in body.split("\n") if len(p.strip()) > 20]
                                if not paragrafos:
                                    paragrafos = [body]
                                texto = "\n\n".join(paragrafos)
                                aceito = True
                                metodo = "globo/next-data"
                                logger.info(f"{PREFIX} NEXT_DATA ok titulo={titulo[:60]}")
                                break
        except Exception as e:
            logger.warning(f"{PREFIX} NEXT_DATA falhou: {e}")

    # 3. article com classe .content
    if not aceito:
        try:
            for sel in ("article.content", "article", ".content", ".mc-body", ".multicontent"):
                container = soup.select_one(sel)
                if container:
                    pars = extract_paragraphs_from_soup(container, None, min_len=30)
                    if len(pars) >= 2:
                        paragrafos = pars
                        texto = "\n\n".join(paragrafos)
                        aceito = True
                        metodo = f"globo/article-{sel}"
                        logger.info(f"{PREFIX} {sel} ok")
                        break
        except Exception as e:
            logger.warning(f"{PREFIX} article falhou: {e}")

    # 4. Og:title, og:description
    if not titulo:
        try:
            og_tit = og_meta(soup, "title")
            if og_tit:
                titulo = og_tit
        except Exception as e:
            logger.warning(f"{PREFIX} og:title falhou: {e}")

    # 5. Fallback parágrafos
    if not aceito:
        try:
            paragrafos = all_meaningful_paragraphs(soup, min_len=40)
            if paragrafos:
                texto = "\n\n".join(paragrafos)
                aceito = True
                metodo = "globo/fallback-p"
                logger.info(f"{PREFIX} fallback-p ok")
        except Exception as e:
            logger.warning(f"{PREFIX} fallback-p falhou: {e}")

    if not aceito or not paragrafos:
        result["motivo"] = "Não foi possível extrair conteúdo do Globo"
        return result

    if len(texto) < 150:
        result["motivo"] = f"Texto muito curto ({len(texto)} chars)"
        return result

    titulo = titulo or titulo_from_soup(soup, prefer_h1=True)
    imagem = imagem or imagem_from_soup(soup)
    legenda = legenda or legenda_from_soup(soup)
    credito = credito or credito_from_soup(soup)

    logger.info(f"{PREFIX} Aceito paragrafos={len(paragrafos)} metodo={metodo}")
    return build_result(
        True, titulo, texto, paragrafos,
        imagem, legenda, credito,
        metodo, "extraído via Globo adapter"
    )
