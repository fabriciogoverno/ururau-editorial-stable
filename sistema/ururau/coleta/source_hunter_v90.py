"""
source_hunter_v90.py
Orquestrador principal de coleta premium do Ururau v90.

Coleta pautas de múltiplas fontes, processa cada URL através de um pipeline
robusto de resolução, extração e critério de aceite editorial.

Fluxo por URL:
    normalizacao → link resolver → variantes → extract pipeline → criterio de aceite

Fontes (ordem de coleta):
    1. RSS dos sites configurados
    2. Google News por termos configurados
    3. Sitemaps dos sites configurados
    4. Homepages dos sites configurados
    5. Editorias (sections) dos sites configurados
    6. Sites com watchlist ativa
"""

import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from ururau.coleta.source_registry_v90 import carregar_config_fontes, listar_fontes_ativas
from ururau.coleta.link_resolver_v90 import resolver_url_final_v90
from ururau.coleta.url_variants_v90 import gerar_variantes_url_v90
from ururau.coleta.extract_pipeline_v90 import extrair_materia_v90
from ururau.coleta.criterio_aceite_v90 import avaliar_aceite_editorial_v90
from ururau.coleta.source_quality_v90 import esta_em_cooldown, registrar_sucesso, registrar_falha
from ururau.coleta.site_introspector_v90 import safe_get, inspecionar_site_v90
# Import lazy de rss (pode depender de feedparser)
try:
    from ururau.coleta.rss import coletar_rss
except ImportError:
    coletar_rss = None

logger = logging.getLogger(__name__)

PREFIX = "[v90][SOURCE_HUNTER]"


def safe_get_dict(obj, key, default=None):
    """Helper seguro para evitar AttributeError em dict.get()."""
    return obj.get(key, default) if isinstance(obj, dict) else default




# ---------------------------------------------------------------------------
# v91B — filtro de URLs que NÃO são matéria
# ---------------------------------------------------------------------------

def _url_invalida_para_materia_v91b(url: str) -> tuple[bool, str]:
    """Bloqueia assets, imagens, favicons, CDN e links que não são matéria."""
    if not url or not isinstance(url, str):
        return True, "url_vazia"

    u = url.strip().lower()
    if not (u.startswith("http://") or u.startswith("https://")):
        return True, "url_nao_http"

    try:
        parsed = urlparse(u)
        dominio = parsed.netloc.lower()
        path = parsed.path.lower()
        query = parsed.query.lower()
    except Exception:
        return True, "url_parse_invalido"

    dominios_asset = (
        "lh3.googleusercontent.com",
        "googleusercontent.com",
        "gstatic.com",
        "googleapis.com",
        "ggpht.com",
        "ytimg.com",
        "gravatar.com",
        "static.",
        "cdn.",
    )
    if any(dominio == d or dominio.endswith("." + d) or d in dominio for d in dominios_asset):
        return True, f"dominio_asset:{dominio}"

    extensoes_asset = (
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp",
        ".css", ".js", ".mjs", ".map", ".woff", ".woff2", ".ttf", ".eot",
        ".mp4", ".mp3", ".webm", ".avi", ".mov", ".pdf", ".zip", ".rar"
    )
    if path.endswith(extensoes_asset):
        return True, "extensao_asset"

    termos_asset = (
        "/wp-content/uploads/",
        "/wp-content/themes/",
        "/wp-includes/",
        "/static/",
        "/assets/",
        "/images/",
        "/img/",
        "/favicon",
        "/logo",
        "/avatar",
        "/thumbnail",
        "/thumb",
    )
    if any(t in path for t in termos_asset):
        return True, "path_asset"

    # URL de miniatura de imagem do Google News, comum em RSS.
    if "w16" in query or "w32" in query or "w64" in query:
        if "googleusercontent" in dominio:
            return True, "thumb_google_news"

    return False, ""


def _filtrar_urls_materia_v91b(urls: list[dict], contexto: str = "") -> list[dict]:
    filtradas = []
    removidas = 0
    for item in urls:
        url = safe_get_dict(item, "url", "")
        invalida, motivo = _url_invalida_para_materia_v91b(url)
        if invalida:
            removidas += 1
            logger.debug("%s [v91B][SKIP_URL] %s | %s | %s", PREFIX, contexto, motivo, str(url)[:120])
            continue
        filtradas.append(item)
    if removidas:
        logger.info("%s [v91B] %d URLs de imagem/asset removidas em %s", PREFIX, removidas, contexto)
    return filtradas


# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------

