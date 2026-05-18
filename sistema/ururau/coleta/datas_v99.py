"""
datas_v100.py/v99 - normalizacao unica de datas de publicacao de fontes.
"""
from __future__ import annotations

import datetime as _dt
import os
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

TZ_BR = ZoneInfo("America/Sao_Paulo")
TZ_UTC = ZoneInfo("UTC")


def janela_publicacao_horas(default: int = 8) -> int:
    """V200_51: janela max default 8h (era 4h). Alinha com hidratador BG."""
    try:
        return max(1, int(os.getenv("URURAU_V100_JANELA_PUBLICACAO_HORAS", os.getenv("URURAU_V99_JANELA_PUBLICACAO_HORAS", os.getenv("URURAU_JANELA_PUBLICACAO_HORAS", str(default))))))
    except Exception:
        return default


_DOMINIOS_REGIONAIS_JANELA_AMPLA = {
    "nfnoticias.com.br", "www.nfnoticias.com.br",
    "tribunanf.com.br", "www.tribunanf.com.br",
    "jornaldesabado.com.br", "www.jornaldesabado.com.br",
    "j3news.com", "www.j3news.com",
    "sfnoticias.com.br", "www.sfnoticias.com.br",
    "odebateon.com.br", "www.odebateon.com.br",
    "parahybano.com.br", "www.parahybano.com.br",
    "campos.rj.gov.br", "www.campos.rj.gov.br",
}


def janela_para_fonte_v200(fonte=None, url_feed: str = "", nome_fonte: str = "") -> int:
    """V200_51: janela UNIFORME para todas as fontes.

    Decisao do usuario: 8h max para TODAS (regional, oficial, normal).
    Alinha com a regra do hidratador BG (JANELA_MAX_H=8, PRIORIDADE_H=4).
    Antes regional=24h e oficial=12h - removido para uniformidade.

    Pode ser overridado com env URURAU_V200_JANELA_REGIONAL_HORAS /
    URURAU_V200_JANELA_OFICIAL_HORAS se precisar reativar diferenca.
    """
    base = janela_publicacao_horas()
    try:
        url_l = (url_feed or "").lower()
        nome_l = (nome_fonte or "").lower()
        fonte = fonte or {}
        host = ""
        try:
            from urllib.parse import urlparse
            host = urlparse(url_l).netloc
        except Exception:
            host = ""
        # V200_51: so amplia se env explicito (default = base 8h)
        is_regional = bool(
            fonte.get("regional_prioritaria")
            or fonte.get("regional_prioritaria_v1304")
            or fonte.get("tipo") in ("rss_regional_prioritario_v1304", "regional_v1305", "regional_config_v1305", "auto_v131_regionais", "auto_v1325_regionais")
            or fonte.get("tipo_coleta") in ("rss_regional_prioritario_v1304", "regional_v1305")
            or host in _DOMINIOS_REGIONAIS_JANELA_AMPLA
            or "nfnoticias" in nome_l
            or "tribuna nf" in nome_l
            or "tribunanf" in nome_l
        )
        if is_regional:
            # V200_51: respeita env, mas default agora e base (8h) - nao mais 24h
            try:
                env_val = os.getenv("URURAU_V200_JANELA_REGIONAL_HORAS")
                if env_val:
                    return max(base, int(env_val))
            except Exception:
                pass
            return base  # uniforme com base (8h)
        is_oficial = bool(
            fonte.get("bypass_score")
            or ".gov.br" in url_l
            or ".jus.br" in url_l
            or ".leg.br" in url_l
            or ".mp.br" in url_l
        )
        if is_oficial:
            try:
                env_val = os.getenv("URURAU_V200_JANELA_OFICIAL_HORAS")
                if env_val:
                    return max(base, int(env_val))
            except Exception:
                pass
            return base  # uniforme com base (8h)
    except Exception:
        pass
    return base


def tolerancia_futuro_minutos(default: int = 10) -> int:
    try:
        return max(0, int(os.getenv("URURAU_V99_TOLERANCIA_FUTURO_MIN", str(default))))
    except Exception:
        return default


def _dt_br_naive(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=None)
    return dt.astimezone(TZ_BR).replace(tzinfo=None)


def normalizar_data_publicacao(entry):
    raw = str(entry.get("published") or entry.get("updated") or entry.get("pubDate") or "").strip()
    if raw:
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is not None:
                return _dt_br_naive(parsed), raw, "raw_tz_to_br"
            dt_local = parsed.replace(tzinfo=None)
            agora = _dt.datetime.now(TZ_BR).replace(tzinfo=None)
            diff_min = (dt_local - agora).total_seconds() / 60
            if diff_min > tolerancia_futuro_minutos() and diff_min <= 330:
                dt_corr = dt_local.replace(tzinfo=TZ_UTC).astimezone(TZ_BR).replace(tzinfo=None)
                return dt_corr, raw, "raw_naive_assumido_utc_to_br"
            return dt_local, raw, "raw_naive_br"
        except Exception:
            pass
    tp = entry.get("published_parsed") or entry.get("updated_parsed")
    if tp:
        try:
            dt_utc = _dt.datetime(*tp[:6], tzinfo=TZ_UTC)
            return _dt_br_naive(dt_utc), raw, "tuple_utc_to_br"
        except Exception:
            pass
    return None, raw, "sem_data"


def formatar_br(dt):
    return dt.strftime("%d/%m/%Y %H:%M") if dt else ""


def ordenar_iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


def parse_data_br_ou_iso(valor: str):
    s = (valor or "").strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return _dt.datetime.strptime(s[:19], fmt)
        except Exception:
            pass
    try:
        d, _, h = s.partition("T")
        if d and h:
            return _dt.datetime.fromisoformat((d + " " + h[:8]).replace("Z", "+00:00")).astimezone(TZ_BR).replace(tzinfo=None)
    except Exception:
        pass
    return None


def dentro_da_janela(dt_pub, agora=None, janela_horas=None):
    if dt_pub is None:
        return False, "sem_data_publicacao", 999999.0
    agora = agora or _dt.datetime.now(TZ_BR).replace(tzinfo=None)
    idade_horas = (agora - dt_pub).total_seconds() / 3600
    if idade_horas < -(tolerancia_futuro_minutos() / 60):
        return False, "data_publicacao_futura", idade_horas
    janela = janela_horas or janela_publicacao_horas()
    if idade_horas > janela:
        return False, "fora_da_janela_" + str(janela) + "h", idade_horas
    return True, "ok", idade_horas
