# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path

from ururau_ai_auditor.repair_planner import gerar_plano
from ururau_ai_auditor.fonte_diagnostics import analisar_fonte


def sistema_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _plano_fonte(diagnostico: dict) -> dict:
    diag = diagnostico.get("diagnostico", diagnostico)
    ranking = diag.get("ranking_dominios", [])
    top = ranking[0] if ranking else {}
    dominio = top.get("dominio", "")
    return {
        "agente": "fonte",
        "dominio_prioritario": dominio,
        "problema": "falhas recorrentes de fonte, rss_fallback e NoneType.get",
        "hipotese": [
            "Alguns adaptadores/filtros de fonte recebem None ou item invalido e chamam .get diretamente.",
            "Trechos de RSS/snippet continuam entrando como pre-conteudo e gerando ruido nos logs.",
            "O contrato FonteValidada ja bloqueia redacao insegura, mas a coleta ainda precisa retornar resultado seguro em vez de excecao recorrente.",
        ],
        "patch_sugerido": [
            "Adicionar wrappers safe_get/safe_dict nos pontos de politica/adaptadores de fonte com maior recorrencia.",
            "Criar politica por dominio para priorizar adaptador correto nos dominios reincidentes.",
            "Converter exceptions conhecidas de fonte para ResultadoExtracao seguro, com status=failed e motivo estruturado.",
            "Adicionar teste de contrato para o dominio prioritario, sem rede, simulando None e rss_fallback.",
        ],
        "arquivos_alvo": [
            "sistema/ururau/coleta/source_policy_v114.py",
            "sistema/ururau/coleta/fonte_extractor_v86.py",
            "sistema/ururau/coleta/fonte_extractor_v104.py",
            "sistema/ururau/coleta/rss.py",
            "sistema/ururau/coleta/fonte_validada.py",
        ],
        "testes_obrigatorios": [
            "31_TESTES_CONTRATO.bat",
            "30_AUDITORIA_TOTAL.bat",
            "32_SANDBOX_AUDITOR.bat",
        ],
    }


def gerar_plano_corretivo() -> dict:
    plano_geral = gerar_plano()
    diag_fonte = analisar_fonte()
    agente = plano_geral.get("plano", {}).get("agente_prioritario", "regressao")
    if agente == "fonte":
        proposta = _plano_fonte(diag_fonte)
    else:
        proposta = {
            "agente": agente,
            "problema": "agente prioritario fora do fluxo fonte",
            "hipotese": ["Usar classificacao do relatorio para gerar patch especifico."],
            "patch_sugerido": ["Criar teste de contrato antes de alterar arquivos."],
            "arquivos_alvo": [],
            "testes_obrigatorios": ["31_TESTES_CONTRATO.bat", "30_AUDITORIA_TOTAL.bat", "32_SANDBOX_AUDITOR.bat"],
        }

    saida = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tipo": "plano_corretor_seguro",
        "plano_base": plano_geral.get("arquivo"),
        "diagnostico_fonte": diag_fonte.get("arquivo"),
        "proposta": proposta,
        "regra_de_ouro": [
            "Nao aplicar patch direto em main.",
            "Criar/ajustar teste primeiro.",
            "Aplicar em auditor-ia.",
            "Rodar auditoria, testes e sandbox.",
            "So promover para main com aprovacao humana.",
        ],
    }
    pasta = sistema_root() / "relatorios_auditoria"
    pasta.mkdir(parents=True, exist_ok=True)
    out = pasta / ("plano_corretor_seguro_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    out.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(out), "plano": saida}


def main() -> int:
    print(json.dumps(gerar_plano_corretivo(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
