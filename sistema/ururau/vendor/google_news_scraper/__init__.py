"""Google News Article Scraper — extract full news articles with structured data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .models import Article, ArticleLink, ScraperConfig, SearchParams
from .utils import ScraperError

if TYPE_CHECKING:
    from .extractor import ArticleExtractor
    from .scraper import GoogleNewsScraper

__version__ = "0.1.0"
__all__ = [
    "Article",
    "ArticleLink",
    "ScraperConfig",
    "SearchParams",
    "ScraperError",
    "GoogleNewsScraper",
    "ArticleExtractor",
]


def __getattr__(name: str):
    """Lazy imports to avoid circular dependencies."""
    if name == "GoogleNewsScraper":
        from .scraper import GoogleNewsScraper as _GoogleNewsScraper
        return _GoogleNewsScraper
    if name == "ArticleExtractor":
        from .extractor import ArticleExtractor as _ArticleExtractor
        return _ArticleExtractor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
