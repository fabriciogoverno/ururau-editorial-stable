# -*- coding: utf-8 -*-
"""bypass_paywall_v200 — camadas de fallback para sites com paywall.

Estrategias gerais usadas por serviços como sem-paywall.com adaptadas
para o pipeline do Ururau. Quando a extracao normal falha (texto
insuficiente, multiassunto, canonical_mismatch), o pipeline tenta:

  1. **Googlebot User-Agent**     — muitos paywalls liberam para o bot do Google
                                    (politica de cloak-for-google).
  2. **Web Archive (Wayback)**    — versao arquivada publica do artigo.
  3. **Google Cache**             — pagina cacheada pelo Google
                                    (depende do site ainda ter cache vivo).
  4. **AMP version**              — paywall geralmente nao se aplica a AMP
                                    (versao mobile acelerada do artigo).
  5. **archive.today / archive.ph** — espelho publico que normalmente bypassa.
  6. **No-cookies / no-JS**       — algumas paywalls so vigiam com JS/cookie.
  7. **Referer Google**           — site libera quando origem e busca.

Politica: NUNCA inventa conteudo. Apenas TENTA carregar a MESMA URL por
outros caminhos publicos. Se nenhuma estrategia entregar texto valido,
devolve dict com `ok=False` e o pipeline marca aviso (NAO descarta a
pauta).

API:

    tentar_bypass_paywall(url, titulo_pauta='') -> dict
        {'ok': bool, 'texto': str, 'estrategia': str, 'url_final': str,
         'tentativas': list[dict]}

    BYPASS_DISPONIVEL  — bool, True se requests esta instalado
"""
from __future__ import annotations

import os
import re
import time
import urllib.parse
from typing import Any

try:
    import requests
    BYPASS_DISPONIVEL = True
except Exception:
    requests = None  # type: ignore
    BYPASS_DISPONIVEL = False

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except Exception:
    BeautifulSoup = None  # type: ignore
    BS4_OK = False


# ─────────────────── Constantes ───────────────────────────────────────────

GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
GOOGLEBOT_NEWS_UA = "Googlebot-News"
BINGBOT_UA = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

TIMEOUT = int(os.getenv("URURAU_BYPASS_TIMEOUT", "15"))
MIN_CHARS_VALIDOS = int(os.getenv("URURAU_BYPASS_MIN_CHARS", "550"))



def _ler_texto_utf8_v200_18(r) -> str:
    """V200_18: decodifica response forcando UTF-8 quando necessario.

    A Folha/Estadao/Globo servem UTF-8 mas o header HTTP as vezes
    declara ISO-8859-1 ou nao declara. O requests confia no header
    e cai em Latin-1, gerando "RevoluÃ§Ã£o" em vez de "Revolucao".
    """
    try:
        raw = r.content or b""
        if not raw:
            return ""
        enc_header = (r.encoding or "").lower()
        try:
            sample = raw[:2048].decode("ascii", errors="ignore").lower()
            if 'charset=utf-8' in sample or 'charset="utf-8"' in sample:
                return raw.decode("utf-8", errors="replace")
            if 'charset=iso-8859-1' in sample or 'charset=latin-1' in sample:
                return raw.decode("iso-8859-1", errors="replace")
        except Exception:
            pass
        if enc_header in ("iso-8859-1", "latin-1", "latin1", "windows-1252", ""):
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("iso-8859-1", errors="replace")
        return r.text or ""
    except Exception:
        return r.text or ""


def _http_get(url: str, *, ua: str = DESKTOP_UA, referer: str = "",
              allow_redirects: bool = True) -> tuple[int, str, str]:
    """Devolve (status, url_final, html). Retorna (0,'','') em falha."""
    if not BYPASS_DISPONIVEL:
        return 0, "", ""
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT,
                          allow_redirects=allow_redirects)
        return r.status_code, r.url, _ler_texto_utf8_v200_18(r)
    except Exception:
        return 0, "", ""


def _extrair_texto_limpo(html: str, titulo_pauta: str = "",
                          url_pauta: str = "") -> str:
    """Aproveita o extrator de artigo unico ja existente."""
    try:
        from ururau.coleta.extracao_limpa_v200 import extrair_article_de_html
        r = extrair_article_de_html(html, url_pauta=url_pauta,
                                     titulo_pauta=titulo_pauta)
        if r.get("ok"):
            return r.get("texto") or ""
        return ""
    except Exception:
        # fallback ingenuo: pega todo o <p> visível
        if not BS4_OK or not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in ("script", "style", "nav", "footer", "aside"):
            for el in soup.find_all(tag):
                el.decompose()
        ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return "\n\n".join(p for p in ps if len(p) >= 30)