def _carregar_config_hunter(path="config/source_hunter_config_v90.json") -> dict:
    """Carrega configurações do source hunter."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path_abs = os.path.join(base, path) if not os.path.isabs(path) else path

    if not os.path.exists(path_abs):
        logger.info("%s Config hunter nao encontrado, usando padrao", PREFIX)
        return _config_padrao()

    try:
        with open(path_abs, "r", encoding="utf-8") as f:
            config = json.load(f)
            if isinstance(config, dict):
                # v92: Google News dentro do Source Hunter fica desligado por padrão.
                # O Google News do projeto continua podendo ser usado como radar externo,
                # mas o pipeline pesado não deve tentar resolver centenas de URLs news.google.
                config["habilitar_google_news"] = os.getenv("URURAU_V92_USAR_GNEWS", str(config.get("habilitar_google_news", "0"))).lower() in ("1", "true", "sim", "yes", "s")
                return config
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("%s Erro ao carregar config hunter: %s", PREFIX, e)

    return _config_padrao()


def _config_padrao() -> dict:
    return {
        "limite_por_fonte": 30,
        "janela_horas": 4,
        "timeout_request": 20,
        "max_tentativas_extracao": 8,
        "cooldown_429_segundos": 300,
        "habilitar_google_news": False,  # v92: Google News só como radar externo; evita spam de links não resolvidos
        "habilitar_rss": True,
        "habilitar_sitemap": True,
        "habilitar_homepage": True,
        "habilitar_wordpress_json": True,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _carregar_termos(path="config/source_terms_config_v90.json") -> dict:
    """Carrega termos de busca configurados."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path_abs = os.path.join(base, path) if not os.path.isabs(path) else path

    if not os.path.exists(path_abs):
        logger.info("%s Config de termos nao encontrada", PREFIX)
        return {
            "termos_regionais": ["Rio de Janeiro", "Campos dos Goytacazes", "Norte Fluminense"],
            "termos_nacionais": ["Brasil", "São Paulo", "FGTS"],
            "termos_trends": ["economia", "saude", "educacao"],
        }

    try:
        with open(path_abs, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("%s Erro ao carregar termos: %s", PREFIX, e)
        return {}


# ---------------------------------------------------------------------------
# Normalização de URL
# ---------------------------------------------------------------------------

def _normalizar_url(url: str) -> str:
    """Normaliza a URL: strip, lowercase dominio, remove fragmentos desnecessários."""
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    # Remover fragmentos (anchors)
    if "#" in url:
        url = url.split("#")[0]
    return url


def _extrair_dominio(url: str) -> str:
    """Extrai o domínio de uma URL."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _deduplicar_urls(urls: list[dict], vistas: set) -> list[dict]:
    """Remove URLs duplicadas mantendo a primeira ocorrência e descarta assets."""
    unicas = []
    for item in urls:
        url = item.get("url", "")
        invalida, motivo = _url_invalida_para_materia_v91b(url)
        if invalida:
            logger.debug("%s [v91B][SKIP_DEDUPE] %s | %s", PREFIX, motivo, str(url)[:100])
            continue
        url_norm = url.rstrip("/")
        if url_norm not in vistas:
            vistas.add(url_norm)
            unicas.append(item)
    return unicas


# ---------------------------------------------------------------------------
# 1. Coleta RSS
# ---------------------------------------------------------------------------

def _coletar_rss_fontes(fontes: list[dict], limite: int, config: dict, vistas: set) -> list[dict]:
    """Coleta pautas via RSS dos sites configurados."""
    if not safe_get_dict(config, "habilitar_rss", True):
        logger.info("%s RSS desabilitado na config", PREFIX)
        return []

    logger.info("%s === FASE 1: RSS ===", PREFIX)
    urls_descobertas = []

    if coletar_rss is None:
        logger.warning("%s coletar_rss nao disponivel (feedparser faltando)", PREFIX)
        return []

    feeds = []
    for fonte in fontes:
        rss_urls = safe_get_dict(fonte, "rss_urls", []) or safe_get_dict(fonte, "rss", [])
        if isinstance(rss_urls, str):
            rss_urls = [rss_urls]
        if not rss_urls:
            # Tentar construir feed padrão a partir de homepage/url_base.
            url_base = safe_get_dict(fonte, "url_base", "") or safe_get_dict(fonte, "homepage", "")
            homepages = safe_get_dict(fonte, "homepages", [])
            if not url_base and isinstance(homepages, list) and homepages:
                url_base = homepages[0]
            if url_base:
                rss_urls = [f"{url_base.rstrip('/')}/feed/"]
        for feed_url in rss_urls:
            feeds.append({
                "url": feed_url,
                "nome": safe_get_dict(fonte, "nome", safe_get_dict(fonte, "name", safe_get_dict(fonte, "domain", "rss"))),
                "canal_forcado": safe_get_dict(fonte, "canal_forcado", ""),
            })

    if not feeds:
        logger.info("%s Nenhum feed RSS configurado", PREFIX)
        return []

    try:
        # coletar_rss do projeto real aceita apenas lista de dicts.
        pautas_rss = coletar_rss(feeds)
        logger.info("%s RSS cru: %d entradas", PREFIX, len(pautas_rss))

        for pauta in pautas_rss[:limite]:
            url = safe_get_dict(pauta, "url", "") or safe_get_dict(pauta, "link_origem", "")
            titulo = safe_get_dict(pauta, "titulo", "") or safe_get_dict(pauta, "titulo_origem", "")
            if url:
                urls_descobertas.append({
                    "url": url,
                    "titulo": titulo,
                    "fonte": safe_get_dict(pauta, "fonte", safe_get_dict(pauta, "fonte_nome", "rss")),
                    "metodo_coleta": "rss",
                    "resumo": safe_get_dict(pauta, "resumo", safe_get_dict(pauta, "resumo_origem", "")),
                })
    except Exception as e:
        logger.error("%s Erro na coleta RSS: %s", PREFIX, e)

    urls_descobertas = _filtrar_urls_materia_v91b(urls_descobertas, "rss")
    # Deduplicar
    result = _deduplicar_urls(urls_descobertas, vistas)
    logger.info("%s RSS: %d URLs unicas descobertas", PREFIX, len(result))
    return result


# ---------------------------------------------------------------------------
# 2. Google News
# ---------------------------------------------------------------------------

def _coletar_google_news(config: dict, termos: dict, limite: int, vistas: set) -> list[dict]:
    """Coleta pautas via Google News por termos configurados."""
    if not safe_get_dict(config, "habilitar_google_news", True):
        logger.info("%s Google News desabilitado", PREFIX)
        return []

    logger.info("%s === FASE 2: GOOGLE NEWS ===", PREFIX)
    urls_descobertas = []

    # Agregar termos de todas as categorias
    todos_termos = []
    for categoria in ["termos_regionais", "termos_nacionais", "termos_trends"]:
        termos_list = safe_get_dict(termos, categoria, [])
        if isinstance(termos_list, list):
            todos_termos.extend(termos_list)

    if not todos_termos:
        logger.info("%s Nenhum termo configurado para Google News", PREFIX)
        return []

    # Usar RSS do Google News (endpoint não-oficial mas funcional)
    for termo in todos_termos[:15]:  # Limitar termos para não sobrecarregar
        try:
            # Google News RSS em português do Brasil
            termo_encoded = requests.utils.quote(termo)
            gn_url = f"https://news.google.com/rss/search?q={termo_encoded}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

            resp = safe_get(gn_url, timeout=15)
            if resp is None:
                continue

            # Parse do RSS
            root = ET.fromstring(resp.content)
            # Namespace do RSS
            ns = {"content": "http://purl.org/rss/1.0/modules/content/"}

            items = root.findall(".//item")
            for item in items[:limite]:
                titulo_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")

                titulo = titulo_el.text if titulo_el is not None else ""
                link = link_el.text if link_el is not None else ""
                desc = desc_el.text if desc_el is not None else ""

                if not link:
                    continue

                # Google News NUNCA é fonte final — o link_resolver vai resolver
                urls_descobertas.append({
                    "url": link,
                    "titulo": titulo,
                    "fonte": f"google_news:{termo}",
                    "metodo_coleta": "google_news",
                    "resumo": desc,
                })

            # Pequeno delay entre termos
            time.sleep(0.5)

        except ET.ParseError as e:
            logger.debug("%s Parse XML erro para termo '%s': %s", PREFIX, termo, e)
        except Exception as e:
            logger.warning("%s Erro Google News termo '%s': %s", PREFIX, termo, e)

    urls_descobertas = _filtrar_urls_materia_v91b(urls_descobertas, "google_news")
    result = _deduplicar_urls(urls_descobertas, vistas)
    logger.info("%s Google News: %d URLs unicas descobertas", PREFIX, len(result))
    return result


# ---------------------------------------------------------------------------
# 3. Sitemaps
# ---------------------------------------------------------------------------

def _coletar_sitemaps(fontes: list[dict], limite: int, config: dict, vistas: set) -> list[dict]:
    """Coleta URLs dos sitemaps dos sites configurados."""
    if not safe_get_dict(config, "habilitar_sitemap", True):
        logger.info("%s Sitemaps desabilitados", PREFIX)
        return []

    logger.info("%s === FASE 3: SITEMAPS ===", PREFIX)
    urls_descobertas = []

    for fonte in fontes:
        url_base = safe_get_dict(fonte, "url_base", "")
        if not url_base:
            continue

        dominio = _extrair_dominio(url_base)

        # Verificar cooldown
        if esta_em_cooldown(dominio):
            logger.info("%s Dominio %s em cooldown, pulando sitemap", PREFIX, dominio)
            continue

        # Sitemaps configurados ou descobertos
        sitemaps = safe_get_dict(fonte, "sitemaps", [])
        if not sitemaps:
            # Tentar sitemap padrão
            sitemaps = [f"{url_base.rstrip('/')}/sitemap.xml"]

        for sm_url in sitemaps:
            try:
                resp = safe_get(sm_url, timeout=15)
                if resp is None:
                    continue

                content = resp.text
                # Extrair URLs do sitemap
                urls_extraidas = _extrair_urls_sitemap(content)
                logger.debug("%s Sitemap %s: %d URLs", PREFIX, sm_url, len(urls_extraidas))

                for url_item in urls_extraidas[:limite]:
                    urls_descobertas.append({
                        "url": url_item,
                        "titulo": "",
                        "fonte": safe_get_dict(fonte, "nome", dominio),
                        "metodo_coleta": "sitemap",
                        "resumo": "",
                    })

            except Exception as e:
                logger.debug("%s Erro sitemap %s: %s", PREFIX, sm_url, e)

        time.sleep(0.2)

    result = _deduplicar_urls(urls_descobertas, vistas)
    logger.info("%s Sitemaps: %d URLs unicas descobertas", PREFIX, len(result))
    return result


def _extrair_urls_sitemap(xml_content: str) -> list[str]:
    """Extrai URLs de um XML de sitemap."""
    urls = []
    if not xml_content or "<urlset" not in xml_content and "<sitemapindex" not in xml_content:
        return urls

    try:
        root = ET.fromstring(xml_content.encode("utf-8"))
        # Namespace comum de sitemap
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Sitemap index
        sitemaps = root.findall(".//ns:loc", ns)
        if not sitemaps:
            sitemaps = root.findall(".//sitemap/loc")
        if not sitemaps:
            sitemaps = root.findall(".//url/loc")
        if not sitemaps:
            # Sem namespace
            sitemaps = root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")

        for loc in sitemaps:
            if loc is not None and loc.text:
                urls.append(loc.text.strip())

        # Se não encontrou nada com namespace, tentar regex como fallback
        if not urls:
            import re
            urls = re.findall(r"<loc>([^<]+)</loc>", xml_content)

    except ET.ParseError:
        # Fallback regex
        import re
        urls = re.findall(r"<loc>([^<]+)</loc>", xml_content)
    except Exception:
        pass

    return urls


# ---------------------------------------------------------------------------
# 4. Homepages
# ---------------------------------------------------------------------------

def _coletar_homepages(fontes: list[dict], limite: int, vistas: set) -> list[dict]:
    """Coleta URLs das homepages dos sites configurados."""
    logger.info("%s === FASE 4: HOMEPAGES ===", PREFIX)
    urls_descobertas = []

    for fonte in fontes:
        url_base = safe_get_dict(fonte, "url_base", "")
        if not url_base:
            continue

        dominio = _extrair_dominio(url_base)

        # Verificar cooldown
        if esta_em_cooldown(dominio):
            logger.info("%s Dominio %s em cooldown, pulando homepage", PREFIX, dominio)
            continue

        try:
            resp = safe_get(url_base, timeout=15)
            if resp is None:
                continue

            html = resp.text
            urls_extraidas = _extrair_links_pagina(html, url_base, limite)
            logger.debug("%s Homepage %s: %d links", PREFIX, url_base, len(urls_extraidas))

            for url_item in urls_extraidas:
                urls_descobertas.append({
                    "url": url_item,
                    "titulo": "",
                    "fonte": safe_get_dict(fonte, "nome", dominio),
                    "metodo_coleta": "homepage",
                    "resumo": "",
                })

        except Exception as e:
            logger.debug("%s Erro homepage %s: %s", PREFIX, url_base, e)

        time.sleep(0.3)

    result = _deduplicar_urls(urls_descobertas, vistas)
    logger.info("%s Homepages: %d URLs unicas descobertas", PREFIX, len(result))
    return result


def _extrair_links_pagina(html: str, base_url: str, limite: int = 50) -> list[str]:
    """Extrai links de notícias de uma página HTML."""
    import re

    if not html:
        return []

    links = []
    padroes_url = re.findall(r'href=["\']([^"\']+)["\']', html)

    base_parsed = urlparse(base_url)
    base_dominio = base_parsed.netloc

    for href in padroes_url:
        # Normalizar URL
        if href.startswith("http"):
            link = href
        elif href.startswith("//"):
            link = f"{base_parsed.scheme}:{href}"
        elif href.startswith("/"):
            link = f"{base_parsed.scheme}://{base_dominio}{href}"
        else:
            link = urljoin(base_url, href)

        # Filtrar apenas URLs do mesmo domínio
        try:
            link_domain = urlparse(link).netloc
            if link_domain != base_dominio and not link_domain.endswith(f".{base_dominio}"):
                continue
        except Exception:
            continue

        # Filtrar URLs que parecem ser notícias (têm slug com data ou path profundo)
        link_lower = link.lower()
        # Excluir assets
        if any(link_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".pdf", ".xml", ".json"]):
            continue
        if "/wp-content/" in link_lower or "/wp-includes/" in link_lower:
            continue
        if "/feed" in link_lower or "/rss" in link_lower:
            continue
        if "?" in link and any(p in link_lower for p in ["page=", "paged=", "offset=", "ajax", "wp-json"]):
            continue

        # Heurística: notícias geralmente têm paths com mais de 2 segmentos ou slug
        parsed_link = urlparse(link)
        path = parsed_link.path.strip("/")
        segmentos = [s for s in path.split("/") if s]

        # Regras de aceite para links de notícia
        parece_noticia = False
        if len(segmentos) >= 2:
            # Path com ano/mes ou categoria/slug
            parece_noticia = True
        if re.search(r"/\d{4}/\d{2}/", link):
            parece_noticia = True
        if re.search(r"/\d{4}/\d{2}/\d{2}/", link):
            parece_noticia = True
        if any(seg in path for seg in ["noticia", "noticia", "materia", "article", "post", "news"]):
            parece_noticia = True

        if parece_noticia:
            links.append(link)

        if len(links) >= limite:
            break

    return links[:limite]


# ---------------------------------------------------------------------------
# 5. Editorias (Sections)
# ---------------------------------------------------------------------------

def _coletar_editorias(fontes: list[dict], limite: int, vistas: set) -> list[dict]:
    """Coleta URLs das editorias/seções dos sites configurados."""
    logger.info("%s === FASE 5: EDITORIAS ===", PREFIX)
    urls_descobertas = []

    # Editorias comuns para tentar
    editorias_comuns = [
        "/politica/", "/brasil/", "/mundo/", "/economia/",
        "/saude/", "/educacao/", "/esportes/", "/tecnologia/",
        "/ciencia/", "/cultura/", "/entretenimento/", "/geral/",
        "/norte-fluminense/", "/campos/", "/rio/", "/cidades/",
        "/policia/", "/acidentes/", "/justica/",
    ]

    for fonte in fontes:
        url_base = safe_get_dict(fonte, "url_base", "")
        if not url_base:
            continue

        dominio = _extrair_dominio(url_base)

        # Verificar cooldown
        if esta_em_cooldown(dominio):
            logger.info("%s Dominio %s em cooldown, pulando editorias", PREFIX, dominio)
            continue

        # Editorias configuradas ou padrão
        editorias = safe_get_dict(fonte, "editorias", [])
        if not editorias:
            editorias = editorias_comuns

        for ed in editorias:
            url_editoria = urljoin(url_base, ed)
            try:
                resp = safe_get(url_editoria, timeout=15)
                if resp is None:
                    continue

                html = resp.text
                urls_extraidas = _extrair_links_pagina(html, url_base, limite // len(editorias) + 1)
                logger.debug("%s Editoria %s: %d links", PREFIX, url_editoria, len(urls_extraidas))

                for url_item in urls_extraidas:
                    urls_descobertas.append({
                        "url": url_item,
                        "titulo": "",
                        "fonte": safe_get_dict(fonte, "nome", dominio),
                        "metodo_coleta": "editoria",
                        "resumo": "",
                    })

            except Exception as e:
                logger.debug("%s Erro editoria %s: %s", PREFIX, url_editoria, e)

        time.sleep(0.2)

    result = _deduplicar_urls(urls_descobertas, vistas)
    logger.info("%s Editorias: %d URLs unicas descobertas", PREFIX, len(result))
    return result


# ---------------------------------------------------------------------------
# 6. Watchlist
# ---------------------------------------------------------------------------

def _coletar_watchlist(config_global: dict, vistas: set) -> list[dict]:
    """Coleta URLs de sites na watchlist configurada no JSON de fontes."""
    logger.info("%s === FASE 6: WATCHLIST ===", PREFIX)
    urls_descobertas = []

    try:
        config_fontes = carregar_config_fontes()
        watchlist = safe_get_dict(config_fontes, "watchlist", [])

        if not watchlist:
            logger.info("%s Nenhuma watchlist configurada", PREFIX)
            return []

        for item in watchlist:
            if not isinstance(item, dict):
                continue

            url_watch = safe_get_dict(item, "url", "")
            titulo = safe_get_dict(item, "titulo", "")
            fonte = safe_get_dict(item, "fonte", "watchlist")

            if url_watch:
                urls_descobertas.append({
                    "url": url_watch,
                    "titulo": titulo,
                    "fonte": fonte,
                    "metodo_coleta": "watchlist",
                    "resumo": safe_get_dict(item, "resumo", ""),
                })

    except Exception as e:
        logger.warning("%s Erro ao carregar watchlist: %s", PREFIX, e)

    result = _deduplicar_urls(urls_descobertas, vistas)
    logger.info("%s Watchlist: %d URLs unicas descobertas", PREFIX, len(result))
    return result


# ---------------------------------------------------------------------------
# Processamento de URL individual
# ---------------------------------------------------------------------------

def _processar_url(item: dict, config: dict) -> dict | None:
    """
    Processa uma URL individual pelo pipeline completo.

    Fluxo:
        normalizacao → link resolver → variantes → extract pipeline → criterio de aceite

    Retorna dict da pauta captada ou None se rejeitada.
    """
    url = safe_get_dict(item, "url", "")
    titulo = safe_get_dict(item, "titulo", "")
    fonte = safe_get_dict(item, "fonte", "")
    metodo_coleta = safe_get_dict(item, "metodo_coleta", "")
    resumo = safe_get_dict(item, "resumo", "")

    if not url:
        return None

    if "news.google.com" in str(url).lower() and os.getenv("URURAU_V92_USAR_GNEWS", "0").lower() not in ("1", "true", "sim", "yes", "s"):
        logger.debug("%s [v92][SKIP_GNEWS] Google News ignorado no Source Hunter: %s", PREFIX, str(url)[:120])
        return None

    invalida, motivo_invalida = _url_invalida_para_materia_v91b(url)
    if invalida:
        logger.info("%s [v91B][SKIP] URL não é matéria: %s | %s", PREFIX, motivo_invalida, str(url)[:120])
        return None

    # ---- 1. Normalizar ----
    url = _normalizar_url(url)
    if not url:
        return None

    dominio = _extrair_dominio(url)

    # Verificar cooldown
    if esta_em_cooldown(dominio):
        logger.debug("%s Dominio %s em cooldown, pulando: %s", PREFIX, dominio, url[:80])
        return None

    logger.info("%s Processando URL: %s", PREFIX, url[:120])

    # ---- 2. Resolver link ----
    resolvido = resolver_url_final_v90(url, titulo=titulo, fonte=fonte)
    if not safe_get_dict(resolvido, "ok", False):
        status = safe_get_dict(resolvido, "status", "desconhecido")
        logger.info("%s [RESOLVE] falhou: %s - %s", PREFIX, status, url[:80])

        # Se for 429, registrar cooldown
        if "429" in str(status):
            registrar_falha(dominio, f"rate_limit:{status}")
        return None

    url_final = safe_get_dict(resolvido, "url_final", url)
    if not url_final:
        return None

    # Google News NUNCA é fonte final
    if "news.google.com" in url_final.lower():
        logger.warning("%s URL ainda aponta para Google News após resolucao: %s", PREFIX, url_final)
        registrar_falha(dominio, "google_news_nao_resolvido")
        return None

    invalida_final, motivo_invalida_final = _url_invalida_para_materia_v91b(url_final)
    if invalida_final:
        logger.info("%s [v91B][SKIP_FINAL] URL final não é matéria: %s | %s", PREFIX, motivo_invalida_final, str(url_final)[:120])
        return None

    dominio_final = _extrair_dominio(url_final)

    if esta_em_cooldown(dominio_final):
        logger.info("%s [v91B][COOLDOWN_FINAL] Dominio final em cooldown: %s", PREFIX, dominio_final)
        return None

    # Detectar tipo de site
    tipo_site = ""
    try:
        from ururau.coleta.site_introspector_v90 import _detect_wordpress
    except ImportError:
        pass

    # Heurística simples de tipo
    if any(d in dominio_final for d in ["wordpress", "blog", "noticias"]):
        tipo_site = "wordpress"
    elif any(d in dominio_final for d in ["g1.globo", "globo.com"]):
        tipo_site = "globo"
    elif "uol.com" in dominio_final:
        tipo_site = "uol"
    elif "folha" in dominio_final:
        tipo_site = "folha"

    # ---- 3. Gerar variantes ----
    variantes = gerar_variantes_url_v90(url_final, dominio_final, tipo_site)
    logger.info("%s [VARIANTS] dominio=%s total=%d", PREFIX, dominio_final, len(variantes))

    # RSS NUNCA é matéria completa — sempre extrair página
    if metodo_coleta == "rss" and not variantes:
        # Mesmo sem variantes, a URL original é a página
        variantes = [url_final]

    # Remover variantes que são imagens/assets e limitar tentativas.
    variantes_filtradas = []
    for v in variantes:
        inv, mot = _url_invalida_para_materia_v91b(v)
        if inv:
            logger.debug("%s [v91B][SKIP_VARIANT] %s | %s", PREFIX, mot, str(v)[:100])
            continue
        variantes_filtradas.append(v)
    variantes = variantes_filtradas or [url_final]

    # Limitar variantes
    max_tentativas = safe_get_dict(config, "max_tentativas_extracao", 8)
    variantes = variantes[:max_tentativas]

    # ---- 4. Tentar extrair cada variante ----
    resultado = None
    for idx, variante in enumerate(variantes):
        logger.info("%s [EXTRACT] tentativa=%d url=%s", PREFIX, idx + 1, variante[:80])
        try:
            resultado = extrair_materia_v90(variante, dominio_final, tipo_site)
            if safe_get_dict(resultado, "aceita", False):
                logger.info("%s [EXTRACT] aceita na tentativa %d via %s",
                            PREFIX, idx + 1, safe_get_dict(resultado, "metodo", ""))
                break
        except Exception as e:
            logger.warning("%s [EXTRACT] erro na tentativa %d: %s", PREFIX, idx + 1, e)
            continue

    if resultado is None:
        logger.info("%s [EXTRACT] nenhuma tentativa bem-sucedida", PREFIX)
        registrar_falha(dominio_final, "extracao_falhou_todas_variantes")
        return None

    # ---- 5. Avaliar aceite ----
    if safe_get_dict(resultado, "aceita", False):
        # Montar pauta captada
        pauta = {
            "status": "captada",
            "titulo": safe_get_dict(resultado, "titulo", ""),
            "url_original": url,
            "url_final": safe_get_dict(resultado, "url_final", url_final),
            "fonte": fonte or dominio_final,
            "texto_fonte": safe_get_dict(resultado, "texto", ""),
            "imagem": safe_get_dict(resultado, "imagem"),
            "metodo_extracao": safe_get_dict(resultado, "metodo", ""),
            "paragrafos": len(safe_get_dict(resultado, "paragrafos", [])),
            "chars": len(safe_get_dict(resultado, "texto", "")),
            "motivo_aceite": safe_get_dict(resultado, "motivo", ""),
            "motivo_bloqueio": "",
            "tentativas": safe_get_dict(resultado, "tentativas", []),
            "metodo_coleta": metodo_coleta,
            "dominio": dominio_final,
            "data_captura": datetime.now(timezone.utc).isoformat(),
        }

        # Salvar
        salvar_pauta_captada_v90(pauta)

        # Registrar sucesso
        registrar_sucesso(dominio_final, safe_get_dict(resultado, "metodo", ""))

        logger.info("%s [FILA] CAPTADA: %s", PREFIX, pauta["titulo"][:80] if pauta["titulo"] else "sem titulo")
        return pauta
    else:
        motivo = safe_get_dict(resultado, "motivo", "extracao_falhou")
        logger.info("%s [BLOCK] motivo=%s url=%s", PREFIX, motivo, url[:80])

        # Bloquear paywall/login/CAPTCHA
        if any(p in motivo.lower() for p in ["paywall", "login", "captcha", "bloqueio"]):
            logger.warning("%s [BLOCK] Paywall/login/CAPTCHA detectado para %s", PREFIX, dominio_final)
            registrar_falha(dominio_final, f"bloqueio:{motivo}")
        else:
            registrar_falha(dominio_final, motivo)

        return None


# ---------------------------------------------------------------------------
# Função auxiliar pública
# ---------------------------------------------------------------------------

def salvar_pauta_captada_v90(pauta: dict) -> None:
    """
    v91: no projeto real, o Source Hunter não grava em fila paralela.
    Ele apenas retorna as pautas; o painel/monitor salvam no banco real.
    """
    print(f"[v91][SOURCE_HUNTER] pauta aceita para retorno: {str(pauta.get('titulo') or '')[:80]}")


# ---------------------------------------------------------------------------
# Função principal pública
# ---------------------------------------------------------------------------

def coletar_pautas_premium_v90(config=None, limite=120, janela=4) -> list[dict]:
    """
    Orquestrador principal de coleta premium do Ururau v90.

    Coleta pautas de múltiplas fontes em sequência, processa cada URL
    através do pipeline de resolução, extração e critério de aceite.

    Args:
        config: Dict com configurações opcionais. Se None, carrega do JSON.
        limite: Limite total de pautas a captar (padrão: 120).
        janela_horas: Janela de tempo para considerar relevância (padrão: 4h).

    Returns:
        list[dict]: Lista de pautas captadas, cada uma com status "captada".

    Ordem de coleta:
        1. RSS dos sites configurados em source_domains_config_v90.json
        2. Google News por termos (source_terms_config_v90.json)
        3. Sitemaps dos sites configurados
        4. Homepages dos sites configurados
        5. Editorias (sections) dos sites configurados
        6. Sites configurados no JSON com watchlist
    """
    logger.info("%s === INICIANDO COLETA PREMIUM v90 === limite=%d janela=%dh",
                PREFIX, limite, janela_horas)

    hora_inicio = datetime.now(timezone.utc)

    # Carregar configurações
    if config is None:
        config = _carregar_config_hunter()
    elif not isinstance(config, dict):
        logger.warning("%s Config invalida, usando padrao", PREFIX)
        config = _carregar_config_hunter()

    # Carregar fontes ativas
    fontes = listar_fontes_ativas()
    logger.info("%s Fontes ativas: %d", PREFIX, len(fontes))

    if not fontes:
        logger.warning("%s Nenhuma fonte ativa encontrada", PREFIX)

    # Carregar termos
    termos = _carregar_termos()

    # Set de URLs já vistas (deduplicação global)
    vistas = set()

    # Lista de todas as URLs descobertas
    todas_urls = []

    # ---- FASE 1: RSS ----
    try:
        urls_rss = _coletar_rss_fontes(fontes, limite // 4, config, vistas)
        todas_urls.extend(urls_rss)
        logger.info("%s Fase 1 (RSS) concluida: %d URLs", PREFIX, len(urls_rss))
    except Exception as e:
        logger.error("%s Erro na fase RSS: %s", PREFIX, e)

    # ---- FASE 2: Google News ----
    # v92: Google News dentro do Source Hunter fica desligado por padrão porque
    # os links news.google.com/rss/articles frequentemente não resolvem e geram
    # centenas de logs. O Google News continua útil no coletor rápido como radar.
    if safe_get_dict(config, "habilitar_google_news", False):
        try:
            urls_gn = _coletar_google_news(config, termos, limite // 4, vistas)
            todas_urls.extend(urls_gn)
            logger.info("%s Fase 2 (Google News) concluida: %d URLs", PREFIX, len(urls_gn))
        except Exception as e:
            logger.error("%s Erro na fase Google News: %s", PREFIX, e)
    else:
        logger.info("%s Fase 2 (Google News) ignorada no v92 para reduzir erros/bloqueios", PREFIX)

    # ---- FASE 3: Sitemaps ----
    try:
        urls_sm = _coletar_sitemaps(fontes, limite // 4, config, vistas)
        todas_urls.extend(urls_sm)
        logger.info("%s Fase 3 (Sitemaps) concluida: %d URLs", PREFIX, len(urls_sm))
    except Exception as e:
        logger.error("%s Erro na fase Sitemaps: %s", PREFIX, e)

    # ---- FASE 4: Homepages ----
    try:
        urls_hp = _coletar_homepages(fontes, limite // 4, vistas)
        todas_urls.extend(urls_hp)
        logger.info("%s Fase 4 (Homepages) concluida: %d URLs", PREFIX, len(urls_hp))
    except Exception as e:
        logger.error("%s Erro na fase Homepages: %s", PREFIX, e)

    # ---- FASE 5: Editorias ----
    try:
        urls_ed = _coletar_editorias(fontes, limite // 4, vistas)
        todas_urls.extend(urls_ed)
        logger.info("%s Fase 5 (Editorias) concluida: %d URLs", PREFIX, len(urls_ed))
    except Exception as e:
        logger.error("%s Erro na fase Editorias: %s", PREFIX, e)

    # ---- FASE 6: Watchlist ----
    try:
        urls_wl = _coletar_watchlist(config, vistas)
        todas_urls.extend(urls_wl)
        logger.info("%s Fase 6 (Watchlist) concluida: %d URLs", PREFIX, len(urls_wl))
    except Exception as e:
        logger.error("%s Erro na fase Watchlist: %s", PREFIX, e)

    logger.info("%s === COLETA CONCLUIDA: %d URLs unicas totais ===",
                PREFIX, len(todas_urls))

    # ---- PROCESSAMENTO: Pipeline por URL ----
    pautas_captadas = []

    for idx, item in enumerate(todas_urls):
        if len(pautas_captadas) >= limite:
            logger.info("%s Limite de %d pautas atingido, parando processamento",
                        PREFIX, limite)
            break

        try:
            pauta = _processar_url(item, config)
            if pauta:
                pautas_captadas.append(pauta)
                logger.info("%s [%d/%d] Pautas captadas: %d/%d",
                            PREFIX, idx + 1, len(todas_urls),
                            len(pautas_captadas), limite)
        except Exception as e:
            logger.error("%s Erro ao processar URL %s: %s", PREFIX,
                         safe_get_dict(item, "url", "")[:80], e)
            continue

        # Pequeno delay para não sobrecarregar fontes
        if idx % 10 == 0 and idx > 0:
            time.sleep(0.1)

    # ---- RESUMO ----
    hora_fim = datetime.now(timezone.utc)
    duracao = (hora_fim - hora_inicio).total_seconds()
    logger.info(
        "%s === RESUMO v90 === captadas=%d de %d URLs processadas em %.1fs ===",
        PREFIX, len(pautas_captadas), len(todas_urls), duracao
    )

    return pautas_captadas


# ---------------------------------------------------------------------------
# Entry point para execução direta
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    pautas = coletar_pautas_premium_v90()
    print(f"\n=== Pautas captadas: {len(pautas)} ===")
    for p in pautas[:10]:
        print(f"  - {p.get('titulo', 'sem titulo')[:60]} | {p.get('fonte', '')}")
