"""
datas_v100.py/v99 — normalização única de datas de publicação de fontes.

Objetivo:
- interpretar corretamente datas de RSS/Google News em UTC/GMT;
- converter tudo para America/Sao_Paulo antes de exibir/salvar;
- bloquear pautas sem data confiável, futuras ou publicadas fora da janela editorial.
"""
from __future__ import annotations

import datetime as _dt
import os
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

TZ_BR = ZoneInfo("America/Sao_Paulo")
TZ_UTC = ZoneInfo("UTC")


def janela_publicacao_horas(default: int = 4) -> int:
    """Janela editorial de coleta: somente matérias publicadas nas últimas N horas."""
    try:
        return max(1, int(os.getenv("URURAU_V100_JANELA_PUBLICACAO_HORAS", os.getenv("URURAU_V99_JANELA_PUBLICACAO_HORAS", os.getenv("URURAU_JANELA_PUBLICACAO_HORAS", str(default))))))
    except Exception:
        return default


def tolerancia_futuro_minutos(default: int = 10) -> int:
    try:
        return max(0, int(os.getenv("URURAU_V99_TOLERANCIA_FUTURO_MIN", str(default))))
    except Exception:
        return default


def _dt_br_naive(dt: _dt.datetime) -> _dt.datetime:
    """Converte datetime para horário de Brasília sem tzinfo, compatível com o restante do projeto."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=None)
    return dt.astimezone(TZ_BR).replace(tzinfo=None)


def normalizar_data_publicacao(entry: dict[str, Any]) -> tuple[Optional[_dt.datetime], str, str]:
    """
    Retorna (dt_br_naive, data_original, metodo).

    Regras:
    1. Se published/updated tem timezone (GMT, +0000, -0300 etc.), converte para Brasília.
    2. Se published/updated não tem timezone, trata como Brasília, exceto quando ficar no futuro.
    3. Se a data sem timezone ficar até ~5h no futuro, assume que era UTC mal declarado e converte.
    4. Se só existir published_parsed/updated_parsed, trata como UTC, pois feedparser costuma normalizar time tuples.
    """
    raw = str(entry.get("published") or entry.get("updated") or entry.get("pubDate") or "").strip()

    # 1) Preferir a string original, porque ela contém offset quando o feed informa corretamente.
    if raw:
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is not None:
                return _dt_br_naive(parsed), raw, "raw_tz_to_br"

            # Sem tzinfo: inicialmente considera Brasília.
            dt_local = parsed.replace(tzinfo=None)
            agora = _dt.datetime.now(TZ_BR).replace(tzinfo=None)
            diff_min = (dt_local - agora).total_seconds() / 60

            # Se ficou no futuro por margem compatível com UTC→BRT, corrige.
            if diff_min > tolerancia_futuro_minutos() and diff_min <= 330:
                dt_corr = dt_local.replace(tzinfo=TZ_UTC).astimezone(TZ_BR).replace(tzinfo=None)
                return dt_corr, raw, "raw_naive_assumido_utc_to_br"

            return dt_local, raw, "raw_naive_br"
        except Exception:
            pass

    # 2) Fallback em tuples do feedparser. Geralmente representam UTC normalizado.
    tp = entry.get("published_parsed") or entry.get("updated_parsed")
    if tp:
        try:
            dt_utc = _dt.datetime(*tp[:6], tzinfo=TZ_UTC)
            return _dt_br_naive(dt_utc), raw, "tuple_utc_to_br"
        except Exception:
            pass

    return None, raw, "sem_data"


def formatar_br(dt: Optional[_dt.datetime]) -> str:
    return dt.strftime("%d/%m/%Y %H:%M") if dt else ""


def ordenar_iso(dt: Optional[_dt.datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""


def parse_data_br_ou_iso(valor: str) -> Optional[_dt.datetime]:
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


def dentro_da_janela(dt_pub: Optional[_dt.datetime], agora: Optional[_dt.datetime] = None, janela_horas: Optional[int] = None) -> tuple[bool, str, float]:
    """Valida se a publicação está dentro da janela v99."""
    if dt_pub is None:
        return False, "sem_data_publicacao", 999999.0
    agora = agora or _dt.datetime.now(TZ_BR).replace(tzinfo=None)
    idade_horas = (agora - dt_pub).total_seconds() / 3600
    if idade_horas < -(tolerancia_futuro_minutos() / 60):
        return False, "data_publicacao_futura", idade_horas
    janela = janela_horas or janela_publicacao_horas()
    if idade_horas > janela:
        return False, f"fora_da_janela_{janela}h", idade_horas
    return True, "ok", idade_horas
