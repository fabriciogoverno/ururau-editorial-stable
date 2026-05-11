# -*- coding: utf-8 -*-
"""Scrapling Engine v136.

Camada central de fetch/parser para captação do Ururau.

Usa os recursos principais do Scrapling:
- Fetcher/FetcherSession para HTTP rápido;
- StealthyFetcher para páginas com proteção/anti-bot;
- DynamicFetcher para páginas com JS;
- CSS/XPath/texto/HTML como estratégias de extração;
- fallback controlado sem tocar no painel visual.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

try:
    from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher, FetcherSession
    SCRAPLING_V136_OK = True
except Exception:
    Fetcher = None  # type: ignore
    StealthyFetcher = None  # type: ignore
    DynamicFetcher = None  # type: ignore
    FetcherSession = None  # type: ignore
    SCRAPLING_V136_OK = False


def env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except Exception:
        return default


@dataclass
class FetchResultV136:
    ok: bool = False
    url: str = ""
    final_url: str = ""
    html: str = ""
    text: str = ""
    method: str = ""
    status: int = 0
    error: str = ""
    attempts: list[str] = field(default_factory=list)


class ScraplingEngineV136:
    def __init__(self) -> None:
        self.timeout_ms = env_int("URURAU_SCRAPLING_TIMEOUT_MS", 18000)
        self.allow_dynamic = env_bool("URURAU_SCRAPLING_DYNAMIC", True)
        self.allow_stealth = env_bool("URURAU_SCRAPLING_STEALTH", True)
        self.disable_resources = env_bool("URURAU_SCRAPLING_DISABLE_RESOURCES", True)
        self._configured = False

    def configure(self) -> None:
        if self._configured or not SCRAPLING_V136_OK:
            return
        try:
            Fetcher.configure(adaptive=True, keep_comments=False, keep_cdata=False)
        except Exception:
            pass
        try:
            StealthyFetcher.configure(adaptive=True, keep_comments=False, keep_cdata=False)
        except Exception:
            pass
        self._configured = True

    def normalize_url(self, url: str, base: str = "") -> str:
        url = (url or "").strip()
        if base:
            url = urljoin(base, url)
        if not url:
            return ""
        if not re.match(r"^https?://", url, re.I):
            url = "https://" + url.lstrip("/")
        p = urlparse(url)
        path = re.sub(r"/{2,}", "/", p.path or "/")
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))

    def domain(self, url: str) -> str:
        try:
            host = urlparse(self.normalize_url(url)).netloc.lower()
            return host[4:] if host.startswith("www.") else host
        except Exception:
            return ""

    def _page_html(self, page: Any) -> str:
        for attr in ("html", "body", "content"):
            try:
                value = getattr(page, attr)
                if callable(value):
                    value = value()
                if isinstance(value, str) and len(value) > 100:
                    return value
            except Exception:
                pass
        try:
            body = page.css("body").get()
            if body:
                return str(body)
        except Exception:
            pass
        return str(page or "")

    def _page_text(self, page: Any, html: str = "") -> str:
        candidates: list[str] = []
        for sel in ["article::text", "main::text", "[role='main']::text", "body::text", "*::text"]:
            try:
                vals = page.css(sel).getall()
                txt = "\n".join(str(v) for v in vals if str(v).strip())
                if len(txt) > 100:
                    candidates.append(txt)
            except Exception:
                pass
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup.find_all(["script", "style", "noscript", "svg", "iframe", "nav", "header", "footer", "aside"]):
                    tag.decompose()
                txt = soup.get_text("\n", strip=True)
                if len(txt) > 100:
                    candidates.append(txt)
            except Exception:
                pass
        candidates.sort(key=len, reverse=True)
        return candidates[0] if candidates else ""

    def fetch(self, url: str, mode: str = "auto") -> FetchResultV136:
        if not SCRAPLING_V136_OK:
            return FetchResultV136(ok=False, url=url, error="scrapling_nao_instalado")
        self.configure()
        norm = self.normalize_url(url)
        attempts: list[str] = []

        modes = []
        if mode in {"auto", "fast"}:
            modes.append("fast")
        if mode in {"auto", "stealth"} and self.allow_stealth:
            modes.append("stealth")
        if mode in {"auto", "dynamic"} and self.allow_dynamic:
            modes.append("dynamic")

        last_error = ""
        for m in modes:
            try:
                attempts.append(m)
                if m == "fast":
                    page = Fetcher.get(norm, stealthy_headers=True, timeout=self.timeout_ms)
                elif m == "stealth":
                    page = StealthyFetcher.fetch(norm, headless=True, network_idle=True, wait_selector="body", timeout=self.timeout_ms)
                else:
                    page = DynamicFetcher.fetch(norm, headless=True, network_idle=True, wait_selector="body", timeout=self.timeout_ms, disable_resources=self.disable_resources)
                html = self._page_html(page)
                text = self._page_text(page, html=html)
                final_url = str(getattr(page, "url", norm) or norm)
                if html or text:
                    return FetchResultV136(ok=True, url=norm, final_url=final_url, html=html, text=text, method=m, attempts=attempts)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                continue
        return FetchResultV136(ok=False, url=norm, final_url=norm, error=last_error, attempts=attempts)
