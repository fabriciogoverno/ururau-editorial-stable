"""
HTTP fetch v109 para coleta editorial Ururau.

Objetivo: conectar, no fluxo real do projeto, os recursos que já existiam no
pacote vendor google_news_scraper: rotação de User-Agent e retry com backoff.

Este módulo não quebra paywall, não faz login, não burla autenticação e não
acessa conteúdo restrito. Ele apenas torna as requisições públicas mais
resilientes contra falhas transitórias, 5xx, timeout e respostas 429.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import random
import re
import time
from typing import Any
from urllib.parse import urlparse

import requests

try:
    from ururau.vendor.google_news_scraper.config import USER_AGENTS as _VENDOR_USER_AGENTS
except Exception:  # pragma: no cover
    _VENDOR_USER_AGENTS = []

_DEFAULT_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
]

_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
_DOMAIN_COOLDOWN_UNTIL: dict[str, float] = {}
_LAST_DOMAIN_HIT: dict[str, float] = {}


@dataclass
class FetchResultV109:
    ok: bool
    text: str = ""
    url_final: str = ""
    status_code: int = 0
    attempts: int = 0
    user_agent: str = ""
    erro: str = ""
    cooldown_seconds: float = 0.0


class FetchBlockedByCooldown(RuntimeError):
    pass


def _env_bool(nome: str, padrao: bool = False) -> bool:
    return str(os.getenv(nome, "1" if padrao else "0")).strip().lower() in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(str(os.getenv(nome, str(padrao))).strip().replace(",", "."))
    except Exception:
        return padrao


def _domain(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def random_user_agent() -> str:
    pool = list(_VENDOR_USER_AGENTS or []) + _DEFAULT_UAS
    return random.choice(pool)


def _retry_after_seconds(valor: str | None) -> float:
    if not valor:
        return 0.0
    valor = valor.strip()
    if valor.isdigit():
        return float(valor)
    # Se vier em formato HTTP-date, evita parse complexo e usa fallback seguro.
    return 0.0


def _wait_domain_pacing(dom: str) -> None:
    delay = _env_float("URURAU_V109_HTTP_DELAY_DOMINIO", 0.35)
    if not dom or delay <= 0:
        return
    last = _LAST_DOMAIN_HIT.get(dom, 0.0)
    elapsed = time.time() - last
    if elapsed < delay:
        time.sleep(delay - elapsed)
    _LAST_DOMAIN_HIT[dom] = time.time()


def _check_cooldown(dom: str) -> None:
    if not dom or not _env_bool("URURAU_V109_HTTP_RESPEITAR_COOLDOWN", True):
        return
    until = _DOMAIN_COOLDOWN_UNTIL.get(dom, 0.0)
    restante = until - time.time()
    if restante > 0:
        raise FetchBlockedByCooldown(f"domínio em cooldown por {restante:.0f}s: {dom}")


def _set_cooldown(dom: str, seconds: float) -> None:
    if not dom or seconds <= 0:
        return
    _DOMAIN_COOLDOWN_UNTIL[dom] = max(_DOMAIN_COOLDOWN_UNTIL.get(dom, 0.0), time.time() + seconds)


def build_headers(base_headers: dict[str, str] | None = None, *, referer: str = "", accept: str = "html") -> dict[str, str]:
    headers = dict(base_headers or {})
    rotate = _env_bool("URURAU_V109_HTTP_ROTATE_UA", True)
    if rotate or not headers.get("User-Agent"):
        headers["User-Agent"] = random_user_agent()
    headers.setdefault("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7")
    if accept == "rss":
        headers.setdefault("Accept", "application/rss+xml,application/xml,text/xml;q=0.9,text/html;q=0.8,*/*;q=0.7")
    else:
        headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8")
    headers.setdefault("Cache-Control", "no-cache")
    headers.setdefault("Pragma", "no-cache")
    headers.setdefault("Connection", "close")
    if referer:
        headers.setdefault("Referer", referer)
    return headers


def fetch_text_v109(
    url: str,
    *,
    base_headers: dict[str, str] | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
    backoff: float | None = None,
    accept: str = "html",
    allow_redirects: bool = True,
    referer: str = "",
) -> FetchResultV109:
    """Busca URL pública com retry, backoff exponencial, UA rotativo e cooldown 429."""
    url = str(url or "").strip()
    if not re.match(r"^https?://", url, flags=re.I):
        return FetchResultV109(ok=False, url_final=url, erro="url_invalida")

    dom = _domain(url)
    timeout = timeout or _env_int("URURAU_V109_HTTP_TIMEOUT", 14)
    max_retries = max_retries if max_retries is not None else _env_int("URURAU_V109_HTTP_MAX_RETRIES", 3)
    backoff = backoff if backoff is not None else _env_float("URURAU_V109_HTTP_BACKOFF", 1.7)
    log = _env_bool("URURAU_V109_HTTP_LOG", False)

    try:
        _check_cooldown(dom)
    except FetchBlockedByCooldown as e:
        until = _DOMAIN_COOLDOWN_UNTIL.get(dom, time.time())
        return FetchResultV109(ok=False, url_final=url, erro=str(e), cooldown_seconds=max(0.0, until - time.time()))

    last_error = ""
    last_status = 0
    last_url = url
    last_ua = ""

    for attempt in range(1, max(1, max_retries) + 1):
        headers = build_headers(base_headers, referer=referer, accept=accept)
        last_ua = headers.get("User-Agent", "")
        try:
            _wait_domain_pacing(dom)
            with requests.Session() as s:
                resp = s.get(url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)
            last_status = int(getattr(resp, "status_code", 0) or 0)
            last_url = str(getattr(resp, "url", "") or url)

            if last_status == 429:
                retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
                cooldown = retry_after if retry_after > 0 else _env_float("URURAU_V109_HTTP_COOLDOWN_429_SEG", 180.0)
                _set_cooldown(dom, cooldown)
                last_error = f"HTTP 429; cooldown {cooldown:.0f}s"
                if log:
                    print(f"[HTTP v109] 429 {dom}; cooldown={cooldown:.0f}s")
                break

            if last_status in _RETRY_STATUS:
                last_error = f"HTTP {last_status}"
                if attempt < max_retries:
                    wait = min((backoff ** attempt) + random.uniform(0.05, 0.55), _env_float("URURAU_V109_HTTP_MAX_SLEEP", 12.0))
                    if log:
                        print(f"[HTTP v109] retry {attempt}/{max_retries} {last_status} {dom}; {wait:.1f}s")
                    time.sleep(wait)
                    continue

            resp.raise_for_status()
            if not resp.encoding or str(resp.encoding).lower() in {"iso-8859-1", "ascii"}:
                try:
                    resp.encoding = resp.apparent_encoding or "utf-8"
                except Exception:
                    pass
            return FetchResultV109(
                ok=True,
                text=resp.text or "",
                url_final=last_url,
                status_code=last_status,
                attempts=attempt,
                user_agent=last_ua,
            )
        except requests.RequestException as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt < max_retries:
                wait = min((backoff ** attempt) + random.uniform(0.05, 0.55), _env_float("URURAU_V109_HTTP_MAX_SLEEP", 12.0))
                if log:
                    print(f"[HTTP v109] retry {attempt}/{max_retries} erro {dom}: {type(e).__name__}; {wait:.1f}s")
                time.sleep(wait)
                continue
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            break

    return FetchResultV109(
        ok=False,
        text="",
        url_final=last_url,
        status_code=last_status,
        attempts=max_retries,
        user_agent=last_ua,
        erro=last_error or "falha_http",
        cooldown_seconds=max(0.0, _DOMAIN_COOLDOWN_UNTIL.get(dom, 0.0) - time.time()),
    )


def fetch_html_v109(url: str, **kwargs: Any) -> tuple[str, str]:
    r = fetch_text_v109(url, accept="html", **kwargs)
    if not r.ok:
        raise RuntimeError(r.erro or f"falha ao buscar {url}")
    return r.text, r.url_final or url


def fetch_rss_v109(url: str, **kwargs: Any) -> FetchResultV109:
    return fetch_text_v109(url, accept="rss", **kwargs)


__all__ = [
    "FetchResultV109",
    "fetch_text_v109",
    "fetch_html_v109",
    "fetch_rss_v109",
    "random_user_agent",
    "build_headers",
]