def _texto_valido(texto: str) -> bool:
    return len((texto or "").strip()) >= MIN_CHARS_VALIDOS


# ─────────────────── Estrategias de bypass ────────────────────────────────

def _tent_googlebot(url: str, titulo: str) -> dict:
    s, uf, html = _http_get(url, ua=GOOGLEBOT_UA,
                             referer="https://www.google.com/")
    texto = _extrair_texto_limpo(html, titulo, uf or url)
    return {"estrategia": "googlebot_ua", "status": s,
            "url_final": uf, "chars": len(texto), "texto": texto,
            "ok": _texto_valido(texto)}


def _tent_googlebot_news(url: str, titulo: str) -> dict:
    s, uf, html = _http_get(url, ua=GOOGLEBOT_NEWS_UA,
                             referer="https://news.google.com/")
    texto = _extrair_texto_limpo(html, titulo, uf or url)
    return {"estrategia": "googlebot_news_ua", "status": s,
            "url_final": uf, "chars": len(texto), "texto": texto,
            "ok": _texto_valido(texto)}


def _tent_referer_google(url: str, titulo: str) -> dict:
    s, uf, html = _http_get(url, ua=DESKTOP_UA,
                             referer="https://www.google.com/search?q=" +
                                     urllib.parse.quote_plus(titulo or url))
    texto = _extrair_texto_limpo(html, titulo, uf or url)
    return {"estrategia": "referer_google_search", "status": s,
            "url_final": uf, "chars": len(texto), "texto": texto,
            "ok": _texto_valido(texto)}


def _tent_amp(url: str, titulo: str) -> dict:
    candidatos = []
    if "?" in url:
        candidatos.append(url + "&amp")
        candidatos.append(url + "&output=amp")
    else:
        candidatos.append(url + "?amp")
        candidatos.append(url + "?output=amp")
    candidatos.append(url + ("amp/" if url.endswith("/") else "/amp"))
    # subdominio amp.exemplo.com
    p = urllib.parse.urlparse(url)
    if p.netloc:
        if not p.netloc.startswith("amp."):
            candidatos.insert(0, urllib.parse.urlunparse(
                p._replace(netloc="amp." + p.netloc.replace("www.", ""))
            ))
    for c in candidatos:
        s, uf, html = _http_get(c, ua=DESKTOP_UA)
        if s == 200 and html:
            texto = _extrair_texto_limpo(html, titulo, uf or c)
            if _texto_valido(texto):
                return {"estrategia": "amp_direto", "status": s,
                        "url_final": uf, "chars": len(texto), "texto": texto,
                        "ok": True}
    return {"estrategia": "amp_direto", "status": 0, "url_final": "",
            "chars": 0, "texto": "", "ok": False}


def _tent_google_cache(url: str, titulo: str) -> dict:
    cache_url = "https://webcache.googleusercontent.com/search?q=cache:" + url
    s, uf, html = _http_get(cache_url, ua=DESKTOP_UA)
    texto = _extrair_texto_limpo(html, titulo, url)
    return {"estrategia": "google_cache", "status": s,
            "url_final": cache_url, "chars": len(texto), "texto": texto,
            "ok": _texto_valido(texto)}


def _tent_wayback(url: str, titulo: str) -> dict:
    # Pega o snapshot mais recente disponivel
    api = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url)
    try:
        s, _, j = _http_get(api, ua=DESKTOP_UA)
        if s != 200 or not j:
            return {"estrategia": "wayback", "status": s, "url_final": "",
                    "chars": 0, "texto": "", "ok": False}
        import json as _json
        info = _json.loads(j) or {}
        snap = (info.get("archived_snapshots") or {}).get("closest") or {}
        if not snap.get("available"):
            return {"estrategia": "wayback", "status": 0, "url_final": "",
                    "chars": 0, "texto": "", "ok": False}
        snap_url = snap.get("url") or ""
        if not snap_url:
            return {"estrategia": "wayback", "status": 0, "url_final": "",
                    "chars": 0, "texto": "", "ok": False}
        # forca a versao "id_" do Wayback (raw, sem chrome do toolbar)
        snap_url = re.sub(r"/web/(\d+)/", r"/web/\1id_/", snap_url)
        s2, uf2, html2 = _http_get(snap_url, ua=DESKTOP_UA)
        texto = _extrair_texto_limpo(html2, titulo, url)
        return {"estrategia": "wayback", "status": s2,
                "url_final": uf2 or snap_url, "chars": len(texto),
                "texto": texto, "ok": _texto_valido(texto)}
    except Exception as e:
        return {"estrategia": "wayback", "status": 0, "url_final": "",
                "chars": 0, "texto": "", "ok": False,
                "erro": str(e)[:80]}


