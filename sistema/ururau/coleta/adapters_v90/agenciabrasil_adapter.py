"""agenciabrasil_adapter.py - Extração para Agência Brasil."""
import logging
from .helpers_v90 import (
    safe_get, get_soup, get_json_ld, find_json_ld_newsarticle,
    extract_paragraphs_from_soup, all_meaningful_paragraphs,
    titulo_from_soup, imagem_from_soup, legenda_from_soup,
    credito_from_soup, fallback_result, build_result,
)

logger = logging.getLogger(__name__)
PREFIX = "[v90][ADAPTER][AGENCIABRASIL]"


def extract(url: str, html: str = "") -> dict:
    result = fallback_result()
    result["metodo"] = "agenciabrasil"
    result["motivo"] = "extração Agência Brasil"

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
    metodo = "agenciabrasil/desconhecido"
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
                metodo = "agenciabrasil/json-ld"
                logger.info(f"{PREFIX} JSON-LD ok titulo={titulo[:60]}")
    except Exception as e:
        logger.warning(f"{PREFIX} JSON-LD falhou: {e}")

    # 2. article
    if not aceito:
        try:
            container = soup.find("article")
            if container:
                pars = extract_paragraphs_from_soup(container, None, min_len=30)
                if len(pars) >= 2:
                    paragrafos = pars
                    texto = "\n\n".join(paragrafos)
                    aceito = True
                    metodo = "agenciabrasil/article"
                    logger.info(f"{PREFIX} article ok")
        except Exception as e:
            logger.warning(f"{PREFIX} article falhou: {e}")

    # 3. .content-body
    if not aceito:
        try:
            container = soup.select_one(".content-body")
            if container:
                pars = extract_paragraphs_from_soup(container, None, min_len=30)
                if pars:
                    paragrafos = pars
                    texto = "\n\n".join(paragrafos)
                    aceito = True
                    metodo = "agenciabrasil/content-body"
                    logger.info(f"{PREFIX} content-body ok")
        except Exception as e:
            logger.warning(f"{PREFIX} content-body falhou: {e}")

    # 4. .texto-materia / .conteudo / .noticia-texto
    if not aceito:
        for sel in (".texto-materia", ".conteudo", ".noticia-texto", ".news", ".content", "main"):
            try:
                container = soup.select_one(sel)
                if container:
                    pars = extract_paragraphs_from_soup(container, None, min_len=30)
                    if len(pars) >= 2:
                        paragrafos = pars
                        texto = "\n\n".join(paragrafos)
                        aceito = True
                        metodo = f"agenciabrasil/{sel}"
                        logger.info(f"{PREFIX} {sel} ok")
                        break
            except Exception as e:
                logger.warning(f"{PREFIX} {sel} falhou: {e}")

    # 5. RSS como fallback (apenas log, sem requisição real)
    if not aceito:
        try:
            for link in soup.find_all("link", rel="alternate"):
                if link.get("type", "") in ("application/rss+xml", "application/atom+xml"):
                    rss_href = link.get("href", "")
                    if rss_href:
                        logger.info(f"{PREFIX} RSS hint encontrado={rss_href}")
                        # Marca que poderíamos usar RSS se tivéssemos o feed
                        break
        except Exception as e:
            logger.warning(f"{PREFIX} RSS hint falhou: {e}")

    # 6. Fallback parágrafos
    if not aceito:
        try:
            paragrafos = all_meaningful_paragraphs(soup, min_len=40)
            if paragrafos:
                texto = "\n\n".join(paragrafos)
                aceito = True
                metodo = "agenciabrasil/fallback-p"
                logger.info(f"{PREFIX} fallback-p ok")
        except Exception as e:
            logger.warning(f"{PREFIX} fallback-p falhou: {e}")

    if not aceito or not paragrafos:
        result["motivo"] = "Não foi possível extrair conteúdo da Agência Brasil"
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
        metodo, "extraído via Agência Brasil adapter"
    )
