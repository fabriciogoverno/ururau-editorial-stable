"""
extract_pipeline_v90.py
Pipeline principal de extração de matérias do Ururau v90.

Testa múltiplas estratégias de extração com fallback automático:
1. Adaptador específico por tipo de site
2. JSON-LD NewsArticle/Article
3. articleBody (itemprop)
4. __NEXT_DATA__ (Next.js)
5. Scripts JSON públicos
6. WordPress REST API
7. article/main/content por densidade de parágrafos
8. AMP
9. mobile (logado, não usado)
10. impressão (logado, não usado)
11. Scrapling opcional
12. Playwright headless opcional

Cada estratégia é isolada em try/except. Nenhuma exceção sobe —
sempre retorna dict com status preenchido.
"""

import json
import logging
import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ururau.coleta.adapters_v90 import get_adapter
from ururau.coleta.adapters_v90.helpers_v90 import (
    all_meaningful_paragraphs,
    build_result,
    extract_paragraphs_from_soup,
    fallback_result,
    find_json_ld_newsarticle,
    get_json_ld,
    get_soup,
    imagem_from_soup,
    legenda_from_soup,
    credito_from_soup,
    titulo_from_soup,
)
from ururau.coleta.criterio_aceite_v90 import avaliar_aceite_editorial_v90
from ururau.coleta.source_quality_v90 import registrar_falha, registrar_sucesso
from ururau.coleta.url_variants_v90 import gerar_variantes_url_v90

logger = logging.getLogger(__name__)
PREFIX = "[v90][EXTRACT]"



def _ler_texto_utf8_v200_18(r) -> str:
    """V200_18: decodifica response forcando UTF-8 quando necessario.

    A Folha/Estadao/Globo servem UTF-8 mas o header HTTP as vezes
    declara ISO-8859-1 ou nao declara. O requests confia no header
    e cai em Latin-1, gerando "RevoluÃ§Ã£o" em vez de "Revolucao".
    """
    try:
        raw = r.content or b""
        if not raw:
            return ""
        enc_header = (r.encoding or "").lower()
        try:
            sample = raw[:2048].decode("ascii", errors="ignore").lower()
            if 'charset=utf-8' in sample or 'charset="utf-8"' in sample:
                return raw.decode("utf-8", errors="replace")
            if 'charset=iso-8859-1' in sample or 'charset=latin-1' in sample:
                return raw.decode("iso-8859-1", errors="replace")
        except Exception:
            pass
        if enc_header in ("iso-8859-1", "latin-1", "latin1", "windows-1252", ""):
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("iso-8859-1", errors="replace")
        return r.text or ""
    except Exception:
        return r.text or ""


def _env_bool(nome: str, padrao: bool = False) -> bool:
    raw = str(os.getenv(nome, "1" if padrao else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao



# Etapa 3+4 do plano premium (13/05/2026): aprende qual estrategia
# funciona melhor para cada dominio e re-prioriza a ordem.
try:
    from ururau.coleta.pipeline_inteligente_v200 import (
        registrar_resultado as _pi_registrar,
        ordem_recomendada_para_url as _pi_ordem,
    )
    _PIPELINE_INTELIGENTE_OK = True
except Exception:
    _PIPELINE_INTELIGENTE_OK = False
    def _pi_registrar(*a, **kw): pass
    def _pi_ordem(url, ordem_default=None): return list(ordem_default or ())


def _url_invalida_para_materia_v91b(url: str) -> tuple[bool, str]:
    if not url or not isinstance(url, str):
        return True, "url_vazia"
    u = url.strip().lower()
    if not (u.startswith("http://") or u.startswith("https://")):
        return True, "url_nao_http"
    parsed = urlparse(u)
    dominio = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()
    if any(x in dominio for x in ("lh3.googleusercontent.com", "googleusercontent.com", "gstatic.com", "ggpht.com", "ytimg.com")):
        return True, f"dominio_asset:{dominio}"
    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".css", ".js", ".pdf")):
        return True, "extensao_asset"
    if any(t in path for t in ("/favicon", "/logo", "/avatar", "/thumbnail", "/thumb", "/wp-content/uploads/", "/static/", "/assets/", "/images/", "/img/")):
        return True, "path_asset"
    if "googleusercontent" in dominio and ("w16" in query or "w32" in query or "w64" in query):
        return True, "thumb_google_news"
    return False, ""


# Headers realistas de navegador
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.0 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.0"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "max-age=0",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def safe_get(obj, key, default=None):
    """Helper seguro para evitar AttributeError em dict.get()."""
    return obj.get(key, default) if isinstance(obj, dict) else default


def _resultado_bloqueado(url_final: str, motivo: str, tentativas: list) -> dict:
    """Monta o dict de resultado quando todas as estratégias falham."""
    return {
        "aceita": False,
        "status": "bloqueada",
        "titulo": "",
        "texto": "",
        "paragrafos": [],
        "imagem": None,
        "legenda": None,
        "credito": None,
        "url_final": url_final,
        "metodo": "bloqueada",
        "motivo": motivo,
        "tentativas": tentativas,
    }


def _resultado_ok(
    url_final: str,
    titulo: str,
    texto: str,
    paragrafos: list,
    imagem: str | None,
    legenda: str | None,
    credito: str | None,
    metodo: str,
    motivo: str,
    tentativas: list,
    status: str = "ok",
) -> dict:
    """Monta o dict de resultado aceito."""
    return {
        "aceita": True,
        "status": status,
        "titulo": titulo,
        "texto": texto,
        "paragrafos": paragrafos,
        "imagem": imagem,
        "legenda": legenda,
        "credito": credito,
        "url_final": url_final,
        "metodo": metodo,
        "motivo": motivo,
        "tentativas": tentativas,
    }


