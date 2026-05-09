"""Configuracoes, User-Agents e utilitarios do google_news_scraper."""

from __future__ import annotations

import random
import re
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# User-Agents rotativos
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENTS: list[str] = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Android
    "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    # iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    # Samsung Internet
    "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/117.0.0.0 Mobile Safari/537.36",
]

# ---------------------------------------------------------------------------
# Blacklist de dominios
# ---------------------------------------------------------------------------

DOMAIN_BLACKLIST: set[str] = {
    "google.com",
    "www.google.com",
    "news.google.com",
    "accounts.google.com",
    "support.google.com",
    "play.google.com",
    "maps.google.com",
    "youtube.com",
    "www.youtube.com",
    "facebook.com",
    "www.facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
}

# ---------------------------------------------------------------------------
# URLs do Google News
# ---------------------------------------------------------------------------

GOOGLE_NEWS_RSS_URL: str = "https://news.google.com/rss"
GOOGLE_NEWS_HTML_URL: str = "https://news.google.com/search"

# ---------------------------------------------------------------------------
# Tags HTML para remover na limpeza
# ---------------------------------------------------------------------------

HTML_CLEANUP_TAGS: frozenset[str] = frozenset({
    "script", "style", "nav", "footer", "header", "aside",
    "advertisement", "ad", "noscript", "iframe", "svg",
    "form", "button", "input", "select", "textarea",
})

# ---------------------------------------------------------------------------
# Funcoes utilitarias
# ---------------------------------------------------------------------------


def get_random_ua() -> str:
    """Retorna um User-Agent aleatorio da lista."""
    return random.choice(DEFAULT_USER_AGENTS)


def is_blacklisted(url: str) -> bool:
    """Verifica se a URL pertence a um dominio blacklisted.

    Args:
        url: URL completa ou dominio.

    Returns:
        True se o dominio esta na blacklist.
    """
    if not url or not url.strip():
        return True  # URL vazia e considerada blacklisted por seguranca
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.lower()
        # Remove www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain in DOMAIN_BLACKLIST
    except Exception:
        return True  # Por seguranca, bloqueia URLs invalidas


def normalize_url(url: str) -> str:
    """Normaliza uma URL removendo parametros de tracking.

    Remove utm_*, fbclid, gclid, etc. e normaliza o scheme.

    Args:
        url: URL original.

    Returns:
        URL normalizada.
    """
    if not url or not url.strip():
        return ""

    url = url.strip()

    # Converte http para https e garante scheme
    if url.startswith("http://"):
        url = "https://" + url[7:]
    elif url.startswith("//"):
        url = f"https:{url}"
    elif not url.startswith("https://"):
        url = f"https://{url}"

    try:
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(url)

        # Remove parametros de tracking
        params = parse_qs(parsed.query, keep_blank_values=True)
        tracking_prefixes = ("utm_", "fbclid", "gclid", "ref", "source",
                             "campaign", "medium", "content", "term",
                             "ito", "cid", "mc_cid", "mc_eid", "mkt_tok")
        clean_params = {
            k: v for k, v in params.items()
            if not any(k.lower().startswith(p) for p in tracking_prefixes)
        }

        new_query = urlencode(clean_params, doseq=True)

        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path,
             parsed.params, new_query, "")
        )
    except Exception:
        return url
