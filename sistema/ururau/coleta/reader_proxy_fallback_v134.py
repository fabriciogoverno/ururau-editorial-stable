# -*- coding: utf-8 -*-
"""
reader_proxy_fallback_v134.py

Fallback autorizado de leitura limpa para links internos/autorizados do projeto.

Ordem:
1. tenta leitura direta pública rápida;
2. tenta SemPaywall/API clean com várias variações de URL;
3. devolve o melhor resultado encontrado.

Este módulo é usado quando a captação normal falha ou quando a meta operacional
é chegar perto de 100% na fila de pautas.
"""

from __future__ import annotations

import html
import os
import re
from urllib.parse import urlparse, urlunparse, urljoin

import requests
from bs4 import BeautifulSoup

try:
    from ururau.config.settings import HEADERS
except Exception:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def _env_bool(nome: str, padrao: bool = True) -> bool:
    raw = str(os.getenv(nome, "1" if padrao else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, flags=re.I):
        url = "https://" + url
    p = urlparse(url)
    return urlunparse((p.scheme or "https", p.netloc, p.path or "/", "", p.query, ""))


def _dominio(url: str) -> str:
    p = urlparse(_normalizar_url(url))
    host = (p.netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def _dominio_autorizado(url: str) -> bool:
    trust_project = str(os.getenv("URURAU_READER_PROXY_TRUST_PROJECT_LINKS", "1")).strip().lower()
    if trust_project in {"1", "true", "sim", "yes", "s", "on"}:
        return True

    raw = os.getenv("URURAU_READER_PROXY_ALLOWED_DOMAINS", "*").strip()
    if raw in {"*", "all", "ALL", "todos", "TODOS"}:
        return True

    permitidos = {
        x.strip().lower().removeprefix("www.")
        for x in raw.split(",")
        if x.strip()
    }

    d = _dominio(url)
    return bool(d and (d in permitidos or any(d.endswith("." + p) for p in permitidos)))


def _url_sem_protocolo(url: str) -> str:
    p = urlparse(_normalizar_url(url))
    return (p.netloc + (p.path or "/") + (("?" + p.query) if p.query else "")).lstrip("/")


def montar_urls_reader_proxy_v134(url: str) -> list[str]:
    prefixo = os.getenv(
        "URURAU_READER_PROXY_PREFIX",
        "https://www.sempaywall.com/api/clean/"
    ).strip()

    if not prefixo.endswith("/"):
        prefixo += "/"

    original = _normalizar_url(url)
    if not original:
        return []

    p = urlparse(original)
    host = p.netloc
    path = p.path or "/"
    query = ("?" + p.query) if p.query else ""

    hosts = []
    if host:
        hosts.append(host)
        if host.startswith("www."):
            hosts.append(host[4:])
        else:
            hosts.append("www." + host)

    caminhos = []
    caminhos.append(path + query)
    if not path.endswith("/"):
        caminhos.append(path + "/" + query)

    variantes = []

    def add(v: str):
        if v and v not in variantes:
            variantes.append(v)

    for h in hosts:
        for caminho in caminhos:
            add(prefixo + h + caminho)

    add(prefixo + original)
    add(prefixo + original.replace("https://", "https:/").replace("http://", "http:/"))

    for h in hosts:
        rebuilt = urlunparse((p.scheme, h, path, "", p.query, ""))
        add(prefixo + rebuilt)
        add(prefixo + rebuilt.replace("https://", "https:/").replace("http://", "http:/"))

    return variantes[:12]


def montar_url_reader_proxy_v134(url: str) -> str:
    urls = montar_urls_reader_proxy_v134(url)
    return urls[0] if urls else ""


def _limpar_linha(s: str) -> str:
    s = html.unescape(str(s or "")).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _limpar_texto(texto: str) -> str:
    junk = re.compile(
        r"(?i)(cookies|newsletter|assine|login|publicidade|compartilhe|"
        r"termos de uso|política de privacidade|mais lidas|últimas notícias|"
        r"continua após a publicidade|receba gratuitamente)"
    )
    linhas = []
    vistos = set()

    for raw in re.split(r"\n+", texto or ""):
        linha = _limpar_linha(raw)
        if len(linha) < 35:
            continue
        if junk.search(linha) and len(linha) < 260:
            continue

        chave = re.sub(r"[^a-z0-9áéíóúãõâêôç]+", "", linha.lower())[:220]
        if chave in vistos:
            continue

        vistos.add(chave)
        linhas.append(linha)

    return "\n\n".join(linhas).strip()


def _extrair_html_limpo(html_text: str, base_url: str = "") -> tuple[str, str, str]:
    soup = BeautifulSoup(html_text or "", "html.parser")

    for tag in soup.find_all([
        "script", "style", "noscript", "svg", "iframe", "form",
        "button", "nav", "header", "footer", "aside"
    ]):
        tag.decompose()

    titulo = ""
    h1 = soup.find("h1")
    if h1:
        titulo = _limpar_linha(h1.get_text(" ", strip=True))

    if not titulo and soup.title:
        titulo = _limpar_linha(soup.title.get_text(" ", strip=True))

    imagem = ""
    for selector in ['meta[property="og:image"]', 'meta[name="twitter:image"]']:
        el = soup.select_one(selector)
        if el and el.get("content"):
            imagem = urljoin(base_url, str(el.get("content")).strip())
            break

    if not imagem:
        img = soup.find("img", src=True)
        if img:
            imagem = urljoin(base_url, img.get("src", ""))

    candidatos = []
    seletores = [
        "article",
        "main",
        "[role='main']",
        ".article",
        ".post",
        ".content",
        ".entry-content",
        ".materia",
        ".noticia",
        ".texto",
        "body",
    ]

    for sel in seletores:
        for el in soup.select(sel)[:10]:
            linhas = []
            for node in el.find_all(["p", "h2", "h3", "blockquote", "li"], recursive=True):
                txt = _limpar_linha(node.get_text(" ", strip=True))
                if len(txt) >= 35:
                    linhas.append(txt)

            texto = "\n\n".join(linhas)
            score = len(texto) + 80 * len([x for x in linhas if len(x) > 80])
            candidatos.append((score, texto))

    candidatos.sort(key=lambda x: x[0], reverse=True)
    texto = _limpar_texto(candidatos[0][1] if candidatos else "")

    return titulo, texto, imagem


def _headers() -> dict:
    headers = dict(HEADERS or {})
    headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"
    )
    headers.setdefault(
        "Accept",
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    )
    headers.setdefault("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8")
    return headers


def _extrair_direto_publico_v134(url: str, titulo_ref: str = "") -> dict:
    if not _env_bool("URURAU_READER_PROXY_DIRECT_FIRST", True):
        return {"ok": False, "erro": "direct_first_desativado"}

    original = _normalizar_url(url)
    if not original:
        return {"ok": False, "erro": "url_invalida"}

    if not _dominio_autorizado(original):
        return {"ok": False, "erro": "dominio_nao_autorizado"}

    timeout = _env_int("URURAU_READER_PROXY_DIRECT_TIMEOUT", 12)
    min_chars = _env_int("URURAU_READER_PROXY_MIN_CHARS", 700)

    tentativas = [original]
    if not original.endswith("/"):
        tentativas.append(original + "/")

    p = urlparse(original)
    if p.netloc.startswith("www."):
        tentativas.append(urlunparse((p.scheme, p.netloc[4:], p.path, "", p.query, "")))
    else:
        tentativas.append(urlunparse((p.scheme, "www." + p.netloc, p.path, "", p.query, "")))

    erros = []
    melhor = {"ok": False, "chars": 0, "erro": "sem_tentativa_util"}

    for tentativa in tentativas:
        try:
            resp = requests.get(tentativa, headers=_headers(), timeout=timeout, allow_redirects=True)

            if int(getattr(resp, "status_code", 0) or 0) >= 400:
                erros.append(f"HTTP {resp.status_code} | {tentativa}")
                continue

            if not resp.encoding or str(resp.encoding).lower() in {"iso-8859-1", "ascii"}:
                try:
                    resp.encoding = resp.apparent_encoding or "utf-8"
                except Exception:
                    pass

            titulo, texto, imagem = _extrair_html_limpo(resp.text or "", tentativa)
            chars = len(texto or "")

            if chars > int(melhor.get("chars") or 0):
                melhor = {
                    "ok": False,
                    "url_clean": tentativa,
                    "titulo": titulo or titulo_ref,
                    "texto": texto[:16000],
                    "imagem": imagem,
                    "chars": chars,
                    "erro": f"texto_insuficiente_{chars}",
                    "metodo": "direct_public_v134",
                    "erros": erros[-8:],
                }

            if chars >= min_chars:
                return {
                    "ok": True,
                    "url_clean": tentativa,
                    "titulo": titulo or titulo_ref,
                    "texto": texto[:16000],
                    "imagem": imagem,
                    "chars": chars,
                    "erro": "",
                    "metodo": "direct_public_v134",
                    "erros": erros[-8:],
                }

            erros.append(f"texto_insuficiente_{chars} | {tentativa}")

        except Exception as e:
            erros.append(f"{type(e).__name__}: {e} | {tentativa}")

    melhor["erros"] = erros[-10:]
    return melhor


def _extrair_via_proxy_v134(url: str, titulo_ref: str = "") -> dict:
    urls_clean = montar_urls_reader_proxy_v134(url)
    if not urls_clean:
        return {"ok": False, "erro": "sem_url_clean"}

    timeout = _env_int("URURAU_READER_PROXY_TIMEOUT", 18)
    min_chars = _env_int("URURAU_READER_PROXY_MIN_CHARS", 700)

    erros = []
    melhor = {"ok": False, "chars": 0, "erro": "sem_tentativa_util"}

    for clean_url in urls_clean:
        try:
            resp = requests.get(clean_url, headers=_headers(), timeout=timeout, allow_redirects=True)

            if int(getattr(resp, "status_code", 0) or 0) >= 400:
                erros.append(f"HTTP {resp.status_code} | {clean_url}")
                continue

            if not resp.encoding or str(resp.encoding).lower() in {"iso-8859-1", "ascii"}:
                try:
                    resp.encoding = resp.apparent_encoding or "utf-8"
                except Exception:
                    pass

            titulo, texto, imagem = _extrair_html_limpo(resp.text or "", clean_url)
            chars = len(texto or "")

            if chars > int(melhor.get("chars") or 0):
                melhor = {
                    "ok": False,
                    "url_clean": clean_url,
                    "titulo": titulo or titulo_ref,
                    "texto": texto[:16000],
                    "imagem": imagem,
                    "chars": chars,
                    "erro": f"texto_insuficiente_{chars}",
                    "metodo": "reader_proxy_v134",
                    "tentativas": urls_clean,
                    "erros": erros[-8:],
                }

            if chars >= min_chars:
                return {
                    "ok": True,
                    "url_clean": clean_url,
                    "titulo": titulo or titulo_ref,
                    "texto": texto[:16000],
                    "imagem": imagem,
                    "chars": chars,
                    "erro": "",
                    "metodo": "reader_proxy_v134",
                    "tentativas": urls_clean,
                    "erros": erros[-8:],
                }

            erros.append(f"texto_insuficiente_{chars} | {clean_url}")

        except Exception as e:
            erros.append(f"{type(e).__name__}: {e} | {clean_url}")

    melhor["erros"] = erros[-10:]
    return melhor


def extrair_reader_proxy_v134(url: str, titulo_ref: str = "") -> dict:
    if not _env_bool("URURAU_READER_PROXY_FALLBACK", True):
        return {"ok": False, "erro": "fallback_desativado"}

    original = _normalizar_url(url)
    if not original:
        return {"ok": False, "erro": "url_invalida"}

    if not _dominio_autorizado(original):
        return {
            "ok": False,
            "erro": "dominio_nao_autorizado",
            "dominio": _dominio(original),
        }

    # 1. Direto primeiro, porque há fontes como Band em que o HTML público já tem o texto.
    direto = _extrair_direto_publico_v134(original, titulo_ref=titulo_ref)
    if direto.get("ok"):
        return direto

    # 2. Reader proxy/SemPaywall com variações.
    proxy = _extrair_via_proxy_v134(original, titulo_ref=titulo_ref)
    if proxy.get("ok"):
        return proxy

    # 3. Retorna melhor tentativa para auditoria.
    if int(direto.get("chars") or 0) >= int(proxy.get("chars") or 0):
        direto["proxy_erros"] = proxy.get("erros") or [proxy.get("erro")]
        return direto

    proxy["direct_erros"] = direto.get("erros") or [direto.get("erro")]
    return proxy


def instalar_reader_proxy_fallback_v134() -> bool:
    try:
        import ururau.coleta.leitura_fonte as leitura
    except Exception:
        return False

    original = getattr(leitura, "ler_fonte_pauta", None)
    ResultadoLeitura = getattr(leitura, "ResultadoLeitura", None)

    if not callable(original) or ResultadoLeitura is None:
        return False

    if getattr(original, "_v134_reader_proxy", False):
        return True

    def wrapper(pauta: dict, forcar_refresh: bool = False):
        resultado = original(pauta, forcar_refresh=forcar_refresh)

        try:
            texto_atual = (getattr(resultado, "texto_limpo", "") or "").strip()
            min_chars = _env_int("URURAU_READER_PROXY_MIN_CHARS", 700)

            if getattr(resultado, "sucesso", False) and len(texto_atual) >= min_chars:
                return resultado
        except Exception:
            pass

        try:
            url = (
                pauta.get("link_origem")
                or pauta.get("url_final")
                or pauta.get("url_original")
                or pauta.get("link")
                or ""
            ).strip()
            titulo_ref = pauta.get("titulo_origem") or pauta.get("titulo") or ""
        except Exception:
            url = ""
            titulo_ref = ""

        data = extrair_reader_proxy_v134(url, titulo_ref=titulo_ref)

        if not data.get("ok"):
            return resultado

        novo = ResultadoLeitura(
            url=data.get("url_clean") or url,
            texto_limpo=data.get("texto") or "",
            titulo_extraido=data.get("titulo") or titulo_ref,
            imagem_url=data.get("imagem") or getattr(resultado, "imagem_url", "") or "",
            termos_destacados=getattr(resultado, "termos_destacados", []) or [],
            score_intel_adicional=getattr(resultado, "score_intel_adicional", 0) or 0,
            intel_log="[v134] " + str(data.get("metodo") or "reader proxy autorizado"),
            tamanho_chars=int(data.get("chars") or 0),
            sucesso=True,
            erro="",
        )

        print(
            f"[V134][READER_PROXY] OK {novo.tamanho_chars} chars via {data.get('url_clean')}",
            flush=True
        )

        return novo

    wrapper._v134_reader_proxy = True
    setattr(leitura, "ler_fonte_pauta", wrapper)
    return True
