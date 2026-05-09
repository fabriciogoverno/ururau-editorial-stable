"""Utility helpers for retry logic, user-agent rotation, URL handling, etc."""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

import httpx

from .config import USER_AGENTS
from .logger import get_logger
from .models import Article, ScraperConfig

logger = get_logger(__name__)


class ScraperError(Exception):
    """Custom exception raised when scraping fails after all retries."""

    pass


def get_random_user_agent() -> str:
    """Return a random modern browser User-Agent string."""
    return random.choice(USER_AGENTS)


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    config: ScraperConfig,
) -> str:
    """Fetch *url* retrying up to *config.max_retries* times with exponential backoff.

    Returns the response text on success. Raises :class:`ScraperError` on failure.
    """
    last_exception: Exception | None = None
    for attempt in range(1, config.max_retries + 1):
        try:
            headers = {"User-Agent": get_random_user_agent()} if config.user_agent_rotation else {}
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exception = exc
            wait = config.retry_backoff ** attempt
            logger.warning("Request failed (attempt %d/%d) for %s: %s — retrying in %.1fs",
                           attempt, config.max_retries, url, exc, wait)
            await asyncio.sleep(wait)
    raise ScraperError(f"Failed to fetch {url} after {config.max_retries} attempts: {last_exception}")


def is_valid_url(url: str) -> bool:
    """Return *True* if *url* looks like a valid HTTP(S) URL."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """Remove fragments and known tracking query parameters from *url*."""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    tracking = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                "fbclid", "gclid", "ref", "source", "medium", "campaign", "si"}
    filtered = {k: v for k, v in query_params.items() if k.lower() not in tracking}
    new_query = urlencode(filtered, doseq=True)
    return urlunparse(parsed._replace(fragment="", query=new_query))


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    """Return *articles* deduplicated by normalized URL, preserving order."""
    seen: set[str] = set()
    result: list[Article] = []
    for art in articles:
        key = normalize_url(art.url)
        if key not in seen:
            seen.add(key)
            result.append(art)
    return result


def parse_relative_time(text: str) -> datetime | None:
    """Convert relative time strings like ``"2 hours ago"`` to UTC datetime.

    Returns ``None`` if the text cannot be parsed.
    """
    if not text:
        return None
    text = text.lower().strip()
    now = datetime.now(timezone.utc)

    # "X minutes/hours/days/weeks/months/years ago"
    m = re.match(r"(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago", text)
    if m:
        qty, unit = int(m.group(1)), m.group(2)
        delta = {
            "minute": timedelta(minutes=qty),
            "hour": timedelta(hours=qty),
            "day": timedelta(days=qty),
            "week": timedelta(weeks=qty),
            "month": timedelta(days=qty * 30),
            "year": timedelta(days=qty * 365),
        }[unit]
        return now - delta

    # Single units without number ("a hour ago", "an hour ago")
    m = re.match(r"(?:a|an)\s+(minute|hour|day|week|month|year)s?\s+ago", text)
    if m:
        unit = m.group(1)
        delta = {
            "minute": timedelta(minutes=1),
            "hour": timedelta(hours=1),
            "day": timedelta(days=1),
            "week": timedelta(weeks=1),
            "month": timedelta(days=30),
            "year": timedelta(days=365),
        }[unit]
        return now - delta

    # "yesterday"
    if "yesterday" in text:
        return now - timedelta(days=1)

    # "just now", "moments ago"
    if text in ("just now", "moments ago"):
        return now

    # Try ISO / common formats as absolute fallback
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None
