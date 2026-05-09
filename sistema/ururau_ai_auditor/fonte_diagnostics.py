# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


def sistema_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ultimo_relatorio() -> Path | None:
    pasta = sistema_root() / "relatorios_auditoria"
    if not pasta.exists():
        return None
    arquivos = sorted(pasta.glob("auditoria_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return arquivos[0] if arquivos else None


def ler_json(path: Path | None, default):
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def extrair_url(texto: str) -> str:
    m = re.search(r"https?://[^\s;]+", texto or "")
    return m.group(0).rstrip(".,);]") if m else ""


def dominio(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def classificar_falha(texto: str) -> list[str]:
    low = (texto or "").lower()
    tags = []
    if "rss_fallback" in low:
        tags.append("rss_fallback")
    if "nonetype" in low or "noneType" in texto:
        tags.append("none_get")
    if "texto útil insuficiente" in low or "texto util insuficiente" in low:
        tags.append("texto_insuficiente")
    if "403" in low or "forbidden" in low:
        tags.append("403")
    if "429" in low or "too many requests" in low:
        tags.append("429")
    if "failed" in low or "falhou" in low or "fail" in low:
        tags.append("falha")
    return tags or ["outro"]


def analisar_fonte() -> dict:
    rel_path = ultimo_relatorio()
    rel = ler_json(rel_path, {})
    logs = rel.get("classificacao", {}).get("logs", [])
    dominios = Counter()
    tags = Counter()
    por_dominio_tags: dict[str, Counter] = defaultdict(Counter)
    amostras = []

    for item in logs:
        texto = str(item.get("texto") or "")
        agente = (((item.get("classificacao") or {}).get("principal") or {}).get("agente") or "")
        if agente != "fonte" and "FONTE" not in texto and "rss_fallback" not in texto:
            continue
        url = extrair_url(texto)
        dom = dominio(url) or "sem_dominio"
        dominios[dom] += 1
        ts = classificar_falha(texto)
        for t in ts:
            tags[t] += 1
            por_dominio_tags[dom][t] += 1
        if len(amostras) < 80:
            amostras.append({"dominio": dom, "tags": ts, "texto": texto[:500]})

    ranking = []
    for dom, qtd in dominios.most_common(50):
        ranking.append({
            "dominio": dom,
            "ocorrencias": qtd,
            "tags": dict(por_dominio_tags[dom].most_common()),
        })

    plano = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "relatorio_base": str(rel_path) if rel_path else "",
        "total_achados_fonte": sum(dominios.values()),
        "tags": dict(tags.most_common()),
        "ranking_dominios": ranking,
        "amostras": amostras,
        "prioridades_tecnicas": [
            "corrigir NoneType.get nos adaptadores de fonte para retornar Resultado seguro",
            "separar rss_fallback de texto_fonte_validado",
            "aplicar FonteValidada antes de qualquer redacao",
            "criar politica por dominio para os maiores reincidentes",
        ],
    }
    out_dir = sistema_root() / "relatorios_auditoria"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ("diagnostico_fonte_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    out.write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(out), "diagnostico": plano}


def main() -> int:
    print(json.dumps(analisar_fonte(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
