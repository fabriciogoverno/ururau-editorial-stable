"""Utilitarios async: retry, dedup, cooldown, normalizacao de URL."""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar

import aiohttp

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Retry com backoff exponencial
# ---------------------------------------------------------------------------


async def fetch_with_retry(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
    max_retries: int = 3,
    backoff: float = 1.7,
    max_sleep: float = 12.0,
    timeout: int = 14,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Faz fetch de uma URL com retry e backoff exponencial + jitter.

    Retorna o conteudo HTML/texto ou None se todas as tentativas falharem.
    Respeita max_sleep como teto do tempo de espera.
    """
    from .config import get_random_ua

    if headers is None:
        headers = {"User-Agent": get_random_ua()}

    client_owned = session is None
    if client_owned:
        session = aiohttp.ClientSession(headers=headers)

    try:
        for attempt in range(1, max_retries + 1):
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
                        # Too Many Requests — espera mais
                        wait = min(backoff ** attempt + random.uniform(0, 2), max_sleep)
                        await asyncio.sleep(wait)
                    elif 500 <= response.status < 600:
                        # Server error — retry
                        wait = min(backoff ** attempt + random.uniform(0, 1), max_sleep)
                        await asyncio.sleep(wait)
                    else:
                        # Outros erros (4xx) — nao retry
                        return None
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                if attempt == max_retries:
                    return None
                wait = min(backoff ** attempt + random.uniform(0, 1), max_sleep)
                await asyncio.sleep(wait)

        return None
    finally:
        if client_owned and session:
            await session.close()


# ---------------------------------------------------------------------------
# Normalizacao de URL
# ---------------------------------------------------------------------------


def extract_domain(url: str) -> str:
    """Extrai o dominio de uma URL, removendo www.

    Args:
        url: URL completa.

    Returns:
        Dominio (ex: 'g1.globo.com').
    """
    if not url:
        return ""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def deduplicate_by_key(
    items: List[T], key_func: Callable[[T], str]
) -> List[T]:
    """Remove duplicatas de uma lista preservando ordem.

    Args:
        items: Lista de itens.
        key_func: Funcao que extrai a chave de cada item.

    Returns:
        Lista sem duplicatas (primeira ocorrencia e mantida).
    """
    seen: set[str] = set()
    result: List[T] = []
    for item in items:
        key = key_func(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# Cooldown de dominio
# ---------------------------------------------------------------------------


class DomainCooldown:
    """Gerencia cooldown por dominio apos HTTP 429.

    Thread-safe usando asyncio.Lock.
    """

    def __init__(self, cooldown_seconds: int = 180):
        self.cooldown_seconds = cooldown_seconds
        self._cooldowns: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _get_domain(self, url_or_domain: str) -> str:
        """Extrai dominio de URL ou string."""
        return extract_domain(url_or_domain)

    def mark_429(self, domain: str) -> None:
        """Marca um dominio como em cooldown."""
        dom = self._get_domain(domain)
        if dom:
            self._cooldowns[dom] = time.monotonic()

    def is_in_cooldown(self, domain: str) -> bool:
        """Verifica se um dominio esta em cooldown."""
        dom = self._get_domain(domain)
        if dom not in self._cooldowns:
            return False
        elapsed = time.monotonic() - self._cooldowns[dom]
        return elapsed < self.cooldown_seconds

    async def wait_if_needed(self, domain: str) -> None:
        """Espera o cooldown de um dominio se necessario."""
        async with self._lock:
            dom = self._get_domain(domain)
            if dom not in self._cooldowns:
                return
            elapsed = time.monotonic() - self._cooldowns[dom]
            remaining = self.cooldown_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
            # Limpa apos esperar
            self._cooldowns.pop(dom, None)


# ---------------------------------------------------------------------------
# Janela temporal
# ---------------------------------------------------------------------------


def is_within_window(
    dt: Optional[datetime], hours: int = 4
) -> bool:
    """Verifica se um datetime esta dentro das ultimas N horas.

    Args:
        dt: Datetime a verificar (timezone-aware ou naive).
        hours: Tamanho da janela em horas.

    Returns:
        True se dt estiver dentro da janela ou se dt for None
        (assume-se que itens sem data passam no filtro).
    """
    if dt is None:
        return True  # Itens sem data nao sao filtrados

    try:
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            # Naive — assume UTC
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt
        return delta <= timedelta(hours=hours)
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Parsing de datas do Google News
# ---------------------------------------------------------------------------


def parse_google_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse de datas do Google News RSS (RFC 2822 e ISO 8601).

    Args:
        date_str: String de data (ex: 'Mon, 15 May 2026 10:30:00 GMT').

    Returns:
        datetime timezone-aware ou None.
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # RFC 2822 (padrao RSS)
    rfc_formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %Z",
    ]

    for fmt in rfc_formats:
        try:
            # Substitui timezone abbreviations por offset
            cleaned = date_str
            if "GMT" in cleaned or "UTC" in cleaned:
                cleaned = cleaned.replace("GMT", "+0000").replace("UTC", "+0000")
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    # ISO 8601
    iso_formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]

    for fmt in iso_formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    return None
