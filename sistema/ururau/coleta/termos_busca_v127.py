from __future__ import annotations

import datetime as _dt
import hashlib
import os
import re
import time
import calendar
from urllib.parse import quote_plus

try:
    import feedparser
except Exception:
    feedparser = None

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

try:
    from ururau.coleta.http_fetch_v109 import fetch_rss_v109
except Exception:
    fetch_rss_v109 = None

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

LAST_DIAGNOSTICO_TERMOS_V128 = {}

try:
    from ururau.coleta.google_news_scraper_v108 import _resolver_link_google_news, _extrair_fonte_do_titulo
except Exception:
    def _resolver_link_google_news(link: str) -> str:
        return link
    def _extrair_fonte_do_titulo(titulo_raw: str) -> tuple[str, str]:
        t = str(titulo_raw or "").strip()
        if " - " in t:
            a, b = t.rsplit(" - ", 1)
            return a.strip(), b.strip()
        return t, "Google News"

def _env_bool(nome: str, padrao: bool = False) -> bool:
    return str(os.getenv(nome, "1" if padrao else "0")).strip().lower() in {"1", "true", "sim", "yes", "s", "on"}

def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao

def _uid(link: str, titulo: str) -> str:
    return hashlib.sha1((str(link) + "|" + str(titulo)).encode("utf-8", errors="ignore")).hexdigest()[:16]

def _normalizar_dt_entry(entry) -> tuple[_dt.datetime | None, dict[str, str]]:
    dt = None
    raw = ""
    for k in ("published", "updated", "created"):
        if entry.get(k):
            raw = str(entry.get(k) or "")
            break

    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            ts = calendar.timegm(parsed)
            dt_utc = _dt.datetime.fromtimestamp(ts, _dt.timezone.utc)
            if ZoneInfo is not None:
                dt_br = dt_utc.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
            else:
                dt_br = dt_utc.replace(tzinfo=None)
            dt = dt_br
        except Exception:
            dt = None

    if dt is None and raw:
        # tenta formatos ISO/RFC simples
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                dtx = _dt.datetime.strptime(raw, fmt)
                if dtx.tzinfo:
                    if ZoneInfo is not None:
                        dtx = dtx.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
                    else:
                        dtx = dtx.replace(tzinfo=None)
                dt = dtx
                break
            except Exception:
                pass

    br = dt.strftime("%d/%m/%Y %H:%M") if dt else ""
    iso = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""
    return dt, {
        "data_pub_fonte": br,
        "data_pub_fonte_br": br,
        "data_publicacao": br,
        "publicado_em": br,
        "data_pub_fonte_original": raw,
        "_data_pub_ordem": iso,
    }

def _termos_ativos_v127() -> list[dict]:
    max_termos = _env_int("URURAU_V127_TERMOS_MAX_TERMOS", _env_int("URURAU_V108_GNEWS_MAX_TERMOS_POR_CICLO", 40))
    termos = []
    vistos = set()
    for item in carregar_termos():
        if not item.get("ativo", True) or not item.get("buscar", True):
            continue
        termo = str(item.get("termo") or "").strip()
        if not termo:
            continue
        k = " ".join(termo.lower().split())
        if k in vistos:
            continue
        vistos.add(k)
        termos.append({**item, "termo": termo})
    return termos[:max_termos]

def obter_diagnostico_termos_v128() -> dict:
    try:
        import copy
        return copy.deepcopy(LAST_DIAGNOSTICO_TERMOS_V128 or {})
    except Exception:
        return dict(LAST_DIAGNOSTICO_TERMOS_V128 or {})


