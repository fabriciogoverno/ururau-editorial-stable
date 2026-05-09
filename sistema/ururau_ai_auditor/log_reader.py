# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

PADROES_ERRO = [
    "Traceback",
    "SyntaxError",
    "NameError",
    "AttributeError",
    "ImportError",
    "falhou",
    "ERRO",
    "ERROR",
    "bloqueada",
    "contaminada",
]


def ler_logs(root: str = ".", max_linhas: int = 5000) -> dict:
    raiz = Path(root).resolve()
    logs_dir = raiz / "sistema" / "logs"
    achados = []
    if not logs_dir.exists():
        return {"logs_dir": str(logs_dir), "existe": False, "achados": [], "baseline_status": {}}
    for path in logs_dir.rglob("*.log"):
        try:
            linhas = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_linhas:]
        except Exception:
            continue
        for i, linha in enumerate(linhas, 1):
            if any(p in linha for p in PADROES_ERRO):
                achados.append({
                    "arquivo": str(path.relative_to(raiz)).replace("\\", "/"),
                    "linha": i,
                    "texto": linha[:500],
                })
    achados = achados[-300:]
    baseline_status = {}
    try:
        from ururau_ai_auditor.log_baseline import separar_novos
        baseline_status = separar_novos(achados)
    except Exception:
        baseline_status = {"total_novos": len(achados), "total_conhecidos": 0, "novos": achados, "conhecidos": []}
    return {"logs_dir": str(logs_dir), "existe": True, "achados": achados, "baseline_status": baseline_status}
