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
from ururau_ai_auditor.report_writer import salvar_relatorio


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    logs = ler_logs(str(root))
    regressao = rodar_regressao(str(root))
    falhas_compilacao = regressao.get("compilacao", {}).get("falhas", [])
    achados_logs = logs.get("achados", [])
    dados = {
        "root": str(root),
        "fluxos": listar_fluxos(),
        "agentes": listar_agentes(),
        "scanner": escanear(str(root)),
        "logs": logs,
        "regressao": regressao,
        "classificacao": {
            "logs": classificar_lista(achados_logs),
            "compilacao": classificar_lista(falhas_compilacao),
        },
    }
    rel = salvar_relatorio(dados, str(root))
    print("Relatorio salvo em:", rel)
    print(json.dumps({
        "python_total": dados["regressao"]["compilacao"]["total"],
        "python_falhas": len(falhas_compilacao),
        "logs_achados": len(achados_logs),
        "logs_classificados": len(dados["classificacao"]["logs"]),
        "relatorio": rel,
    }, ensure_ascii=False, indent=2))
    return 0 if dados["regressao"]["compilacao"].get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