def _tent_archive_today(url: str, titulo: str) -> dict:
    # archive.ph nao tem API publica de "available", entao tenta direto:
    # archive.ph/newest/URL  ou  archive.ph/URL
    for ach in ("https://archive.ph/newest/", "https://archive.today/newest/"):
        s, uf, html = _http_get(ach + url, ua=DESKTOP_UA,
                                 allow_redirects=True)
        texto = _extrair_texto_limpo(html, titulo, url)
        if _texto_valido(texto):
            return {"estrategia": "archive_today", "status": s,
                    "url_final": uf, "chars": len(texto), "texto": texto,
                    "ok": True}
    return {"estrategia": "archive_today", "status": 0, "url_final": "",
            "chars": 0, "texto": "", "ok": False}


def _tent_no_cookies(url: str, titulo: str) -> dict:
    if not BYPASS_DISPONIVEL:
        return {"estrategia": "no_cookies", "status": 0, "url_final": "",
                "chars": 0, "texto": "", "ok": False}
    headers = {"User-Agent": DESKTOP_UA, "Cookie": ""}
    try:
        # session vazia, sem cookies
        s_obj = requests.Session()
        s_obj.cookies.clear()
        r = s_obj.get(url, headers=headers, timeout=TIMEOUT,
                       allow_redirects=True)
        html = _ler_texto_utf8_v200_18(r)
        texto = _extrair_texto_limpo(html, titulo, r.url)
        return {"estrategia": "no_cookies", "status": r.status_code,
                "url_final": r.url, "chars": len(texto), "texto": texto,
                "ok": _texto_valido(texto)}
    except Exception:
        return {"estrategia": "no_cookies", "status": 0, "url_final": "",
                "chars": 0, "texto": "", "ok": False}


# V200_4: regra Burlesco por dominio — primeira tentativa quando o site
# esta na lista do projeto Burlesco (33 portais brasileiros). Se o dominio
# nao for reconhecido OU a regra falhar, cai nas estrategias genericas.
try:
    from ururau.coleta.paywall_rules_burlesco_v200 import (
        tentar_bypass_burlesco as _tent_burlesco,
    )
    _BURLESCO_OK = True
except Exception:
    _BURLESCO_OK = False
    def _tent_burlesco(url: str, titulo: str) -> dict:
        return {"estrategia": "burlesco_indisponivel", "status": 0,
                "url_final": "", "chars": 0, "texto": "", "ok": False}


# Lista ordenada das estrategias. Burlesco roda primeiro (regra por
# dominio); depois AMP/Googlebot/etc como fallback generico.
ESTRATEGIAS = (
    _tent_burlesco,        # regra Burlesco por dominio (33 portais BR)
    _tent_amp,             # mais barato e eficaz
    _tent_googlebot_news,  # Folha, Estadao
    _tent_googlebot,       # Globo, UOL
    _tent_referer_google,  # paywall soft (~5 artigos/mes)
    _tent_no_cookies,      # paywall por cookie tracker
    _tent_wayback,         # ja arquivado publicamente
    _tent_google_cache,    # ainda cacheado pelo Google
    _tent_archive_today,   # archive.ph
)


# ─────────────────── API publica ──────────────────────────────────────────

def tentar_bypass_paywall(url: str, titulo_pauta: str = "") -> dict:
    """Tenta carregar o artigo por todas as estrategias em ordem.

    Devolve no primeiro sucesso (texto >= MIN_CHARS_VALIDOS).
    """
    out = {
        "ok": False, "texto": "", "estrategia": "", "url_final": "",
        "tentativas": [],
    }
    if not BYPASS_DISPONIVEL:
        out["erro"] = "requests nao instalado"
        return out
    for tent in ESTRATEGIAS:
        try:
            r = tent(url, titulo_pauta)
        except Exception as e:
            r = {"estrategia": tent.__name__, "status": 0,
                 "url_final": "", "chars": 0, "texto": "", "ok": False,
                 "erro": str(e)[:80]}
        # nao inclui o texto inteiro no relatorio (so chars)
        out["tentativas"].append({k: v for k, v in r.items() if k != "texto"})
        if r.get("ok"):
            out["ok"] = True
            out["texto"] = r["texto"]
            out["estrategia"] = r["estrategia"]
            out["url_final"] = r.get("url_final") or url
            return out
        time.sleep(0.4)  # respeita rate limit
    return out


__all__ = [
    "BYPASS_DISPONIVEL",
    "ESTRATEGIAS",
    "tentar_bypass_paywall",
]
