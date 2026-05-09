"""
ururau.coleta.site_introspector_v90
=====================================
Módulo de introspecção de sites para descoberta automática de:
- sitemaps, feeds RSS, endpoints WordPress, editorias, AMP, JSON-LD,
  seletor provável de cards e adaptador recomendado.

Uso:
    from ururau.coleta.site_introspector_v90 import inspecionar_site_v90
    resultado = inspecionar_site_v90("https://exemplo.com.br")
"""

import logging
import re
import time
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Caminhos a testar automaticamente
SITEMAP_PATHS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/news-sitemap.xml",
    "/sitemap-news.xml",
    "/post-sitemap.xml",
]

RSS_PATHS = [
    "/feed/",
    "/rss",
    "/rss.xml",
]

WP_API_PATHS = [
    "/wp-json/wp/v2/posts",
]

SECTION_PATHS = [
    "/politica/",
    "/rio/",
    "/cidades/",
    "/policia/",
    "/saude/",
    "/economia/",
    "/brasil/",
    "/mundo/",
    "/esportes/",
    "/norte-fluminense/",
    "/campos/",
]

# Heurística para detectar WordPress no HTML
WP_HINTS = [
    re.compile(r"/wp-content/", re.IGNORECASE),
    re.compile(r"/wp-includes/", re.IGNORECASE),
    re.compile(r"wp-json", re.IGNORECASE),
    re.compile(r"<meta\s+name=['\"]generator['\"]\s+content=['\"]WordPress", re.IGNORECASE),
    re.compile(r"/wp-login\.php", re.IGNORECASE),
    re.compile(r"/wp-admin/", re.IGNORECASE),
    re.compile(r"class=['\"][^'\"]*wp-block", re.IGNORECASE),
]

# Heurística para AMP
AMP_HINTS = [
    re.compile(r"<html\s[^>]*amp\b", re.IGNORECASE),
    re.compile(r"<html\s[^>]*⚡", re.IGNORECASE),
    re.compile(r'rel=["\']amphtml["\']', re.IGNORECASE),
    re.compile(r'<link[^>]+amp\.html', re.IGNORECASE),
]

# Heurística para JSON-LD
JSONLD_HINTS = [
    re.compile(r'<script\s+type=["\']application/ld\+json["\']', re.IGNORECASE),
]

# Heurística para seletor de cards
CARD_SELECTORS = [
    ("article", 5),
    (".post", 5),
    (".card", 5),
    (".news-item", 5),
    (".entry", 5),
    ("[class*='card']", 4),
    ("[class*='post']", 4),
    ("[class*='news']", 4),
    ("[class*='article']", 4),
    (".noticia", 4),
    (".materia", 4),
]

# ---------------------------------------------------------------------------
# safe_get
# ---------------------------------------------------------------------------

def _log(level: str, message: str) -> None:
    """Emite log prefixado com [v90][INTROSPECTOR]."""
    prefix = "[v90][INTROSPECTOR]"
    if level == "debug":
        logger.debug("%s %s", prefix, message)
    elif level == "info":
        logger.info("%s %s", prefix, message)
    elif level == "warning":
        logger.warning("%s %s", prefix, message)
    elif level == "error":
        logger.error("%s %s", prefix, message)


