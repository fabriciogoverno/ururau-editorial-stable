"""Full article content extraction from arbitrary news pages."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
from readability import Document

from .config import DEFAULT_CONFIG, ID_CLASS_BLACKLIST
from .logger import get_logger
from .models import Article, ScraperConfig
from .utils import fetch_with_retry, is_valid_url

logger = get_logger(__name__)


class ArticleExtractor:
    """Extract structured article data from a news article URL."""

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or DEFAULT_CONFIG

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract_article(self, url: str) -> Article | None:
        """Fetch *url* and extract a structured :class:`Article`.

        Returns ``None`` if the page cannot be parsed or does not contain
        enough article text.
        """
        if not is_valid_url(url):
            logger.warning("Invalid URL skipped: %s", url)
            return None

        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout,
                follow_redirects=True,
            ) as client:
                html = await fetch_with_retry(client, url, self.config)
        except Exception as exc:
            logger.warning("Failed to fetch article %s: %s", url, exc)
            return None

        # ---- Primary: trafilatura ------------------------------------
        primary = self._extract_with_trafilatura(html, url)
        text = primary.get("article_text", "")

        # ---- Fallback: readability + BeautifulSoup -------------------
        fallback: dict[str, str | datetime | list[str] | None] = {}
        if len(text) < 200:
            logger.debug("Trafilatura text too short (%d chars), using fallback for %s", len(text), url)
            fallback = self._extract_with_fallback(html, url)
            # Merge: prefer fallback text, keep trafilatura metadata
            if fallback.get("article_text") and len(str(fallback["article_text"])) > len(text):
                primary["article_text"] = fallback["article_text"]
            for key in ("title", "author", "published_date", "description", "image", "images", "language"):
                if fallback.get(key) and not primary.get(key):
                    primary[key] = fallback[key]  # type: ignore[literal-required]

        article_text = str(primary.get("article_text", "")).strip()
        if len(article_text) < 100:
            logger.debug("Insufficient article text for %s (%d chars)", url, len(article_text))
            return None

        # ---- Build Article --------------------------------------------
        domain = urlparse(url).netloc
        published = primary.get("published_date")
        if isinstance(published, str):
            published = self._parse_date_string(published)

        image = primary.get("image")
        images = primary.get("images", [])
        if image and image not in images:
            images = [image] + images

        return Article(
            title=str(primary.get("title", "") or "Untitled"),
            description=primary.get("description"),
            author=primary.get("author"),
            published_date=published,
            image=image,
            images=images,
            article_text=article_text,
            url=url,
            domain=domain,
            language=primary.get("language"),
        )

    # ------------------------------------------------------------------
    # Extraction engines
    # ------------------------------------------------------------------

    def _extract_with_trafilatura(
        self, html: str, url: str
    ) -> dict[str, str | datetime | list[str] | None]:
        """Extract article using trafilatura (best quality)."""
        result: dict[str, str | datetime | list[str] | None] = {}
        try:
            extracted = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                include_images=True,
                include_formatting=False,
                output_format="json",
                with_metadata=True,
            )
            if extracted:
                data = json.loads(extracted) if isinstance(extracted, str) else extracted
                result["title"] = data.get("title") or data.get("sitename")
                result["author"] = data.get("author")
                result["description"] = data.get("description")
                result["article_text"] = data.get("raw_text") or data.get("text", "")
                result["language"] = data.get("language")
                result["image"] = data.get("image")
                result["images"] = [data["image"]] if data.get("image") else []
                date_raw = data.get("date")
                if date_raw:
                    result["published_date"] = self._parse_date_string(date_raw)
        except Exception as exc:
            logger.debug("Trafilatura extraction failed for %s: %s", url, exc)
        return result

    def _extract_with_fallback(
        self, html: str, url: str
    ) -> dict[str, str | datetime | list[str] | None]:
        """Fallback extraction using readability-lxml + BeautifulSoup."""
        result: dict[str, str | datetime | list[str] | None] = {}
        try:
            doc = Document(html)
            summary_html = doc.summary()
            soup = BeautifulSoup(html, "lxml")
            summary_soup = BeautifulSoup(summary_html, "lxml")

            # Title
            result["title"] = (
                self._meta_tag(soup, "og:title")
                or self._meta_tag(soup, "twitter:title")
                or doc.title()
                or soup.title.string if soup.title else None
            )

            # Description
            result["description"] = (
                self._meta_tag(soup, "og:description")
                or self._meta_tag(soup, "description")
            )

            # Author
            result["author"] = (
                self._meta_tag(soup, "article:author")
                or self._meta_tag(soup, "author")
                or self._extract_author_from_jsonld(soup)
            )

            # Date
            date_str = (
                self._meta_tag(soup, "article:published_time")
                or self._meta_tag(soup, "datePublished")
                or self._extract_date_from_jsonld(soup)
            )
            if date_str:
                result["published_date"] = self._parse_date_string(str(date_str))

            # Text
            result["article_text"] = self._clean_text(summary_soup.get_text(separator="\n"))

            # Images
            result["image"] = (
                self._meta_tag(soup, "og:image")
                or self._meta_tag(soup, "twitter:image")
            )
            result["images"] = self._extract_images_from_soup(summary_soup, url)
            if result["image"] and result["image"] not in result["images"]:
                result["images"] = [result["image"]] + result["images"]  # type: ignore[assignment]

            # Language
            lang_meta = soup.find("meta", attrs={"http-equiv": "content-language"})
            if lang_meta:
                result["language"] = lang_meta.get("content")
            else:
                html_tag = soup.find("html")
                if html_tag:
                    result["language"] = html_tag.get("lang")

        except Exception as exc:
            logger.debug("Fallback extraction failed for %s: %s", url, exc)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _meta_tag(soup: BeautifulSoup, name: str) -> str | None:
        """Return the content of a meta tag by *name* or *property*."""
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        return tag.get("content") if tag else None

    @staticmethod
    def _extract_date_from_jsonld(soup: BeautifulSoup) -> str | None:
        """Find ``datePublished`` in JSON-LD NewsArticle scripts."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "datePublished" in item:
                            return item["datePublished"]
                elif isinstance(data, dict):
                    return data.get("datePublished")
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    @staticmethod
    def _extract_author_from_jsonld(soup: BeautifulSoup) -> str | None:
        """Find author name in JSON-LD scripts."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    data = data[0] if data else {}
                if isinstance(data, dict):
                    author = data.get("author")
                    if isinstance(author, dict):
                        return author.get("name")
                    if isinstance(author, list) and author:
                        first = author[0]
                        return first.get("name") if isinstance(first, dict) else str(first)
                    if isinstance(author, str):
                        return author
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    @staticmethod
    def _extract_images_from_soup(soup: BeautifulSoup, base_url: str) -> list[str]:
        """Extract image URLs from the article content."""
        images: list[str] = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-original")
            if not src:
                continue
            src = src.strip()
            if src.startswith("data:"):
                continue
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(base_url, src)
            elif not src.startswith("http"):
                src = urljoin(base_url, src)

            # Filter ads by domain blacklist
            from .config import IMAGE_BLACKLIST
            if any(bad in src.lower() for bad in IMAGE_BLACKLIST):
                continue
            if src not in images:
                images.append(src)
        return images

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove residual HTML tags, collapse whitespace, normalise Unicode."""
        if not text:
            return ""
        # Remove any lingering HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode common HTML entities first
        import html
        text = html.unescape(text)
        # Collapse all whitespace (spaces, tabs, newlines) into single space
        text = re.sub(r"[ \t\n\r\f\v]+", " ", text)
        return text.strip()

    @staticmethod
    def _parse_date_string(value: str) -> datetime | None:
        """Parse a date string into an aware UTC datetime."""
        if not value:
            return None
        value = value.strip()

        # Already has timezone info
        fmts_tz = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%a, %d %b %Y %H:%M:%S %z",
        ]
        for fmt in fmts_tz:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue

        # No timezone — assume UTC
        fmts = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
        ]
        for fmt in fmts:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        # ISO format with Z
        if value.endswith("Z"):
            try:
                dt = datetime.fromisoformat(value[:-1])
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        # RFC 2822 without explicit tz
        try:
            from dateutil import parser as dateutil_parser
            dt = dateutil_parser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

        return None


__all__ = ["ArticleExtractor"]
