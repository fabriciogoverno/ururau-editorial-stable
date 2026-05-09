"""Adapter v130.6 — NF Notícias

Motivo: o feed https://www.nfnoticias.com.br/rss/ responde RSS válido,
mas o fluxo regional genérico vinha registrando 0 itens úteis. Este adaptador
lê o XML diretamente, sem depender do parser genérico, aceita links com e sem
www e gera pautas no mesmo formato esperado pela fila.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import html
import os
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

from ururau.coleta.datas_v99 import dentro_da_janela, formatar_br, ordenar_iso

URLS_RSS_NF = [
    "https://www.nfnoticias.com.br/rss/",
    "https://www.nfnoticias.com.br/rss",
]

HEADERS_NF = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 UrurauBot/130.6",
    "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
    "Cache-Control": "no-cache",
}


def _txt(v: Any) -> str:
    s = str(v or "").strip()
    s = html.unescape(s)
    # O NF às vezes entrega ldquo; e rdquo; sem ampersand.
    repl = {
        "ldquo;": "“", "rdquo;": "”", "lsquo;": "‘", "rsquo;": "’",
        "&nbsp;": " ", "nbsp;": " ",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _html_text(v: Any) -> str:
    s = _txt(v)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _uid(link: str, titulo: str) -> str:
    return hashlib.sha1((link or titulo or "").encode("utf-8", "ignore")).hexdigest()[:16]


def _parse_pubdate(raw: str):
    raw = _txt(raw)
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
        return dt.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            dt = _dt.datetime.strptime(raw, fmt)
            if dt.tzinfo is not None:
                dt = dt.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
            return dt
        except Exception:
            continue
    return None


def _same_news_domain(link: str) -> bool:
    try:
        host = (urlparse(link).hostname or "").lower().replace("www.", "")
        return host == "nfnoticias.com.br"
    except Exception:
        return False


def _fetch_rss() -> tuple[str, str, str]:
    last_err = ""
    for url in URLS_RSS_NF:
        try:
            r = requests.get(url, headers=HEADERS_NF, timeout=int(os.getenv("URURAU_V1306_NF_TIMEOUT", "15") or "15"))
            ctype = r.headers.get("content-type", "")
            text = r.text or ""
            if r.status_code < 400 and "<rss" in text.lower() and "<item" in text.lower():
                return text, url, ctype
            last_err = f"{url}: status={r.status_code} content-type={ctype} len={len(text)}"
        except Exception as e:
            last_err = f"{url}: {type(e).__name__}: {e}"
    raise RuntimeError(last_err or "NF Notícias: RSS indisponível")


def _parse_items_etree(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text.encode("utf-8", "ignore"))
    out: list[dict] = []
    for item in root.findall(".//item"):
        def find_text(tag: str) -> str:
            el = item.find(tag)
            return _txt(el.text if el is not None else "")
        enc_url = ""
        enc_type = ""
        for enc in item.findall("enclosure"):
            enc_url = _txt(enc.attrib.get("url"))
            enc_type = _txt(enc.attrib.get("type"))
            if enc_url:
                break
        out.append({
            "title": find_text("title"),
            "link": find_text("link") or find_text("guid"),
            "guid": find_text("guid"),
            "description": _html_text(find_text("description")),
            "pubDate": find_text("pubDate"),
            "image": enc_url,
            "image_type": enc_type,
        })
    return out


def _parse_items_bs4(xml_text: str) -> list[dict]:
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(xml_text, "xml")
    out: list[dict] = []
    for item in soup.find_all("item"):
        def get(tag: str) -> str:
            el = item.find(tag)
            return _txt(el.get_text(" ") if el else "")
        enc = item.find("enclosure")
        img = _txt(enc.get("url") if enc else "")
        typ = _txt(enc.get("type") if enc else "")
        out.append({
            "title": get("title"),
            "link": get("link") or get("guid"),
            "guid": get("guid"),
            "description": _html_text(get("description")),
            "pubDate": get("pubDate"),
            "image": img,
            "image_type": typ,
        })
    return out


def _parse_items(xml_text: str) -> tuple[list[dict], str, str]:
    try:
        itens = _parse_items_etree(xml_text)
        return itens, "xml.etree", ""
    except Exception as e1:
        try:
            itens = _parse_items_bs4(xml_text)
            return itens, "bs4_xml", f"xml.etree falhou: {type(e1).__name__}: {e1}"
        except Exception as e2:
            return [], "falhou", f"xml.etree={type(e1).__name__}: {e1}; bs4={type(e2).__name__}: {e2}"


def coletar_nfnoticias_v1306(max_itens: int | None = None) -> tuple[list[dict], dict]:
    max_itens = max_itens or int(os.getenv("URURAU_V1306_NF_MAX_ITENS", "10") or "10")
    xml_text, url_usada, ctype = _fetch_rss()
    itens, parser, erro_parser = _parse_items(xml_text)
    agora = _dt.datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)

    pautas: list[dict] = []
    stats = {
        "url_usada": url_usada,
        "content_type": ctype,
        "parser": parser,
        "erro_parser": erro_parser,
        "rss_items": len(itens),
        "titulo_link": 0,
        "fora_dominio": 0,
        "fora_janela": 0,
        "sem_data": 0,
        "aceitas": 0,
        "primeiro_titulo": "",
    }

    for it in itens:
        titulo = _txt(it.get("title"))
        link = _txt(it.get("link"))
        resumo = _html_text(it.get("description"))
        if not titulo or not link:
            continue
        stats["titulo_link"] += 1
        if not stats["primeiro_titulo"]:
            stats["primeiro_titulo"] = titulo
        if not _same_news_domain(link):
            stats["fora_dominio"] += 1
            continue
        dt = _parse_pubdate(it.get("pubDate") or "")
        if dt is None:
            stats["sem_data"] += 1
            continue
        ok, motivo_janela, idade_horas = dentro_da_janela(dt, agora)
        if not ok:
            stats["fora_janela"] += 1
            continue
        if idade_horas <= 1:
            prio = 3
        elif idade_horas <= 2:
            prio = 2
        else:
            prio = 1
        data_br = formatar_br(dt)
        pauta = {
            "titulo_origem": titulo,
            "titulo": titulo,
            "link_origem": link,
            "link": link,
            "url": link,
            "fonte_nome": "NF Notícias",
            "fonte": "NF Notícias",
            "nome_fonte": "NF Notícias",
            "resumo_origem": resumo[:800],
            "canal_forcado": "",
            "data_pub_fonte": data_br,
            "data_pub_fonte_br": data_br,
            "data_pub_fonte_original": _txt(it.get("pubDate")),
            "data_pub_metodo_v99": "nfnoticias_rss_pubDate_v1306",
            "_data_pub_ordem": ordenar_iso(dt),
            "_uid": _uid(link, titulo),
            "uid": _uid(link, titulo),
            "prioridade": prio,
            "tipo_fonte": "regional_nfnoticias_v1306",
            "origem": "NF Notícias RSS v130.6",
            "origem_feed": url_usada,
            "regional_prioritaria": True,
            "bypass_score": True,
            "_v1306_nf_adapter": True,
            "_v1306_motivo": "NF Notícias: RSS regional com parser XML direto, sem depender do coletor genérico.",
        }
        img = _txt(it.get("image"))
        if img:
            pauta["imagem_url"] = img
            pauta["imagem_url_rss"] = img
            pauta.setdefault("imagem_credito", "Reprodução")
            pauta["imagem_status"] = "url_pendente"
        try:
            from ururau.editorial.classificador_editorial_contextual_v117 import aplicar_editoria_contextual
            pauta = aplicar_editoria_contextual(pauta)
        except Exception:
            pass
        pautas.append(pauta)
        stats["aceitas"] += 1
        if len(pautas) >= max_itens:
            break

    return pautas, stats
