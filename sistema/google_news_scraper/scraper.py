"""GoogleNewsScraper — busca de artigos no Google News via RSS e HTML."""

from __future__ import annotations

import asyncio
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup

from .config import (
    GOOGLE_NEWS_HTML_URL,
    GOOGLE_NEWS_RSS_URL,
    get_random_ua,
    is_blacklisted,
    normalize_url,
)
from .logger import get_logger
from .models import Article, ScraperConfig, SearchParams
from .utils import DomainCooldown, deduplicate_by_key, extract_domain, parse_google_date

logger = get_logger("scraper")


class GoogleNewsScraper:
    """Scraper de artigos do Google News.

    Usa RSS como fonte primaria e HTML como fallback.
    Resolve redirects de news.google.com para URLs reais.
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or ScraperConfig()
        self.cooldown = DomainCooldown(self.config.cooldown_429_seconds)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "GoogleNewsScraper":
        headers = {}
        if self.config.rotate_user_agent:
            headers["User-Agent"] = get_random_ua()
        self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError(
                "Scraper deve ser usado como async context manager "
                "(async with scraper:)"
            )
        return self._session

    # ------------------------------------------------------------------
    # Busca publica
    # ------------------------------------------------------------------

    async def search(self, params: SearchParams) -> List[Article]:
        """Busca artigos no Google News (metadata apenas, sem texto completo).

        Tenta RSS primeiro; se retornar < 3 resultados, tenta HTML.

        Args:
            params: Parametros de busca.

        Returns:
            Lista de Article com titulo, URL, data, etc. (sem article_text).
        """
        logger.info(f"Buscando: {params.query!r} (max={params.max_results})")

        # Tenta RSS primeiro
        articles = await self._search_rss(params)
        logger.info(f"RSS retornou {len(articles)} artigos")

        # Fallback para HTML se RSS retornar pouco
        if len(articles) < 3:
            html_articles = await self._search_html(params)
            logger.info(f"HTML retornou {len(html_articles)} artigos")
            articles.extend(html_articles)

        # Deduplica
        articles = self._deduplicate(articles)

        # Limita ao max_results
        if len(articles) > params.max_results:
            articles = articles[: params.max_results]

        logger.info(f"Total apos dedup: {len(articles)} artigos")
        return articles

    async def search_and_extract(
        self, params: SearchParams
    ) -> List[Article]:
        """Busca + extrai texto completo de cada artigo.

        Args:
            params: Parametros de busca.

        Returns:
            Lista de Article com article_text preenchido.
        """
        from .extractor import ArticleExtractor

        articles = await self.search(params)
        if not articles:
            return []

        extractor = ArticleExtractor(self.config)
        semaphore = asyncio.Semaphore(self.config.concurrency)

        async def _extract_one(article: Article) -> Article:
            async with semaphore:
                try:
                    result = await extractor.extract(article.url)
                    if result and result.get("article_text"):
                        article.article_text = result["article_text"]
                    if result:
                        if result.get("author"):
                            article.author = result["author"]
                        if result.get("images"):
                            article.images = result["images"]
                        if result.get("published_date"):
                            article.published_date = result["published_date"]
                except Exception as e:
                    logger.warning(f"Erro extraindo {article.url}: {e}")
                return article

        tasks = [_extract_one(a) for a in articles]
        return await asyncio.gather(*tasks)

    # ------------------------------------------------------------------
    # Busca RSS (primaria)
    # ------------------------------------------------------------------

    async def _search_rss(self, params: SearchParams) -> List[Article]:
        """Busca via RSS do Google News."""
        rss_url = self._build_rss_url(params)
        logger.debug(f"RSS URL: {rss_url}")

        try:
            async with self.session.get(
                rss_url,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status != 200:
                    logger.warning(f"RSS HTTP {response.status}")
                    return []

                xml_text = await response.text()
                return self._parse_rss(xml_text, params)

        except Exception as e:
            logger.warning(f"Erro RSS: {e}")
            return []

    def _parse_rss(self, xml_text: str, params: SearchParams) -> List[Article]:
        """Parse do XML RSS retornado pelo Google News."""
        articles: List[Article] = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"Erro parse XML: {e}")
            return []

        # Namespace do RSS
        ns = {"content": "http://purl.org/rss/1.0/modules/content/"}

        for item in root.findall(".//item"):
            try:
                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="").strip()
                pub_date_str = item.findtext("pubDate", default="")
                description = item.findtext("description", default="").strip()
                source_elem = item.find("source")
                source_name = (
                    source_elem.text.strip() if source_elem is not None else ""
                )

                if not title or not link:
                    continue

                # Resolve redirect do Google News
                resolved_url = link
                if "news.google.com" in link:
                    # Deferido: resolucao async seria ideal mas
                    # fazemos best-effort sync aqui
                    resolved_url = self._resolve_sync(link) or link

                if is_blacklisted(resolved_url):
                    continue

                domain = extract_domain(resolved_url)
                pub_date = parse_google_date(pub_date_str)

                articles.append(
                    Article(
                        title=title,
                        description=description or None,
                        author=source_name or None,
                        published_date=pub_date,
                        url=resolved_url,
                        domain=domain,
                        language=params.language.value,
                        source_type="google_news",
                    )
                )

                if len(articles) >= params.max_results * 2:
                    break

            except Exception as e:
                logger.debug(f"Erro parse item RSS: {e}")
                continue

        return articles

    # ------------------------------------------------------------------
    # Busca HTML (fallback)
    # ------------------------------------------------------------------

    async def _search_html(self, params: SearchParams) -> List[Article]:
        """Busca via pagina HTML do Google News (fallback)."""
        html_url = self._build_html_url(params)
        logger.debug(f"HTML URL: {html_url}")

        try:
            async with self.session.get(
                html_url,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status != 200:
                    return []

                html = await response.text()
                return self._parse_html(html, params)

        except Exception as e:
            logger.warning(f"Erro HTML: {e}")
            return []

    def _parse_html(self, html: str, params: SearchParams) -> List[Article]:
        """Parse da pagina HTML do Google News."""
        articles: List[Article] = []

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # Tenta encontrar article cards
        selectors = [
            "article",
            '[data-n-tid]',
            ".NiLAwe",
            ".xrnccd",
            "c-wiz article",
        ]

        for selector in selectors:
            cards = soup.select(selector)
            for card in cards:
                try:
                    article = self._parse_html_card(card, params)
                    if article:
                        articles.append(article)
                except Exception:
                    continue

            if len(articles) >= params.max_results:
                break

        # Se nao encontrou com selectores, tenta regex
        if not articles:
            articles = self._parse_html_regex(html, params)

        return articles[: params.max_results * 2]

    def _parse_html_card(self, card, params: SearchParams) -> Optional[Article]:
        """Extrai dados de um card de artigo do HTML."""
        # Link
        a_tag = card.find("a", href=True)
        if not a_tag:
            return None

        href = a_tag["href"]
        if href.startswith("./"):
            href = f"https://news.google.com{href[1:]}"
        elif href.startswith("/"):
            href = f"https://news.google.com{href}"

        if is_blacklisted(href):
            return None

        # Resolve redirect
        resolved = self._resolve_sync(href) or href
        if is_blacklisted(resolved):
            return None

        # Titulo
        title = ""
        for sel in ["h3", "h4", ".JtKRv", ".ipQwMb", ".DY5T1d"]:
            t = card.select_one(sel)
            if t:
                title = t.get_text(strip=True)
                break

        if not title:
            title = a_tag.get_text(strip=True)

        if not title:
            return None

        # Source
        source = ""
        for sel in [".wEwyrc", ".SVJrMe", ".MgUU6d"]:
            s = card.select_one(sel)
            if s:
                source = s.get_text(strip=True)
                break

        # Data
        date_str = ""
        for sel in ["time", ".WW6dff", ".fgOd93"]:
            d = card.select_one(sel)
            if d:
                date_str = d.get("datetime", "") or d.get_text(strip=True)
                break

        domain = extract_domain(resolved)
        pub_date = parse_google_date(date_str)

        return Article(
            title=title,
            author=source or None,
            published_date=pub_date,
            url=resolved,
            domain=domain,
            language=params.language.value,
            source_type="google_news",
        )

    def _parse_html_regex(self, html: str, params: SearchParams) -> List[Article]:
        """Fallback com regex para extrair links do Google News HTML."""
        import re

        articles: List[Article] = []

        # Padrao: articles com links do Google News
        pattern = re.compile(
            r'<article[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?</article>',
            re.DOTALL | re.IGNORECASE,
        )

        for match in pattern.finditer(html):
            try:
                href = match.group(1)
                title_text = re.sub(r"<[^>]+>", "", match.group(2)).strip()

                if not href or not title_text:
                    continue

                if href.startswith("./"):
                    href = f"https://news.google.com{href[1:]}"
                elif href.startswith("/"):
                    href = f"https://news.google.com{href}"

                resolved = self._resolve_sync(href) or href
                if is_blacklisted(resolved):
                    continue

                articles.append(
                    Article(
                        title=title_text,
                        url=resolved,
                        domain=extract_domain(resolved),
                        language=params.language.value,
                        source_type="google_news",
                    )
                )
            except Exception:
                continue

        return articles[: params.max_results]

    # ------------------------------------------------------------------
    # Resolucao de redirect
    # ------------------------------------------------------------------

    async def _resolve_redirect(self, google_url: str) -> Optional[str]:
        """Resolve um link news.google.com para a URL real do artigo.

        Args:
            google_url: URL do Google News (ex: https://news.google.com/rss/articles/...).

        Returns:
            URL real do artigo ou None se nao conseguir resolver.
        """
        if "news.google.com" not in google_url:
            return google_url

        # Extrai a URL do parametro 'url' ou 'u' se presente
        parsed = urllib.parse.urlparse(google_url)
        qs = urllib.parse.parse_qs(parsed.query)

        if "url" in qs:
            return qs["url"][0]
        if "u" in qs:
            try:
                # O parametro 'u' pode estar base64-encoded
                import base64
                decoded = base64.b64decode(qs["u"][0] + "==").decode("utf-8")
                if decoded.startswith("http"):
                    return decoded
            except Exception:
                pass

        # Tenta seguir redirect com HEAD request
        try:
            async with self.session.head(
                google_url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                final_url = str(response.url)
                if final_url != google_url and "news.google.com" not in final_url:
                    return final_url
        except Exception:
            pass

        return None

    def _resolve_sync(self, google_url: str) -> Optional[str]:
        """Versao sincrona da resolucao de redirect (best-effort)."""
        if "news.google.com" not in google_url:
            return google_url

        parsed = urllib.parse.urlparse(google_url)
        qs = urllib.parse.parse_qs(parsed.query)

        if "url" in qs:
            return qs["url"][0]

        # Decodifica parametro 'u' (base64)
        if "u" in qs and qs["u"]:
            try:
                import base64
                decoded = base64.b64decode(qs["u"][0] + "==").decode("utf-8")
                if decoded.startswith("http"):
                    return decoded
            except Exception:
                pass

        # Padrao direto no path
        if parsed.path.startswith("./articles/"):
            article_id = parsed.path.split("/")[-1]
            try:
                import base64
                decoded = base64.b64decode(article_id + "==").decode("utf-8")
                if decoded.startswith("http"):
                    return decoded
            except Exception:
                pass

        return None

    # ------------------------------------------------------------------
    # Builders de URL
    # ------------------------------------------------------------------

    def _build_rss_url(self, params: SearchParams) -> str:
        """Constroi a URL do RSS do Google News."""
        query_parts = [params.query]

        # Filtro de data
        if params.from_date:
            query_parts.append(f"after:{params.from_date}")
        if params.to_date:
            query_parts.append(f"before:{params.to_date}")

        full_query = " ".join(query_parts)
        encoded = urllib.parse.quote_plus(full_query)

        ceid = f"{params.country.value}:{params.language.value}"

        return (
            f"{GOOGLE_NEWS_RSS_URL}/search?q={encoded}"
            f"&hl={params.language.value}"
            f"&gl={params.country.value}"
            f"&ceid={ceid}"
        )

    def _build_html_url(self, params: SearchParams) -> str:
        """Constroi a URL de busca HTML do Google News."""
        query_parts = [params.query]

        if params.from_date:
            query_parts.append(f"after:{params.from_date}")
        if params.to_date:
            query_parts.append(f"before:{params.to_date}")

        full_query = " ".join(query_parts)
        encoded = urllib.parse.quote_plus(full_query)

        return (
            f"{GOOGLE_NEWS_HTML_URL}?q={encoded}"
            f"&hl={params.language.value}"
            f"&gl={params.country.value}"
            f"&ceid={params.country.value}:{params.language.value}"
        )

    # ------------------------------------------------------------------
    # Deduplicacao
    # ------------------------------------------------------------------

    def _deduplicate(self, articles: List[Article]) -> List[Article]:
        """Remove artigos duplicados por URL normalizada."""
        return deduplicate_by_key(
            articles, lambda a: normalize_url(a.url)
        )
