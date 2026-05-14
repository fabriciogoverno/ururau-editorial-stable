from __future__ import annotations

"""
Coletor especial para Manchete RJ — v129.14

Motivo: o diagnóstico completo de 02/05/2026 mostrou que mancheterj.com
funciona, mas a entrada simples https://mancheterj.com/feed/ pode retornar
0 item útil no ciclo real. A estratégia correta é:
1. RSS /portal/feed/
2. RSS /portal/rss/
3. RSS raiz como fallback
4. WP REST API como fallback leve
5. Sitemap/HTML apenas em último caso

Este módulo não altera o motor global de RSS. Ele só trata Manchete RJ quando
chamado explicitamente pelo painel.
"""

import datetime as _dt
import hashlib
import os
import re
import time
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import urljoin, urlparse

import feedparser
import requests

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

from ururau.config.settings import HEADERS, TIMEOUT_PADRAO
from ururau.coleta.datas_v99 import (
    dentro_da_janela,
    formatar_br,
    ordenar_iso,
    janela_publicacao_horas,
)

try:
    from ururau.coleta.rss import (
        _aplicar_preconteudo_rss_v106,
        _campos_data_publicacao,
        _extrair_dt,
        _limpar_html,
    )
except Exception:  # fallback mínimo, sem quebrar o painel
    _aplicar_preconteudo_rss_v106 = None  # type: ignore
    _campos_data_publicacao = None  # type: ignore
    _extrair_dt = None  # type: ignore
    def _limpar_html(texto: str) -> str:  # type: ignore
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto or "")).strip()

NOME_FONTE = "Manchete RJ"
FEEDS_PRINCIPAIS = [
    "https://mancheterj.com/portal/feed/",
    "https://mancheterj.com/portal/rss/",
]
FEEDS_FALLBACK = [
    "https://mancheterj.com/feed/",
    "https://mancheterj.com/rss/",
]
WP_API = "https://mancheterj.com/wp-json/wp/v2/posts?per_page=10"
SITEMAPS = [
    "https://mancheterj.com/sitemap.xml",
    "https://mancheterj.com/wp-sitemap.xml",
]
HTML_LISTAGENS = [
    "https://mancheterj.com/",
    "https://mancheterj.com/portal/",
    "https://mancheterj.com/politica/",
    "https://mancheterj.com/policia/",
    "https://mancheterj.com/regiao/",
    "https://mancheterj.com/geral/",
]

_DIAG: dict = {
    "feeds": [],
    "wp_api": {},
    "sitemaps": [],
    "html": [],
    "estrategia_usada": "",
    "total_final": 0,
}


def _reset_diag() -> None:
    global _DIAG
    _DIAG = {
        "feeds": [],
        "wp_api": {},
        "sitemaps": [],
        "html": [],
        "estrategia_usada": "",
        "total_final": 0,
    }


def obter_diagnostico_mancheterj_v12914() -> dict:
    return dict(_DIAG)


def _uid(link: str, titulo: str) -> str:
    return hashlib.md5(f"{link}{titulo}".encode("utf-8", errors="ignore")).hexdigest()[:16]


def _headers() -> dict:
    h = dict(HEADERS or {})
    h.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36")
    h.setdefault("Accept", "application/rss+xml, application/xml, text/xml, application/json, text/html;q=0.9, */*;q=0.8")
    return h


def _agora_sp_naive() -> _dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return _dt.datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    except Exception:
        return _dt.datetime.now()


def _parse_iso_wp(valor: str | None) -> _dt.datetime | None:
    if not valor:
        return None
    s = str(valor).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = _dt.datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            try:
                from zoneinfo import ZoneInfo
                dt = dt.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
            except Exception:
                dt = dt.replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _campos_data_manual(dt: _dt.datetime | None, raw: str = "", metodo: str = "manual") -> dict:
    return {
        "data_pub_fonte": formatar_br(dt),
        "data_pub_fonte_br": formatar_br(dt),
        "data_pub_fonte_original": raw or "",
        "data_pub_metodo_v99": metodo,
        "_data_pub_ordem": ordenar_iso(dt),
    }


def _dentro(dt: _dt.datetime | None, agora: _dt.datetime) -> tuple[bool, str, float]:
    try:
        return dentro_da_janela(dt, agora)
    except Exception:
        if dt is None:
            return False, "sem_data_publicacao", 999999.0
        idade = max(0.0, (agora - dt).total_seconds() / 3600.0)
        return idade <= float(janela_publicacao_horas(4)), "ok" if idade <= 4 else "fora_da_janela", idade


