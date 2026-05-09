"""Google News Scraper — extracao completa de artigos."""

from .models import (
    Article,
    CountryCode,
    LanguageCode,
    ScraperConfig,
    SearchParams,
)
from .scraper import GoogleNewsScraper
from .extractor import ArticleExtractor
from .config import (
    get_random_ua,
    is_blacklisted,
    normalize_url,
)
from .utils import (
    DomainCooldown,
    deduplicate_by_key,
    extract_domain,
    fetch_with_retry,
    is_within_window,
    parse_google_date,
)
from .logger import get_logger

__version__ = "1.0.0"

__all__ = [
    # Models
    "Article",
    "SearchParams",
    "ScraperConfig",
    "CountryCode",
    "LanguageCode",
    # Engines
    "GoogleNewsScraper",
    "ArticleExtractor",
    # Config
    "get_random_ua",
    "is_blacklisted",
    "normalize_url",
    # Utils
    "DomainCooldown",
    "deduplicate_by_key",
    "extract_domain",
    "fetch_with_retry",
    "is_within_window",
    "parse_google_date",
    # Logger
    "get_logger",
]
