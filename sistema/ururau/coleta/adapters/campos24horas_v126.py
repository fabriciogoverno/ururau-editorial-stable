from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from urllib.parse import urlparse
import hashlib
import os
import calendar
import re

try:
    import feedparser
except Exception:
    feedparser = None

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

from ururau.coleta.fonte_registry_v126 import normalizar_nome_fonte_v126

LAST_DIAGNOSTICO_CAMPOS24_V128 = {}


def obter_diagnostico_campos24_v128() -> dict:
    try:
        import copy
        return copy.deepcopy(LAST_DIAGNOSTICO_CAMPOS24_V128 or {})
    except Exception:
        return dict(LAST_DIAGNOSTICO_CAMPOS24_V128 or {})

CAMPOS24_FEEDS = [
    "https://campos24horas.com.br/portal/feed/",
    "https://campos24horas.com.br/portal/rss/",
    "https://campos24horas.com.br/portal/categoria/policia/feed/",
    "https://campos24horas.com.br/portal/categoria/politica/feed/",
    "https://campos24horas.com.br/portal/categoria/regiao/feed/",
    "https://campos24horas.com.br/portal/categoria/geral/feed/",
]

CAMPOS24_HTML_LISTAS = [
    "https://campos24horas.com.br/",
    "https://campos24horas.com.br/noticias/",
    "https://campos24horas.com.br/editoria/policia",
    "https://campos24horas.com.br/editoria/politica",
]

def _uid(url: str, titulo: str) -> str:
    return hashlib.sha1((url + "|" + titulo).encode("utf-8", "ignore")).hexdigest()[:16]