def _prioridade_por_idade(idade_horas: float) -> int:
    if idade_horas <= 1:
        return 3
    if idade_horas <= 2:
        return 2
    if idade_horas <= float(janela_publicacao_horas(4)):
        return 1
    return 0


def _normalizar_pauta_para_fila_v12914(pauta: dict) -> dict:
    """Deixa a pauta da Manchete RJ no mesmo contrato usado pelo Campos 24 Horas.

    O problema da v129.13 era parecido com o antigo caso Campos 24 Horas:
    o coletor achava/salvava a matéria, mas a fila visual podia ocultá-la
    porque faltavam campos duplicados esperados pela UI e porque o fallback fora
    da janela era salvo, mas não era considerado visível pela Fila de Pautas.
    """
    titulo = (pauta.get("titulo_origem") or pauta.get("titulo") or "").strip()
    link = (pauta.get("link_origem") or pauta.get("url") or pauta.get("link") or "").strip()
    pauta["titulo_origem"] = titulo
    pauta["titulo"] = titulo
    pauta["link_origem"] = link
    pauta["url"] = link
    pauta["link"] = link
    pauta["fonte_nome"] = NOME_FONTE
    pauta["fonte"] = NOME_FONTE
    pauta["nome_fonte"] = NOME_FONTE
    pauta.setdefault("resumo_origem", "")
    pauta.setdefault("canal_forcado", "")
    pauta.setdefault("canal", pauta.get("canal_forcado", ""))
    pauta.setdefault("canal_sugerido", pauta.get("canal_forcado", ""))
    data_br = pauta.get("data_pub_fonte") or pauta.get("data_pub_fonte_br") or pauta.get("publicado_em") or ""
    pauta["data_pub_fonte"] = data_br
    pauta.setdefault("data_pub_fonte_br", data_br)
    pauta.setdefault("data_publicacao", data_br)
    pauta.setdefault("publicado_em", data_br)
    pauta.setdefault("_uid", _uid(link, titulo))
    pauta.setdefault("uid", pauta.get("_uid"))
    pauta["tipo_fonte"] = "rss_especial_mancheterj_v12914"
    pauta["origem_feed"] = "mancheterj_v12914"
    pauta["origem"] = NOME_FONTE
    pauta["_coletor_especial"] = "mancheterj_v12914"
    pauta["_v94_listagem_rapida"] = True
    pauta["_v94_precisa_hidratar"] = True
    pauta["precisa_hidratar_fonte"] = True
    pauta.setdefault("prioridade", 3)
    # Se o fallback escolheu uma matéria fora da janela, ela deve aparecer na fila
    # do mesmo jeito que foi permitido salvar. Mantemos a data original para diagnóstico.
    if pauta.get("_excecao_fora_janela_v123"):
        pauta["_v12914_forcar_visivel_fila"] = True
        pauta["_v12914_motivo_visivel_fila"] = "mancheterj_fallback_operacional"
        pauta.setdefault("_v12914_data_pub_original", data_br)
    return pauta


def _finalizar_pauta(pauta: dict) -> dict:
    pauta = _normalizar_pauta_para_fila_v12914(pauta)
    try:
        from ururau.editorial.classificador_editorial_contextual_v117 import aplicar_editoria_contextual
        pauta = aplicar_editoria_contextual(pauta)
        pauta = _normalizar_pauta_para_fila_v12914(pauta)
    except Exception:
        pass
    return pauta


def _pauta_de_rss_entry(entry: dict, url_feed: str, agora: _dt.datetime) -> tuple[dict | None, dict]:
    titulo = (entry.get("title") or "").strip()
    link = (entry.get("link") or "").strip()
    info = {"titulo": titulo[:100], "link": link, "motivo": ""}
    if not titulo or not link:
        info["motivo"] = "sem_titulo_ou_link"
        return None, info
    resumo = _limpar_html(entry.get("summary") or entry.get("description") or "")
    try:
        dt = _extrair_dt(entry) if _extrair_dt else None
        campos_data = _campos_data_publicacao(entry, dt) if _campos_data_publicacao else _campos_data_manual(dt, metodo="rss")
    except Exception:
        dt = None
        campos_data = _campos_data_manual(None, metodo="rss_erro_data")
    ok, motivo, idade = _dentro(dt, agora)
    info["motivo"] = motivo
    pauta = {
        "titulo_origem": titulo,
        "link_origem": link,
        "fonte_nome": NOME_FONTE,
        "resumo_origem": resumo[:600],
        "canal_forcado": "",
        "data_pub_fonte": campos_data.get("data_pub_fonte") or "",
        **campos_data,
        "_uid": _uid(link, titulo),
        "prioridade": _prioridade_por_idade(float(idade or 0)),
        "_mancheterj_url_feed_v12914": url_feed,
    }
    if _aplicar_preconteudo_rss_v106:
        try:
            pauta = _aplicar_preconteudo_rss_v106(pauta, entry, titulo)
        except Exception:
            pass
    if not ok:
        pauta["_excecao_fora_janela_v123"] = True
        pauta["_motivo_excecao_janela_v123"] = str(motivo)
        pauta["_idade_pub_horas_v123"] = round(float(idade or 0), 2)
    return _finalizar_pauta(pauta), info


