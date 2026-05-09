"""Modelos Pydantic v2 para o google_news_scraper."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CountryCode(str, Enum):
    """Codigos de pais suportados pelo Google News."""

    US = "US"
    BR = "BR"
    IN = "IN"
    GB = "GB"
    CA = "CA"
    AU = "AU"
    DE = "DE"
    FR = "FR"
    JP = "JP"
    MX = "MX"


class LanguageCode(str, Enum):
    """Codigos de idioma suportados pelo Google News."""

    EN = "en"
    PT = "pt"
    ES = "es"
    FR = "fr"
    DE = "de"
    JA = "ja"
    HI = "hi"
    IT = "it"
    RU = "ru"
    ZH = "zh"


class SearchParams(BaseModel):
    """Parametros de busca no Google News."""

    query: str = Field(..., min_length=1, description="Termo de busca")
    max_results: int = Field(
        default=10, ge=1, le=100, description="Maximo de resultados"
    )
    from_date: Optional[str] = Field(
        default=None, description="Data inicial (YYYY-MM-DD)"
    )
    to_date: Optional[str] = Field(
        default=None, description="Data final (YYYY-MM-DD)"
    )
    country: CountryCode = Field(
        default=CountryCode.BR, description="Codigo do pais"
    )
    language: LanguageCode = Field(
        default=LanguageCode.PT, description="Codigo do idioma"
    )
    use_proxies: bool = Field(
        default=False, description="Usar proxies para as requisicoes"
    )
    proxy_list: Optional[List[str]] = Field(
        default=None, description="Lista de URLs de proxy"
    )


class ScraperConfig(BaseModel):
    """Configuracao do scraper."""

    max_retries: int = Field(default=3, description="Numero maximo de retries")
    backoff_factor: float = Field(
        default=1.7, description="Fator de backoff exponencial"
    )
    max_sleep: float = Field(
        default=12.0, description="Tempo maximo de sleep entre retries (segundos)"
    )
    timeout: int = Field(
        default=14, description="Timeout das requisicoes HTTP (segundos)"
    )
    delay_per_domain: float = Field(
        default=0.35, description="Delay entre requisicoes ao mesmo dominio (segundos)"
    )
    cooldown_429_seconds: int = Field(
        default=180, description="Cooldown apos HTTP 429 (segundos)"
    )
    rotate_user_agent: bool = Field(
        default=True, description="Rotacionar User-Agent a cada requisicao"
    )
    concurrency: int = Field(
        default=4, description="Numero maximo de requisicoes concorrentes"
    )
    delay_between_requests: float = Field(
        default=0.4, description="Delay entre requisicoes (segundos)"
    )
    min_article_chars: int = Field(
        default=900,
        description="Minimo de caracteres para considerar artigo valido",
    )
    log_level: str = Field(default="INFO", description="Nivel de log")


class Article(BaseModel):
    """Representa um artigo de noticia extraido."""

    title: str = Field(..., description="Titulo do artigo")
    description: Optional[str] = Field(
        default=None, description="Descricao ou resumo do artigo"
    )
    author: Optional[str] = Field(default=None, description="Nome do autor")
    published_date: Optional[datetime] = Field(
        default=None, description="Data de publicacao"
    )
    image: Optional[str] = Field(
        default=None, description="URL da imagem principal"
    )
    images: List[str] = Field(
        default_factory=list, description="Lista de URLs de imagens"
    )
    article_text: Optional[str] = Field(
        default=None, description="Texto completo do artigo"
    )
    url: str = Field(..., description="URL do artigo")
    domain: str = Field(..., description="Dominio da fonte")
    scraped_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Data/hora da coleta",
    )
    language: Optional[str] = Field(
        default=None, description="Idioma detectado do artigo"
    )
    source_type: Optional[str] = Field(
        default=None,
        description="Tipo de fonte: google_news, rss, direct",
    )

    def to_dict(self) -> dict:
        """Serializa o artigo como dict JSON-safe."""
        return {
            "title": self.title,
            "description": self.description,
            "author": self.author,
            "published_date": (
                self.published_date.isoformat()
                if self.published_date
                else None
            ),
            "image": self.image,
            "images": self.images,
            "article_text": self.article_text,
            "url": self.url,
            "domain": self.domain,
            "scraped_at": self.scraped_at.isoformat(),
            "language": self.language,
            "source_type": self.source_type,
        }
