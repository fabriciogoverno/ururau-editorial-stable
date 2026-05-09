from __future__ import annotations
import csv, json, os, re
from pathlib import Path

def _load_json(path: str, default):
    try:
        p = Path(path)
        if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    except Exception: pass
    return default

def carregar_termos_trends_v88() -> list[dict]:
    config = _load_json("radar_audiencia_config_v88.json", {})
    termos = []
    for fonte in config.get("fontes_termos", []):
        p = Path(fonte)
        if not p.exists(): continue
        if p.suffix.lower() == ".json":
            data = _load_json(str(p), {})
            termos.extend(data.get("termos", []) if isinstance(data, dict) else (data if isinstance(data, list) else []))
        elif p.suffix.lower() == ".csv":
            try:
                with p.open("r", encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f):
                        termo = row.get("Tendências") or row.get("termo") or row.get("Termo") or row.get("query") or ""
                        if termo: termos.append({"termo": termo, "volume": row.get("Volume de pesquisa", ""), "geo": row.get("geo", "BR-RJ")})
            except Exception: pass
    return [t for t in termos if str(t.get("termo", "")).strip()]

def termos_para_google_news_v88() -> list[str]:
    config = _load_json("radar_audiencia_config_v88.json", {})
    prioridade = [str(x).lower() for x in config.get("termos_prioritarios", [])]
    baixa = [str(x).lower() for x in config.get("termos_baixa_prioridade", [])]
    out, vistos = [], set()
    for item in carregar_termos_trends_v88():
        termo = re.sub(r"\s+", " ", str(item.get("termo", "")).strip())
        low = termo.lower()
        if not termo or low in vistos: continue
        if any(b in low for b in baixa) and not any(p in low for p in prioridade): continue
        vistos.add(low); out.append(termo)
        if "rio" not in low and "rj" not in low and any(p in low for p in prioridade): out.append(f"{termo} Rio de Janeiro")
        if any(x in low for x in ("anvisa", "fgts", "governo", "polícia", "saúde")): out.append(f"{termo} site:g1.globo.com OR site:uol.com.br OR site:agenciabrasil.ebc.com.br")
    return out[: int(os.getenv("URURAU_V88_MAX_TERMOS_TRENDS", "40"))]
