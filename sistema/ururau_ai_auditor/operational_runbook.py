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


def gerar_runbook() -> dict:
    auditoria = ultimo_arquivo("auditoria_*.json")
    sandbox = ultimo_arquivo("sandbox_*.json")
    plano = ultimo_arquivo("plano_correcao_*.json")
    status = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "relatorios": {
            "auditoria": str(auditoria) if auditoria else "",
            "sandbox": str(sandbox) if sandbox else "",
            "plano": str(plano) if plano else "",
        },
        "rotina_diaria": [
            "git checkout auditor-ia",
            "git pull origin auditor-ia",
            ".\\35_PIPELINE_AUDITOR_SEGURO.bat",
            ".\\02_ABRIR_PAINEL.bat",
        ],
        "antes_de_corrigir": [
            "Criar ou ajustar teste de contrato.",
            "Aplicar alteracao apenas na branch auditor-ia.",
            "Rodar 35_PIPELINE_AUDITOR_SEGURO.bat.",
            "Se passar, commitar e enviar auditor-ia.",
        ],
        "proibido_sem_revisao": [
            "Comitar credenciais ou .env.",
            "Comitar banco local, logs ou imagens de cache.",
            "Fazer merge em main sem gate de promocao.",
            "Remover fail-closed de fonte, imagem ou CMS.",
        ],
        "comandos_uteis": {
            "abrir_painel": ".\\02_ABRIR_PAINEL.bat",
            "abrir_auditor": ".\\33_ABRIR_AUDITOR_IA.bat",
            "pipeline_seguro": ".\\35_PIPELINE_AUDITOR_SEGURO.bat",
            "status_agentes": ".\\39_STATUS_AGENTES.bat",
            "gate_promocao": ".\\41_GATE_PROMOCAO_MAIN.bat",
        },
    }
    pasta = sistema_root() / "documentacao"
    pasta.mkdir(parents=True, exist_ok=True)
    out = pasta / "RUNBOOK_OPERACIONAL_AUDITOR_IA.json"
    out.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(out), "runbook": status}


def main() -> int:
    print(json.dumps(gerar_runbook(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
