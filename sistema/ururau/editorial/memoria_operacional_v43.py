"""memoria_operacional_v43.py — memória editorial operacional ajustável.

Não treina o GPT. Registra decisões do operador e transforma o histórico em
pesos editoriais, consultáveis e editáveis por JSON.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


def base_dir() -> Path:
    try:
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path.cwd()


def path_memoria() -> Path:
    p = base_dir() / "config" / "memoria_editorial_operacional_v43.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _norm(s: str) -> str:
    s = (s or "").lower()
    mapa = str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")
    s = s.translate(mapa)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def _load() -> dict[str, Any]:
    p = path_memoria()
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(d, dict):
                d.setdefault("version", "V43 Premium")
                d.setdefault("events", [])
                d.setdefault("weights", {"fontes": {}, "termos": {}, "editorias": {}, "acoes": {}})
                d.setdefault("manual", {"boost_fontes": {}, "boost_termos": {}, "penalizar_termos": {}, "observacoes": "Editável pelo operador."})
                return d
        except Exception:
            pass
    return {
        "version": "V43 Premium",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "manual": {"boost_fontes": {}, "boost_termos": {}, "penalizar_termos": {}, "observacoes": "Memória editorial operacional. Pode editar manualmente."},
        "weights": {"fontes": {}, "termos": {}, "editorias": {}, "acoes": {}},
        "events": [],
    }


def _save(d: dict[str, Any]) -> None:
    d["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    d["events"] = d.get("events", [])[-2000:]
    path_memoria().write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def registrar_decisao_v43(acao: str, pauta: dict[str, Any] | None = None, extra: dict[str, Any] | None = None) -> None:
    pauta = pauta or {}
    d = _load()
    fonte = pauta.get("fonte_nome") or pauta.get("nome_fonte") or pauta.get("fonte") or ""
    editoria = pauta.get("canal_forcado") or pauta.get("editoria") or pauta.get("canal") or ""
    titulo = pauta.get("titulo_origem") or pauta.get("titulo") or ""
    texto = " ".join([titulo, pauta.get("resumo_origem") or "", editoria, fonte])
    termos = [t for t in _norm(texto).split() if len(t) >= 4][:40]
    evento = {
        "quando": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "acao": acao,
        "titulo": titulo[:220],
        "fonte": fonte,
        "editoria": editoria,
        "url": pauta.get("link_origem") or pauta.get("url") or "",
        "score": pauta.get("score_editorial"),
        "extra": extra or {},
    }
    d.setdefault("events", []).append(evento)
    weights = d.setdefault("weights", {"fontes": {}, "termos": {}, "editorias": {}, "acoes": {}})
    pesos_acao = {"publicar": 4, "aprovar": 3, "copydesk": 2, "redigir": 1, "preview": 1, "descartar": -3, "reprovar": -4, "bloquear": -4}
    delta = pesos_acao.get(acao, 0)
    if fonte:
        weights.setdefault("fontes", {})[fonte] = int(weights.setdefault("fontes", {}).get(fonte, 0)) + delta
    if editoria:
        weights.setdefault("editorias", {})[editoria] = int(weights.setdefault("editorias", {}).get(editoria, 0)) + delta
    for t in termos[:12]:
        if t in {"para", "com", "sem", "sobre", "este", "esta", "noticia", "noticias"}:
            continue
        weights.setdefault("termos", {})[t] = int(weights.setdefault("termos", {}).get(t, 0)) + delta
    weights.setdefault("acoes", {})[acao] = int(weights.setdefault("acoes", {}).get(acao, 0)) + 1
    _save(d)


def bonus_pauta_v43(pauta: dict[str, Any] | None) -> int:
    pauta = pauta or {}
    d = _load()
    weights = d.get("weights", {})
    manual = d.get("manual", {})
    fonte = pauta.get("fonte_nome") or pauta.get("nome_fonte") or pauta.get("fonte") or ""
    editoria = pauta.get("canal_forcado") or pauta.get("editoria") or pauta.get("canal") or ""
    texto = _norm(" ".join([pauta.get("titulo_origem") or pauta.get("titulo") or "", pauta.get("resumo_origem") or ""]))
    bonus = 0
    if fonte:
        bonus += max(-10, min(12, int(weights.get("fontes", {}).get(fonte, 0)) // 3))
        bonus += int(manual.get("boost_fontes", {}).get(fonte, 0) or 0)
    if editoria:
        bonus += max(-8, min(8, int(weights.get("editorias", {}).get(editoria, 0)) // 4))
    termos_w = weights.get("termos", {})
    for termo, peso in list(termos_w.items())[:500]:
        if termo and termo in texto:
            bonus += max(-2, min(3, int(peso) // 10))
    for termo, val in manual.get("boost_termos", {}).items():
        if _norm(termo) in texto:
            bonus += int(val or 0)
    for termo, val in manual.get("penalizar_termos", {}).items():
        if _norm(termo) in texto:
            bonus -= abs(int(val or 0))
    return max(-20, min(25, bonus))


def prompt_contexto_memoria_v43() -> str:
    d = _load()
    fontes = sorted((d.get("weights", {}).get("fontes", {}) or {}).items(), key=lambda x: x[1], reverse=True)[:10]
    termos = sorted((d.get("weights", {}).get("termos", {}) or {}).items(), key=lambda x: x[1], reverse=True)[:20]
    return (
        "MEMÓRIA EDITORIAL OPERACIONAL V43\n"
        "Use como contexto adaptativo, sem inventar fatos e sem contrariar o manual editorial.\n"
        f"Fontes valorizadas recentemente: {fontes}\n"
        f"Termos/temas valorizados recentemente: {termos}\n"
        f"Observações manuais: {d.get('manual', {}).get('observacoes', '')}\n"
    )
