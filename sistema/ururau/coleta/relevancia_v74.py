"""Score de relevância automática para priorizar manchetes — v74."""
from __future__ import annotations

import re
from typing import Any


def _n(text: str) -> str:
    text = (text or "").lower()
    repl = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")
    return text.translate(repl)


REGIONAIS = ("campos", "norte fluminense", "sao joao da barra", "são joão da barra", "macae", "macaé", "porto do acu", "porto do açu", "rio de janeiro", "alerj", "governo do rio")
IMPACTO = ("morre", "morte", "preso", "operacao", "operação", "investiga", "denuncia", "denúncia", "prefeito", "governador", "alerj", "stf", "tse", "caixa", "fgts", "pis", "pasep", "saude", "saúde")
SERVICO = ("prazo", "calendario", "calendário", "como consultar", "quem recebe", "inscricao", "inscrição", "pagamento", "vacinacao", "vacinação")
FONTES_FORTES = ("g1", "poder360", "agencia brasil", "agência brasil", "alerj", "stf", "tse", "mprj", "tjrj", "senado", "camara", "câmara")


def calcular_relevancia_v74(pauta: dict[str, Any]) -> dict[str, Any]:
    title = pauta.get("titulo_origem") or pauta.get("titulo") or ""
    text = " ".join([title, pauta.get("resumo_origem", "") or "", pauta.get("texto_fonte", "") or pauta.get("dossie", "") or "", pauta.get("fonte_nome", "") or ""])
    n = _n(text)
    score = 0
    reasons: list[str] = []

    for kw in REGIONAIS:
        if _n(kw) in n:
            score += 14; reasons.append(f"regional:{kw}"); break
    for kw in IMPACTO:
        if _n(kw) in n:
            score += 10; reasons.append(f"impacto:{kw}")
            if score >= 40: break
    if any(_n(k) in n for k in SERVICO):
        score += 12; reasons.append("serviço útil ao leitor")
    if any(_n(k) in n for k in FONTES_FORTES):
        score += 10; reasons.append("fonte forte")
    if re.search(r"\b\d{1,2}[h:]\d{0,2}\b|\bhoje\b|\bnesta\b|\bsegunda\b|\bterça\b|\bterca\b|\bquarta\b|\bquinta\b|\bsexta\b", n):
        score += 6; reasons.append("temporalidade")
    if len(n) < 160:
        score -= 10; reasons.append("texto curto")
    if any(x in n for x in ("horoscopo", "signo", "loteria", "receita de")):
        score -= 20; reasons.append("baixo valor editorial")

    score = max(0, min(100, score))
    if score >= 55:
        prioridade = "manchete"
    elif score >= 38:
        prioridade = "alta"
    elif score >= 22:
        prioridade = "media"
    else:
        prioridade = "baixa"
    return {"score_relevancia_v74": score, "prioridade_v74": prioridade, "motivos_relevancia_v74": reasons[:8]}