def _fazer_requisicao(url: str, timeout: int = 20, headers: dict | None = None) -> tuple:
    """
    Faz requisição HTTP e retorna (html, url_final).
    Em caso de erro, retorna ("", url).
    """
    hs = headers or _BROWSER_HEADERS
    try:
        resp = requests.get(url, headers=hs, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        html = _ler_texto_utf8_v200_18(resp)
        url_final = resp.url
        logger.info("%s Requisicao OK url=%s final=%s status=%d len_html=%d",
                    PREFIX, url, url_final, resp.status_code, len(html) if html else 0)
        return html, url_final
    except requests.exceptions.Timeout:
        logger.warning("%s Timeout ao carregar URL=%s", PREFIX, url)
        return "", url
    except requests.exceptions.HTTPError as e:
        # v1.15.4: sinaliza 403/401/451 (bloqueios anti-bot) para que o caller
        # nao tente bypass inutilmente e o usuario veja o motivo real.
        try:
            _status = getattr(e.response, "status_code", 0) or 0
        except Exception:
            _status = 0
        if _status in (401, 403, 451):
            logger.warning("%s BLOQUEIO_ANTI_BOT %d url=%s", PREFIX, _status, url)
            # Retorna marcador especial que extrair_materia_v90 reconhece.
            return f"__HTTP_BLOCK_{_status}__", url
        logger.warning("%s HTTPError url=%s erro=%s", PREFIX, url, e)
        return "", url
    except requests.exceptions.ConnectionError as e:
        logger.warning("%s ConnectionError url=%s erro=%s", PREFIX, url, e)
        return "", url
    except Exception as e:
        logger.warning("%s Erro requisicao url=%s erro=%s", PREFIX, url, e)
        return "", url


def _estrategia_json_ld(soup: BeautifulSoup, tentativas: list) -> dict | None:
    """
    Estratégia A: JSON-LD NewsArticle/Article.
    Retorna dict com dados extraídos ou None se falhar.
    """
    metodo = "json-ld"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        scripts = get_json_ld(soup)
        article = find_json_ld_newsarticle(scripts)
        if article:
            titulo = safe_get(article, "headline", "")
            texto = safe_get(article, "articleBody", "")
            img_data = safe_get(article, "image", {})
            imagem = None
            if isinstance(img_data, dict):
                imagem = safe_get(img_data, "url", None)
            elif isinstance(img_data, str):
                imagem = img_data
            descricao = safe_get(article, "description", "")

            if titulo and texto:
                paragrafos = [p.strip() for p in texto.split("\n") if len(p.strip()) > 20]
                if not paragrafos:
                    paragrafos = [texto]
                logger.info("%s metodo=%s SUCESSO titulo=%s", PREFIX, metodo, titulo[:60])
                tentativas.append({"metodo": metodo, "status": "sucesso"})
                return {
                    "titulo": titulo,
                    "texto": texto,
                    "paragrafos": paragrafos,
                    "imagem": imagem,
                    "legenda": None,
                    "credito": None,
                    "metodo": metodo,
                    "motivo": "extraido via JSON-LD NewsArticle",
                }
            if titulo and descricao and not texto:
                # Pelo menos temos título + descrição
                logger.info("%s metodo=%s parcial: so tem descricao, nao articleBody", PREFIX, metodo)

        logger.info("%s metodo=%s falhou: nenhum JSON-LD valido", PREFIX, metodo)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": "nenhum JSON-LD valido"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)})
        return None


def _estrategia_articlebody(soup: BeautifulSoup, tentativas: list) -> dict | None:
    """
    Estratégia B: articleBody via itemprop.
    Retorna dict com dados extraídos ou None se falhar.
    """
    metodo = "articleBody"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        body_el = soup.find(attrs={"itemprop": "articleBody"})
        if not body_el:
            # Tentar também por role e outras marcações
            body_el = soup.find(attrs={"role": "article"}) or soup.find("article")

        if body_el:
            paragrafos = extract_paragraphs_from_soup(body_el, None, min_len=30)
            if paragrafos and len(paragrafos) >= 1:
                texto = "\n\n".join(paragrafos)
                titulo = titulo_from_soup(soup, prefer_h1=True)
                imagem = imagem_from_soup(soup)
                legenda = legenda_from_soup(soup)
                credito = credito_from_soup(soup)
                if len(texto) >= 100:
                    logger.info("%s metodo=%s SUCESSO paragrafos=%d", PREFIX, metodo, len(paragrafos))
                    tentativas.append({"metodo": metodo, "status": "sucesso"})
                    return {
                        "titulo": titulo,
                        "texto": texto,
                        "paragrafos": paragrafos,
                        "imagem": imagem,
                        "legenda": legenda,
                        "credito": credito,
                        "metodo": metodo,
                        "motivo": "extraido via articleBody/itemprop",
                    }

        logger.info("%s metodo=%s falhou: nenhum articleBody encontrado", PREFIX, metodo)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": "nenhum articleBody encontrado"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)})
        return None


def _estrategia_next_data(soup: BeautifulSoup, html: str, tentativas: list) -> dict | None:
    """
    Estratégia C: __NEXT_DATA__ (Next.js).
    Retorna dict com dados extraídos ou None se falhar.
    """
    metodo = "__NEXT_DATA__"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        for script in soup.find_all("script"):
            txt = script.string or ""
            if "__NEXT_DATA__" in txt and "props" in txt:
                match = re.search(r'window\.__NEXT_DATA__\s*=\s*({.*?});?\s*$', txt, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    page_props = safe_get(data, "props", {})
                    page_props = safe_get(page_props, "pageProps", page_props)

                    # Busca recursiva por artigo
                    def _find_article(d):
                        if isinstance(d, dict):
                            if "headline" in d and ("body" in d or "articleBody" in d or "text" in d):
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
                        titulo = safe_get(art, "headline", "")
                        body = safe_get(art, "body", "") or safe_get(art, "articleBody", "") or safe_get(art, "text", "")
                        if body:
                            paragrafos = [p.strip() for p in body.split("\n") if len(p.strip()) > 20]
                            if not paragrafos:
                                paragrafos = [body]
                            texto = "\n\n".join(paragrafos)
                            img_data = safe_get(art, "image", {})
                            imagem = None
                            if isinstance(img_data, dict):
                                imagem = safe_get(img_data, "url", None)
                            elif isinstance(img_data, str):
                                imagem = img_data
                            if titulo and texto:
                                logger.info("%s metodo=%s SUCESSO titulo=%s", PREFIX, metodo, titulo[:60])
                                tentativas.append({"metodo": metodo, "status": "sucesso"})
                                return {
                                    "titulo": titulo,
                                    "texto": texto,
                                    "paragrafos": paragrafos,
                                    "imagem": imagem,
                                    "legenda": None,
                                    "credito": None,
                                    "metodo": metodo,
                                    "motivo": "extraido via __NEXT_DATA__",
                                }

        logger.info("%s metodo=%s falhou: nenhum __NEXT_DATA__ valido", PREFIX, metodo)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": "nenhum __NEXT_DATA__ valido"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)})
        return None


def _estrategia_scripts_json(soup: BeautifulSoup, tentativas: list) -> dict | None:
    """
    Estratégia D: Scripts JSON públicos (dados estruturados em <script>).
    Retorna dict com dados extraídos ou None se falhar.
    """
    metodo = "scripts-json"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        for script in soup.find_all("script", type="application/json"):
            try:
                raw = script.string or ""
                if not raw or len(raw) < 100:
                    continue
                data = json.loads(raw, strict=False)
                # Busca recursiva por conteúdo de artigo
                def _find_content(d, depth=0):
                    if depth > 10:
                        return None
                    if isinstance(d, dict):
                        # Campos comuns de artigo
                        headline = safe_get(d, "headline", "") or safe_get(d, "title", "")
                        body = (
                            safe_get(d, "articleBody", "")
                            or safe_get(d, "body", "")
                            or safe_get(d, "text", "")
                            or safe_get(d, "content", "")
                            or safe_get(d, "description", "")
                        )
                        if headline and body and len(body) > 100:
                            return {"headline": headline, "body": body, "image": safe_get(d, "image", {})}
                        for v in d.values():
                            r = _find_content(v, depth + 1)
                            if r:
                                return r
                    elif isinstance(d, list) and depth < 5:
                        for item in d:
                            r = _find_content(item, depth + 1)
                            if r:
                                return r
                    return None

                result = _find_content(data)
                if result:
                    titulo = result["headline"]
                    body = result["body"]
                    paragrafos = [p.strip() for p in body.split("\n") if len(p.strip()) > 20]
                    if not paragrafos:
                        paragrafos = [body]
                    texto = "\n\n".join(paragrafos)
                    img_data = result.get("image", {})
                    imagem = None
                    if isinstance(img_data, dict):
                        imagem = safe_get(img_data, "url", None)
                    elif isinstance(img_data, str):
                        imagem = img_data
                    logger.info("%s metodo=%s SUCESSO titulo=%s", PREFIX, metodo, titulo[:60])
                    tentativas.append({"metodo": metodo, "status": "sucesso"})
                    return {
                        "titulo": titulo,
                        "texto": texto,
                        "paragrafos": paragrafos,
                        "imagem": imagem,
                        "legenda": None,
                        "credito": None,
                        "metodo": metodo,
                        "motivo": "extraido via script JSON publico",
                    }
            except Exception:
                continue

        logger.info("%s metodo=%s falhou: nenhum script JSON valido", PREFIX, metodo)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": "nenhum script JSON valido"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)})
        return None


def _estrategia_wordpress_rest(url: str, soup: BeautifulSoup, html: str, tentativas: list) -> dict | None:
    """
    Estratégia E: WordPress REST API.
    Só tenta se o site parecer WordPress.
    Retorna dict com dados extraídos ou None se falhar.
    """
    metodo = "wordpress-rest"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)

    # Verificar se parece WordPress
    parece_wp = False
    if html and isinstance(html, str):
        if "/wp-content/" in html or "wp-includes" in html or "/wp-json/" in html:
            parece_wp = True
        if not parece_wp and soup:
            meta = soup.find("meta", attrs={"name": "generator"})
            if meta and "WordPress" in (meta.get("content", "") or ""):
                parece_wp = True

    if not parece_wp:
        logger.info("%s metodo=%s pulado: nao parece WordPress", PREFIX, metodo)
        tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "nao parece WordPress"})
        return None

    try:
        parsed = urlparse(url)
        slug = parsed.path.strip("/").split("/")[-1] if parsed.path else ""
        slug = re.sub(r"\.[a-zA-Z]+$", "", slug)  # remover extensão
        if not slug or len(slug) < 2:
            logger.info("%s metodo=%s falhou: slug invalido", PREFIX, metodo)
            tentativas.append({"metodo": metodo, "status": "falha", "motivo": "slug invalido"})
            return None

        base = f"{parsed.scheme}://{parsed.netloc}"
        api_url = f"{base}/wp-json/wp/v2/posts?slug={slug}&_embed"

        logger.info("%s metodo=%s tentando API: %s", PREFIX, metodo, api_url)
        resp = requests.get(api_url, headers=_BROWSER_HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                post = data[0]
                titulo_html = safe_get(safe_get(post, "title", {}), "rendered", "")
                conteudo_html = safe_get(safe_get(post, "content", {}), "rendered", "")
                if titulo_html and conteudo_html:
                    # Parse HTML do conteúdo para extrair parágrafos
                    content_soup = BeautifulSoup(conteudo_html, "html.parser")
                    paragrafos = [p.get_text(strip=True) for p in content_soup.find_all("p") if len(p.get_text(strip=True)) > 20]
                    if not paragrafos:
                        # Tentar extrair todo texto
                        texto_limpo = content_soup.get_text(separator="\n", strip=True)
                        paragrafos = [p.strip() for p in texto_limpo.split("\n") if len(p.strip()) > 20]
                    texto = "\n\n".join(paragrafos) if paragrafos else content_soup.get_text(strip=True)

                    # Imagem do _embed
                    imagem = None
                    embedded = safe_get(post, "_embedded", {})
                    featured_media = safe_get(embedded, "wp:featuredmedia", [])
                    if featured_media and len(featured_media) > 0:
                        media_details = safe_get(featured_media[0], "media_details", {})
                        sizes = safe_get(media_details, "sizes", {})
                        if "full" in sizes:
                            imagem = safe_get(sizes["full"], "source_url", None)
                        elif "large" in sizes:
                            imagem = safe_get(sizes["large"], "source_url", None)
                        if not imagem:
                            imagem = safe_get(featured_media[0], "source_url", None)

                    # Limpar título de HTML
                    titulo_soup = BeautifulSoup(titulo_html, "html.parser")
                    titulo = titulo_soup.get_text(strip=True)

                    if titulo and texto and len(texto) > 100:
                        logger.info("%s metodo=%s SUCESSO titulo=%s", PREFIX, metodo, titulo[:60])
                        tentativas.append({"metodo": metodo, "status": "sucesso"})
                        return {
                            "titulo": titulo,
                            "texto": texto,
                            "paragrafos": paragrafos,
                            "imagem": imagem,
                            "legenda": None,
                            "credito": None,
                            "metodo": metodo,
                            "motivo": "extraido via WordPress REST API",
                        }

        # Tentar pages também
        api_page_url = f"{base}/wp-json/wp/v2/pages?slug={slug}&_embed"
        logger.info("%s metodo=%s tentando pages API: %s", PREFIX, metodo, api_page_url)
        resp = requests.get(api_page_url, headers=_BROWSER_HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                page = data[0]
                titulo_html = safe_get(safe_get(page, "title", {}), "rendered", "")
                conteudo_html = safe_get(safe_get(page, "content", {}), "rendered", "")
                if titulo_html and conteudo_html:
                    content_soup = BeautifulSoup(conteudo_html, "html.parser")
                    paragrafos = [p.get_text(strip=True) for p in content_soup.find_all("p") if len(p.get_text(strip=True)) > 20]
                    if not paragrafos:
                        texto_limpo = content_soup.get_text(separator="\n", strip=True)
                        paragrafos = [p.strip() for p in texto_limpo.split("\n") if len(p.strip()) > 20]
                    texto = "\n\n".join(paragrafos) if paragrafos else content_soup.get_text(strip=True)
                    titulo_soup = BeautifulSoup(titulo_html, "html.parser")
                    titulo = titulo_soup.get_text(strip=True)
                    if titulo and texto and len(texto) > 100:
                        logger.info("%s metodo=%s SUCESSO (page) titulo=%s", PREFIX, metodo, titulo[:60])
                        tentativas.append({"metodo": f"{metodo}-pages", "status": "sucesso"})
                        return {
                            "titulo": titulo,
                            "texto": texto,
                            "paragrafos": paragrafos,
                            "imagem": None,
                            "legenda": None,
                            "credito": None,
                            "metodo": f"{metodo}-pages",
                            "motivo": "extraido via WordPress REST API (pages)",
                        }

        logger.info("%s metodo=%s falhou: API nao retornou dados validos", PREFIX, metodo)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": "API nao retornou dados validos"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)})
        return None


def _estrategia_densidade_paragrafos(soup: BeautifulSoup, tentativas: list) -> dict | None:
    """
    Estratégia F: article/main/content por densidade de parágrafos.
    Retorna dict com dados extraídos ou None se falhar.

    CORRECAO (fix/extracao-causa-raiz-sem-bloqueio):
    Antes de aplicar os seletores, REMOVE do soup os elementos
    contaminadores tipicos (nav, header, footer, aside, .sidebar,
    .related, .newsletter, .login, ads). Sem isso, sites como RJNEWS
    em que o <article> ou <main> envolve a pagina inteira retornavam
    home/listagem/login/rodape misturado como se fosse o artigo.
    """
    metodo = "densidade-paragrafos"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        # PRE-LIMPEZA: trabalhar em uma copia limpa do soup.
        try:
            from ururau.coleta.extracao_limpa_v200 import limpar_html_para_extracao
            soup_clean = limpar_html_para_extracao(soup) or soup
        except Exception:
            soup_clean = soup
        soup = soup_clean
        melhor_container = None
        melhor_count = 0
        melhor_sel = ""

        seletores = [
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
            ".texto-noticia",
            ".texto-materia",
            ".mainContent",
            "section",
            # v1.15.4: seletores observados em portais regionais BR.
            ".segundo",       # campos24horas.com.br
            ".materia",
            ".noticia",
            ".post",
            "#materia",
            "#noticia",
            ".single-content",
            ".td-post-content",
            ".elementor-widget-theme-post-content",
            "#post-content",
            ".post-body",
        ]

        for sel in seletores:
            try:
                container = soup.select_one(sel)
                if container:
                    paras = container.find_all("p")
                    count = len(paras)
                    total_len = sum(len(p.get_text(strip=True)) for p in paras)
                    # Score = número de parágrafos * comprimento médio
                    score = count * (total_len / max(count, 1))
                    if count >= melhor_count and total_len > 100:
                        melhor_container = container
                        melhor_count = count
                        melhor_sel = sel
            except Exception:
                continue

        # v1.15.4 AUTO-DISCOVERY: se nenhum seletor predefinido teve >=2 paragrafos,
        # examina TODAS as divs e procura a que tem maior densidade real de texto.
        # Isso garante que sites com classes desconhecidas/customizadas funcionem.
        if not melhor_container or melhor_count < 2:
            try:
                from bs4 import BeautifulSoup as _BS
                # Itera por todas as divs ordenadas por quantos <p> longos contem
                candidatos = []
                for div in soup.find_all(["div", "section", "main"]):
                    paras_div = div.find_all("p", recursive=True)
                    bons = [p for p in paras_div if len(p.get_text(strip=True)) >= 50]
                    if len(bons) >= 2:
                        soma = sum(len(p.get_text(strip=True)) for p in bons)
                        # penaliza containers gigantes (provavel home/listagem)
                        # bonus para containers com poucos <a> proporcional ao texto
                        n_links = len(div.find_all("a"))
                        # ratio: texto/links - matérias tem MUITO texto e poucos links
                        ratio = soma / max(n_links, 1)
                        candidatos.append((len(bons), soma, ratio, div))
                # Escolhe o melhor: mais paragrafos longos E maior ratio texto/link
                candidatos.sort(key=lambda x: (x[2], x[0]), reverse=True)
                if candidatos:
                    _, soma, ratio, div_top = candidatos[0]
                    melhor_container = div_top
                    melhor_count = len(div_top.find_all("p"))
                    melhor_sel = "auto-discovery"
                    logger.info(
                        "%s metodo=%s auto-discovery achou container "
                        "(%d <p>, %d chars, ratio=%.1f)",
                        PREFIX, metodo, melhor_count, soma, ratio,
                    )
            except Exception as _e_auto:
                logger.info("%s auto-discovery falhou: %s", PREFIX, _e_auto)

        if melhor_container and melhor_count >= 2:
            paragrafos = extract_paragraphs_from_soup(melhor_container, None, min_len=30)
            if paragrafos and len(paragrafos) >= 2:
                texto = "\n\n".join(paragrafos)
                if len(texto) >= 150:
                    titulo = titulo_from_soup(soup, prefer_h1=True)
                    imagem = imagem_from_soup(soup)
                    legenda = legenda_from_soup(soup)
                    credito = credito_from_soup(soup)
                    logger.info("%s metodo=%s SUCESSO sel=%s paragrafos=%d",
                                PREFIX, metodo, melhor_sel, len(paragrafos))
                    tentativas.append({"metodo": metodo, "status": "sucesso", "seletor": melhor_sel})
                    return {
                        "titulo": titulo,
                        "texto": texto,
                        "paragrafos": paragrafos,
                        "imagem": imagem,
                        "legenda": legenda,
                        "credito": credito,
                        "metodo": metodo,
                        "motivo": f"extraido via densidade de paragrafos em {melhor_sel}",
                    }

        # Fallback: todos os <p> significativos
        paragrafos = all_meaningful_paragraphs(soup, min_len=40)
        if paragrafos and len(paragrafos) >= 2:
            texto = "\n\n".join(paragrafos)
            if len(texto) >= 150:
                titulo = titulo_from_soup(soup, prefer_h1=True)
                imagem = imagem_from_soup(soup)
                legenda = legenda_from_soup(soup)
                credito = credito_from_soup(soup)
                logger.info("%s metodo=%s SUCESSO (fallback-p) paragrafos=%d", PREFIX, metodo, len(paragrafos))
                tentativas.append({"metodo": f"{metodo}-fallback-p", "status": "sucesso"})
                return {
                    "titulo": titulo,
                    "texto": texto,
                    "paragrafos": paragrafos,
                    "imagem": imagem,
                    "legenda": legenda,
                    "credito": credito,
                    "metodo": f"{metodo}-fallback-p",
                    "motivo": "extraido via fallback de paragrafos <p>",
                }

        logger.info("%s metodo=%s falhou: nenhum container com densidade suficiente", PREFIX, metodo)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": "nenhum container com densidade suficiente"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)})
        return None


def _estrategia_amp(url: str, soup: BeautifulSoup, tentativas: list) -> dict | None:
    """
    Estratégia G: AMP (Accelerated Mobile Pages).
    Tenta encontrar e extrair conteúdo de versão AMP.
    Retorna dict com dados extraídos ou None se falhar.
    """
    metodo = "amp"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        # Verificar se a página atual é AMP
        is_amp = False
        html_tag = soup.find("html")
        if html_tag:
            attr = html_tag.get("amp") or html_tag.get("⚡") or html_tag.get("data-amp") or html_tag.get("amp-boilerplate")
            if attr is not None or soup.find("script", src=re.compile(r"cdn\.ampproject\.org")):
                is_amp = True

        amp_link = None
        if not is_amp:
            # Procurar link rel="amphtml"
            link_amp = soup.find("link", rel="amphtml")
            if link_amp:
                amp_link = link_amp.get("href", "")

        if amp_link:
            logger.info("%s metodo=%s carregando AMP: %s", PREFIX, metodo, amp_link)
            html_amp, url_amp = _fazer_requisicao(amp_link, timeout=15)
            if html_amp:
                soup = get_soup(html_amp)
                is_amp = True

        if not soup:
            logger.info("%s metodo=%s falhou: soup invalido", PREFIX, metodo)
            tentativas.append({"metodo": metodo, "status": "falha", "motivo": "soup invalido"})
            return None

        # Extrair de AMP
        # AMP usa <article> ou <div> com classe amp-content
        amp_selectors = [
            "article",
            ".amp-content",
            ".article-body",
            "main",
            '[role="main"]',
            ".content",
            ".post-content",
        ]

        for sel in amp_selectors:
            try:
                container = soup.select_one(sel)
                if container:
                    paragrafos = extract_paragraphs_from_soup(container, None, min_len=25)
                    if paragrafos and len(paragrafos) >= 2:
                        texto = "\n\n".join(paragrafos)
                        if len(texto) >= 100:
                            titulo = titulo_from_soup(soup, prefer_h1=True)
                            imagem = imagem_from_soup(soup)
                            logger.info("%s metodo=%s SUCESSO sel=%s paragrafos=%d",
                                        PREFIX, metodo, sel, len(paragrafos))
                            tentativas.append({"metodo": metodo, "status": "sucesso", "seletor": sel})
                            return {
                                "titulo": titulo,
                                "texto": texto,
                                "paragrafos": paragrafos,
                                "imagem": imagem,
                                "legenda": None,
                                "credito": None,
                                "metodo": metodo,
                                "motivo": f"extraido via AMP ({sel})",
                            }
            except Exception:
                continue

        logger.info("%s metodo=%s falhou: nenhum conteudo AMP encontrado", PREFIX, metodo)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": "nenhum conteudo AMP encontrado"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)})
        return None


def _estrategia_mobile(url: str, tentativas: list) -> dict | None:
    """
    Estratégia H: mobile.
    Não utilizada — apenas logada para rastreabilidade.
    """
    metodo = "mobile"
    logger.info("%s tentativa=%d metodo=%s [NAO UTILIZADA - apenas log]", PREFIX, len(tentativas) + 1, metodo)
    tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "estrategia mobile nao utilizada nesta versao"})
    return None


