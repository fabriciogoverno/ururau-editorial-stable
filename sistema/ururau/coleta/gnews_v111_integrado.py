"""
ururau/coleta/gnews_v111_integrado.py

Wrapper operacional da v110 teste para usar o pacote google_news_scraper
como coletor consolidado do Ururau.

A integração é aditiva: se a flag URURAU_V111_GNEWS_INTEGRADO estiver
desligada, o fluxo legado v108-v110 continua disponível. Este módulo não
faz bypass de paywall, login, anti-bot privado ou conteúdo restrito; coleta
apenas resultados e páginas públicas.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import logging
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


_LOG = logging.getLogger("ururau.gnews_v111")
if not _LOG.handlers:
    _LOG.addHandler(logging.StreamHandler())
_LOG.setLevel(logging.INFO)


def _project_root() -> Path:
    """Localiza a raiz do projeto Ururau a partir deste arquivo ou do cwd."""
    candidatos: list[Path] = []
    try:
        here = Path(__file__).resolve()
        candidatos.extend(here.parents)
    except Exception:
        pass
    try:
        cwd = Path.cwd().resolve()
        candidatos.extend([cwd, *cwd.parents])
    except Exception:
        pass

    nomes_chave = (
        "consultas_google_news.json",
        "radar_audiencia_config_v88.json",
        "fontes_rss.json",
        "ururau_monitor.py",
    )
    for base in candidatos:
        try:
            if any((base / n).exists() for n in nomes_chave):
                return base
        except Exception:
            continue
    return Path.cwd()


ROOT_DIR = _project_root()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


try:
    from google_news_scraper.google_news_integrado import GoogleNewsIntegrado
    from google_news_scraper.models import ScraperConfig
    _IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover
    GoogleNewsIntegrado = None  # type: ignore
    ScraperConfig = None  # type: ignore
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


_CANAL_FALLBACK = {
    "alerj": "Política",
    "governo_rj": "Estado RJ",
    "rj_politica": "Política",
    "rj_policia": "Polícia",
    "campos_local": "Cidades",
    "norte_fluminense": "Cidades",
    "porto_do_acu": "Economia",
    "servico_brasil": "Serviço",
    "alto_trafego_brasil": "Brasil",
    "alertas_globais": "Brasil e Mundo",
    "deputados_rj": "Política",
    "pre_candidatos_governo_rj": "Política",
    "transparencia_e_investigacao": "Política",
    "utilidade_publica_rj": "Estado RJ",
}
_REGIAO_FALLBACK = {
    "campos_local": "Norte Fluminense",
    "norte_fluminense": "Norte Fluminense",
    "porto_do_acu": "Norte Fluminense",
    "rj_politica": "Rio de Janeiro",
    "rj_policia": "Rio de Janeiro",
    "governo_rj": "Rio de Janeiro",
    "alerj": "Rio de Janeiro",
    "deputados_rj": "Rio de Janeiro",
    "pre_candidatos_governo_rj": "Rio de Janeiro",
    "servico_brasil": "Nacional",
    "alto_trafego_brasil": "Nacional",
    "alertas_globais": "Internacional",
    "utilidade_publica_rj": "Rio de Janeiro",
    "transparencia_e_investigacao": "Rio de Janeiro",
}
_CIDADE_FALLBACK = {
    "campos_local": "Campos dos Goytacazes",
    "norte_fluminense": "Campos dos Goytacazes",
    "porto_do_acu": "São João da Barra",
    "rj_politica": "Rio de Janeiro",
    "rj_policia": "Rio de Janeiro",
    "governo_rj": "Rio de Janeiro",
    "alerj": "Rio de Janeiro",
    "deputados_rj": "Rio de Janeiro",
    "pre_candidatos_governo_rj": "Rio de Janeiro",
    "utilidade_publica_rj": "Rio de Janeiro",
    "transparencia_e_investigacao": "Rio de Janeiro",
}


def _get_env_int(key: str, default: int) -> int:
    """Lê inteiro do ambiente com fallback seguro."""
    try:
        return int(str(os.environ.get(key, str(default))).strip())
    except Exception:
        return default


def _get_env_float(key: str, default: float) -> float:
    try:
        return float(str(os.environ.get(key, str(default))).strip().replace(",", "."))
    except Exception:
        return default


def _get_env_bool(key: str, default: bool = False) -> bool:
    val = str(os.environ.get(key, "1" if default else "0")).strip().lower()
    return val in {"1", "true", "sim", "yes", "s", "on"}


def _agora_br() -> _dt.datetime:
    if ZoneInfo is not None:
        return _dt.datetime.now(ZoneInfo("America/Sao_Paulo"))
    return _dt.datetime.now()


def _parse_iso(data: Any) -> _dt.datetime | None:
    if isinstance(data, _dt.datetime):
        return data
    texto = str(data or "").strip()
    if not texto:
        return None
    try:
        return _dt.datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except Exception:
        pass
    # fallback para formato brasileiro usado em algumas rotas antigas
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(texto, fmt)
        except Exception:
            continue
    return None


def _formatar_data_br(data: Any) -> str:
    dt = _parse_iso(data)
    if not dt:
        return str(data or "")
    try:
        if dt.tzinfo is not None and ZoneInfo is not None:
            dt = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
        else:
            dt = dt.replace(tzinfo=None)
    except Exception:
        pass
    return dt.strftime("%d/%m/%Y %H:%M")


def _uid(link: str, titulo: str) -> str:
    return hashlib.md5(f"{link}{titulo}".encode("utf-8", errors="ignore")).hexdigest()[:16]


def _dominio(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def _normalizar_texto(texto: str, titulo: str = "") -> str:
    texto = str(texto or "").strip()
    if not texto:
        return ""
    try:
        from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101
        return limpar_texto_artigo_v101(texto, titulo=titulo, max_chars=22000)
    except Exception:
        texto = re.sub(r"\r\n?", "\n", texto)
        texto = re.sub(r"\n{3,}", "\n\n", texto)
        texto = re.sub(r"[ \t]{2,}", " ", texto)
        return texto.strip()[:22000]


def _texto_util_chars(texto: str) -> int:
    try:
        from ururau.coleta.limpeza_texto_v81 import texto_util_chars
        return int(texto_util_chars(texto))
    except Exception:
        return len(str(texto or "").strip())


def _resolve_config(nome: str) -> str:
    """Encontra JSON da raiz do Ururau em múltiplos locais."""
    candidatos = [
        ROOT_DIR / nome,
        Path.cwd() / nome,
        ROOT_DIR / "config" / nome,
        ROOT_DIR / "ururau" / "config" / nome,
        Path(__file__).resolve().parents[2] / nome,
    ]
    for p in candidatos:
        if p.exists():
            return str(p)
    _LOG.warning("[V111][GNEWS] Config não encontrada: %s; usando fallback do pacote", nome)
    return str(ROOT_DIR / nome)


def _build_scraper_config():
    if ScraperConfig is None:
        raise RuntimeError(_IMPORT_ERROR or "google_news_scraper indisponível")
    kwargs = {
        "timeout": _get_env_int("URURAU_V111_GNEWS_TIMEOUT", _get_env_int("URURAU_V109_HTTP_TIMEOUT", 14)),
        "max_retries": _get_env_int("URURAU_V111_GNEWS_RETRIES", _get_env_int("URURAU_V109_HTTP_MAX_RETRIES", 3)),
        "concurrency": min(3, max(1, _get_env_int("URURAU_V111_GNEWS_CONCURRENCY", 3))),
        "min_article_chars": _get_env_int("URURAU_V111_GNEWS_MIN_CHARS_FONTE", 1200),
    }
    # O pacote Kimi v111 usa nomes diferentes da ponte v110. Detecta sem quebrar.
    campos = set(getattr(ScraperConfig, "model_fields", {}).keys())
    if "backoff_factor" in campos:
        kwargs["backoff_factor"] = _get_env_float("URURAU_V111_GNEWS_BACKOFF", _get_env_float("URURAU_V109_HTTP_BACKOFF", 1.7))
    if "max_sleep" in campos:
        kwargs["max_sleep"] = _get_env_float("URURAU_V111_GNEWS_MAX_SLEEP", 12.0)
    if "cooldown_429_seconds" in campos:
        kwargs["cooldown_429_seconds"] = _get_env_int("URURAU_V111_GNEWS_COOLDOWN_429", 180)
    if "rotate_user_agent" in campos:
        kwargs["rotate_user_agent"] = _get_env_bool("URURAU_V111_GNEWS_ROTATE_UA", True)
    if "delay_between_requests" in campos:
        kwargs["delay_between_requests"] = _get_env_float("URURAU_V111_GNEWS_DELAY", 0.4)
    if "delay_per_domain" in campos:
        kwargs["delay_per_domain"] = _get_env_float("URURAU_V111_GNEWS_DELAY_DOMAIN", 0.35)
    return ScraperConfig(**kwargs)


def _novo_integrado():
    if GoogleNewsIntegrado is None:
        raise RuntimeError(_IMPORT_ERROR or "google_news_scraper indisponível")
    return GoogleNewsIntegrado(
        config_path=_resolve_config("radar_audiencia_config_v88.json"),
        aliases_path=_resolve_config("aliases_editoriais.json"),
        consultas_path=_resolve_config("consultas_google_news.json"),
        fontes_path=_resolve_config("fontes_oficiais_prioritarias.json"),
        scraper_config=_build_scraper_config(),
    )


def _inferir_grupo(pauta: Dict[str, Any]) -> str:
    grupo = str(pauta.get("grupo") or pauta.get("grupo_tematico") or "").strip()
    if grupo:
        return grupo
    termo = str(pauta.get("termo_busca") or "").lower()
    if any(x in termo for x in ("campos", "uenf", "iff")):
        return "campos_local"
    if any(x in termo for x in ("porto do açu", "porto acu", "prumo")):
        return "porto_do_acu"
    if any(x in termo for x in ("alerj", "assembleia legislativa", "deputado estadual")):
        return "alerj"
    if any(x in termo for x in ("polícia", "policia", "pmerj", "pcerj", "operação policial")):
        return "rj_policia"
    if any(x in termo for x in ("governo rj", "governo rio", "cláudio castro", "claudio castro")):
        return "governo_rj"
    if any(x in termo for x in ("norte fluminense", "macaé", "macae", "quissamã", "quissama")):
        return "norte_fluminense"
    return ""


def _calcular_prioridade(data_publicacao: Any) -> int:
    dt = _parse_iso(data_publicacao)
    if not dt:
        return 1
    agora = _agora_br()
    try:
        if dt.tzinfo is not None and agora.tzinfo is not None:
            dt = dt.astimezone(agora.tzinfo)
        elif dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
            agora = agora.replace(tzinfo=None)
        elif agora.tzinfo is not None:
            agora = agora.replace(tzinfo=None)
        idade = max(0.0, (agora - dt).total_seconds() / 3600.0)
    except Exception:
        return 1
    if idade <= 1:
        return 3
    if idade <= 2:
        return 2
    return 1


def _adaptar_para_monitor_ururau(pauta: Dict[str, Any]) -> Dict[str, Any]:
    """Adiciona campos legados exigidos por RSS/scoring/workflow sem remover o schema v111."""
    p = dict(pauta or {})
    titulo = str(p.get("titulo") or p.get("titulo_origem") or "").strip()
    url = str(p.get("url") or p.get("link_origem") or "").strip()
    resumo = str(p.get("descricao") or p.get("resumo_origem") or "").strip()
    grupo = _inferir_grupo(p)
    canal = str(p.get("canal_sugerido") or p.get("canal_forcado") or _CANAL_FALLBACK.get(grupo, "")).strip()
    regiao = str(p.get("regiao") or _REGIAO_FALLBACK.get(grupo, "")).strip()
    cidade = str(p.get("cidade") or _CIDADE_FALLBACK.get(grupo, "")).strip()
    dominio = str(p.get("dominio") or _dominio(url)).strip()

    p.setdefault("id", f"gnews_{_uid(url, titulo)}")
    p["titulo"] = titulo
    p["descricao"] = resumo
    p["url"] = url
    p["dominio"] = dominio
    p["canal_sugerido"] = canal
    p["cidade"] = cidade
    p["regiao"] = regiao
    p.setdefault("fonte_tipo", "google_news")
    p.setdefault("coletado_em", _dt.datetime.utcnow().isoformat())
    p.setdefault("status", "pendente")

    p["titulo_origem"] = titulo
    p["link_origem"] = url
    p["resumo_origem"] = resumo[:700]
    p["fonte_nome"] = p.get("fonte_nome") or dominio or "Google News"
    p["canal_forcado"] = canal
    p["data_pub_fonte"] = _formatar_data_br(p.get("data_publicacao"))
    p["data_pub_fonte_br"] = p["data_pub_fonte"]
    p["data_pub_fonte_original"] = p.get("data_publicacao") or ""
    p["data_pub_metodo_v99"] = "google_news_v111"
    p["_data_pub_ordem"] = p.get("data_publicacao") or p.get("coletado_em") or ""
    p["_uid"] = p.get("_uid") or _uid(url, titulo)
    p["prioridade"] = int(p.get("prioridade") or _calcular_prioridade(p.get("data_publicacao")))

    texto = _normalizar_texto(str(p.get("texto_fonte") or ""), titulo=titulo)
    chars = _texto_util_chars(texto)
    p["texto_fonte"] = texto
    p["chars_fonte"] = int(p.get("chars_fonte") or chars)
    if texto:
        p["_fonte_aba_texto"] = texto
        p["fonte_aba_texto"] = texto
        p["leitura_fonte_texto"] = texto
        p["cleaned_source_text"] = texto
        p["raw_source_text"] = texto
        p["original_source_text"] = texto
        p["dossie"] = texto[:14000]
        p["extraction_status"] = "ok" if chars >= _get_env_int("URURAU_V111_GNEWS_MIN_CHARS_FONTE", 1200) else "short_text"
        p["extraction_method"] = p.get("metodo_extracao") or "gnews_v111"
        p["status_fonte_v111"] = p["extraction_status"]
        p["fonte_chars_v111"] = chars

    imagens = p.get("imagens") or []
    imagem = str(p.get("imagem") or (imagens[0] if imagens else "") or "").strip()
    if imagem:
        p["imagem"] = imagem
        p.setdefault("imagem_url", imagem)
        p.setdefault("imagem_status", "url_pendente")
        p.setdefault("imagem_credito", "Reprodução")
    return p


def _filtrar_janela_temporal_local(pautas: List[Dict[str, Any]], horas: int) -> List[Dict[str, Any]]:
    """Filtro temporal local usado nos testes e como defesa se o integrado falhar."""
    agora = _dt.datetime.now(_dt.timezone.utc)
    out: list[dict] = []
    for p in pautas:
        dt = _parse_iso(p.get("data_publicacao"))
        if not dt:
            out.append(p)
            continue
        try:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.timezone.utc)
            if agora - dt <= _dt.timedelta(hours=horas):
                out.append(p)
        except Exception:
            out.append(p)
    return out


def _deduplicar_por_url_local(pautas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    vistos: set[str] = set()
    out: list[dict] = []
    for p in pautas:
        url = str(p.get("url") or p.get("link_origem") or "").strip()
        try:
            u = urlparse(url)
            chave = f"{u.netloc.lower().replace('www.', '')}{u.path.rstrip('/')}"
        except Exception:
            chave = url
        if chave and chave in vistos:
            continue
        if chave:
            vistos.add(chave)
        out.append(p)
    return out


async def coletar_pautas_gnews_v111(
    modo: str = "termos_config",
    termo: str = "",
    grupo: str = "",
    janela_horas: int | None = None,
    max_resultados: int | None = None,
) -> List[Dict[str, Any]]:
    """
    Coleta pautas Google News pelo pacote integrado.

    Modos:
    - termos_config: usa radar_audiencia_config_v88.json
    - termo_livre: usa termo manual
    - grupo: usa consultas_google_news.json por grupo temático
    """
    janela = janela_horas if janela_horas is not None else _get_env_int("URURAU_V111_GNEWS_JANELA_HORAS", 4)
    max_res = max_resultados if max_resultados is not None else _get_env_int("URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO", 3)
    max_termos = _get_env_int("URURAU_V111_GNEWS_MAX_TERMOS_POR_CICLO", 20)
    min_peso = _get_env_int("URURAU_V111_GNEWS_MIN_PESO_TERMO", 0)

    modo = (modo or "termos_config").strip().lower()
    integrado = _novo_integrado()

    _LOG.info("[V111][GNEWS] Iniciando coleta modo=%s janela=%sh max=%s", modo, janela, max_res)
    async with integrado:
        if modo == "termo_livre":
            if not termo:
                _LOG.warning("[V111][GNEWS] termo_livre sem termo; retornando vazio")
                return []
            pautas = await integrado.coletar_por_termo_livre(termo, max_resultados=max_res, janela=janela)
            _LOG.info("[V111][GNEWS] Termo '%s': %s entrada(s)", termo, len(pautas))
        elif modo == "grupo":
            if not grupo:
                _LOG.warning("[V111][GNEWS] modo grupo sem grupo; retornando vazio")
                return []
            pautas = await integrado.coletar_grupo_tematico(grupo, max_por_grupo=max_res, janela=janela)
            _LOG.info("[V111][GNEWS] Grupo '%s': %s entrada(s)", grupo, len(pautas))
        else:
            pautas = await integrado.coletar_por_termos_config(
                max_termos_por_ciclo=max_termos,
                max_resultados_por_termo=max_res,
                janela=janela,
                min_peso_termo=min_peso,
            )
            _LOG.info("[V111][GNEWS] Termos de config: %s entrada(s)", len(pautas))

    pautas = _filtrar_janela_temporal_local([_adaptar_para_monitor_ururau(p) for p in pautas], janela)
    pautas = _deduplicar_por_url_local(pautas)
    pautas.sort(key=lambda p: int(p.get("score") or 0), reverse=True)
    _LOG.info("[V111][GNEWS] Coleta final: %s pauta(s) únicas", len(pautas))
    return pautas


async def extrair_fonte_v111(url: str) -> Dict[str, Any]:
    """
    Extrai texto completo e imagens de uma URL pública.

    Retorna: {texto, autor, data, imagens, metodo, chars, url, suficiente}
    """
    min_chars = _get_env_int("URURAU_V111_GNEWS_MIN_CHARS_FONTE", 1200)
    integrado = _novo_integrado()
    try:
        res = await integrado.extrair_fonte_completa(url, min_chars=min_chars)
    except Exception as exc:
        _LOG.warning("[V111][FONTE] ERRO %s: %s", type(exc).__name__, url)
        return {
            "texto": "",
            "autor": "",
            "data": "",
            "imagens": [],
            "metodo": "erro",
            "chars": 0,
            "url": url,
            "suficiente": False,
            "erro": str(exc),
        }

    texto = _normalizar_texto(str(res.get("texto") or ""), titulo="")
    chars = _texto_util_chars(texto)
    res["texto"] = texto
    res["chars"] = chars
    res["suficiente"] = chars >= min_chars
    metodo = str(res.get("metodo") or "unknown")
    if res["suficiente"]:
        _LOG.info("[V111][FONTE] OK %s chars via %s: %s", chars, metodo, url)
    else:
        _LOG.warning("[V111][FONTE] CURTO %s chars via %s: %s", chars, metodo, url)
    return res


def rodar_async_v111(coro):
    """Executa coroutine tanto fora quanto dentro de event loop já ativo."""
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


def coletar_pautas_gnews_v111_sync(*args, **kwargs) -> List[Dict[str, Any]]:
    """Versão síncrona para o monitor legado."""
    return rodar_async_v111(coletar_pautas_gnews_v111(*args, **kwargs))


def extrair_fonte_v111_sync(url: str) -> Dict[str, Any]:
    """Versão síncrona para hidratação durante o ciclo legado."""
    return rodar_async_v111(extrair_fonte_v111(url))