def _coletar_feeds(urls: list[str], agora: _dt.datetime, max_itens: int) -> list[dict]:
    aceitas: list[dict] = []
    fallback_fora_janela: dict | None = None
    vistos_links: set[str] = set()
    for url in urls:
        d = {"url": url, "status": "", "entradas": 0, "aceitas_janela": 0, "fallback_fora_janela": 0, "erro": ""}
        try:
            # V200_3: feedparser.parse(url) faz fetch SEM timeout e trava o
            # ciclo. Roteia pelo HTTP resiliente com timeout duro.
            try:
                from ururau.coleta.http_fetch_v109 import fetch_rss_v109 as _frss_mrj
                _rmrj = _frss_mrj(url, timeout=12, max_retries=2)
                feed = feedparser.parse(_rmrj.text) if (_rmrj.ok and _rmrj.text) else feedparser.parse("")
            except Exception:
                feed = feedparser.parse("")
            entradas = feed.get("entries", []) or []
            d["entradas"] = len(entradas)
            for entry in entradas[:30]:
                pauta, info = _pauta_de_rss_entry(entry, url, agora)
                if not pauta:
                    continue
                link = (pauta.get("link_origem") or "").strip()
                if not link or link in vistos_links:
                    continue
                if pauta.get("_excecao_fora_janela_v123"):
                    if fallback_fora_janela is None:
                        fallback_fora_janela = pauta
                    continue
                aceitas.append(pauta)
                vistos_links.add(link)
                d["aceitas_janela"] += 1
                if len(aceitas) >= max_itens:
                    break
            d["status"] = "ok"
        except Exception as exc:
            d["status"] = "erro"
            d["erro"] = f"{type(exc).__name__}: {exc}"
        _DIAG["feeds"].append(d)
        if len(aceitas) >= max_itens:
            break
        # Se o feed principal retornou item útil, não precisa gastar tempo nos fallbacks.
        if d.get("aceitas_janela", 0) > 0 and url in FEEDS_PRINCIPAIS:
            break
        time.sleep(0.15)
    if not aceitas and fallback_fora_janela is not None:
        _DIAG["feeds"][-1]["fallback_fora_janela"] = 1
        aceitas.append(fallback_fora_janela)
    return aceitas[:max_itens]


def _html_texto(valor: str) -> str:
    valor = str(valor or "")
    if BeautifulSoup is None:
        return _limpar_html(valor)
    soup = BeautifulSoup(valor, "html.parser")
    return soup.get_text(" ", strip=True)


