"""
Ponte v110 para o pacote Kimi Google News Scraper.

Este módulo integra, no motor real do Ururau, os recursos úteis do projeto
`google_news_scraper` enviado pelo Kimi:
- busca Google News por HTML + RSS;
- rotação de User-Agent, retries e backoff via configuração do pacote;
- deduplicação de links;
- extração estruturada de matéria com trafilatura + readability/BeautifulSoup.

Não quebra paywall, não faz login, não burla autenticação e não tenta acessar
conteúdo restrito. Atua somente sobre páginas públicas.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse, unquote, parse_qs

try:
    from dateutil import parser as _date_parser
except Exception:  # pragma: no cover
    _date_parser = None

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

try:
    from ururau.vendor.google_news_scraper.models import SearchParams, ScraperConfig
    from ururau.vendor.google_news_scraper.scraper import GoogleNewsScraper
    _KIMI_IMPORT_ERROR = ""
except Exception as _e:  # pragma: no cover
    SearchParams = None  # type: ignore
    ScraperConfig = None  # type: ignore
    GoogleNewsScraper = None  # type: ignore
    _KIMI_IMPORT_ERROR = f"{type(_e).__name__}: {_e}"

# ArticleExtractor é importado sob demanda para não pesar a abertura do painel.
ArticleExtractor = None  # type: ignore
_KIMI_EXTRACTOR_IMPORT_ERROR = ""

try:
    from ururau.coleta.datas_v99 import (
        dentro_da_janela,
        formatar_br,
        janela_publicacao_horas,
        ordenar_iso,
    )
except Exception:  # pragma: no cover
    def janela_publicacao_horas(padrao: int = 4) -> int:
        return padrao
    def dentro_da_janela(dt, agora=None, janela=None, janela_horas=None):
        if dt is None:
            return False, "sem_data_publicacao", 999999.0
        agora = agora or _dt.datetime.now()
        limite = janela if janela is not None else (janela_horas if janela_horas is not None else 4)
        idade = (agora - dt).total_seconds() / 3600
        return 0 <= idade <= limite, "ok", idade
    def formatar_br(dt):
        return dt.strftime("%d/%m/%Y %H:%M") if dt else ""
    def ordenar_iso(dt):
        return dt.isoformat() if dt else ""

try:
    from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101
except Exception:  # pragma: no cover
    def limpar_texto_artigo_v101(texto: str, titulo: str = "", max_chars: int = 22000) -> str:
        return re.sub(r"\s+", " ", texto or "").strip()[:max_chars]

try:
    from ururau.coleta.limpeza_texto_v81 import texto_util_chars
except Exception:  # pragma: no cover
    def texto_util_chars(texto: str) -> int:
        return len(str(texto or "").strip())


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


def _agora_br_naive() -> _dt.datetime:
    if ZoneInfo is not None:
        return _dt.datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    return _dt.datetime.now()


def _to_br_naive(dt: _dt.datetime | None) -> _dt.datetime | None:
    if dt is None:
        return None
    try:
        if dt.tzinfo is not None and ZoneInfo is not None:
            return dt.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        return dt.replace(tzinfo=None)
    except Exception:
        return None



def _dentro_da_janela_compat_v122(dt, agora=None, janela=4):
    """
    Compatibilidade v122:
    as versões do projeto alternaram entre dentro_da_janela(..., janela_horas=)
    e dentro_da_janela(..., janela=). Esta função tenta todas as assinaturas
    sem descartar pauta válida por TypeError.
    """
    try:
        return dentro_da_janela(dt, agora, janela_horas=janela)
    except TypeError:
        try:
            return dentro_da_janela(dt, agora, janela=janela)
        except TypeError:
            try:
                return dentro_da_janela(dt, agora)
            except TypeError:
                return dentro_da_janela(dt)


def _parse_data_google(texto: str) -> _dt.datetime | None:
    texto = str(texto or "").strip()
    if not texto:
        return None
    # RSS costuma vir RFC 2822; HTML pode vir relativo em inglês.
    try:
        from ururau.vendor.google_news_scraper.utils import parse_relative_time
        rel = parse_relative_time(texto)
        if rel:
            return _to_br_naive(rel)
    except Exception:
        pass
    if _date_parser is not None:
        try:
            return _to_br_naive(_date_parser.parse(texto))
        except Exception:
            pass
    for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"]:
        try:
            return _to_br_naive(_dt.datetime.strptime(texto, fmt))
        except Exception:
            continue
    return None


def _uid(link: str, titulo: str) -> str:
    return hashlib.md5(f"{link}{titulo}".encode("utf-8", errors="ignore")).hexdigest()[:16]


def _normalizar_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return ""
    try:
        from ururau.vendor.google_news_scraper.utils import normalize_url
        return normalize_url(url)
    except Exception:
        return url.split("#", 1)[0]


def _dominio(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def _titulo_fonte(titulo: str, fonte: str = "") -> tuple[str, str]:
    titulo = " ".join(str(titulo or "").split()).strip()
    fonte = " ".join(str(fonte or "").split()).strip()
    if not fonte and " - " in titulo:
        partes = titulo.rsplit(" - ", 1)
        if len(partes) == 2 and partes[1].strip():
            return partes[0].strip(), partes[1].strip()
    return titulo, fonte or "Google News"


def _resolver_google_news_publico(link: str) -> str:
    """Resolve link Google News usando o resolvedor já estabilizado da v109."""
    link = str(link or "").strip()
    if not link:
        return ""
    if "news.google." not in link and "news.url.google." not in link:
        return link
    try:
        qs = parse_qs(urlparse(link).query)
        for key in ("url", "u", "q"):
            if qs.get(key):
                val = unquote(qs[key][0])
                if val.startswith("http") and "google." not in _dominio(val):
                    return val
    except Exception:
        pass
    try:
        from ururau.coleta.google_news_scraper_v108 import _resolver_link_google_news
        return _resolver_link_google_news(link) or link
    except Exception:
        return link


def _rodar_async(coro):
    """Executa coroutine também em ambientes que já tenham event loop ativo."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    caixa: dict[str, Any] = {}

    def _runner():
        try:
            caixa["result"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover
            caixa["error"] = exc

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()
    if "error" in caixa:
        raise caixa["error"]
    return caixa.get("result")


def _config_kimi() -> Any:
    if ScraperConfig is None:
        return None
    return ScraperConfig(
        timeout=_env_int("URURAU_V110_KIMI_TIMEOUT", _env_int("URURAU_V109_HTTP_TIMEOUT", 14)),
        max_retries=_env_int("URURAU_V110_KIMI_RETRIES", _env_int("URURAU_V109_HTTP_MAX_RETRIES", 3)),
        retry_backoff=_env_float("URURAU_V110_KIMI_BACKOFF", _env_float("URURAU_V109_HTTP_BACKOFF", 1.7)),
        concurrency=_env_int("URURAU_V110_KIMI_CONCURRENCY", 4),
        request_delay=_env_float("URURAU_V110_KIMI_DELAY", 0.4),
        user_agent_rotation=_env_bool("URURAU_V109_HTTP_ROTATE_UA", True),
        proxy=os.getenv("URURAU_V110_KIMI_PROXY") or None,
    )


async def _buscar_links_kimi(termo: str, max_resultados: int, janela: int) -> list[Any]:
    if GoogleNewsScraper is None or SearchParams is None:
        raise RuntimeError(_KIMI_IMPORT_ERROR or "google_news_scraper indisponivel")
    cfg = _config_kimi()
    scraper = GoogleNewsScraper(cfg)
    # O operador when mantém a busca fresca; o filtro final por data permanece obrigatório.
    query = f"{termo} when:{janela}h"
    params = SearchParams(
        query=query,
        max_results=max(1, min(100, max_resultados)),
        country="BR",
        language="pt",
        use_proxy=bool(os.getenv("URURAU_V110_KIMI_PROXY")),
        proxy_url=os.getenv("URURAU_V110_KIMI_PROXY") or None,
    )
    return await scraper.search(params)


def coletar_google_news_kimi_v110(termos: Iterable[dict[str, Any]] | Iterable[str] | None = None) -> list[dict]:
    """Coleta Google News com o scraper Kimi, retornando pautas no formato Ururau."""
    if not _env_bool("URURAU_V110_KIMI_GNEWS_HTML", True):
        return []
    if GoogleNewsScraper is None:
        print(f"[KIMI v110] pacote indisponível: {_KIMI_IMPORT_ERROR}")
        return []

    if termos is None:
        try:
            from ururau.coleta.google_news_scraper_v108 import _termos_priorizados
            termos = _termos_priorizados()
        except Exception:
            termos = ["Rio de Janeiro", "Campos dos Goytacazes", "Norte Fluminense", "ALERJ"]

    itens: list[dict[str, Any]] = []
    for t in termos or []:
        if isinstance(t, dict):
            termo = str(t.get("termo") or "").strip()
            if termo:
                itens.append(dict(t, termo=termo))
        else:
            termo = str(t or "").strip()
            if termo:
                itens.append({"termo": termo, "peso": 18, "canal": ""})

    if not itens:
        return []

    janela = _env_int("URURAU_V108_GNEWS_JANELA_HORAS", janela_publicacao_horas(4))
    max_por_termo = _env_int("URURAU_V110_KIMI_MAX_RESULTADOS_POR_TERMO", _env_int("URURAU_V108_GNEWS_MAX_RESULTADOS_POR_TERMO", 3))
    max_busca = max(max_por_termo * 3, max_por_termo)
    permitir_sem_data = _env_bool("URURAU_V110_KIMI_PERMITIR_SEM_DATA", False)
    agora = _agora_br_naive()

    saida: list[dict] = []
    vistos: set[str] = set()
    print(f"[KIMI v110] Google News HTML+RSS: {len(itens)} termo(s), janela={janela}h, máx={max_por_termo}/termo")

    for item in itens:
        termo = item.get("termo", "")
        try:
            links = _rodar_async(_buscar_links_kimi(str(termo), max_busca, janela)) or []
            print(f"[KIMI v110] {termo}: {len(links)} link(s) brutos")
        except Exception as exc:
            print(f"[KIMI v110] falha no termo '{termo}': {type(exc).__name__}: {exc}")
            continue

        usados_termo = 0
        for link in links:
            if usados_termo >= max_por_termo:
                break
            try:
                titulo_raw = str(getattr(link, "title", "") or "").strip()
                url_raw = str(getattr(link, "url", "") or "").strip()
                fonte_raw = str(getattr(link, "source", "") or "").strip()
                snippet = str(getattr(link, "snippet", "") or "").strip()
                pub_txt = str(getattr(link, "published_time_text", "") or "").strip()
                if not titulo_raw or not url_raw:
                    continue
                titulo, fonte_nome = _titulo_fonte(titulo_raw, fonte_raw)
                dt = _parse_data_google(pub_txt)
                if dt is None and not permitir_sem_data:
                    continue
                if dt is not None:
                    ok, motivo, idade = _dentro_da_janela_compat_v122(dt, agora, janela=janela)
                    if not ok:
                        continue
                else:
                    motivo, idade = "sem_data_permitida", 999.0
                link_real = _resolver_google_news_publico(url_raw)
                chave = _normalizar_url(link_real or url_raw)
                if not chave or chave in vistos:
                    continue
                vistos.add(chave)
                if fonte_nome == "Google News" and _dominio(link_real):
                    fonte_nome = _dominio(link_real)
                pauta = {
                    "titulo_origem": titulo,
                    "link_origem": link_real or url_raw,
                    "link_google_news": url_raw,
                    "fonte_nome": fonte_nome,
                    "resumo_origem": snippet[:700],
                    "canal_forcado": str(item.get("canal") or item.get("canal_forcado") or ""),
                    "origem_feed": "google_news_kimi_v110",
                    "termo_busca_v108": str(termo),
                    "termo_busca_v110": str(termo),
                    "peso_termo_v108": int(item.get("peso") or 18),
                    "data_pub_fonte": formatar_br(dt),
                    "data_pub_fonte_br": formatar_br(dt),
                    "data_pub_fonte_original": pub_txt,
                    "data_pub_metodo_v99": "kimi_v110:google_html_rss",
                    "_data_pub_ordem": ordenar_iso(dt),
                    "_uid": _uid(chave, titulo),
                    "prioridade": 3 if idade <= 1 else 2 if idade <= 2 else 1,
                }
                saida.append(pauta)
                usados_termo += 1
            except Exception as exc:
                print(f"[KIMI v110] item ignorado: {type(exc).__name__}: {exc}")
                continue

    saida.sort(key=lambda p: p.get("_data_pub_ordem", ""), reverse=True)
    print(f"[KIMI v110] {len(saida)} pauta(s) candidatas após janela/dedup")
    return saida


@dataclass
class ResultadoKimiV110:
    ok: bool = False
    texto: str = ""
    titulo: str = ""
    descricao: str = ""
    autor: str = ""
    data_publicacao: str = ""
    imagem: str = ""
    imagens: list[str] | None = None
    url_final: str = ""
    dominio: str = ""
    idioma: str = ""
    metodo: str = "v110_kimi_failed"
    erro: str = ""
    util_chars: int = 0


async def _extrair_artigo_kimi_async(url: str) -> Any:
    try:
        from ururau.vendor.google_news_scraper.extractor import ArticleExtractor as _ArticleExtractor
    except Exception as exc:
        raise RuntimeError(f"ArticleExtractor indisponivel: {type(exc).__name__}: {exc}")
    extractor = _ArticleExtractor(_config_kimi())
    return await extractor.extract_article(url)


def extrair_artigo_kimi_v110(url: str, titulo: str = "") -> ResultadoKimiV110:
    """Extrai matéria pública com ArticleExtractor do Kimi e devolve formato simples."""
    if not _env_bool("URURAU_V110_USAR_KIMI_EXTRACTOR", True):
        return ResultadoKimiV110(erro="kimi_extractor_desativado")
    url = _resolver_google_news_publico(url)
    try:
        article = _rodar_async(_extrair_artigo_kimi_async(url))
        if not article:
            return ResultadoKimiV110(url_final=url, erro="sem_artigo_extraido")
        texto_raw = str(getattr(article, "article_text", "") or "")
        titulo_art = str(getattr(article, "title", "") or titulo or "")
        texto = limpar_texto_artigo_v101(texto_raw, titulo=titulo_art, max_chars=22000).strip()
        util = texto_util_chars(texto)
        min_chars = _env_int("URURAU_V110_KIMI_MIN_CHARS", _env_int("URURAU_V104_MIN_CHARS_ARTIGO", _env_int("URURAU_MIN_CHARS_TEXTO_FONTE", 900)))
        images = list(getattr(article, "images", []) or [])
        published = getattr(article, "published_date", None)
        if published:
            try:
                published_s = published.isoformat()
            except Exception:
                published_s = str(published)
        else:
            published_s = ""
        return ResultadoKimiV110(
            ok=util >= min_chars,
            texto=texto[:18000],
            titulo=titulo_art,
            descricao=str(getattr(article, "description", "") or ""),
            autor=str(getattr(article, "author", "") or ""),
            data_publicacao=published_s,
            imagem=str(getattr(article, "image", "") or (images[0] if images else "") or ""),
            imagens=images,
            url_final=str(getattr(article, "url", "") or url),
            dominio=str(getattr(article, "domain", "") or _dominio(url)),
            idioma=str(getattr(article, "language", "") or ""),
            metodo="v110_kimi_article_extractor",
            util_chars=util,
            erro="" if util >= min_chars else f"texto_insuficiente:{util}/{min_chars}",
        )
    except Exception as exc:
        return ResultadoKimiV110(url_final=url, erro=f"{type(exc).__name__}: {exc}", metodo="v110_kimi_error")


def mesclar_sem_duplicar(pautas_base: list[dict], pautas_extra: list[dict]) -> list[dict]:
    vistos = set()
    out: list[dict] = []
    for p in list(pautas_base or []) + list(pautas_extra or []):
        link = _normalizar_url(str(p.get("link_origem") or p.get("link_google_news") or ""))
        titulo = re.sub(r"\W+", "", str(p.get("titulo_origem") or "").lower())[:180]
        chave = link or titulo
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        out.append(p)
    out.sort(key=lambda p: p.get("_data_pub_ordem", ""), reverse=True)
    return out


__all__ = [
    "ResultadoKimiV110",
    "coletar_google_news_kimi_v110",
    "extrair_artigo_kimi_v110",
    "mesclar_sem_duplicar",
]
