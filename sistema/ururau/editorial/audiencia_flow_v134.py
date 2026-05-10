# -*- coding: utf-8 -*-
"""Fluxo editorial de audiência v134.

Preserva matérias de alcance — celebridade, novela, entretenimento, MLS,
serviço nacional e curiosidades — em trilho próprio. Essas pautas não são
tratadas como erro; elas entram como rascunho/alcance, separadas do núcleo
local, político, policial e regional.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FluxoAudienciaV134:
    fluxo: str = "nucleo_editorial"  # nucleo_editorial | alcance_audiencia | descarte_ruido
    score_delta: int = 0
    motivos: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


def _get(pauta: Any, *keys: str) -> str:
    for k in keys:
        try:
            if isinstance(pauta, dict):
                v = pauta.get(k)
            else:
                v = getattr(pauta, k, None)
            if v:
                return str(v)
        except Exception:
            pass
    return ""


def texto_pauta_v134(pauta: Any) -> str:
    partes = [
        _get(pauta, "titulo", "titulo_origem", "title"),
        _get(pauta, "resumo", "resumo_origem", "summary"),
        _get(pauta, "fonte", "nome_fonte", "source"),
        _get(pauta, "canal", "canal_forcado", "editoria"),
        _get(pauta, "link", "link_origem", "url"),
    ]
    return _norm(" ".join(partes))


def classificar_fluxo_audiencia_v134(pauta: Any, canal: str = "") -> FluxoAudienciaV134:
    txt = texto_pauta_v134(pauta)
    canal_norm = _norm(canal)

    nucleo = [
        "campos", "goytacazes", "norte fluminense", "sao joao da barra", "sfi",
        "macae", "porto do acu", "alerj", "tce-rj", "mprj", "prefeitura",
        "wladimir", "bacellar", "claudio castro", "eduardo paes", "policia",
        "homicidio", "prisao", "trafico", "hospital ferreira machado", "guarus",
        "br-101", "imtt", "codemca", "educacao municipal", "saude de campos",
    ]
    if any(t in txt for t in nucleo):
        return FluxoAudienciaV134("nucleo_editorial", 0, ["aderência ao núcleo local/político/policial"], ["nucleo"])

    grupos = {
        "entretenimento": ["novela", "atriz", "ator", "celebridade", "paolla", "bbb", "reality", "met gala", "streaming", "show", "filme", "serie"],
        "esporte_alcance": ["mls", "gol -", "melhores momentos", "onde assistir", "brasileirao", "vasco", "flamengo", "fluminense", "botafogo", "ufc"],
        "servico_nacional": ["desenrola", "inss", "fgts", "restituicao", "imposto de renda", "tempo e a temperatura", "concurso", "calendario"],
        "curiosidade_busca": ["ovni", "viral", "raro", "curioso", "surpreendente", "lego", "legos", "pet", "dia das maes"],
    }

    tags: list[str] = []
    motivos: list[str] = []
    for tag, termos in grupos.items():
        if any(t in txt for t in termos) or tag in canal_norm:
            tags.append(tag)
            motivos.append(f"potencial de alcance: {tag}")

    ruido_forte = ["horoscopo", "mega-sena", "publi", "picanha grill", "loteria"]
    if any(t in txt for t in ruido_forte):
        return FluxoAudienciaV134("descarte_ruido", -10, ["ruído comercial/baixo controle editorial"], ["ruido"])

    if tags:
        boost = _env_int("URURAU_AUDIENCIA_SCORE_DELTA", 6)
        return FluxoAudienciaV134("alcance_audiencia", boost, motivos[:3], tags[:4])

    return FluxoAudienciaV134("nucleo_editorial", 0, ["sem marcador específico de audiência"], ["geral"])


def aplicar_fluxo_em_pauta_v134(pauta: Any) -> Any:
    fluxo = classificar_fluxo_audiencia_v134(pauta)
    try:
        if isinstance(pauta, dict):
            pauta["fluxo_editorial_v134"] = fluxo.fluxo
            pauta["tags_fluxo_v134"] = fluxo.tags
            pauta["motivos_fluxo_v134"] = fluxo.motivos
            if fluxo.fluxo == "alcance_audiencia":
                pauta["trilho_audiencia"] = True
                pauta["destino_preferencial"] = "rascunho_alcance"
        else:
            setattr(pauta, "fluxo_editorial_v134", fluxo.fluxo)
            setattr(pauta, "tags_fluxo_v134", fluxo.tags)
            setattr(pauta, "motivos_fluxo_v134", fluxo.motivos)
            if fluxo.fluxo == "alcance_audiencia":
                setattr(pauta, "trilho_audiencia", True)
                setattr(pauta, "destino_preferencial", "rascunho_alcance")
    except Exception:
        pass
    return pauta


def aplicar_fluxo_em_score_v134(resultado: Any, pauta: Any) -> Any:
    canal = getattr(resultado, "canal_sugerido", "") or _get(pauta, "canal", "canal_forcado")
    fluxo = classificar_fluxo_audiencia_v134(pauta, canal=canal)
    try:
        setattr(resultado, "fluxo_editorial_v134", fluxo.fluxo)
        setattr(resultado, "tags_fluxo_v134", fluxo.tags)
        setattr(resultado, "motivos_fluxo_v134", fluxo.motivos)
        if fluxo.fluxo == "alcance_audiencia":
            atual = int(getattr(resultado, "score_potencial_audiencia", 0) or 0)
            setattr(resultado, "score_potencial_audiencia", max(atual, 12))
            resultado.score_editorial = min(100, int(getattr(resultado, "score_editorial", 0) or 0) + int(fluxo.score_delta))
            if hasattr(resultado, "motivos_aprovacao"):
                resultado.motivos_aprovacao.append("trilho de alcance/audiência v134: " + ", ".join(fluxo.tags))
            if getattr(resultado, "modo_destino", "rascunho") == "autopublicacao" and os.getenv("URURAU_AUDIENCIA_AUTOPUB", "0").lower() not in {"1", "true", "sim", "on"}:
                resultado.modo_destino = "rascunho"
        elif fluxo.fluxo == "descarte_ruido":
            resultado.score_editorial = max(0, int(getattr(resultado, "score_editorial", 0) or 0) + int(fluxo.score_delta))
            if hasattr(resultado, "motivos_rejeicao"):
                resultado.motivos_rejeicao.append("ruído comercial/baixo controle editorial v134")
    except Exception:
        pass
    return resultado