def _coletar_wp_api(agora: _dt.datetime, max_itens: int) -> list[dict]:
    d = {"url": WP_API, "status": "", "itens": 0, "aceitas_janela": 0, "fallback_fora_janela": 0, "erro": ""}
    aceitas: list[dict] = []
    fallback: dict | None = None
    try:
        resp = requests.get(WP_API, headers=_headers(), timeout=int(os.getenv("URURAU_MANCHETERJ_TIMEOUT", TIMEOUT_PADRAO or 12)))
        d["status_http"] = resp.status_code
        resp.raise_for_status()
        itens = resp.json()
        if isinstance(itens, dict):
            itens = itens.get("posts") or itens.get("data") or []
        d["itens"] = len(itens or [])
        for post in (itens or [])[:30]:
            titulo = _html_texto(((post.get("title") or {}).get("rendered") if isinstance(post.get("title"), dict) else post.get("title")) or "").strip()
            link = str(post.get("link") or "").strip()
            if not titulo or not link:
                continue
            resumo = _html_texto(((post.get("excerpt") or {}).get("rendered") if isinstance(post.get("excerpt"), dict) else post.get("excerpt")) or "")
            raw_date = str(post.get("date_gmt") or post.get("date") or post.get("modified") or "")
            dt = _parse_iso_wp(raw_date)
            campos = _campos_data_manual(dt, raw=raw_date, metodo="wp_api")
            ok, motivo, idade = _dentro(dt, agora)
            pauta = {
                "titulo_origem": titulo,
                "link_origem": link,
                "fonte_nome": NOME_FONTE,
                "resumo_origem": resumo[:600],
                "canal_forcado": "",
                "data_pub_fonte": campos.get("data_pub_fonte") or "",
                **campos,
                "_uid": _uid(link, titulo),
                "prioridade": _prioridade_por_idade(float(idade or 0)),
                "_mancheterj_wp_api_v12914": True,
            }
            try:
                img = (((post.get("yoast_head_json") or {}).get("og_image") or [{}])[0] or {}).get("url")
                if img:
                    pauta["imagem_url"] = img
                    pauta["imagem_url_rss"] = img
                    pauta.setdefault("imagem_credito", "Reprodução")
            except Exception:
                pass
            pauta = _finalizar_pauta(pauta)
            if not ok:
                pauta["_excecao_fora_janela_v123"] = True
                pauta["_motivo_excecao_janela_v123"] = motivo
                pauta["_idade_pub_horas_v123"] = round(float(idade or 0), 2)
                if fallback is None:
                    fallback = pauta
                continue
            aceitas.append(pauta)
            d["aceitas_janela"] += 1
            if len(aceitas) >= max_itens:
                break
        d["status"] = "ok"
    except Exception as exc:
        d["status"] = "erro"
        d["erro"] = f"{type(exc).__name__}: {exc}"
    if not aceitas and fallback is not None:
        d["fallback_fora_janela"] = 1
        aceitas.append(fallback)
    _DIAG["wp_api"] = d
    return aceitas[:max_itens]


def _eh_url_artigo(url: str) -> bool:
    u = str(url or "").strip()
    if not u.startswith("http"):
        return False
    lu = u.lower()
    if any(x in lu for x in ("/wp-content/", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".css", ".js")):
        return False
    host = urlparse(u).netloc.lower()
    if not (host == "mancheterj.com" or host.endswith(".mancheterj.com")):
        return False
    return bool(re.search(r"/20\d{2}/\d{2}/\d{2}/", u))


def _extrair_meta_artigo(url: str, agora: _dt.datetime) -> dict | None:
    try:
        resp = requests.get(url, headers=_headers(), timeout=int(os.getenv("URURAU_MANCHETERJ_TIMEOUT", "12") or 12))
        resp.raise_for_status()
        html = resp.text or ""
        if BeautifulSoup is None:
            return None
        soup = BeautifulSoup(html, "html.parser")
        def meta(prop: str) -> str:
            tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
            return str(tag.get("content") or "").strip() if tag else ""
        titulo = meta("og:title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
        desc = meta("og:description") or meta("description")
        img = meta("og:image")
        raw_date = meta("article:published_time") or meta("date") or ""
        dt = _parse_iso_wp(raw_date)
        if dt is None:
            m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
            if m:
                try:
                    dt = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, 0, 0)
                    raw_date = "/".join(m.groups())
                except Exception:
                    pass
        if not titulo:
            return None
        campos = _campos_data_manual(dt, raw=raw_date, metodo="html_og")
        ok, motivo, idade = _dentro(dt, agora)
        pauta = {
            "titulo_origem": titulo,
            "link_origem": url,
            "fonte_nome": NOME_FONTE,
            "resumo_origem": desc[:600],
            "canal_forcado": "",
            "data_pub_fonte": campos.get("data_pub_fonte") or "",
            **campos,
            "_uid": _uid(url, titulo),
            "prioridade": _prioridade_por_idade(float(idade or 0)),
            "_mancheterj_html_v12914": True,
        }
        if img:
            pauta["imagem_url"] = img
            pauta["imagem_url_rss"] = img
            pauta.setdefault("imagem_credito", "Reprodução")
        if not ok:
            pauta["_excecao_fora_janela_v123"] = True
            pauta["_motivo_excecao_janela_v123"] = motivo
            pauta["_idade_pub_horas_v123"] = round(float(idade or 0), 2)
        return _finalizar_pauta(pauta)
    except Exception:
        return None


