# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path


def sistema_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ultimo_arquivo(padrao: str) -> Path | None:
    pasta = sistema_root() / "relatorios_auditoria"
    if not pasta.exists():
        return None
    arquivos = sorted(pasta.glob(padrao), key=lambda p: p.stat().st_mtime, reverse=True)
    return arquivos[0] if arquivos else None


def ler_json(path: Path | None, default):
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def gerar_status() -> dict:
    auditoria_path = ultimo_arquivo("auditoria_*.json")
    sandbox_path = ultimo_arquivo("sandbox_*.json")
    plano_path = ultimo_arquivo("plano_correcao_*.json")
    auditoria = ler_json(auditoria_path, {})
    sandbox = ler_json(sandbox_path, {})
    plano = ler_json(plano_path, {})

    comp = auditoria.get("regressao", {}).get("compilacao", {})
    logs = auditoria.get("logs", {})
    baseline = logs.get("baseline_status", {}) or {}
    contrato_ok = (sandbox.get("validacoes", {}).get("testes_contrato", {}).get("returncode") == 0)
    sandbox_ok = (sandbox.get("validacoes", {}).get("auditoria_total", {}).get("returncode") == 0 and contrato_ok)

    status = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "auditoria": {
            "arquivo": str(auditoria_path) if auditoria_path else "",
            "python_total": comp.get("total"),
            "python_falhas": len(comp.get("falhas", [])),
            "logs_achados": len(logs.get("achados", [])),
            "logs_novos": len((baseline.get("novos") or [])),
            "logs_conhecidos": baseline.get("total_conhecidos", 0),
        },
        "contratos": {
            "ok": contrato_ok,
            "sandbox_ok": sandbox_ok,
            "sandbox_relatorio": str(sandbox_path) if sandbox_path else "",
        },
        "agente_prioritario": (plano.get("plano", {}) or {}).get("agente_prioritario", ""),
        "proximo_passo": "Reduzir achados de fonte com testes e politica por dominio; depois medir logs_novos apos uso real.",
    }
    out = sistema_root() / "relatorios_auditoria" / ("status_agentes_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(out), "status": status}


def main() -> int:
    print(json.dumps(gerar_status(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
