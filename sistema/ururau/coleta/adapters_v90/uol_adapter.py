"""uol_adapter.py - Extração para UOL."""
import re
import json
import logging
from .helpers_v90 import (
    safe_get, get_soup, get_json_ld, find_json_ld_newsarticle,
    extract_paragraphs_from_soup, all_meaningful_paragraphs,
    titulo_from_soup, imagem_from_soup, legenda_from_soup,
    credito_from_soup, fallback_result, build_result,
)

logger = logging.getLogger(__name__)
PREFIX = "[v90][ADAPTER][UOL]"


def extract(url: str, html: str = "") -> dict:
    result = fallback_result()
    result["metodo"] = "uol"
    result["motivo"] = "extração UOL"

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
    metodo = "uol/desconhecido"
    aceito = False

    # 1. JSON-LD
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
                metodo = "uol/json-ld"
                logger.info(f"{PREFIX} JSON-LD ok titulo={titulo[:60]}")
    except Exception as e:
        logger.warning(f"{PREFIX} JSON-LD falhou: {e}")

    # 2. Canonical (apenas log, não usamos como extração direta)
    if not aceito:
        try:
            link = soup.find("link", rel="canonical")
            if link:
                canonical = link.get("href", "")
                logger.info(f"{PREFIX} canonical={canonical}")
        except Exception as e:
            logger.warning(f"{PREFIX} canonical falhou: {e}")

    # 3. article.mainContent ou .texto
    if not aceito:
        for sel in ("article.mainContent", ".mainContent", ".texto", ".conteudo", "article", ".content"):
            try:
                container = soup.select_one(sel)
                if container:
                    pars = extract_paragraphs_from_soup(container, None, min_len=30)
                    if len(pars) >= 2:
                        paragrafos = pars
                        texto = "\n\n".join(paragrafos)
                        aceito = True
                        metodo = f"uol/{sel}"
                        logger.info(f"{PREFIX} {sel} ok")
                        break
            except Exception as e:
                logger.warning(f"{PREFIX} {sel} falhou: {e}")

    # 4. Scripts internos com dados (UOL às vezes embarca dados em script)
    if not aceito:
        try:
            for script in soup.find_all("script"):
                txt = script.string or ""
                # Procura por objetos javascript que contenham texto do artigo
                if "texto" in txt or "conteudo" in txt:
                    match = re.search(r'"texto"\s*:\s*"(.*?)"', txt, re.DOTALL)
                    if match:
                        raw = match.group(1)
                        # Remove escapes
                        raw = raw.replace('\\n', '\n').replace('\\t', '\t')
                        if len(raw) > 200:
                            paragrafos = [p.strip() for p in raw.split("\n") if len(p.strip()) > 20]
                            if paragrafos:
                                texto = "\n\n".join(paragrafos)
                                aceito = True
                                metodo = "uol/script-texto"
                                logger.info(f"{PREFIX} script-texto ok")
                                break
        except Exception as e:
            logger.warning(f"{PREFIX} script interno falhou: {e}")

    # 5. Fallback parágrafos
    if not aceito:
        try:
            paragrafos = all_meaningful_paragraphs(soup, min_len=40)
            if paragrafos:
                texto = "\n\n".join(paragrafos)
                aceito = True
                metodo = "uol/fallback-p"
                logger.info(f"{PREFIX} fallback-p ok")
        except Exception as e:
            logger.warning(f"{PREFIX} fallback-p falhou: {e}")

    if not aceito or not paragrafos:
        result["motivo"] = "Não foi possível extrair conteúdo do UOL"
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
        metodo, "extraído via UOL adapter"
    )
