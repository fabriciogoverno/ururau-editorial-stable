"""Google News search scraper."""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from urllib.parse import quote, urlencode

import httpx
from bs4 import BeautifulSoup

from .config import DEFAULT_CONFIG, GOOGLE_NEWS_URL, GOOGLE_NEWS_RSS_URL
from .logger import get_logger
from .models import Article, ArticleLink, ScraperConfig, SearchParams
from .utils import fetch_with_retry, normalize_url

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class GoogleNewsScraper:
    """Search Google News and optionally extract full article content."""

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self._logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(self, params: SearchParams) -> list[ArticleLink]:
        """Search Google News and return a deduplicated list of article links."""
        html_results = await self._fetch_html_results(params)
        rss_results = await self._fetch_rss_results(params)
        merged = self._merge_results(html_results, rss_results)
        self._logger.info("Search for %r returned %d unique links", params.query, len(merged))
        return merged[: params.max_results]

    async def scrape_full_articles(self, params: SearchParams) -> list[Article]:
        """Search Google News and extract full article text for each result."""
        links = await self.search(params)
        if not links:
            return []

        # Lazy import to avoid circular dependency
        from .extractor import ArticleExtractor

        extractor = ArticleExtractor(self.config)
        semaphore = asyncio.Semaphore(self.config.concurrency)

        async def _extract(link: ArticleLink) -> Article | None:
            async with semaphore:
                try:
                    return await extractor.extract_article(link.url)
                except Exception as exc:
                    self._logger.warning("Extraction failed for %s: %s", link.url, exc)
                    return None

        tasks = [asyncio.create_task(_extract(link)) for link in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles: list[Article] = []
        failures = 0
        for res in results:
            if isinstance(res, Article):
                articles.append(res)
            else:
                failures += 1

        self._logger.info(
            "Scraped %d articles successfully (%d failures) for query %r",
            len(articles),
            failures,
            params.query,
        )
        return articles

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_search_url(self, params: SearchParams, use_rss: bool = False) -> str:
        """Build the Google News search URL (HTML or RSS)."""
        base = GOOGLE_NEWS_RSS_URL if use_rss else GOOGLE_NEWS_URL
        hl = params.language.lower()
        gl = params.country.upper()
        ceid = f"{gl}:{hl}"

        query_parts = {"q": params.query, "hl": hl, "gl": gl, "ceid": ceid}

        # Date range filter
        if params.from_date and params.to_date:
            cd_min = params.from_date.strftime("%m/%d/%Y")
            cd_max = params.to_date.strftime("%m/%d/%Y")
            query_parts["tbs"] = f"cdr:1,cd_min:{cd_min},cd_max:{cd_max}"

        return f"{base}?{urlencode(query_parts)}"

    async def _fetch_html_results(self, params: SearchParams) -> list[ArticleLink]:
        """Fetch the HTML search results page and parse article cards."""
        url = self._build_search_url(params, use_rss=False)
        self._logger.debug("Fetching HTML results: %s", url)

        proxies = self._proxy_dict(params)
        async with httpx.AsyncClient(
            timeout=self.config.timeout,
            proxy=proxies,  
            follow_redirects=True,
        ) as client:
            html = await fetch_with_retry(client, url, self.config)
            await asyncio.sleep(self.config.request_delay)
        return self._parse_article_cards(html)

    async def _fetch_rss_results(self, params: SearchParams) -> list[ArticleLink]:
        """Fetch the RSS feed for additional results."""
        url = self._build_search_url(params, use_rss=True)
        self._logger.debug("Fetching RSS results: %s", url)

        proxies = self._proxy_dict(params)
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout,
                proxy=proxies,  
                follow_redirects=True,
            ) as client:
                xml_text = await fetch_with_retry(client, url, self.config)
                await asyncio.sleep(self.config.request_delay)
        except Exception as exc:
            self._logger.warning("RSS fetch failed: %s", exc)
            return []

        return self._parse_rss(xml_text)

    def _parse_article_cards(self, html: str) -> list[ArticleLink]:
        """Parse article cards from the Google News HTML page."""
        soup = BeautifulSoup(html, "lxml")
        links: list[ArticleLink] = []

        # Strategy 1: <article> tags (most common structure)
        articles = soup.find_all("article")
        if articles:
            for article in articles:
                try:
                    link = self._extract_card_from_article_tag(article)
                    if link:
                        links.append(link)
                except Exception:
                    continue
            if links:
                return links

        # Strategy 2: div[data-n-tid] containers
        containers = soup.find_all("div", attrs={"data-n-tid": True})
        if containers:
            for container in containers:
                try:
                    link = self._extract_card_from_container(container)
                    if link:
                        links.append(link)
                except Exception:
                    continue
            if links:
                return links

        # Strategy 3: any <a> pointing to ./articles/
        for a_tag in soup.find_all("a", href=re.compile(r"^\./articles/")):
            try:
                href = a_tag.get("href", "")
                url = "https://news.google.com" + href.lstrip(".")
                title = a_tag.get_text(strip=True)
                if title and url:
                    links.append(ArticleLink(url=url, title=title))
            except Exception:
                continue

        return links

    def _extract_card_from_article_tag(self, article) -> ArticleLink | None:
        """Extract ArticleLink from a BeautifulSoup <article> tag."""
        a_tag = article.find("a", href=re.compile(r"^\./articles/"))
        if not a_tag:
            return None
        href = a_tag.get("href", "")
        url = "https://news.google.com" + href.lstrip(".")
        title = a_tag.get_text(strip=True) if a_tag else ""

        # Source name
        source_div = article.find("div", attrs={"data-n-tid": True})
        source = source_div.get_text(strip=True) if source_div else ""
        if not source:
            # Alternative: <div> with img (favicon) followed by text
            img = article.find("img")
            if img and img.find_parent("div"):
                source = img.find_parent("div").get_text(strip=True)

        # Time
        time_div = article.find("div", class_=re.compile("time"))
        time_text = time_div.get_text(strip=True) if time_div else ""
        if not time_text:
            time_span = article.find("span")
            if time_span:
                time_text = time_span.get_text(strip=True)

        # Snippet
        snippet_div = article.find("div", class_=re.compile("desc|snippet|summary"))
        snippet = snippet_div.get_text(strip=True) if snippet_div else ""

        if title and url:
            return ArticleLink(
                url=url, title=title, source=source,
                published_time_text=time_text, snippet=snippet,
            )
        return None

    def _extract_card_from_container(self, container) -> ArticleLink | None:
        """Extract ArticleLink from a div[data-n-tid] container."""
        a_tag = container.find("a", href=re.compile(r"^\./articles/"))
        if not a_tag:
            a_tag = container.find("a")
        if not a_tag:
            return None

        href = a_tag.get("href", "")
        if href.startswith("./"):
            url = "https://news.google.com" + href.lstrip(".")
        elif href.startswith("http"):
            url = href
        else:
            url = "https://news.google.com/" + href.lstrip("/")

        title = a_tag.get_text(strip=True)

        source = container.get("data-n-tid", "")
        time_text = ""
        snippet = ""

        if title and url:
            return ArticleLink(
                url=url, title=title, source=source,
                published_time_text=time_text, snippet=snippet,
            )
        return None

    def _parse_rss(self, xml_text: str) -> list[ArticleLink]:
        """Parse Google News RSS feed XML."""
        links: list[ArticleLink] = []
        try:
            root = ET.fromstring(xml_text)
            # RSS 2.0 namespace
            channel = root.find("channel")
            if channel is None:
                return links
            for item in channel.findall("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                pub_date_el = item.find("pubDate")
                source_el = item.find("source")

                title = title_el.text if title_el is not None else ""
                url = link_el.text if link_el is not None else ""
                pub_date = pub_date_el.text if pub_date_el is not None else ""
                source = source_el.text if source_el is not None else ""

                if title and url:
                    links.append(
                        ArticleLink(
                            url=url,
                            title=title,
                            source=source,
                            published_time_text=pub_date,
                        )
                    )
        except ET.ParseError as exc:
            self._logger.warning("RSS XML parse error: %s", exc)
        return links

    def _merge_results(
        self, html_results: list[ArticleLink], rss_results: list[ArticleLink]
    ) -> list[ArticleLink]:
        """Merge HTML and RSS results, preferring HTML metadata, deduplicated by URL."""
        seen: dict[str, ArticleLink] = {}

        # HTML results get priority
        for link in html_results:
            key = normalize_url(link.url)
            if key not in seen:
                seen[key] = link

        # Fill in from RSS only if URL not already present
        for link in rss_results:
            key = normalize_url(link.url)
            if key not in seen:
                seen[key] = link

        return list(seen.values())

    def _proxy_dict(self, params: SearchParams) -> str | None:
        """Return httpx-compatible proxy URL if enabled."""
        if params.use_proxy and params.proxy_url:
            return params.proxy_url
        if self.config.proxy:
            return self.config.proxy
        return None


# Back-compat alias
__all__ = ["GoogleNewsScraper"]
