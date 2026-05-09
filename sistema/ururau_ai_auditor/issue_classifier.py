# -*- coding: utf-8 -*-
from __future__ import annotations

from ururau_ai_auditor.agent_registry import listar_agentes


def classificar_achado(texto: str) -> dict:
    texto_norm = (texto or "").lower()
    agentes = listar_agentes()
    scores = []
    for nome, cfg in agentes.items():
        score = 0
        for p in cfg.get("padroes", []):
            if p.lower() in texto_norm:
                score += 1
        if score:
            scores.append({"agente": nome, "score": score, "descricao": cfg.get("descricao", "")})
    scores.sort(key=lambda x: x["score"], reverse=True)
    if not scores:
        scores = [{"agente": "regressao", "score": 0, "descricao": agentes["regressao"]["descricao"]}]
    return {"principal": scores[0], "candidatos": scores[:3]}


def classificar_lista(achados: list[dict]) -> list[dict]:
    saida = []
    for item in achados:
        texto = " ".join(str(item.get(k, "")) for k in ["texto", "erro", "arquivo"])
        novo = dict(item)
        novo["classificacao"] = classificar_achado(texto)
        saida.append(novo)
    return saida
