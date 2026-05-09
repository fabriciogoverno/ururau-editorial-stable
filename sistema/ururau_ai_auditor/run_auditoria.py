# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from ururau_ai_auditor.scanner_codigo import escanear
from ururau_ai_auditor.log_reader import ler_logs
from ururau_ai_auditor.regression_tests import rodar_regressao
from ururau_ai_auditor.fluxo_registry import listar_fluxos
from ururau_ai_auditor.agent_registry import listar_agentes
from ururau_ai_auditor.issue_classifier import classificar_lista
from ururau_ai_auditor.memory_store import salvar_snapshot_auditoria
from ururau_ai_auditor.report_writer import salvar_relatorio


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    logs = ler_logs(str(root))
    regressao = rodar_regressao(str(root))
    falhas_compilacao = regressao.get("compilacao", {}).get("falhas", [])
    achados_logs = logs.get("achados", [])
    baseline_status = logs.get("baseline_status", {}) or {}

    # Importante: lista vazia de novos achados é um resultado válido.
    # A versão anterior usava "or achados_logs", fazendo logs_novos voltar a 98
    # mesmo quando todos os achados estavam no baseline.
    if "novos" in baseline_status:
        logs_novos = baseline_status.get("novos") or []
    else:
        logs_novos = achados_logs

    dados = {
        "root": str(root),
        "fluxos": listar_fluxos(),
        "agentes": listar_agentes(),
        "scanner": escanear(str(root)),
        "logs": logs,
        "regressao": regressao,
        "classificacao": {
            "logs": classificar_lista(achados_logs),
            "logs_novos": classificar_lista(logs_novos),
            "compilacao": classificar_lista(falhas_compilacao),
        },
    }
    dados["memoria"] = salvar_snapshot_auditoria(dados, str(root))
    rel = salvar_relatorio(dados, str(root))
    print("Relatorio salvo em:", rel)
    print(json.dumps({
        "python_total": dados["regressao"]["compilacao"]["total"],
        "python_falhas": len(falhas_compilacao),
        "logs_achados": len(achados_logs),
        "logs_novos": len(logs_novos),
        "logs_conhecidos": baseline_status.get("total_conhecidos", 0),
        "baseline_total": (baseline_status.get("baseline") or {}).get("total", 0),
        "logs_classificados": len(dados["classificacao"]["logs"]),
        "memoria": dados.get("memoria", {}),
        "relatorio": rel,
    }, ensure_ascii=False, indent=2))
    return 0 if dados["regressao"]["compilacao"].get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
