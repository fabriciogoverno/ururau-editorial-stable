"""
Google News por Termos v109.

Usa os termos da aba Config > Termos para buscar notícias no Google News dentro
da janela editorial (4h por padrão). É uma fonte opcional e controlada para
complementar RSS, não substitui a fila principal.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re
import time
from typing import Any
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

import feedparser

try:
    from ururau.coleta.http_fetch_v109 import fetch_rss_v109, fetch_text_v109
except Exception:
    fetch_rss_v109 = None
    fetch_text_v109 = None

from ururau.coleta.datas_v99 import (
    dentro_da_janela,
    formatar_br,
    janela_publicacao_horas,
    normalizar_data_publicacao,
    ordenar_iso,
)

try:
    from ururau.coleta.termos_config_v98 import carregar_termos
except Exception:
    def carregar_termos():
        return []

try:
    from ururau.coleta.rss import _aplicar_preconteudo_rss_v106, _limpar_html
except Exception:
    def _limpar_html(t: str) -> str:
        return re.sub(r"<[^>]+>", " ", str(t or "")).strip()
    def _aplicar_preconteudo_rss_v106(pauta: dict, entry: dict, titulo: str) -> dict:
        return pauta


def _env_bool(nome: str, padrao: bool = False) -> bool:
    return str(os.getenv(nome, "1" if padrao else "0")).strip().lower() in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _uid(link: str, titulo: str) -> str:
    return hashlib.md5(f"{link}{titulo}".encode("utf-8", errors="ignore")).hexdigest()[:16]


def _termos_priorizados() -> list[dict[str, Any]]:
    min_peso = _env_int("URURAU_V108_GNEWS_MIN_PESO_TERMO", 18)
    max_termos = _env_int("URURAU_V108_GNEWS_MAX_TERMOS_POR_CICLO", 20)
    itens = []
    vistos = set()
    for t in carregar_termos():
        if not t.get("ativo", True) or not t.get("buscar", True):
            continue
        termo = str(t.get("termo") or "").strip()
        if not termo:
            continue
        try:
            peso = int(t.get("peso") or 18)
        except Exception:
            peso = 18
        if peso < min_peso:
            continue
        k = termo.lower()
        if k in vistos:
            continue
        vistos.add(k)
        itens.append({**t, "peso": peso, "termo": termo})
    itens.sort(key=lambda x: int(x.get("peso") or 0), reverse=True)
    return itens[:max_termos]


def _data_campos(entry: dict) -> tuple[_dt.datetime | None, dict[str, str]]:
    dt, raw, metodo = normalizar_data_publicacao(entry)
    return dt, {
        "data_pub_fonte": formatar_br(dt),
        "data_pub_fonte_br": formatar_br(dt),
        "data_pub_fonte_original": raw,
        "data_pub_metodo_v99": f"gnews_v108:{metodo}",
        "_data_pub_ordem": ordenar_iso(dt),
    }


def _extrair_fonte_do_titulo(titulo: str) -> tuple[str, str]:
    fonte = "Google News"
    t = str(titulo or "").strip()
    if " - " in t:
        partes = t.rsplit(" - ", 1)
        if len(partes) == 2 and partes[1].strip():
            return partes[0].strip(), partes[1].strip()
    return t, fonte


def _resolver_link_google_news(link: str) -> str:
    """Tenta resolver o link real público do Google News sem depender de login."""
    link = str(link or "").strip()
    if not link:
        return ""
    if "news.google." not in link and "news.url.google." not in link:
        return link
    # Alguns links carregam URL real como parâmetro.
    try:
        qs = parse_qs(urlparse(link).query)
        for key in ("url", "u", "q"):
            if qs.get(key):
                u = unquote(qs[key][0])
                if u.startswith("http") and "google." not in urlparse(u).netloc.lower():
                    return u
    except Exception:
        pass
    if not _env_bool("URURAU_V108_RESOLVER_GNEWS_HTTP", True):
        return link
    try:
        if fetch_text_v109 is not None and str(os.getenv("URURAU_V109_HTTP_FETCH", "1")).lower() not in {"0", "false", "nao", "não"}:
            fr = fetch_text_v109(
                link,
                timeout=_env_int("URURAU_V108_GNEWS_RESOLVE_TIMEOUT", 8),
                max_retries=_env_int("URURAU_V109_GNEWS_RESOLVE_RETRIES", _env_int("URURAU_V109_HTTP_MAX_RETRIES", 3)),
                accept="html",
                referer="https://news.google.com/",
            )
            if fr.ok:
                final = str(fr.url_final or link)
                if final and final.startswith("http") and "news.google." not in final:
                    return final
                # fallback: procurar links externos na página
                m = re.search(r'https?://(?!news\.google|www\.google|accounts\.google)[^"\'<>\\]+', fr.text or "")
                if m:
                    cand = m.group(0).replace("\\u003d", "=").replace("\\u0026", "&")
                    return cand
            else:
                print(f"[GNEWS v109] resolver falhou/cooldown: {fr.erro}")
        else:
            import requests
            h = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            }
            r = requests.get(link, headers=h, timeout=_env_int("URURAU_V108_GNEWS_RESOLVE_TIMEOUT", 8), allow_redirects=True)
            final = str(r.url or link)
            if final and final.startswith("http") and "news.google." not in final:
                return final
            m = re.search(r'https?://(?!news\.google|www\.google|accounts\.google)[^"\'<>\\]+', r.text or "")
            if m:
                cand = m.group(0).replace("\\u003d", "=").replace("\\u0026", "&")
                return cand
    except Exception as e:
        print(f"[GNEWS v109] resolver exceção: {e}")
    return link


def coletar_google_news_termos_v108() -> list[dict]:
    if not _env_bool("URURAU_V108_GNEWS_TERMOS", True):
        print("[GNEWS v109] desligado. Ative URURAU_V108_GNEWS_TERMOS=1.")
        return []
    janela = _env_int("URURAU_V108_GNEWS_JANELA_HORAS", janela_publicacao_horas(4))
    max_por_termo = _env_int("URURAU_V108_GNEWS_MAX_RESULTADOS_POR_TERMO", 3)
    delay = float(os.getenv("URURAU_V108_GNEWS_DELAY_TERMO", "0.7") or "0.7")
    termos = _termos_priorizados()
    if not termos:
        print("[GNEWS v109] nenhum termo ativo com Buscar=1 e peso mínimo.")
        return []
    from zoneinfo import ZoneInfo
    agora = _dt.datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    pautas: list[dict] = []
    vistos_links = set()
    print(f"[GNEWS v109] buscando {len(termos)} termo(s), janela={janela}h, máx={max_por_termo}/termo")
    for item in termos:
        termo = item["termo"]
        # when:4h ajuda o Google News; o filtro final por data continua obrigatório.
        query = quote_plus(f'{termo} when:{janela}h')
        url_feed = f"https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        try:
            if fetch_rss_v109 is not None and str(os.getenv("URURAU_V109_HTTP_FETCH", "1")).lower() not in {"0", "false", "nao", "não"}:
                frss = fetch_rss_v109(
                    url_feed,
                    timeout=_env_int("URURAU_V109_GNEWS_RSS_TIMEOUT", 12),
                    max_retries=_env_int("URURAU_V109_GNEWS_RSS_RETRIES", _env_int("URURAU_V109_HTTP_MAX_RETRIES", 3)),
                    referer="https://news.google.com/",
                )
                if not frss.ok:
                    print(f"[GNEWS v109] {termo}: falha RSS ({frss.erro})")
                    continue
                feed = feedparser.parse(frss.text)
            else:
                feed = feedparser.parse(url_feed)
            entradas = feed.get("entries", []) or []
            print(f"[GNEWS v109] {termo}: {len(entradas)} entrada(s)")
            count = 0
            for entry in entradas[:max(max_por_termo * 3, max_por_termo)]:
                if count >= max_por_termo:
                    break
                titulo_raw = (entry.get("title") or "").strip()
                link_gnews = (entry.get("link") or "").strip()
                if not titulo_raw or not link_gnews:
                    continue
                titulo, fonte_nome = _extrair_fonte_do_titulo(titulo_raw)
                dt, campos_data = _data_campos(entry)
                ok, motivo, idade = (False, "sem_data_publicacao", 999999.0) if dt is None else ((0 <= (agora - dt).total_seconds()/3600 <= janela), "ok", (agora - dt).total_seconds()/3600)
                if not ok:
                    continue
                link_real = _resolver_link_google_news(link_gnews)
                link_chave = link_real or link_gnews
                if link_chave in vistos_links:
                    continue
                vistos_links.add(link_chave)
                resumo = _limpar_html(entry.get("summary") or entry.get("description") or "")
                pauta = {
                    "titulo_origem": titulo,
                    "link_origem": link_real or link_gnews,
                    "link_google_news": link_gnews,
                    "fonte_nome": fonte_nome,
                    "resumo_origem": resumo[:600],
                    "canal_forcado": str(item.get("canal") or ""),
                    "origem_feed": "google_news_termos_v108",
                    "termo_busca_v108": termo,
                    "peso_termo_v108": int(item.get("peso") or 18),
                    "prioridade": 3 if idade <= 1 else 2 if idade <= 2 else 1,
                    **campos_data,
                    "_uid": _uid(link_chave, titulo),
                }
                pauta = _aplicar_preconteudo_rss_v106(pauta, entry, titulo)
                pautas.append(pauta)
                count += 1
        except Exception as e:
            print(f"[GNEWS v109] falha em '{termo}': {e}")
        time.sleep(delay)
    # v110: incorpora a busca HTML+RSS do pacote Kimi como camada complementar.
    # Mantém a coleta RSS da v109 e só acrescenta links novos/resolvidos.
    if _env_bool("URURAU_V110_KIMI_GNEWS_HTML", True):
        try:
            from ururau.coleta.kimi_bridge_v110 import coletar_google_news_kimi_v110, mesclar_sem_duplicar
            pautas_kimi = coletar_google_news_kimi_v110(termos)
            if pautas_kimi:
                antes = len(pautas)
                pautas = mesclar_sem_duplicar(pautas, pautas_kimi)
                print(f"[KIMI v110] Google News complementar adicionou {max(0, len(pautas)-antes)} pauta(s) nova(s)")
        except Exception as e:
            print(f"[KIMI v110] complemento ignorado por falha: {e}")

    pautas.sort(key=lambda p: p.get("_data_pub_ordem", ""), reverse=True)
    print(f"[GNEWS v110] {len(pautas)} pauta(s) candidatas após janela/dedup local")
    return pautas


__all__ = ["coletar_google_news_termos_v108"]
