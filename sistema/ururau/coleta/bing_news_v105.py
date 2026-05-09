"""
ururau/coleta/bing_news_v105.py

Integração opcional com Bing News Search API v7 para descoberta legal/paga
de notícias por termos editoriais. Usa apenas metadados públicos retornados
pela API e mantém a extração do texto pelo pipeline de fonte do projeto.

Ativação:
    URURAU_V105_USAR_BING_NEWS=1
    BING_NEWS_API_KEY=<sua chave>

Parâmetros principais:
    URURAU_V105_BING_MKT=pt-BR
    URURAU_V105_BING_COUNT=5
    URURAU_V105_BING_FRESHNESS=Day
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import time
from typing import Iterable

import requests

from ururau.config.settings import HEADERS, TIMEOUT_PADRAO
from ururau.coleta.datas_v99 import (
    dentro_da_janela,
    formatar_br,
    janela_publicacao_horas,
    ordenar_iso,
    parse_data_br_ou_iso,
)

ENDPOINT = "https://api.bing.microsoft.com/v7.0/news/search"


def _env_bool(chave: str, padrao: str = "0") -> bool:
    return os.getenv(chave, padrao).strip().lower() in {"1", "true", "sim", "yes", "s"}


def _api_key() -> str:
    for k in ("BING_NEWS_API_KEY", "BING_SEARCH_API_KEY", "AZURE_BING_SEARCH_KEY", "MS_BING_API_KEY"):
        v = os.getenv(k, "").strip()
        if v:
            return v
    return ""


def _uid(link: str, titulo: str) -> str:
    return hashlib.md5(f"bing:{link}{titulo}".encode("utf-8", "ignore")).hexdigest()[:16]


def _normalizar_dt_bing(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    # Bing costuma retornar ISO UTC: 2026-04-29T14:00:00.0000000Z
    try:
        txt = raw.replace("Z", "+00:00")
        if "." in txt:
            # datetime.fromisoformat não aceita 7 casas em todas as versões.
            txt = txt.replace("+00:00", "")
            base, frac = txt.split(".", 1)
            frac = frac[:6]
            txt = base + "." + frac + "+00:00"
        dt = _dt.datetime.fromisoformat(txt)
        if dt.tzinfo is not None:
            from zoneinfo import ZoneInfo
            dt = dt.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        return dt
    except Exception:
        return parse_data_br_ou_iso(raw)


def coletar_bing_news_v105(termos: Iterable[str], max_por_termo: int | None = None) -> list[dict]:
    """Retorna pautas descobertas pelo Bing News, filtradas pela janela de publicação."""
    if not _env_bool("URURAU_V105_USAR_BING_NEWS", "0"):
        return []
    key = _api_key()
    if not key:
        print("[BING v105] Desativado: defina BING_NEWS_API_KEY para usar Bing News Search.")
        return []

    count = max_por_termo or int(os.getenv("URURAU_V105_BING_COUNT", "5") or "5")
    mkt = os.getenv("URURAU_V105_BING_MKT", "pt-BR") or "pt-BR"
    freshness = os.getenv("URURAU_V105_BING_FRESHNESS", "Day") or "Day"
    headers = dict(HEADERS or {})
    headers["Ocp-Apim-Subscription-Key"] = key
    headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122 Safari/537.36")

    pautas: list[dict] = []
    vistos: set[str] = set()
    termos_limpos = [str(t or "").strip() for t in termos if str(t or "").strip()]
    if not termos_limpos:
        termos_limpos = ["Rio de Janeiro", "Campos dos Goytacazes", "Alerj"]

    for termo in termos_limpos:
        params = {
            "q": termo,
            "mkt": mkt,
            "safeSearch": "Moderate",
            "textFormat": "Raw",
            "sortBy": "Date",
            "freshness": freshness,
            "count": count,
            "offset": 0,
            "originalImg": "true",
        }
        try:
            r = requests.get(ENDPOINT, headers=headers, params=params, timeout=int(TIMEOUT_PADRAO or 14))
            if r.status_code in (401, 403):
                print(f"[BING v105] Chave recusada ou sem permissão: HTTP {r.status_code}")
                return pautas
            if r.status_code == 429:
                print("[BING v105] Limite/rate limit atingido; pausando uso nesta rodada.")
                return pautas
            r.raise_for_status()
            dados = r.json()
            itens = dados.get("value") or []
            print(f"[BING v105] Termo '{termo}': {len(itens)} resultados")
            for it in itens:
                titulo = str(it.get("name") or "").strip()
                link = str(it.get("url") or "").strip()
                if not titulo or not link or link in vistos:
                    continue
                vistos.add(link)
                dt = _normalizar_dt_bing(str(it.get("datePublished") or ""))
                ok, motivo, idade = dentro_da_janela(dt)
                if not ok:
                    continue
                provider = "Bing News"
                prov = it.get("provider") or []
                if isinstance(prov, list) and prov:
                    provider = str(prov[0].get("name") or provider).strip() or provider
                desc = str(it.get("description") or "").strip()
                img = ""
                try:
                    img = (it.get("image") or {}).get("contentUrl") or (it.get("image") or {}).get("thumbnail", {}).get("contentUrl") or ""
                except Exception:
                    img = ""
                pautas.append({
                    "titulo_origem": titulo,
                    "link_origem": link,
                    "fonte_nome": provider,
                    "resumo_origem": desc[:600],
                    "canal_forcado": "",
                    "data_pub_fonte": formatar_br(dt),
                    "data_pub_fonte_br": formatar_br(dt),
                    "data_pub_fonte_original": str(it.get("datePublished") or ""),
                    "data_pub_metodo_v99": "bing_news_datePublished",
                    "_data_pub_ordem": ordenar_iso(dt),
                    "origem_feed": "bing_news_v105",
                    "imagem_url": img,
                    "_uid": _uid(link, titulo),
                    "prioridade": 3 if idade <= 1 else 2 if idade <= 2 else 1,
                })
        except Exception as e:
            print(f"[BING v105] Falha no termo '{termo}': {e}")
        time.sleep(float(os.getenv("URURAU_V105_BING_INTERVALO", "0.7") or "0.7"))

    pautas.sort(key=lambda p: p.get("_data_pub_ordem", ""), reverse=True)
    return pautas
