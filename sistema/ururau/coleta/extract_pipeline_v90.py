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
11. Playwright opcional (logado, não usado)

Cada estratégia é isolada em try/except. Nenhuma exceção sobe —
sempre retorna dict com status preenchido.
"""

import json
import logging
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
    "Accept-Encoding": "gzip, deflate, br",
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
        html = resp.text
        url_final = resp.url
        logger.info("%s Requisicao OK url=%s final=%s status=%d len_html=%d",
                    PREFIX, url, url_final, resp.status_code, len(html) if html else 0)
        return html, url_final
    except requests.exceptions.Timeout:
        logger.warning("%s Timeout ao carregar URL=%s", PREFIX, url)
        return "", url
    except requests.exceptions.HTTPError as e:
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
            ".mainContent",
            "section",
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


def _estrategia_playwright(url: str, tentativas: list) -> dict | None:
    """
    Estratégia J: Playwright opcional.
    Não utilizada — apenas logada para rastreabilidade.
    """
    metodo = "playwright"
    logger.info("%s tentativa=%d metodo=%s [NAO UTILIZADA - apenas log]", PREFIX, len(tentativas) + 1, metodo)
    tentativas.append({"metodo": metodo, "status": "pulado", "motivo": "Playwright nao disponivel nesta versao"})
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
        resultado["aceita"] = False
        resultado["status"] = "bloqueada"
        resultado["motivo"] = safe_get(avaliacao, "motivo", "rejeitado pelo criterio editorial")
        if dominio:
            registrar_falha(dominio, safe_get(avaliacao, "motivo", "rejeitado editorial"))
        logger.info("%s Criterio aceite: BLOQUEADO metodo=%s motivo=%s",
                    PREFIX, metodo, safe_get(avaliacao, "motivo", ""))

    return resultado


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
    for var_url in variantes:
        inv_var, motivo_var = _url_invalida_para_materia_v91b(var_url)
        if inv_var:
            tentativas.append({"metodo": "v91b_skip_variant", "url": var_url, "motivo": motivo_var})
            continue
        html, url_final = _fazer_requisicao(var_url, timeout=20)
        if html and len(html) > 100:
            break
        tentativas.append({"metodo": "requisicao", "url": var_url, "status": "falha"})

    if not html or len(html) < 100:
        logger.error("%s Falha: HTML vazio ou muito curto apos todas as variantes", PREFIX)
        if dominio:
            registrar_falha(dominio, "HTML vazio ou muito curto")
        return _resultado_bloqueado(
            url_final or url,
            "HTML vazio ou muito curto apos requisicao",
            tentativas,
        )

    tentativas.append({"metodo": "requisicao", "url": url_final, "status": "sucesso", "html_len": len(html)})

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

    # H. mobile (não usar, apenas logar)
    if not resultado_extraido:
        _estrategia_mobile(url_final, tentativas)

    # I. impressão (não usar, apenas logar)
    if not resultado_extraido:
        _estrategia_impressao(url_final, tentativas)

    # J. Playwright opcional (não usar, apenas logar)
    if not resultado_extraido:
        _estrategia_playwright(url_final, tentativas)

    # --- ETAPA 6: Verificar resultado ---
    if resultado_extraido and safe_get(resultado_extraido, "texto", ""):
        logger.info("%s Extraido via fallback metodo=%s", PREFIX, safe_get(resultado_extraido, "metodo", ""))
        resultado = _resultado_ok(
            url_final=url_final,
            titulo=safe_get(resultado_extraido, "titulo", ""),
            texto=safe_get(resultado_extraido, "texto", ""),
            paragrafos=safe_get(resultado_extraido, "paragrafos", []),
            imagem=safe_get(resultado_extraido, "imagem", None),
            legenda=safe_get(resultado_extraido, "legenda", None),
            credito=safe_get(resultado_extraido, "credito", None),
            metodo=safe_get(resultado_extraido, "metodo", "fallback"),
            motivo=safe_get(resultado_extraido, "motivo", "extraido via fallback"),
            tentativas=tentativas,
        )
        return _aplicar_criterio_aceite(resultado, url, tentativas, dominio)

    # --- ETAPA 7: BYPASS PAYWALL antes de declarar falha ---
    # Tenta carregar a MESMA URL via outras vias publicas: Googlebot UA,
    # AMP, Wayback, Google Cache, archive.ph, no-cookies. So acessa
    # caminhos PUBLICOS (sem inventar conteudo).
    try:
        from ururau.coleta.bypass_paywall_v200 import (
            tentar_bypass_paywall, BYPASS_DISPONIVEL,
        )
        if BYPASS_DISPONIVEL:
            logger.info("%s tentando bypass de paywall para url=%s", PREFIX, url)
            bp = tentar_bypass_paywall(url, titulo_pauta="")
            tentativas.append({"metodo": "bypass_paywall",
                                "estrategias": bp.get("tentativas", []),
                                "ok": bp.get("ok", False),
                                "estrategia_vencedora": bp.get("estrategia", "")})
            if bp.get("ok") and bp.get("texto"):
                resultado = _resultado_ok(
                    url=url, url_final=bp.get("url_final") or url,
                    titulo="", texto=bp["texto"], imagem="", autor="",
                    data="", metodo="bypass_" + (bp.get("estrategia") or ""),
                    motivo="extraido via bypass de paywall",
                    tentativas=tentativas,
                )
                return _aplicar_criterio_aceite(resultado, url, tentativas, dominio)
    except Exception as _e_bypass:
        logger.warning("%s bypass paywall falhou: %s", PREFIX, _e_bypass)
        tentativas.append({"metodo": "bypass_paywall", "ok": False,
                           "erro": str(_e_bypass)[:120]})

    # --- ETAPA 8: Nenhuma estrategia (incluindo bypass) funcionou ---
    logger.error("%s Todas as estrategias falharam para url=%s", PREFIX, url)
    if dominio:
        registrar_falha(dominio, "todas as estrategias falharam (incluindo bypass)")
    return _resultado_bloqueado(
        url_final,
        "Nenhuma estrategia de extracao conseguiu obter conteudo valido (incluindo bypass)",
        tentativas,
    )
