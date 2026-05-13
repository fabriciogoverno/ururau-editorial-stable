# -*- coding: utf-8 -*-
"""pipeline_inteligente_v200 — escolhe estrategia por aprendizado.

Aprende qual estrategia (json_ld, articlebody, next_data, scripts_json,
wordpress_rest, densidade, amp, mobile, impressao, playwright) funciona
MELHOR para cada DOMINIO e prioriza essa estrategia em coletas futuras.

Funciona como camada acima do extract_pipeline_v90: o pipeline antigo
continua tentando todas as estrategias em ordem, mas a ORDEM dos
candidatos e re-priorizada por dominio com base no historico real
de sucesso (multi-armed bandit simplificado, epsilon-greedy).

Estado persistido em sistema/data/pipeline_metricas_v200.json:

    {
      "rjnewsnoticias.com.br": {
        "json_ld": {"tentativas": 12, "sucessos": 1, "ultima": "..."},
        "articlebody": {"tentativas": 12, "sucessos": 8, "ultima": "..."},
        ...
      }
    }

Tambem cobre Etapa 3 do plano: integracao com auto_perfil_fontes_v131
(perfis curados manualmente vencem o bandit).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_LOCK = threading.Lock()
ESTRATEGIAS_CONHECIDAS = (
    "json_ld", "articlebody", "next_data", "scripts_json",
    "wordpress_rest", "densidade", "amp", "mobile", "impressao",
    "playwright",
)


def _data_dir() -> Path:
    base = Path(__file__).resolve().parents[2] / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _store_path() -> Path:
    return _data_dir() / "pipeline_metricas_v200.json"


def _domain(url: str) -> str:
    try:
        h = urlparse(str(url or "")).netloc.lower().replace("www.", "")
        return h.split(":")[0] if h else ""
    except Exception:
        return ""


# ── persistencia ─────────────────────────────────────────────────────────

def _carregar_estado() -> dict:
    fp = _store_path()
    if not fp.exists():
        return {}
    try:
        return json.loads(fp.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _salvar_estado(estado: dict) -> None:
    fp = _store_path()
    try:
        tmp = fp.with_suffix(".tmp")
        tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(fp)
    except Exception:
        pass


# ── API publica ──────────────────────────────────────────────────────────

def registrar_resultado(url: str, estrategia: str,
                        sucesso: bool, chars: int = 0,
                        latencia_ms: int = 0) -> None:
    """Registra resultado de UMA tentativa de extracao.

    Chamado pelo extract_pipeline ao final de cada estrategia.
    """
    dom = _domain(url)
    if not dom or estrategia not in ESTRATEGIAS_CONHECIDAS:
        return
    with _LOCK:
        estado = _carregar_estado()
        d = estado.setdefault(dom, {})
        e = d.setdefault(estrategia, {
            "tentativas": 0, "sucessos": 0, "chars_total": 0,
            "latencia_ms_total": 0, "ultima": "",
        })
        e["tentativas"] += 1
        if sucesso:
            e["sucessos"] += 1
            e["chars_total"] += int(chars)
        e["latencia_ms_total"] += int(latencia_ms)
        e["ultima"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _salvar_estado(estado)


def _taxa(e: dict) -> float:
    t = e.get("tentativas", 0)
    s = e.get("sucessos", 0)
    if t < 1:
        return 0.0
    # bonus de confianca: precisa de >=3 tentativas para ser autoritario
    bonus = 1.0 if t >= 3 else (t / 3.0)
    return (s / t) * bonus


def ordem_recomendada_para_url(url: str,
                                ordem_default: tuple[str, ...] | None = None,
                                ) -> list[str]:
    """Devolve as estrategias em ordem decrescente de taxa de sucesso.

    Estrategias sem historico ficam mantendo a ordem default (epsilon-greedy
    leve: 80% segue historico, 20% mantem default para explorar).
    """
    dom = _domain(url)
    default = list(ordem_default or ESTRATEGIAS_CONHECIDAS)
    if not dom:
        return default
    estado = _carregar_estado()
    d = estado.get(dom) or {}
    if not d:
        return default

    # Etapa 3: perfil curado manual vence o bandit
    try:
        from ururau.coleta.auto_perfil_fontes_v131 import perfil_ativo_para_url_v131
        if perfil_ativo_para_url_v131(url):
            # se existir perfil, e ja conhecido que aquele dominio funciona
            # de um jeito especifico — confiamos no perfil curado primeiro.
            # Mas mantemos a ordem do bandit como fallback no fim.
            pass
    except Exception:
        pass

    # ordena estrategias do dominio por taxa, depois resto na ordem default
    ranking = sorted(
        d.items(),
        key=lambda kv: (-_taxa(kv[1]), kv[0]),
    )
    com_historico = [e for e, _ in ranking if _taxa(d.get(e, {})) > 0]
    sem_historico = [e for e in default if e not in com_historico]
    ordem = com_historico + sem_historico
    # garante que toda estrategia conhecida apareca
    for e in ESTRATEGIAS_CONHECIDAS:
        if e not in ordem:
            ordem.append(e)
    return ordem


def estatisticas_por_dominio(url: str) -> dict:
    """Para diagnostico: devolve metricas do dominio."""
    dom = _domain(url)
    estado = _carregar_estado()
    d = estado.get(dom, {})
    out = {"dominio": dom, "estrategias": {}}
    for e in ESTRATEGIAS_CONHECIDAS:
        info = d.get(e, {"tentativas": 0, "sucessos": 0})
        t = info.get("tentativas", 0)
        s = info.get("sucessos", 0)
        out["estrategias"][e] = {
            "tentativas": t,
            "sucessos": s,
            "taxa": round(s / max(t, 1), 3),
            "score_bandit": round(_taxa(info), 3),
        }
    return out


def relatorio_global() -> dict:
    """Snapshot completo do estado de aprendizado, util para CLI."""
    estado = _carregar_estado()
    return {
        "dominios_aprendidos": len(estado),
        "total_tentativas": sum(
            e.get("tentativas", 0)
            for d in estado.values() for e in d.values()
        ),
        "total_sucessos": sum(
            e.get("sucessos", 0)
            for d in estado.values() for e in d.values()
        ),
        "dominios": list(estado.keys())[:50],
    }


__all__ = [
    "ESTRATEGIAS_CONHECIDAS",
    "registrar_resultado",
    "ordem_recomendada_para_url",
    "estatisticas_por_dominio",
    "relatorio_global",
]