def _estrategia_impressao(url: str, tentativas: list) -> dict | None:
    """
    Estratégia I: impressão.
    Não utilizada — apenas logada para rastreabilidade.
    """
    metodo = "impressao"
    logger.info("%s tentativa=%d metodo=%s [NAO UTILIZADA - apenas log]", PREFIX, len(tentativas) + 1, metodo)
    tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "estrategia impressao nao utilizada nesta versao"})
    return None


def _prefixar_metodo_renderizado(resultado: dict, metodo_base: str) -> dict:
    out = dict(resultado or {})
    metodo_original = safe_get(out, "metodo", "html")
    motivo_original = safe_get(out, "motivo", "")
    out["metodo"] = f"{metodo_base}/{metodo_original}"
    out["motivo"] = (
        f"extraido apos renderizacao {metodo_base}: {motivo_original}"
        if motivo_original
        else f"extraido apos renderizacao {metodo_base}"
    )
    return out


def _extrair_trafilatura_html_renderizado(
    url: str,
    html: str,
    tentativas: list,
    metodo_base: str,
) -> dict | None:
    metodo = f"{metodo_base}/trafilatura-html"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        import trafilatura
    except ImportError:
        tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "biblioteca nao instalada"})
        return None

    try:
        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
            with_metadata=True,
            output_format="json",
            target_language="pt",
        )
        if not result:
            tentativas.append({"metodo": metodo, "status": "falha", "motivo": "extract retornou vazio"})
            return None

        d = json.loads(result)
        titulo = (d.get("title") or "").strip()
        texto = (d.get("text") or "").strip()
        imagem = d.get("image") or None
        autor = d.get("author") or ""
        if texto and len(texto) >= 150:
            paragrafos = [p.strip() for p in texto.split("\n") if len(p.strip()) >= 30]
            if not paragrafos:
                paragrafos = [texto]
            tentativas.append({"metodo": metodo, "status": "sucesso", "chars": len(texto)})
            return {
                "titulo": titulo,
                "texto": texto,
                "paragrafos": paragrafos,
                "imagem": imagem,
                "legenda": None,
                "credito": autor or None,
                "metodo": metodo,
                "motivo": f"trafilatura extraiu HTML renderizado ({len(texto)} chars)",
            }
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": f"texto curto: {len(texto)} chars"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)[:120]})
        return None


