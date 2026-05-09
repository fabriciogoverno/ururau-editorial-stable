# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from ururau_ai_auditor.log_reader import ler_logs


def sistema_root() -> Path:
    return Path(__file__).resolve().parents[1]


def memoria_dir() -> Path:
    pasta = sistema_root() / "ururau_ai_auditor" / "memoria"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def chave_achado(item: dict) -> str:
    base = "|".join(str(item.get(k, "")) for k in ["arquivo", "texto"])
    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()[:20]


def baseline_path() -> Path:
    return memoria_dir() / "baseline_logs.json"


def carregar_baseline() -> dict:
    p = baseline_path()
    if not p.exists():
        return {"chaves": [], "criado_em": "", "total": 0}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {"chaves": [], "criado_em": "", "total": 0}


def marcar_baseline(root: str = ".") -> dict:
    logs = ler_logs(root)
    achados = logs.get("achados", [])
    chaves = sorted({chave_achado(a) for a in achados})
    data = {
        "criado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(chaves),
        "chaves": chaves,
    }
    baseline_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def separar_novos(achados: list[dict]) -> dict:
    base = carregar_baseline()
    conhecidas = set(base.get("chaves") or [])
    novos = []
    antigos = []
    for a in achados:
        key = chave_achado(a)
        item = dict(a)
        item["baseline_key"] = key
        if key in conhecidas:
            item["baseline_status"] = "conhecido"
            antigos.append(item)
        else:
            item["baseline_status"] = "novo"
            novos.append(item)
    return {
        "baseline": {"criado_em": base.get("criado_em"), "total": base.get("total", 0)},
        "novos": novos,
        "conhecidos": antigos,
        "total_novos": len(novos),
        "total_conhecidos": len(antigos),
    }


def main() -> int:
    root = str(sistema_root().parent)
    data = marcar_baseline(root)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
