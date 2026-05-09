"""
url_variants_v90.py
Módulo de geração de variantes de URL para tentativas de resolução (v90).
Gera URLs alternativas por domínio/tipo de site sem criar /amp/ cego.
"""

import logging
import re
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

def safe_get(obj, key, default=None):
    """Helper seguro para evitar AttributeError em dict.get()."""
    return obj.get(key, default) if isinstance(obj, dict) else default


def gerar_variantes_url_v90(url: str, dominio: str, tipo_site: str = "") -> list[str]:
    """
    Gera variantes de URL para tentar resolver conteúdo.

    Regras por tipo:
    - WordPress: original, canonical, /amp/, /?amp, /wp-json/wp/v2/posts?slug=<slug>
    - Globo/G1: original, sem /amp, canonical, og:url, jsonld
    - UOL: original, canonical, jsonld, scripts internos
    - Folha: redir.folha.com.br → url real, canonical, jsonld
    - Fontes oficiais: rss oficial, notícias, article/main

    Retorna lista de variantes únicas.
    """
    logger.info("[v90][URL_VARIANTS] Gerando variantes para url=%r dominio=%r tipo=%r",
                url, dominio, tipo_site)

    if not url or not isinstance(url, str):
        logger.warning("[v90][URL_VARIANTS] URL invalida: %r", url)
        return []

    variantes = []
    parsed = urlparse(url)
    dominio_lc = dominio.lower().strip() if dominio else ""
    tipo_site_lc = tipo_site.lower().strip() if tipo_site else ""

    # Sempre incluir a original
    variantes.append(url)

    # ---- WORDPRESS ----
    if "wordpress" in tipo_site_lc or _eh_wordpress(dominio_lc):
        variantes.append(url)  # original já adicionada
        # canonical = original em WP (geralmente)
        # AMP com /amp/
        amp_url = _inserir_amp_no_path(url, parsed)
        if amp_url and amp_url not in variantes:
            variantes.append(amp_url)
        # AMP com ?amp
        if "?" not in url:
            amp_query = f"{url}?amp"
            if amp_query not in variantes:
                variantes.append(amp_query)
        # WP JSON API via slug
        slug = _extrair_slug(parsed.path)
        if slug:
            # Construir API REST do WordPress
            base = f"{parsed.scheme}://{parsed.netloc}"
            api_url = f"{base}/wp-json/wp/v2/posts?slug={slug}&_embed"
            if api_url not in variantes:
                variantes.append(api_url)
            # Também tentar pages
            api_page_url = f"{base}/wp-json/wp/v2/pages?slug={slug}&_embed"
            if api_page_url not in variantes:
                variantes.append(api_page_url)

        logger.info("[v90][URL_VARIANTS] WordPress: %d variantes", len(variantes))

    # ---- GLOBO / G1 ----
    elif any(d in dominio_lc for d in ["g1.globo.com", "globo.com", "oglobo.globo.com"]):
        # Original sem /amp (Globo às vezes serve AMP)
        url_sem_amp = re.sub(r"/amp/?$", "", url)
        url_sem_amp = re.sub(r"\.amp\.html$", ".html", url_sem_amp)
        url_sem_amp = re.sub(r"/amp\.", ".", url_sem_amp)
        if url_sem_amp not in variantes:
            variantes.append(url_sem_amp)
        # JSON-LD endpoint não é direto, mas marcamos a original
        logger.info("[v90][URL_VARIANTS] Globo/G1: %d variantes", len(variantes))

    # ---- UOL ----
    elif "uol.com.br" in dominio_lc or "uol.com" in dominio_lc:
        # Canonical = original (geralmente)
        # JSON-LD na página
        # Script interno de notícias
        logger.info("[v90][URL_VARIANTS] UOL: mantendo original + possiveis scripts")

    # ---- FOLHA ----
    elif "folha.uol.com.br" in dominio_lc or "folha.com.br" in dominio_lc or "redir.folha.com.br" in dominio_lc:
        # Se for redir, tentar resolver
        if "redir.folha.com.br" in parsed.netloc.lower():
            # Tentar extrair URL real de query params ou path
            url_real = _resolver_redir_folha(url, parsed)
            if url_real and url_real not in variantes:
                variantes.append(url_real)
        # Canonical
        # JSON-LD
        logger.info("[v90][URL_VARIANTS] Folha: %d variantes", len(variantes))

    # ---- ESTADÃO ----
    elif "estadao.com.br" in dominio_lc:
        url_sem_amp = re.sub(r"\.amp\.html$", ".html", url)
        url_sem_amp = re.sub(r"/amp$", "", url_sem_amp)
        if url_sem_amp not in variantes:
            variantes.append(url_sem_amp)

    # ---- TERRA / TELESPECTADOR ----
    elif any(d in dominio_lc for d in ["terra.com.br", "telespectador"]):
        url_sem_amp = re.sub(r"/amp$", "", url)
        if url_sem_amp not in variantes:
            variantes.append(url_sem_amp)

    # ---- GENÉRICO: detectar AMP na URL e gerar canonical ----
    if "/amp" in parsed.path or ".amp." in url or url.endswith("?amp") or url.endswith("&amp"):
        canonical = re.sub(r"/amp/?$", "", url)
        canonical = re.sub(r"\.amp\.html$", ".html", canonical)
        canonical = re.sub(r"\?amp$", "", canonical)
        canonical = re.sub(r"&amp$", "", canonical)
        if canonical and canonical not in variantes:
            variantes.append(canonical)
            logger.info("[v90][URL_VARIANTS] AMP detectado, canonical=%r", canonical)

    # ---- RSS / FONTES OFICIAIS ----
    if tipo_site_lc in ("rss", "feed", "oficial"):
        # Para feeds, a URL já é a original
        # Tentar encontrar URL do artigo no link
        pass

    # ---- Remover duplicatas mantendo ordem ----
    unicas = []
    vistas = set()
    for v in variantes:
        v_norm = v.rstrip("/")
        if v_norm not in vistas:
            vistas.add(v_norm)
            unicas.append(v)

    logger.info("[v90][URL_VARIANTS] Total variantes unicas: %d", len(unicas))
    return unicas