def _extrair_de_html_renderizado(
    url: str,
    html: str,
    tentativas: list,
    metodo_base: str,
) -> dict | None:
    if not html or len(html) < 120:
        tentativas.append({"metodo": metodo_base, "status": "falha", "motivo": "html renderizado vazio/curto"})
        return None

    resultado = _extrair_trafilatura_html_renderizado(url, html, tentativas, metodo_base)
    if resultado and safe_get(resultado, "texto", ""):
        return resultado

    soup = get_soup(html)
    if not soup:
        tentativas.append({"metodo": f"{metodo_base}/parse", "status": "falha", "motivo": "BeautifulSoup nao parseou HTML renderizado"})
        return None

    extratores = (
        lambda: _estrategia_json_ld(soup, tentativas),
        lambda: _estrategia_articlebody(soup, tentativas),
        lambda: _estrategia_next_data(soup, html, tentativas),
        lambda: _estrategia_scripts_json(soup, tentativas),
        lambda: _estrategia_densidade_paragrafos(soup, tentativas),
    )
    for extrator in extratores:
        try:
            resultado = extrator()
            if resultado and safe_get(resultado, "texto", ""):
                return _prefixar_metodo_renderizado(resultado, metodo_base)
        except Exception as e:
            tentativas.append({"metodo": metodo_base, "status": "falha", "motivo": str(e)[:120]})

    tentativas.append({"metodo": metodo_base, "status": "falha", "motivo": "html renderizado sem texto util"})
    return None