def _limpar_html(txt: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", txt or "")
    return re.sub(r"\s+", " ", txt).strip()

def _data_entry_campos_v127(entry) -> dict[str, str]:
    raw = ""
    for k in ("published", "updated", "created"):
        if entry.get(k):
            raw = str(entry.get(k) or "")
            break

    dt = None
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            ts = calendar.timegm(parsed)
            dt_utc = datetime.fromtimestamp(ts, timezone.utc)
            if ZoneInfo is not None:
                dt_br = dt_utc.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
            else:
                dt_br = dt_utc.replace(tzinfo=None)
            dt = dt_br
        except Exception:
            dt = None

    br = dt.strftime("%d/%m/%Y %H:%M") if dt else ""
    iso = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""
    return {
        "data_pub_fonte": br,
        "data_pub_fonte_br": br,
        "data_publicacao": br,
        "publicado_em": br,
        "data_pub_fonte_original": raw,
        "_data_pub_ordem": iso,
        "_campos24_data_corrigida_v127": bool(dt),
    }

def _pauta(titulo: str, link: str, resumo: str = "", data: dict | None = None, categoria: str = "", metodo: str = "rss") -> dict:
    titulo = re.sub(r"\s+", " ", (titulo or "").strip())
    link = (link or "").strip()
    uid = _uid(link, titulo)
    data = data or {}
    return {
        "titulo_origem": titulo,
        "titulo": titulo,
        "link_origem": link,
        "url": link,
        "link": link,
        "fonte_nome": "Campos 24 Horas",
        "fonte": "Campos 24 Horas",
        "nome_fonte": "Campos 24 Horas",
        "resumo_origem": (resumo or "")[:700],
        "canal_forcado": "",
        "canal": "",
        "canal_sugerido": "",
        **data,
        "_uid": uid,
        "uid": uid,
        "tipo_fonte": "especial_campos24_v126",
        "origem_feed": metodo,
        "origem": "Campos 24 Horas",
        "_v94_listagem_rapida": True,
        "_v94_precisa_hidratar": True,
        "precisa_hidratar_fonte": True,
        # Se o feed vier sem data por alguma mudança do site, ainda entra ao menos como exceção operacional.
        "_excecao_fora_janela_v123": True,
        "_motivo_excecao_janela_v123": "campos24_especial_v127",
        "prioridade": 5,
        "score_editorial": 130,
        "score": 150,
    }

def coletar_campos24horas_v126(limite: int | None = None) -> list[dict]:
    global LAST_DIAGNOSTICO_CAMPOS24_V128
    """
    Coletor especial para Campos 24 Horas.

    Estratégia:
    1. RSS real em /portal/feed/ e categorias.
    2. Se RSS trouxer pouco, fallback HTML de listagens públicas.
    3. Sitemap continua existindo no fluxo XML/Sitemap legado.
    """
    limite = int(limite or os.getenv("URURAU_V126_CAMPOS24_LIMITE", "30") or 30)
    LAST_DIAGNOSTICO_CAMPOS24_V128 = {"limite": limite, "feeds": [], "html": [], "total_final": 0}
    vistos: set[str] = set()
    saida: list[dict] = []

    if feedparser is not None:
        for feed_url in CAMPOS24_FEEDS:
            if len(saida) >= limite:
                break
            try:
                # V200_3: feedparser.parse(url) faz fetch SEM timeout e trava
                # o ciclo. Roteia pelo HTTP resiliente com timeout duro.
                try:
                    from ururau.coleta.http_fetch_v109 import fetch_rss_v109 as _frss_c24
                    _rc24 = _frss_c24(feed_url, timeout=12, max_retries=2)
                    feed = feedparser.parse(_rc24.text) if (_rc24.ok and _rc24.text) else feedparser.parse("")
                except Exception:
                    feed = feedparser.parse("")
                entries = feed.get("entries", []) or []
                LAST_DIAGNOSTICO_CAMPOS24_V128["feeds"].append({
                    "url": feed_url,
                    "status_http": getattr(feed, "status", ""),
                    "itens": len(entries),
                    "erro": "",
                })
                print(f"[CAMPOS24 v126][RSS] {feed_url}: {len(entries)} entrada(s)")
                for entry in entries:
                    titulo = (entry.get("title") or "").strip()
                    link = (entry.get("link") or "").strip()
                    if not titulo or not link:
                        continue
                    chave = link.lower().rstrip("/")
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    resumo = _limpar_html(entry.get("summary") or entry.get("description") or "")
                    cats = entry.get("tags") or []
                    categoria = ""
                    if cats and isinstance(cats, list):
                        try:
                            categoria = str(cats[0].get("term") or "")
                        except Exception:
                            categoria = ""
                    saida.append(_pauta(titulo, link, resumo, _data_entry_campos_v127(entry), categoria, "rss_campos24_v126"))
                    if len(saida) >= limite:
                        break
            except Exception as exc:
                LAST_DIAGNOSTICO_CAMPOS24_V128["feeds"].append({
                    "url": feed_url,
                    "status_http": "",
                    "itens": 0,
                    "erro": f"{type(exc).__name__}: {exc}",
                })
                print(f"[CAMPOS24 v126][RSS] falha {feed_url}: {type(exc).__name__}: {exc}")

    # fallback leve por HTML só se RSS veio pobre
    minimo_html = int(os.getenv("URURAU_V126_CAMPOS24_HTML_SE_MENOS_QUE", "5") or 5)
    if len(saida) < minimo_html and requests is not None and BeautifulSoup is not None:
        headers = {"User-Agent": "Mozilla/5.0"}
        for url in CAMPOS24_HTML_LISTAS:
            if len(saida) >= limite:
                break
            try:
                r = requests.get(url, headers=headers, timeout=20)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                links = []
                for a in soup.select("a[href]"):
                    href = (a.get("href") or "").strip()
                    text = re.sub(r"\s+", " ", a.get_text(" ", strip=True) or "").strip()
                    if not href or not text:
                        continue
                    if "campos24horas.com.br" not in href:
                        continue
                    if "/portal/" not in href and "/noticia/" not in href:
                        continue
                    links.append((text, href))
                LAST_DIAGNOSTICO_CAMPOS24_V128["html"].append({
                    "url": url,
                    "status_http": getattr(r, "status_code", ""),
                    "links": len(links),
                    "erro": "",
                })
                print(f"[CAMPOS24 v126][HTML] {url}: {len(links)} link(s)")
                for titulo, href in links:
                    chave = href.lower().rstrip("/")
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    saida.append(_pauta(titulo, href, "", {}, "", "html_campos24_v126"))
                    if len(saida) >= limite:
                        break
            except Exception as exc:
                LAST_DIAGNOSTICO_CAMPOS24_V128["html"].append({
                    "url": url,
                    "status_http": "",
                    "links": 0,
                    "erro": f"{type(exc).__name__}: {exc}",
                })
                print(f"[CAMPOS24 v126][HTML] falha {url}: {type(exc).__name__}: {exc}")

    LAST_DIAGNOSTICO_CAMPOS24_V128["total_final"] = len(saida[:limite])
    return saida[:limite]
