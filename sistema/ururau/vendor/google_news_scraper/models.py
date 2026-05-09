"""Pydantic data models for Google News Article Scraper."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, HttpUrl


class SearchParams(BaseModel):
    """Parameters for a Google News search query."""

    query: str = Field(..., min_length=1, description="Search query string")
    max_results: int = Field(
        default=10, ge=1, le=100, description="Maximum number of results (1-100)"
    )
    from_date: date | None = Field(
        default=None, description="Filter articles published on or after this date"
    )
    to_date: date | None = Field(
        default=None, description="Filter articles published on or before this date"
    )
    country: str = Field(default="US", description="ISO 3166-1 alpha-2 country code")
    language: str = Field(default="en", description="ISO 639-1 language code")
    use_proxy: bool = Field(default=False, description="Whether to use a proxy")
    proxy_url: str | None = Field(default=None, description="Proxy URL if use_proxy is True")

    @field_validator("country")
    @classmethod
    def _uppercase_country(cls, v: str) -> str:
        return v.upper()[:2]

    @field_validator("language")
    @classmethod
    def _lowercase_language(cls, v: str) -> str:
        return v.lower()[:2]


class ArticleLink(BaseModel):
    """Internal model representing a raw link found on Google News."""

    url: str
    title: str
    source: str = ""
    published_time_text: str = ""
    snippet: str = ""


class Article(BaseModel):
    """A fully extracted news article with all metadata."""

    title: str = Field(..., description="Article headline")
    description: str | None = Field(default=None, description="Meta description or summary")
    author: str | None = Field(default=None, description="Article author")
    published_date: datetime | None = Field(
        default=None, description="Publication date (UTC when possible)"
    )
    image: str | None = Field(default=None, description="Primary image URL")
    images: list[str] = Field(default_factory=list, description="All extracted image URLs")
    article_text: str = Field(..., description="Full article plain text content")
    url: str = Field(..., description="Original article URL")
    domain: str = Field(..., description="Article domain")
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the article was scraped",
    )
    language: str | None = Field(default=None, description="Detected article language")

    model_config = {"populate_by_name": True}


class ScraperConfig(BaseModel):
    """Global scraper configuration."""

    timeout: int = Field(default=30, ge=1, description="HTTP request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Max retries per request")
    retry_backoff: float = Field(
        default=2.0, ge=0, description="Exponential backoff base in seconds"
    )
    concurrency: int = Field(
        default=5, ge=1, le=20, description="Max concurrent article extractions"
    )
    request_delay: float = Field(
        default=1.0, ge=0, description="Delay between requests in seconds"
    )
    user_agent_rotation: bool = Field(
        default=True, description="Rotate User-Agent headers"
    )
    respect_robots_txt: bool = Field(
        default=False, description="Whether to respect robots.txt"
    )
    proxy: str | None = Field(default=None, description="Proxy URL (e.g. http://proxy:8080)")