def _estrategia_scrapling(url: str, tentativas: list) -> dict | None:
    """Estratégia J: Scrapling como fallback real para sites com HTML difícil."""
    metodo = "scrapling"
    if not _env_bool("URURAU_PIPELINE_SCRAPLING", True):
        tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "URURAU_PIPELINE_SCRAPLING=0"})
        return None

    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        from ururau.coleta.scrapling_extractor import UrurauScraplingExtractor
    except Exception as e:
        tentativas.append({"metodo": metodo, "status": "pulado", "motivo": f"import falhou: {e}"[:140]})
        return None

    try:
        res = UrurauScraplingExtractor().extrair(url)
        texto = (getattr(res, "texto", "") or "").strip()
        util_chars = int(getattr(res, "util_chars", 0) or len(texto))
        min_chars = _env_int("URURAU_MIN_CHARS_TEXTO_FONTE", _env_int("URURAU_MIN_VALID", 550))
        # ScraplingResult.ok ja inclui a validacao de artigo unico. Antes esta
        # etapa aceitava qualquer texto >= minimo, mesmo quando o extrator
        # marcava contaminacao/multiassunto no erro.
        ok = bool(getattr(res, "ok", False))
        if ok and texto:
            paragrafos = [p.strip() for p in texto.split("\n\n") if len(p.strip()) >= 30]
            if len(paragrafos) < 2:
                paragrafos = [p.strip() for p in texto.splitlines() if len(p.strip()) >= 30]
            if not paragrafos:
                paragrafos = [texto]
            submetodo = getattr(res, "metodo", "") or metodo
            tentativas.append({
                "metodo": metodo,
                "status": "sucesso",
                "submetodo": submetodo,
                "chars": len(texto),
                "util_chars": util_chars,
                "tentativas": list(getattr(res, "tentativas", []) or []),
            })
            return {
                "titulo": getattr(res, "titulo", "") or "",
                "texto": texto,
                "paragrafos": paragrafos,
                "imagem": getattr(res, "imagem", "") or None,
                "legenda": None,
                "credito": getattr(res, "credito_foto", "") or None,
                "url_final": getattr(res, "url_final", "") or url,
                "metodo": submetodo,
                "motivo": f"extraido via Scrapling ({util_chars} chars uteis)",
            }

        tentativas.append({
            "metodo": metodo,
            "status": "falha",
            "chars": len(texto),
            "util_chars": util_chars,
            "motivo": getattr(res, "erro", "") or getattr(res, "status", "") or "texto insuficiente",
            "tentativas": list(getattr(res, "tentativas", []) or []),
        })
        return None
    except Exception as e:
        logger.warning("%s metodo=%s falhou: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)[:140]})
        return None


def _estrategia_playwright(url: str, tentativas: list) -> dict | None:
    """Estratégia K: renderiza a página com Chromium headless e reusa os extratores."""
    metodo = "playwright"
    if not _env_bool("URURAU_PIPELINE_PLAYWRIGHT", True):
        tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "URURAU_PIPELINE_PLAYWRIGHT=0"})
        return None

    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        tentativas.append({"metodo": metodo, "status": "pulado", "motivo": f"playwright indisponivel: {e}"[:140]})
        return None

    timeout_ms = max(3000, _env_int("URURAU_PIPELINE_PLAYWRIGHT_TIMEOUT_MS", 18000))
    wait_ms = max(0, _env_int("URURAU_PIPELINE_PLAYWRIGHT_WAIT_MS", 1200))
    html = ""
    final_url = url
    browser = None
    context = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                locale="pt-BR",
                user_agent=_BROWSER_HEADERS.get("User-Agent"),
                java_script_enabled=True,
            )
            page = context.new_page()
            try:
                page.set_default_timeout(timeout_ms)
            except Exception:
                pass
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 6000))
            except Exception:
                pass
            if wait_ms:
                page.wait_for_timeout(wait_ms)
            html = page.content()
            final_url = getattr(page, "url", url) or url
            try:
                context.close()
                context = None
            except Exception:
                pass
            try:
                browser.close()
                browser = None
            except Exception:
                pass
    except Exception as e:
        logger.warning("%s metodo=%s falhou ao renderizar: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)[:160]})
        return None
    finally:
        try:
            if context is not None:
                context.close()
        except Exception:
            pass
        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass

    tentativas.append({"metodo": metodo, "status": "renderizado", "url_final": final_url, "html_len": len(html or "")})
    return _extrair_de_html_renderizado(final_url or url, html, tentativas, metodo)


def _estrategia_trafilatura(url: str, html: str, tentativas: list) -> dict | None:
    """
    Estratégia K (v1.15.4): trafilatura - extrator BR-friendly mais robusto
    do mercado para portais de noticias. Resolve sites que o BS4+JSON-LD falham.
    Provado em teste: Diario do Rio 3389 chars, Campos 24h 666 chars.

    Usa o HTML ja baixado (nao re-baixa) para nao duplicar requisicao.
    """
    metodo = "trafilatura"
    logger.info("%s tentativa=%d metodo=%s", PREFIX, len(tentativas) + 1, metodo)
    try:
        import trafilatura
    except ImportError:
        logger.info("%s trafilatura nao instalado (pip install trafilatura)", PREFIX)
        tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "biblioteca nao instalada"})
        return None
    try:
        # v1.15.4: trafilatura prefere baixar ela mesma (tem encoding-detect proprio).
        # Se nosso fetch teve sucesso, ela tambem consegue (mesmo IP/sem cookies).
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            # Fallback: tenta com html que ja temos.
            if not html or len(html) < 200:
                tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "fetch_url vazio e html sem fallback"})
                return None
            downloaded = html
        # Extrai com favor_recall (mais agressivo) e metadados.
        result = trafilatura.extract(
            downloaded,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
            with_metadata=True,
            output_format="json",
            target_language="pt",
        )
        if not result:
            tentativas.append({"metodo": metodo, "status": "falha", "motivo": "extract retornou vazio"})
            return None
        import json as _json
        d = _json.loads(result)
        titulo = (d.get("title") or "").strip()
        texto = (d.get("text") or "").strip()
        imagem = d.get("image") or None
        autor = d.get("author") or ""
        if texto and len(texto) >= 150:
            paragrafos = [p.strip() for p in texto.split("\n") if len(p.strip()) >= 30]
            if not paragrafos:
                paragrafos = [texto]
            logger.info("%s metodo=%s SUCESSO titulo=%s texto=%d chars",
                        PREFIX, metodo, titulo[:60], len(texto))
            tentativas.append({"metodo": metodo, "status": "sucesso", "chars": len(texto)})
            return {
                "titulo": titulo,
                "texto": texto,
                "paragrafos": paragrafos,
                "imagem": imagem,
                "legenda": None,
                "credito": autor or None,
                "metodo": metodo,
                "motivo": f"trafilatura extraiu {len(texto)} chars",
            }
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": f"texto curto: {len(texto)} chars"})
        return None
    except Exception as e:
        logger.warning("%s metodo=%s erro: %s", PREFIX, metodo, e)
        tentativas.append({"metodo": metodo, "status": "falha", "motivo": str(e)[:120]})
        return None


