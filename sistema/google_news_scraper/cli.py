"""CLI do Google News Scraper."""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from datetime import datetime
from typing import Any, Dict, List

import click

from .extractor import ArticleExtractor
from .models import CountryCode, LanguageCode, ScraperConfig, SearchParams
from .scraper import GoogleNewsScraper


def _article_to_dict(article) -> Dict[str, Any]:
    """Converte Article para dict serializavel."""
    return {
        "title": article.title,
        "description": article.description,
        "author": article.author,
        "published_date": (
            article.published_date.isoformat()
            if article.published_date
            else None
        ),
        "image": article.image,
        "images": article.images,
        "article_text": article.article_text,
        "url": article.url,
        "domain": article.domain,
        "scraped_at": article.scraped_at.isoformat(),
        "language": article.language,
        "source_type": article.source_type,
    }


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Google News Article Scraper — CLI"""
    pass


@cli.command()
@click.argument("query")
@click.option("--max-results", default=10, type=int, help="Maximo de resultados")
@click.option("--from-date", help="Data inicial (YYYY-MM-DD)")
@click.option("--to-date", help="Data final (YYYY-MM-DD)")
@click.option("--country", default="BR", help="Codigo do pais (BR, US, etc.)")
@click.option("--language", default="pt", help="Codigo do idioma (pt, en, etc.)")
@click.option("--output", "-o", help="Caminho do arquivo de saida")
@click.option(
    "--format", "fmt", default="json",
    type=click.Choice(["json", "csv"]), help="Formato de saida"
)
@click.option(
    "--extract", is_flag=True,
    help="Tambem extrair texto completo do artigo"
)
@click.option("--proxy", multiple=True, help="URLs de proxy")
@click.option("--timeout", default=14, help="Timeout HTTP (segundos)")
@click.option("--retries", default=3, help="Numero de retries")
def search(query, max_results, from_date, to_date, country, language,
           output, fmt, extract, proxy, timeout, retries):
    """Busca artigos no Google News."""
    try:
        country_enum = CountryCode(country.upper())
    except ValueError:
        click.echo(f"Erro: pais invalido: {country}", err=True)
        sys.exit(1)

    try:
        lang_enum = LanguageCode(language.lower())
    except ValueError:
        click.echo(f"Erro: idioma invalido: {language}", err=True)
        sys.exit(1)

    params = SearchParams(
        query=query,
        max_results=max_results,
        from_date=from_date,
        to_date=to_date,
        country=country_enum,
        language=lang_enum,
        proxy_list=list(proxy) if proxy else None,
    )

    config = ScraperConfig(
        timeout=timeout,
        max_retries=retries,
    )

    async def _run():
        scraper = GoogleNewsScraper(config)
        async with scraper:
            if extract:
                articles = await scraper.search_and_extract(params)
            else:
                articles = await scraper.search(params)
        return articles

    try:
        articles = asyncio.run(_run())
    except Exception as e:
        click.echo(f"Erro na busca: {e}", err=True)
        sys.exit(1)

    if not articles:
        click.echo("Nenhum artigo encontrado.")
        return

    # Saida
    if fmt == "json":
        data = [_article_to_dict(a) for a in articles]
        json_output = json.dumps(data, ensure_ascii=False, indent=2)
        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(json_output)
            click.echo(f"Resultados salvos em: {output}")
        else:
            click.echo(json_output)

    elif fmt == "csv":
        fieldnames = [
            "title", "description", "author", "published_date",
            "url", "domain", "language", "article_text",
        ]
        rows = []
        for a in articles:
            rows.append({
                "title": a.title,
                "description": a.description or "",
                "author": a.author or "",
                "published_date": (
                    a.published_date.isoformat()
                    if a.published_date else ""
                ),
                "url": a.url,
                "domain": a.domain,
                "language": a.language or "",
                "article_text": (a.article_text or "")[:500],
            })

        if output:
            with open(output, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            click.echo(f"Resultados salvos em: {output}")
        else:
            writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    cli()
