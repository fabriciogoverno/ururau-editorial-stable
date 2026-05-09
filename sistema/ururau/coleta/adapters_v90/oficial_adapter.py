"""oficial_adapter.py - Extração para sites oficiais do governo."""
import logging
from .helpers_v90 import (
    safe_get, get_soup, get_json_ld, find_json_ld_newsarticle,
    extract_paragraphs_from_soup, all_meaningful_paragraphs,
    titulo_from_soup, imagem_from_soup, legenda_from_soup,
    credito_from_soup, fallback_result, build_result,
)

logger = logging.getLogger(__name__)
PREFIX = "[v90][ADAPTER][OFICIAL]"


def extract(url: str, html: str = "") -> dict:
    result = fallback_result()
    result["metodo"] = "oficial"
    result["motivo"] = "extração site oficial do governo"

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
    metodo = "oficial/desconhecido"
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
                metodo = "oficial/json-ld"
                logger.info(f"{PREFIX} JSON-LD ok titulo={titulo[:60]}")
    except Exception as e:
        logger.warning(f"{PREFIX} JSON-LD falhou: {e}")

    # 2. article/main
    if not aceito:
        for sel in ("article", "main"):
            try:
                container = soup.find(sel)
                if container:
                    pars = extract_paragraphs_from_soup(container, None, min_len=30)
                    if len(pars) >= 2:
                        paragrafos = pars
                        texto = "\n\n".join(paragrafos)
                        aceito = True
                        metodo = f"oficial/{sel}"
                        logger.info(f"{PREFIX} {sel} ok")
                        break
            except Exception as e:
                logger.warning(f"{PREFIX} {sel} falhou: {e}")

    # 3. .documentDescription / .documento / .noticia / .conteudo
    if not aceito:
        for sel in (
            ".documentDescription",
            ".documento",
            ".noticia",
            ".conteudo",
            ".content",
            ".texto",
            ".news",
            ".release",
            ".press",
            ".pauta",
            ".materia",
        ):
            try:
                container = soup.select_one(sel)
                if container:
                    pars = extract_paragraphs_from_soup(container, None, min_len=30)
                    if len(pars) >= 2:
                        paragrafos = pars
                        texto = "\n\n".join(paragrafos)
                        aceito = True
                        metodo = f"oficial/{sel}"
                        logger.info(f"{PREFIX} {sel} ok")
                        break
            except Exception as e:
                logger.warning(f"{PREFIX} {sel} falhou: {e}")

    # 4. Tabelas de conteúdo (sites governamentais costumam usar tabelas)
    if not aceito:
        try:
            tables = soup.find_all("table")
            for tbl in tables:
                cells = tbl.find_all("td")
                texts = []
                for td in cells:
                    txt = td.get_text(strip=True)
                    if len(txt) > 60:
                        texts.append(txt)
                if len(texts) >= 2:
                    paragrafos = texts
                    texto = "\n\n".join(paragrafos)
                    aceito = True
                    metodo = "oficial/table"
                    logger.info(f"{PREFIX} table ok")
                    break
        except Exception as e:
            logger.warning(f"{PREFIX} table falhou: {e}")

    # 5. Fallback parágrafos
    if not aceito:
        try:
            paragrafos = all_meaningful_paragraphs(soup, min_len=40)
            if paragrafos:
                texto = "\n\n".join(paragrafos)
                aceito = True
                metodo = "oficial/fallback-p"
                logger.info(f"{PREFIX} fallback-p ok")
        except Exception as e:
            logger.warning(f"{PREFIX} fallback-p falhou: {e}")

    if not aceito or not paragrafos:
        result["motivo"] = "Não foi possível extrair conteúdo do site oficial"
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
        metodo, "extraído via oficial adapter"
    )
