from __future__ import annotations
import json, re
from pathlib import Path

def _load_json(path: str, default):
    try:
        p = Path(path)
        if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    except Exception: pass
    return default

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def calcular_opportunity_score_v88(pauta: dict, config: dict | None = None) -> tuple[int, list[str]]:
    config = config or _load_json("source_hunter_config_v88.json", {})
    filtros = (config.get("filtros_interesse") or {}) if isinstance(config, dict) else {}
    fortes = [str(x).lower() for x in filtros.get("termos_fortes", [])]
    fracos = [str(x).lower() for x in filtros.get("termos_fracos_descartar", [])]
    texto = _norm(" ".join([str(pauta.get("titulo_origem", "")), str(pauta.get("resumo_origem", "")), str(pauta.get("fonte_nome", "")), str(pauta.get("_intel_log", ""))]))
    score = int(pauta.get("_source_hunter_score", pauta.get("score_descoberta", 0)) or 0)
    motivos = []
    for termo in fortes:
        if termo and termo in texto:
            score += 12; motivos.append(f"termo forte: {termo}")
            if len(motivos) >= 5: break
    for termo in fracos:
        if termo and termo in texto:
            score -= 20; motivos.append(f"baixa prioridade: {termo}"); break
    origem = str(pauta.get("origem_feed", ""))
    if "sitemap" in origem: score += 6; motivos.append("sitemap")
    if "source_page" in origem: score += 4; motivos.append("página de editoria")
    if "google_news" in origem: score += 3; motivos.append("Google News reforço")
    if pauta.get("_intel_watchlists") or "Watch:" in str(pauta.get("_intel_log", "")):
        score += 15; motivos.append("watchlist")
    return max(0, min(100, score)), motivos