def _coletar_sitemap_html(agora: _dt.datetime, max_itens: int) -> list[dict]:
    links: list[str] = []
    vistos: set[str] = set()
    for sm in SITEMAPS:
        d = {"url": sm, "status": "", "urls": 0, "artigos_candidatos": 0, "erro": ""}
        try:
            resp = requests.get(sm, headers=_headers(), timeout=int(os.getenv("URURAU_MANCHETERJ_TIMEOUT", "12") or 12))
            d["status_http"] = resp.status_code
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
            locs = [el.text.strip() for el in root.iter() if el.tag.endswith("loc") and el.text]
            d["urls"] = len(locs)
            for loc in locs:
                if _eh_url_artigo(loc) and loc not in vistos:
                    links.append(loc); vistos.add(loc)
            d["artigos_candidatos"] = len(links)
            d["status"] = "ok"
        except Exception as exc:
            d["status"] = "erro"; d["erro"] = f"{type(exc).__name__}: {exc}"
        _DIAG["sitemaps"].append(d)
        time.sleep(0.1)
    if len(links) < max_itens:
        for page in HTML_LISTAGENS:
            d = {"url": page, "status": "", "links": 0, "artigos_candidatos": 0, "erro": ""}
            try:
                resp = requests.get(page, headers=_headers(), timeout=int(os.getenv("URURAU_MANCHETERJ_TIMEOUT", "12") or 12))
                d["status_http"] = resp.status_code
                resp.raise_for_status()
                html = resp.text or ""
                if BeautifulSoup:
                    soup = BeautifulSoup(html, "html.parser")
                    hrefs = [urljoin(page, str(a.get("href") or "")) for a in soup.find_all("a")]
                else:
                    hrefs = re.findall(r'href=["\']([^"\']+)', html, flags=re.I)
                    hrefs = [urljoin(page, h) for h in hrefs]
                d["links"] = len(hrefs)
                for h in hrefs:
                    if _eh_url_artigo(h) and h not in vistos:
                        links.append(h); vistos.add(h)
                d["artigos_candidatos"] = len(links)
                d["status"] = "ok"
            except Exception as exc:
                d["status"] = "erro"; d["erro"] = f"{type(exc).__name__}: {exc}"
            _DIAG["html"].append(d)
            if len(links) >= max_itens:
                break
            time.sleep(0.1)
    aceitas: list[dict] = []
    fallback: dict | None = None
    for link in links[:max(max_itens * 3, 10)]:
        pauta = _extrair_meta_artigo(link, agora)
        if not pauta:
            continue
        if pauta.get("_excecao_fora_janela_v123"):
            if fallback is None:
                fallback = pauta
            continue
        aceitas.append(pauta)
        if len(aceitas) >= max_itens:
            break
    if not aceitas and fallback is not None:
        aceitas.append(fallback)
    return aceitas[:max_itens]


def coletar_mancheterj_v12914(max_itens: int | None = None) -> list[dict]:
    """Coleta Manchete RJ com fallback seguro e diagnóstico por etapa."""
    _reset_diag()
    try:
        max_itens = int(max_itens or os.getenv("URURAU_MANCHETERJ_MAX_ITENS", "10") or 10)
    except Exception:
        max_itens = 10
    agora = _agora_sp_naive()

    # 1) RSS recomendado no diagnóstico.
    pautas = _coletar_feeds(FEEDS_PRINCIPAIS + FEEDS_FALLBACK, agora, max_itens)
    if pautas:
        _DIAG["estrategia_usada"] = "rss_portal_ou_raiz"
        _DIAG["total_final"] = len(pautas)
        return pautas[:max_itens]

    # 2) WP REST API.
    pautas = _coletar_wp_api(agora, max_itens)
    if pautas:
        _DIAG["estrategia_usada"] = "wp_api"
        _DIAG["total_final"] = len(pautas)
        return pautas[:max_itens]

    # 3) Sitemap/HTML fallback final.
    pautas = _coletar_sitemap_html(agora, max_itens)
    if pautas:
        _DIAG["estrategia_usada"] = "sitemap_html"
        _DIAG["total_final"] = len(pautas)
        return pautas[:max_itens]

    _DIAG["estrategia_usada"] = "nenhuma"
    _DIAG["total_final"] = 0
    return []

# Compatibilidade com a integração v129.13 no painel antigo.
def obter_diagnostico_mancheterj_v12913() -> dict:
    return obter_diagnostico_mancheterj_v12914()


def coletar_mancheterj_v12913(max_itens: int | None = None) -> list[dict]:
    return coletar_mancheterj_v12914(max_itens=max_itens)