def coletar_busca_termos_v127() -> list[dict]:
    """
    Busca explícita por termos cadastrados em Config > Termos.
    Usa Google News RSS oficial, janela padrão de 24h e envia candidatos para a fila.

    v128: registra termo, URL Google News, resultados e descartes sem mudar a coleta.
    """
    global LAST_DIAGNOSTICO_TERMOS_V128
    if not _env_bool("URURAU_V127_BUSCA_TERMOS_ATIVA", True):
        print("[TERMOS v127] desligado: URURAU_V127_BUSCA_TERMOS_ATIVA=0")
        return []
    if feedparser is None:
        print("[TERMOS v127] feedparser indisponível")
        return []

    janela = _env_int("URURAU_V127_TERMOS_JANELA_HORAS", 24)
    max_por_termo = _env_int("URURAU_V127_TERMOS_MAX_POR_TERMO", _env_int("URURAU_V108_GNEWS_MAX_RESULTADOS_POR_TERMO", 4))
    delay = float(os.getenv("URURAU_V127_TERMOS_DELAY", os.getenv("URURAU_V108_GNEWS_DELAY_TERMO", "0.5")) or "0.5")
    termos = _termos_ativos_v127()
    LAST_DIAGNOSTICO_TERMOS_V128 = {
        "janela_horas": janela,
        "max_por_termo": max_por_termo,
        "total_termos": len(termos),
        "termos": [],
        "total_resultados_brutos": 0,
        "total_candidatos": 0,
    }
    print(f"[TERMOS v127] buscando {len(termos)} termo(s), janela={janela}h, max={max_por_termo}/termo")
    if not termos:
        print("[TERMOS v127] nenhum termo ativo na aba Config > Termos")
        return []

    agora = _dt.datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None) if ZoneInfo else _dt.datetime.now()
    pautas = []
    vistos = set()

    for item in termos:
        termo = item["termo"]
        query = quote_plus(f'"{termo}" when:{janela}h')
        url_feed = f"https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        diag_item_v128 = {
            "termo": termo,
            "url_google_news_rss": url_feed,
            "resultados_brutos": 0,
            "candidatos_gerados": 0,
            "descartes": {
                "sem_titulo_ou_link": 0,
                "sem_data_publicacao": 0,
                "fora_janela": 0,
                "duplicado_no_ciclo": 0,
                "erro_rss": 0,
            },
            "erro": "",
        }
        LAST_DIAGNOSTICO_TERMOS_V128["termos"].append(diag_item_v128)
        try:
            if fetch_rss_v109 is not None and str(os.getenv("URURAU_V109_HTTP_FETCH", "1")).lower() not in {"0", "false", "nao", "não"}:
                frss = fetch_rss_v109(
                    url_feed,
                    timeout=_env_int("URURAU_V127_TERMOS_RSS_TIMEOUT", 12),
                    max_retries=_env_int("URURAU_V127_TERMOS_RSS_RETRIES", 2),
                    referer="https://news.google.com/",
                )
                if not getattr(frss, "ok", False):
                    diag_item_v128["descartes"]["erro_rss"] += 1
                    diag_item_v128["erro"] = str(getattr(frss, "erro", ""))
                    print(f"[TERMOS v127] {termo}: falha RSS ({getattr(frss, 'erro', '')})")
                    continue
                feed = feedparser.parse(getattr(frss, "text", ""))
            else:
                # V200_3: feedparser.parse(url) faz fetch SEM timeout e pode
                # travar o ciclo. Sem o HTTP resiliente, pula o termo.
                print(f"[TERMOS v127] {termo}: HTTP resiliente desativado — termo pulado (evita trava)")
                continue

            entradas = feed.get("entries", []) or []
            diag_item_v128["resultados_brutos"] = len(entradas)
            LAST_DIAGNOSTICO_TERMOS_V128["total_resultados_brutos"] += len(entradas)
            print(f"[TERMOS v127] {termo}: {len(entradas)} entrada(s)")
            count = 0
            for entry in entradas[:max(max_por_termo * 4, max_por_termo)]:
                if count >= max_por_termo:
                    break
                titulo_raw = (entry.get("title") or "").strip()
                link_gnews = (entry.get("link") or "").strip()
                if not titulo_raw or not link_gnews:
                    diag_item_v128["descartes"]["sem_titulo_ou_link"] += 1
                    continue

                titulo, fonte_nome = _extrair_fonte_do_titulo(titulo_raw)
                dt, campos_data = _normalizar_dt_entry(entry)
                if dt is None:
                    diag_item_v128["descartes"]["sem_data_publicacao"] += 1
                    continue
                idade = (agora - dt).total_seconds() / 3600
                if idade < 0 or idade > janela:
                    diag_item_v128["descartes"]["fora_janela"] += 1
                    continue

                link_real = _resolver_link_google_news(link_gnews) or link_gnews
                chave = (link_real or link_gnews).lower().rstrip("/")
                if chave in vistos:
                    diag_item_v128["descartes"]["duplicado_no_ciclo"] += 1
                    continue
                vistos.add(chave)

                resumo = _limpar_html(entry.get("summary") or entry.get("description") or "")
                pauta = {
                    "titulo_origem": titulo,
                    "titulo": titulo,
                    "link_origem": link_real,
                    "url": link_real,
                    "link": link_real,
                    "link_google_news": link_gnews,
                    "fonte_nome": fonte_nome or "Google News",
                    "fonte": fonte_nome or "Google News",
                    "nome_fonte": fonte_nome or "Google News",
                    "resumo_origem": resumo[:700],
                    "canal_forcado": str(item.get("canal") or ""),
                    "origem_feed": "busca_termos_v127",
                    "origem": f"Busca por termo: {termo}",
                    "termo_busca_v127": termo,
                    "peso_termo_v127": int(item.get("peso") or 18),
                    "prioridade": 4 if idade <= 1 else 3 if idade <= 6 else 2,
                    "score_editorial": 100,
                    "score": 120,
                    **campos_data,
                    "_uid": _uid(chave, titulo),
                    "uid": _uid(chave, titulo),
                }
                pauta = _aplicar_preconteudo_rss_v106(pauta, entry, titulo)
                pautas.append(pauta)
                count += 1
                diag_item_v128["candidatos_gerados"] += 1
                LAST_DIAGNOSTICO_TERMOS_V128["total_candidatos"] += 1
        except Exception as e:
            diag_item_v128["erro"] = f"{type(e).__name__}: {e}"
            print(f"[TERMOS v127] falha em '{termo}': {type(e).__name__}: {e}")
        time.sleep(delay)

    pautas.sort(key=lambda p: p.get("_data_pub_ordem", ""), reverse=True)
    print(f"[TERMOS v127] {len(pautas)} pauta(s) candidatas por termos")
    return pautas

__all__ = ["coletar_busca_termos_v127", "obter_diagnostico_termos_v128"]