def safe_get(url: str, timeout: int = 15, allow_redirects: bool = True) -> requests.Response | None:
    """
    Faz GET seguro com tratamento de exceções.

    Retorna Response ou None em caso de erro/404/timeout.
    """
    try:
        _log("debug", f"safe_get → {url}")
        resp = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )
        # Tratamos 404 como "não encontrado" sem levantar exceção
        if resp.status_code == 404:
            _log("debug", f"safe_get 404 para {url}")
            return None
        resp.raise_for_status()
        return resp
    except requests.exceptions.Timeout:
        _log("warning", f"safe_get TIMEOUT para {url}")
        return None
    except requests.exceptions.ConnectionError as exc:
        _log("warning", f"safe_get CONNECTION_ERROR para {url}: {exc}")
        return None
    except requests.exceptions.HTTPError as exc:
        # 4xx/5xx fora do 404
        _log("warning", f"safe_get HTTP_ERROR {exc.response.status_code if exc.response else '?'} para {url}")
        return None
    except requests.exceptions.RequestException as exc:
        _log("warning", f"safe_get REQUEST_EXCEPTION para {url}: {exc}")
        return None
    except Exception as exc:
        _log("error", f"safe_get UNEXPECTED_EXCEPTION para {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Helpers de detecção
# ---------------------------------------------------------------------------

def _extract_domain(base_url: str) -> str:
    """Extrai domínio limpo a partir de uma URL."""
    parsed = urlparse(base_url)
    domain = parsed.netloc or parsed.path
    # Remove www. se existir
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.lower()


def _detect_wordpress(html: str | None, wp_json_ok: bool) -> bool:
    """Retorna True se há indícios de WordPress no HTML ou API acessível."""
    if wp_json_ok:
        return True
    if not html:
        return False
    for pattern in WP_HINTS:
        if pattern.search(html):
            return True
    return False


def _detect_amp(html: str | None) -> bool:
    """Retorna True se há indícios de AMP no HTML."""
    if not html:
        return False
    for pattern in AMP_HINTS:
        if pattern.search(html):
            return True
    return False


def _detect_jsonld(html: str | None) -> bool:
    """Retorna True se há JSON-LD no HTML."""
    if not html:
        return False
    for pattern in JSONLD_HINTS:
        if pattern.search(html):
            return True
    return False


def _count_selector_occurrences(html: str, selector: str) -> int:
    """
    Conta ocorrências aproximadas de um seletor CSS no HTML.
    Simplificado: busca por tags ou classes no HTML bruto.
    """
    if not html:
        return 0
    # Seletor simples de tag
    if selector.startswith("."):
        class_name = selector[1:]
        # busca class="... class_name ..." ou class='... class_name ...'
        pattern = re.compile(
            rf'class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\']',
            re.IGNORECASE,
        )
    elif selector.startswith("[class*="):
        # extrai o nome entre aspas
        match = re.search(r"\['\"](.+?)['\"]\]", selector)
        if match:
            class_name = match.group(1)
            pattern = re.compile(
                rf'class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\']',
                re.IGNORECASE,
            )
        else:
            return 0
    else:
        # tag direta
        pattern = re.compile(rf"<{re.escape(selector)}\b", re.IGNORECASE)

    return len(pattern.findall(html))


def _guess_card_selector(html: str | None) -> str | None:
    """
    Tenta adivinhar o seletor CSS mais provável para cards/notícias
    a partir da contagem de ocorrências no HTML.
    """
    if not html:
        return None
    best_selector = None
    best_score = 0
    for selector, weight in CARD_SELECTORS:
        count = _count_selector_occurrences(html, selector)
        score = count * weight
        if score > best_score:
            best_score = score
            best_selector = selector
    # Só retorna se houver pelo menos 3 ocorrências
    if best_score >= 3:
        return best_selector
    return None


def _choose_adapter(domain: str, wp_detected: bool, wp_json_ok: bool, has_amp: bool) -> str:
    """Escolhe o adaptador recomendado baseado nas características detectadas."""
    if wp_json_ok:
        return "wordpress_json"
    if wp_detected:
        return "wordpress"
    if has_amp:
        return "amp"
    # Fallback genérico
    return "generic"


# ---------------------------------------------------------------------------
# Introspector principal
# ---------------------------------------------------------------------------

def inspecionar_site_v90(base_url: str) -> dict:
    """
    Descobre:
    - domínio;
    - se parece WordPress;
    - RSS possíveis;
    - sitemaps possíveis;
    - páginas de editoria;
    - se há JSON-LD;
    - se há AMP;
    - seletor provável de cards;
    - método recomendado.

    Parâmetros
    ----------
    base_url : str
        URL base do site (ex.: "https://exemplo.com.br").

    Retorna
    -------
    dict
        Estrutura padronizada com os achados da introspecção.
    """
    _log("info", f"Iniciando introspecção para: {base_url}")

    notes: list[str] = []
    sitemaps_found: list[str] = []
    rss_found: list[str] = []
    sections_found: list[str] = []
    wp_json_ok = False
    html_content: str | None = None
    home_status: int | None = None

    # Normaliza base_url
    base_url = base_url.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
        notes.append(f"Protocolo omitido; assumido https: {base_url}")

    domain = _extract_domain(base_url)

    # ------------------------------------------------------------------
    # 1. Fetch da homepage para obter HTML base
    # ------------------------------------------------------------------
    home_resp = safe_get(base_url, timeout=15)
    if home_resp is not None:
        home_status = home_resp.status_code
        try:
            html_content = home_resp.text
            _log("info", f"Homepage acessada com sucesso: {home_status}")
        except Exception as exc:
            notes.append(f"Erro ao ler HTML da homepage: {exc}")
            _log("warning", f"Falha ao extrair texto da homepage: {exc}")
    else:
        notes.append("Homepage não acessível (timeout/erro/404).")
        _log("warning", "Homepage não acessível.")

    # ------------------------------------------------------------------
    # 2. Testa sitemaps
    # ------------------------------------------------------------------
    for path in SITEMAP_PATHS:
        url = urljoin(base_url, path)
        resp = safe_get(url, timeout=10)
        if resp is not None:
            content_type = resp.headers.get("Content-Type", "").lower()
            # Aceita XML ou texto genérico (alguns servidores enviam text/plain)
            if "xml" in content_type or resp.text.strip().startswith("<?xml") or "<urlset" in resp.text or "<sitemapindex" in resp.text:
                sitemaps_found.append(url)
                _log("info", f"Sitemap encontrado: {url}")
            else:
                _log("debug", f"Path {url} respondeu mas não parece XML de sitemap (CT={content_type}).")
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # 3. Testa RSS/Feeds
    # ------------------------------------------------------------------
    for path in RSS_PATHS:
        url = urljoin(base_url, path)
        resp = safe_get(url, timeout=10)
        if resp is not None:
            content_type = resp.headers.get("Content-Type", "").lower()
            body = resp.text.strip()
            if "rss" in content_type or body.startswith("<?xml") or "<rss" in body or "<feed" in body:
                rss_found.append(url)
                _log("info", f"RSS/Feed encontrado: {url}")
            else:
                _log("debug", f"Path {url} respondeu mas não parece feed (CT={content_type}).")
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # 4. Testa WordPress JSON API
    # ------------------------------------------------------------------
    for path in WP_API_PATHS:
        url = urljoin(base_url, path)
        resp = safe_get(url, timeout=10)
        if resp is not None:
            content_type = resp.headers.get("Content-Type", "").lower()
            body = resp.text.strip()
            if "json" in content_type or body.startswith("[") or body.startswith("{"):
                wp_json_ok = True
                _log("info", f"WP JSON API encontrada: {url}")
            else:
                _log("debug", f"Path {url} respondeu mas não parece JSON (CT={content_type}).")
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # 5. Testa editorias/seções
    # ------------------------------------------------------------------
    for path in SECTION_PATHS:
        url = urljoin(base_url, path)
        resp = safe_get(url, timeout=10)
        if resp is not None and resp.status_code < 400:
            # Verifica se a resposta parece uma página válida (HTML ou redirecionamento 200)
            content_type = resp.headers.get("Content-Type", "").lower()
            if "html" in content_type or resp.text.strip().startswith("<"):
                sections_found.append(url)
                _log("info", f"Seção encontrada: {url}")
            else:
                _log("debug", f"Seção {url} respondeu mas CT={content_type} não indica HTML.")
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # 6. Detecções no HTML
    # ------------------------------------------------------------------
    wp_detected = _detect_wordpress(html_content, wp_json_ok)
    has_amp = _detect_amp(html_content)
    has_jsonld = _detect_jsonld(html_content)
    probable_selector = _guess_card_selector(html_content)

    site_type = "wordpress" if wp_detected else "generic"
    recommended_adapter = _choose_adapter(domain, wp_detected, wp_json_ok, has_amp)

    # Monta type com mais granularidade
    if wp_detected and wp_json_ok:
        site_type = "wordpress_json"
    elif wp_detected:
        site_type = "wordpress"
    elif has_amp:
        site_type = "amp"
    else:
        site_type = "generic"

    # ------------------------------------------------------------------
    # 7. Monta resultado
    # ------------------------------------------------------------------
    result = {
        "ok": True,
        "domain": domain,
        "type": site_type,
        "rss_found": rss_found,
        "sitemaps_found": sitemaps_found,
        "sections_found": sections_found,
        "wp_json": wp_json_ok,
        "has_amp": has_amp,
        "has_jsonld": has_jsonld,
        "recommended_adapter": recommended_adapter,
        "notes": notes,
    }

    # Adiciona seletor provável se encontrado
    if probable_selector:
        result["probable_card_selector"] = probable_selector

    _log("info", f"Introspecção concluída para {domain}. "
                 f"Sitemaps={len(sitemaps_found)}, RSS={len(rss_found)}, "
                 f"Sections={len(sections_found)}, WP={wp_detected}, AMP={has_amp}, JSON-LD={has_jsonld}")

    return result