def _eh_wordpress(dominio: str) -> bool:
    """Heurística para detectar se um domínio provavelmente usa WordPress."""
    indicadores_wp = [
        "wordpress", "wp", "blog", "noticias", "jornal", "revista",
    ]
    return any(ind in dominio for ind in indicadores_wp)


def _inserir_amp_no_path(url: str, parsed) -> str | None:
    """Insere /amp/ no path da URL de forma inteligente."""
    path = parsed.path
    if not path or path == "/":
        return None
    # Se já tem amp, não modificar
    if "/amp" in path:
        return None
    # Inserir /amp antes da extensão ou no final
    if path.endswith("/"):
        novo_path = path + "amp/"
    elif "." in path.split("/")[-1]:
        # Tem extensão (ex: .html)
        partes = path.rsplit(".", 1)
        novo_path = partes[0] + ".amp." + partes[1]
    else:
        novo_path = path + "/amp/"

    return urlunparse((parsed.scheme, parsed.netloc, novo_path, parsed.params, parsed.query, parsed.fragment))


def _extrair_slug(path: str) -> str | None:
    """Extrai o slug de uma URL WordPress a partir do path."""
    if not path or path == "/":
        return None
    # Remover barras e pegar último segmento
    segmentos = [s for s in path.split("/") if s]
    if not segmentos:
        return None
    slug = segmentos[-1]
    # Remover extensão
    slug = re.sub(r"\.[^.]+$", "", slug)
    # Remover query-like
    slug = slug.split("?")[0]
    if not slug or len(slug) < 2:
        return None
    return slug


def _resolver_redir_folha(url: str, parsed) -> str | None:
    """Tenta resolver redirecionamento do redir.folha.com.br."""
    # O redir.folha geralmente tem a URL real em query param ou no path
    # Exemplo: https://redir.folha.com.br/redir/online/.../url_real
    path = parsed.path
    if not path:
        return None

    # Tentar extrair de /redir/online/.../ ou query
    match = re.search(r"/redir/online/[^/]+/(.+)", path)
    if match:
        possivel = match.group(1)
        if possivel.startswith("http"):
            return possivel
        return f"https://www.folha.uol.com.br{possivel}"

    # Tentar de query string
    query = parsed.query
    if query:
        for param in ["url", "u", "link", "dest"]:
            match = re.search(rf"{param}=([^&]+)", query)
            if match:
                valor = match.group(1)
                if valor.startswith("http"):
                    return valor
                return f"https://www.folha.uol.com.br{valor}"

    return None
