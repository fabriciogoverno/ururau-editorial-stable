"""Command-line interface for Google News Article Scraper."""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from datetime import date

import click

from .config import SUPPORTED_COUNTRIES, SUPPORTED_LANGUAGES
from .extractor import ArticleExtractor
from .logger import get_logger
from .models import Article, ScraperConfig, SearchParams
from .scraper import GoogleNewsScraper

logger = get_logger(__name__)


def _serialize_article(article: Article) -> dict:
    """Convert an Article to a JSON-serialisable dict."""
    data = article.model_dump()
    for key in ("published_date", "scraped_at"):
        if data.get(key):
            data[key] = data[key].isoformat()
    return data


@click.group()
@click.version_option(version="0.1.0", prog_name="google-news-scraper")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose/debug logging")
def main(verbose: bool) -> None:
    """Google News Article Scraper — CLI tool."""
    if verbose:
        import os
        os.environ["GOOGLE_NEWS_SCRAPER_LOG_LEVEL"] = "DEBUG"


@main.command()
@click.argument("query")
@click.option("--max-results", default=10, show_default=True, type=int,
              help="Maximum number of articles to retrieve (1-100)")
@click.option("--from-date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Filter articles published on or after this date (YYYY-MM-DD)")
@click.option("--to-date", type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Filter articles published on or before this date (YYYY-MM-DD)")
@click.option("--country", default="US", show_default=True,
              type=click.Choice(list(SUPPORTED_COUNTRIES.keys()), case_sensitive=False),
              help="Country code for search results")
@click.option("--language", default="en", show_default=True,
              type=click.Choice(list(SUPPORTED_LANGUAGES.keys()), case_sensitive=False),
              help="Language code for search results")
@click.option("--output", "-o", default="-", show_default=True,
              type=click.Path(allow_dash=True),
              help="Output file path (use - for stdout)")
@click.option("--format", "fmt", default="json", show_default=True,
              type=click.Choice(["json", "csv"]),
              help="Output format")
@click.option("--proxy", help="Proxy URL (e.g. http://proxy:8080)")
@click.option("--concurrency", default=5, show_default=True, type=int,
              help="Max concurrent article extractions")
@click.option("--timeout", default=30, show_default=True, type=int,
              help="HTTP request timeout in seconds")
@click.option("--max-retries", default=3, show_default=True, type=int,
              help="Max retries per failed request")
def search(
    query: str,
    max_results: int,
    from_date: date | None,
    to_date: date | None,
    country: str,
    language: str,
    output: str,
    fmt: str,
    proxy: str | None,
    concurrency: int,
    timeout: int,
    max_retries: int,
) -> None:
    """Search Google News and extract full article content."""
    params = SearchParams(
        query=query,
        max_results=max_results,
        from_date=from_date,
        to_date=to_date,
        country=country,
        language=language,
        use_proxy=bool(proxy),
        proxy_url=proxy,
    )
    config = ScraperConfig(
        timeout=timeout,
        max_retries=max_retries,
        concurrency=concurrency,
        proxy=proxy,
    )

    async def _run() -> list[Article]:
        scraper = GoogleNewsScraper(config)
        return await scraper.scrape_full_articles(params)

    articles = asyncio.run(_run())

    if not articles:
        click.echo("No articles found.", err=True)
        sys.exit(1)

    click.echo(f"Found {len(articles)} articles.", err=True)

    serialized = [_serialize_article(a) for a in articles]

    if fmt == "json":
        content = json.dumps(serialized, indent=2, ensure_ascii=False)
    else:
        import io
        buffer = io.StringIO()
        if serialized:
            writer = csv.DictWriter(buffer, fieldnames=list(serialized[0].keys()))
            writer.writeheader()
            writer.writerows(serialized)
        content = buffer.getvalue()

    if output == "-":
        click.echo(content)
    else:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(content)
        click.echo(f"Results written to {output}", err=True)


@main.command()
def list_countries() -> None:
    """List supported country codes."""
    for code, name in sorted(SUPPORTED_COUNTRIES.items()):
        click.echo(f"{code:<4} {name}")


@main.command()
def list_languages() -> None:
    """List supported language codes."""
    for code, name in sorted(SUPPORTED_LANGUAGES.items()):
        click.echo(f"{code:<4} {name}")


if __name__ == "__main__":
    main()