def _aplicar_criterio_aceite(
    resultado: dict,
    url: str,
    tentativas: list,
    dominio: str,
) -> dict:
    """
    Aplica o critério de aceite editorial ao resultado.
    Atualiza aceita, status, motivo conforme avaliação.
    Registra sucesso/falha em source_quality_v90.
    """
    titulo = safe_get(resultado, "titulo", "")
    texto = safe_get(resultado, "texto", "")
    metodo = safe_get(resultado, "metodo", "")

    if not titulo and not texto:
        logger.warning("%s Criterio aceite: titulo e texto vazios, bloqueando", PREFIX)
        resultado["aceita"] = False
        resultado["status"] = "bloqueada"
        resultado["motivo"] = "titulo e texto vazios apos extracao"
        if dominio:
            registrar_falha(dominio, "titulo e texto vazios")
        return resultado

    avaliacao = avaliar_aceite_editorial_v90(titulo, texto, metodo, url)

    if safe_get(avaliacao, "aceita", False):
        resultado["aceita"] = True
        resultado["motivo"] = safe_get(avaliacao, "motivo", "aceito pelo criterio editorial")
        if safe_get(resultado, "status", "") != "ok_por_paragrafos":
            resultado["status"] = "ok"
        if dominio:
            registrar_sucesso(dominio, metodo)
        logger.info("%s Criterio aceite: ACEITO metodo=%s motivo=%s",
                    PREFIX, metodo, safe_get(avaliacao, "motivo", ""))
    else:
        motivo_avaliacao = safe_get(avaliacao, "motivo", "")
        # V200_5: se o bloqueio for por paywall/login/captcha/assinante,
        # tenta o BYPASS BURLESCO (regras por dominio + Googlebot/AMP/Wayback)
        # antes de desistir. Esse e o caminho que faz os 33 portais BR
        # (Folha, Estadao, Globo, Veja, Epoca, El Pais...) entrarem na fila.
        # Flag _v200_bypass_tentado evita loop.
        _ja_tentou_bypass = bool(resultado.get("_v200_bypass_tentado"))
        _eh_paywall = any(
            p in (motivo_avaliacao or "").lower()
            for p in ("paywall", "login", "captcha", "assinante", "assinatura")
        )
        if _eh_paywall and not _ja_tentou_bypass and url:
            try:
                from ururau.coleta.bypass_paywall_v200 import (
                    tentar_bypass_paywall as _byp,
                )
                logger.info(
                    "%s Paywall detectado, tentando bypass Burlesco para %s",
                    PREFIX, url[:80],
                )
                _bp = _byp(url, titulo_pauta=titulo or "")
                if _bp.get("ok") and _bp.get("texto"):
                    _novo_texto = str(_bp.get("texto") or "")
                    _paragrafos = [
                        p.strip() for p in _novo_texto.split("\n\n") if p.strip()
                    ]
                    resultado["texto"] = _novo_texto
                    resultado["paragrafos"] = _paragrafos
                    resultado["titulo"] = titulo or str(_bp.get("titulo") or "")
                    resultado["metodo"] = "bypass_" + str(_bp.get("estrategia") or "burlesco")
                    resultado["url_final"] = (
                        _bp.get("url_final")
                        or safe_get(resultado, "url_final", "")
                        or url
                    )
                    resultado["_v200_bypass_tentado"] = True
                    tentativas.append({
                        "metodo": resultado["metodo"], "ok": True,
                        "estrategia": _bp.get("estrategia", ""),
                        "chars": len(_novo_texto),
                    })
                    logger.info(
                        "%s Bypass OK: %d chars via %s — reavaliando",
                        PREFIX, len(_novo_texto), _bp.get("estrategia", "?"),
                    )
                    # Re-avalia. Se o bypass tambem nao passar, vira BLOQUEADO
                    # de verdade (a flag impede mais um retry).
                    return _aplicar_criterio_aceite(
                        resultado, url, tentativas, dominio,
                    )
                else:
                    tentativas.append({
                        "metodo": "bypass_paywall_v200", "ok": False,
                        "motivo": _bp.get("estrategia", "no_match"),
                    })
                    logger.info(
                        "%s Bypass falhou: %s", PREFIX,
                        _bp.get("estrategia", "no_match"),
                    )
            except Exception as _e_bp:
                logger.warning(
                    "%s Bypass excecao: %s", PREFIX, str(_e_bp)[:120],
                )
                tentativas.append({
                    "metodo": "bypass_paywall_v200", "ok": False,
                    "erro": str(_e_bp)[:120],
                })

        resultado["aceita"] = False
        resultado["status"] = "bloqueada"
        resultado["motivo"] = motivo_avaliacao or "rejeitado pelo criterio editorial"
        if dominio:
            registrar_falha(dominio, motivo_avaliacao or "rejeitado editorial")
        logger.info("%s Criterio aceite: BLOQUEADO metodo=%s motivo=%s",
                    PREFIX, metodo, motivo_avaliacao)

    return resultado


def _resultado_extraido_para_saida(
    resultado_extraido: dict,
    url_final: str,
    url: str,
    tentativas: list,
    dominio: str,
) -> dict:
    logger.info("%s Extraido via fallback metodo=%s", PREFIX, safe_get(resultado_extraido, "metodo", ""))
    resultado = _resultado_ok(
        url_final=safe_get(resultado_extraido, "url_final", "") or url_final or url,
        titulo=safe_get(resultado_extraido, "titulo", ""),
        texto=safe_get(resultado_extraido, "texto", ""),
        paragrafos=safe_get(resultado_extraido, "paragrafos", []),
        imagem=safe_get(resultado_extraido, "imagem", None),
        legenda=safe_get(resultado_extraido, "legenda", None),
        credito=safe_get(resultado_extraido, "credito", None),
        metodo=safe_get(resultado_extraido, "metodo", "fallback"),
        motivo=safe_get(resultado_extraido, "motivo", "extraido por fallback"),
        tentativas=tentativas,
    )
    return _aplicar_criterio_aceite(resultado, url, tentativas, dominio)


def extrair_materia_v90(
    url: str,
    dominio: str = "",
    tipo_site: str = "",
    contexto: dict | None = None,
) -> dict:
    """
    Pipeline principal de extração de matérias do Ururau v90.

    Args:
        url: URL da matéria a extrair.
        dominio: Domínio da fonte (ex: g1.globo.com).
        tipo_site: Tipo de site para adaptador específico (ex: wordpress, globo, uol).
        contexto: Dict opcional com informações adicionais de contexto.

    Returns:
        Dict com campos obrigatórios:
            aceita, status, titulo, texto, paragrafos, imagem, legenda,
            credito, url_final, metodo, motivo, tentativas
    """
    logger.info("%s Iniciando extracao url=%s dominio=%s tipo=%s",
                PREFIX, url, dominio, tipo_site)

    inv_url, motivo_url = _url_invalida_para_materia_v91b(url)
    if inv_url:
        return _resultado_bloqueado(url or "", f"url_nao_materia:{motivo_url}", [{"metodo": "v91b_precheck", "motivo": motivo_url, "url": url}])

    tentativas: list[dict] = []
    url_final = url
    contexto = contexto or {}

    # --- ETAPA 1: Gerar variantes de URL ---
    variantes = gerar_variantes_url_v90(url, dominio, tipo_site)
    if not variantes:
        variantes = [url]
    logger.info("%s Variantes geradas: %d", PREFIX, len(variantes))

    # --- ETAPA 2: Requisição HTML ---
    html = ""
    _bloqueio_http = None  # v1.15.4: captura status de bloqueio se houver
    for var_url in variantes:
        inv_var, motivo_var = _url_invalida_para_materia_v91b(var_url)
        if inv_var:
            tentativas.append({"metodo": "v91b_skip_variant", "url": var_url, "motivo": motivo_var})
            continue
        html, url_final = _fazer_requisicao(var_url, timeout=20)
        # v1.15.4: captura sinal de bloqueio anti-bot
        if isinstance(html, str) and html.startswith("__HTTP_BLOCK_"):
            try:
                _bloqueio_http = int(html.replace("__HTTP_BLOCK_", "").rstrip("_"))
            except Exception:
                _bloqueio_http = 403
            html = ""  # zera para nao processar como HTML
            tentativas.append({"metodo": "requisicao", "url": var_url, "status": f"bloqueio_http_{_bloqueio_http}"})
            continue
        if html and len(html) > 100:
            break
        tentativas.append({"metodo": "requisicao", "url": var_url, "status": "falha"})

    # v1.15.4: se TODAS variantes deram bloqueio anti-bot, retorna motivo claro.
    if not html and _bloqueio_http:
        logger.warning("%s BLOQUEIO_ANTI_BOT confirmado em todas variantes: %d", PREFIX, _bloqueio_http)
        resultado_extraido = _estrategia_scrapling(url_final or url, tentativas)
        if not resultado_extraido:
            resultado_extraido = _estrategia_playwright(url_final or url, tentativas)
        if resultado_extraido and safe_get(resultado_extraido, "texto", ""):
            return _resultado_extraido_para_saida(resultado_extraido, url_final or url, url, tentativas, dominio)
        if dominio:
            registrar_falha(dominio, f"site bloqueia bots (HTTP {_bloqueio_http})")
        _motivo_bloqueio = {
            401: "ACESSO_NEGADO_401: o site exige login para ler esta materia.",
            403: "BLOQUEIO_ANTI_BOT_403: o site recusa requisicoes automatizadas (qualquer User-Agent). Sem proxy/IP rotativo nao ha como acessar.",
            451: "BLOQUEIO_LEGAL_451: conteudo bloqueado por motivos legais nesta jurisdicao.",
        }.get(_bloqueio_http, f"BLOQUEIO_HTTP_{_bloqueio_http}: o site recusou a requisicao.")
        return _resultado_bloqueado(url_final or url, _motivo_bloqueio, tentativas)

    if not html or len(html) < 100:
        logger.error("%s Falha: HTML vazio ou muito curto apos todas as variantes", PREFIX)
        resultado_extraido = _estrategia_scrapling(url_final or url, tentativas)
        if not resultado_extraido:
            resultado_extraido = _estrategia_playwright(url_final or url, tentativas)
        if resultado_extraido and safe_get(resultado_extraido, "texto", ""):
            return _resultado_extraido_para_saida(resultado_extraido, url_final or url, url, tentativas, dominio)
        if dominio:
            registrar_falha(dominio, "HTML vazio ou muito curto")
        return _resultado_bloqueado(
            url_final or url,
            "HTML vazio ou muito curto apos requisicao",
            tentativas,
        )

    tentativas.append({"metodo": "requisicao", "url": url_final, "status": "sucesso", "html_len": len(html)})

    # v1.15.4: DETECCAO 1 - REDIRECT EXPLICITO PARA /404
    # url_final termina em /404, /404.html, /erro, etc.
    # Deteccao mais confiavel (ex: nfnoticias redireciona pra /404.html).
    _url_final_low = (url_final or "").lower()
    _redirect_404 = (
        "/404.html" in _url_final_low
        or "/404.htm" in _url_final_low
        or _url_final_low.endswith("/404")
        or _url_final_low.endswith("/404/")
        or "/erro/" in _url_final_low
        or "/page-not-found" in _url_final_low
        or "/pagina-nao-encontrada" in _url_final_low
        or "/not-found" in _url_final_low
    )
    if _redirect_404:
        logger.warning("%s 404 POR REDIRECT detectado: url_final=%s", PREFIX, url_final)
        tentativas.append({"metodo": "deteccao_404_redirect", "url_final": url_final, "html_len": len(html)})
        if dominio:
            registrar_falha(dominio, "materia 404: servidor redirecionou para pagina de erro")
        return _resultado_bloqueado(
            url_final or url,
            "MATERIA_REMOVIDA: o servidor redirecionou para " + str(url_final) + " (pagina de erro). A materia nao existe mais nesse caminho.",
            tentativas,
        )

    # v1.15.4: DETECCAO 2 - PADROES NO HTML para sites que servem o 404 sem redirect.
    _html_low = html.lower()
    if len(html) < 12000:
        _padroes_404 = (
            ("404" in _html_low and "não existe" in _html_low),
            ("404" in _html_low and "nao existe" in _html_low),
            ("not found" in _html_low and len(html) < 8000),
            ("conteúdo não encontrado" in _html_low),
            ("conteudo nao encontrado" in _html_low),
            ("página removida" in _html_low),
            ("pagina removida" in _html_low),
            ("lamentamos" in _html_low and "página" in _html_low),
        )
        if any(_padroes_404):
            logger.warning("%s 404 MASCARADO detectado: url=%s devolveu pagina de erro", PREFIX, url_final)
            tentativas.append({"metodo": "deteccao_404_mascarado", "html_len": len(html)})
            if dominio:
                registrar_falha(dominio, "materia 404 mascarada (link quebrado no servidor)")
            return _resultado_bloqueado(
                url_final or url,
                "MATERIA_REMOVIDA: o link do RSS aponta para uma materia que nao existe mais no servidor (404 mascarado como 200). Causa: o publicador removeu/movou a materia depois que entrou no feed.",
                tentativas,
            )

    # --- ETAPA 3: Parse BeautifulSoup ---
    soup = get_soup(html)
    if not soup:
        logger.error("%s Falha: BeautifulSoup nao conseguiu parsear HTML", PREFIX)
        if dominio:
            registrar_falha(dominio, "BeautifulSoup parse falhou")
        return _resultado_bloqueado(
            url_final,
            "BeautifulSoup nao conseguiu parsear HTML",
            tentativas,
        )

    # --- ETAPA 3b: V200_43 - Isolamento por dominio (estrategia mais robusta) ---
    # Para sites onde sabemos exatamente ONDE esta o corpo da materia, em vez
    # de remover boilerplate, ISOLAMOS apenas o container do corpo. Sobra so a
    # materia, nada mais. Robusto contra mudancas no resto do layout.
    try:
        _dom_lower = (dominio or "").lower()
        _isolou = False
        if "campos.rj.gov.br" in _dom_lower:
            # campos.rj.gov.br: corpo esta em div.imateria
            _alvo = soup.select_one("div.imateria") or soup.select_one(".imateria")
            if _alvo:
                # Captura tambem o titulo (h1) e a imagem destacada antes de isolar
                _titulo_el = soup.select_one("h1") or soup.select_one("h2")
                _img_el = None
                for _candidato in (
                    "div.box-detail-noticia img",
                    "div.box-detail-noticia .carousel img",
                    "article img",
                    "main img",
                ):
                    _img_el = soup.select_one(_candidato)
                    if _img_el:
                        break
                # Constroi novo soup minimalista
                from bs4 import BeautifulSoup as _BS
                _novo = _BS("<html><head></head><body></body></html>", "html.parser")
                _body = _novo.body
                if _titulo_el:
                    _body.append(_titulo_el.extract())
                if _img_el:
                    _body.append(_img_el.extract())
                _body.append(_alvo.extract())
                soup = _novo
                html = str(soup)
                _isolou = True
                logger.info("%s V200_43 ISOLOU corpo (div.imateria) em campos.rj.gov.br", PREFIX)
        if _isolou:
            pass  # ja isolou, pula pre-limpeza padrao
        _seletores_remover: list[str] = []
        if not _isolou and "campos.rj.gov.br" in _dom_lower:
            # V200_42: estrutura REAL inspecionada no HTML
            # - ul.ul-noticias-detail: lista lateral com <a.link-noticia-list-detail>
            # - div.box-mais-noticias: bloco "Mais noticias" com tabs
            # - #mais-noticias / #mais-lidas: tab panes
            # - a.item-mais-lida: cards de "mais lidas"
            # - p.data-mais-lida, span.data-text, span.data-date: textos dos cards
            _seletores_remover = [
                # Lista lateral de notícias
                "ul.ul-noticias-detail",
                "a.link-noticia-list-detail",
                # Bloco "Mais notícias" no rodapé
                "div.box-mais-noticias",
                "#mais-noticias",
                "#mais-lidas",
                "div.tab-pane",            # qualquer painel de tab
                "ul.nav-tabs",             # navegação por tabs
                "ul.mais-noticias-tabs",
                # Cards individuais (defensivo)
                "a.item-mais-lida",
                "p.data-mais-lida",
                "span.info-data",
                # Botões sociais
                "div.box-fluid-midia-social",
                "div.box-icons-media",
                "div.bg-fluid-midia-social",
                "div.addthis_toolbox",
                # Header / navegação geral
                "nav.navbar",
                "header",
                "footer",
                "div.container-fluid > nav",
            ]
        if _seletores_remover:
            _removidos = 0
            for _sel in _seletores_remover:
                try:
                    for _el in soup.select(_sel):
                        _el.decompose()
                        _removidos += 1
                except Exception:
                    pass
            if _removidos:
                logger.info(
                    "%s pre-limpeza V200_41 dominio=%s removeu %d blocos boilerplate",
                    PREFIX, _dom_lower, _removidos,
                )
                # Re-serializa html limpo para que adapters que usam string crua tambem se beneficiem
                try:
                    html = str(soup)
                except Exception:
                    pass
    except Exception as _e:
        logger.debug("%s pre-limpeza V200_41 falhou (nao critico): %s", PREFIX, _e)

    # --- ETAPA 4: Adaptador específico ---
    tipo_adapter = (tipo_site or "generic").strip().lower()
    adapter = get_adapter(tipo_adapter)
    adapter_nome = tipo_adapter if tipo_adapter in (
        "generic", "wordpress", "globo", "uol", "folha",
        "agenciabrasil", "oficial", "local",
    ) else "generic"

    logger.info("%s tentativa=%d metodo=adapter tipo=%s", PREFIX, len(tentativas) + 1, adapter_nome)
    try:
        adapter_result = adapter(url, html)
        if safe_get(adapter_result, "aceita", False):
            logger.info("%s adapter=%s ACEITOU", PREFIX, adapter_nome)
            tentativas.append({"metodo": f"adapter-{adapter_nome}", "status": "sucesso"})

            resultado = _resultado_ok(
                url_final=url_final,
                titulo=safe_get(adapter_result, "titulo", ""),
                texto=safe_get(adapter_result, "texto", ""),
                paragrafos=safe_get(adapter_result, "paragrafos", []),
                imagem=safe_get(adapter_result, "imagem", None),
                legenda=safe_get(adapter_result, "legenda", None),
                credito=safe_get(adapter_result, "credito", None),
                metodo=safe_get(adapter_result, "metodo", adapter_nome),
                motivo=safe_get(adapter_result, "motivo", "aceito pelo adaptador"),
                tentativas=tentativas,
            )
            return _aplicar_criterio_aceite(resultado, url, tentativas, dominio)
        else:
            motivo_adapter = safe_get(adapter_result, "motivo", "adaptador rejeitou")
            logger.info("%s adapter=%s REJEITOU motivo=%s", PREFIX, adapter_nome, motivo_adapter)
            tentativas.append({"metodo": f"adapter-{adapter_nome}", "status": "falha", "motivo": motivo_adapter})
    except Exception as e:
        logger.warning("%s adapter=%s FALHOU: %s", PREFIX, adapter_nome, e)
        tentativas.append({"metodo": f"adapter-{adapter_nome}", "status": "falha", "motivo": str(e)})

    # --- ETAPA 5: Estratégias de fallback ---
    resultado_extraido = None

    # v1.15.4 K. Trafilatura (PRIMEIRO porque tem melhor heuristica BR para portais)
    if not resultado_extraido:
        resultado_extraido = _estrategia_trafilatura(url_final, html, tentativas)

    # A. JSON-LD NewsArticle/Article
    if not resultado_extraido:
        resultado_extraido = _estrategia_json_ld(soup, tentativas)

    # B. articleBody
    if not resultado_extraido:
        resultado_extraido = _estrategia_articlebody(soup, tentativas)

    # C. __NEXT_DATA__
    if not resultado_extraido:
        resultado_extraido = _estrategia_next_data(soup, html, tentativas)

    # D. Scripts JSON públicos
    if not resultado_extraido:
        resultado_extraido = _estrategia_scripts_json(soup, tentativas)

    # E. WordPress REST API
    if not resultado_extraido:
        resultado_extraido = _estrategia_wordpress_rest(url_final, soup, html, tentativas)

    # F. article/main/content por densidade de parágrafos
    if not resultado_extraido:
        resultado_extraido = _estrategia_densidade_paragrafos(soup, tentativas)

    # G. AMP
    if not resultado_extraido:
        resultado_extraido = _estrategia_amp(url_final, soup, tentativas)

    # H. Scrapling: fallback real para sites com HTML dinâmico/anti-bot leve
    if not resultado_extraido:
        resultado_extraido = _estrategia_scrapling(url_final, tentativas)

    # I. Playwright: renderiza JavaScript e reaplica os extratores
    if not resultado_extraido:
        resultado_extraido = _estrategia_playwright(url_final, tentativas)

    # J. mobile (não usar, apenas logar)
    if not resultado_extraido:
        _estrategia_mobile(url_final, tentativas)

    # K. impressão (não usar, apenas logar)
    if not resultado_extraido:
        _estrategia_impressao(url_final, tentativas)

    # ETAPA 6: verifica fallback
    if resultado_extraido and safe_get(resultado_extraido, "texto", ""):
        return _resultado_extraido_para_saida(resultado_extraido, url_final, url, tentativas, dominio)

    # ETAPA 7: bypass de paywall (ultimo recurso).
    # V200_5: prefere bypass_paywall_v200 (com regras Burlesco para os 33
    # portais BR) e cai para o v90 se aquele nao estiver disponivel.
    try:
        try:
            from ururau.coleta.bypass_paywall_v200 import tentar_bypass_paywall
        except ImportError:
            from ururau.coleta.bypass_paywall_v90 import tentar_bypass_paywall  # type: ignore
        logger.info("%s tentando bypass de paywall para url=%s", PREFIX, url)
        bp = tentar_bypass_paywall(url, titulo_pauta="")
        tentativas.append({"metodo": "bypass_paywall", "ok": bp.get("ok", False), "estrategia": bp.get("estrategia", "")})
        if bp.get("ok") and bp.get("texto"):
            _texto_bp = bp["texto"] or ""
            _paragrafos_bp = [p.strip() for p in _texto_bp.split("\n\n") if p.strip()]
            resultado = _resultado_ok(
                url_final=bp.get("url_final") or url,
                titulo=bp.get("titulo") or "",
                texto=_texto_bp,
                paragrafos=_paragrafos_bp,
                imagem=bp.get("imagem"),
                legenda=None,
                credito=None,
                metodo="bypass_" + (bp.get("estrategia") or ""),
                motivo="extraido via bypass de paywall",
                tentativas=tentativas,
            )
            return _aplicar_criterio_aceite(resultado, url, tentativas, dominio)
    except Exception as _e_bypass:
        logger.warning("%s bypass paywall falhou: %s", PREFIX, _e_bypass)
        tentativas.append({"metodo": "bypass_paywall", "ok": False, "erro": str(_e_bypass)[:120]})

    # v1.15.6: ETAPA 7B - JINA READER (ultima chance ANTES de bloquear)
    try:
        from ururau.coleta.jina_extractor import extrair_via_jina
        logger.info("%s tentando JINA READER url=%s", PREFIX, url)
        _jina = extrair_via_jina(url_final or url, timeout=20, min_chars=300)
        tentativas.append({"metodo": "jina_reader",
                            "ok": _jina.get("ok", False),
                            "chars": _jina.get("chars", 0),
                            "motivo": _jina.get("motivo", "")})
        if _jina.get("ok") and _jina.get("texto"):
            _texto_jina = _jina["texto"]
            resultado = _resultado_ok(
                url_final=url_final or url,
                titulo=_jina.get("titulo") or "",
                texto=_texto_jina,
                paragrafos=_jina.get("paragrafos") or [],
                imagem=None,
                legenda=None,
                credito=None,
                metodo="jina_reader",
                motivo="extraido via Jina Reader: " + str(_jina.get("chars", 0)) + " chars",
                tentativas=tentativas,
            )
            return _aplicar_criterio_aceite(resultado, url, tentativas, dominio)
    except Exception as _e_jina:
        logger.warning("%s jina_reader falhou: %s", PREFIX, _e_jina)
        tentativas.append({"metodo": "jina_reader", "ok": False, "erro": str(_e_jina)[:120]})

    # ETAPA 8: nada funcionou
    logger.error("%s Todas as estrategias falharam para url=%s", PREFIX, url)
    if dominio:
        registrar_falha(dominio, "todas as estrategias falharam (incluindo bypass + jina)")
    return _resultado_bloqueado(
        url_final or url,
        "Nenhuma estrategia de extracao conseguiu obter conteudo valido (incluindo Jina Reader)",
        tentativas,
    )
