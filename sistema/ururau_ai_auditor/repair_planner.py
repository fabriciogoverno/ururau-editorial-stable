# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path


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


def resumo_por_agente(classificados: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in classificados or []:
        agente = (((item.get("classificacao") or {}).get("principal") or {}).get("agente") or "indefinido")
        out[agente] = out.get(agente, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))


def plano_para_agente(agente: str) -> list[str]:
    planos = {
        "fonte": [
            "Revisar dominios com falha recorrente de extracao.",
            "Separar snippet/RSS de texto integral em campos diferentes.",
            "Criar teste de contrato para fonte curta, fonte contaminada e fonte com 403/429.",
            "Garantir que Redigir so use texto validado por UID e link_origem.",
        ],
        "imagem": [
            "Listar dominios com 429 ou imagem invalida.",
            "Reforcar filtro contra logo/avatar/gravatar como imagem final.",
            "Criar teste de contrato para fallback com imagem alternativa valida.",
        ],
        "cms": [
            "Validar preflight antes de chamar Playwright.",
            "Criar teste para imagem obrigatoria, modo rascunho e campo de canal.",
            "Isolar erro de login, erro de formulario e erro de publicacao.",
        ],
        "monitor": [
            "Garantir que PARAR bloqueia novo ciclo ate status INATIVO.",
            "Garantir que Google/Kimi nao seguram ciclo quando bloqueados.",
            "Criar teste com coletor lento simulado.",
        ],
        "redacao": [
            "Garantir snapshot fechado pauta/fonte/materia.",
            "Bloquear fallback local como publicacao direta.",
            "Criar teste para resposta curta da OpenAI e regeneracao.",
        ],
        "ui": [
            "Garantir que selecao da fila atualiza UID selecionado.",
            "Bloquear atualizacao visual por worker se UID mudou.",
            "Criar teste manual guiado para setas, F5 e preview.",
        ],
        "regressao": [
            "Manter compilacao limpa.",
            "Rodar testes de contrato antes de qualquer patch.",
            "Executar sandbox antes de promover mudanca.",
        ],
    }
    return planos.get(agente, ["Analisar logs classificados e criar teste de contrato antes de corrigir."])


def gerar_plano() -> dict:
    rel_path = ultimo_relatorio()
    rel = ler_json(rel_path, {})
    class_logs = rel.get("classificacao", {}).get("logs", [])
    class_comp = rel.get("classificacao", {}).get("compilacao", [])
    por_agente = resumo_por_agente(class_logs + class_comp)
    principal = next(iter(por_agente.keys()), "regressao")
    plano = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "relatorio_base": str(rel_path) if rel_path else "",
        "agente_prioritario": principal,
        "achados_por_agente": por_agente,
        "acoes_recomendadas": plano_para_agente(principal),
        "regra_de_execucao": [
            "Criar ou ajustar teste de contrato primeiro.",
            "Aplicar mudanca somente em branch auditor-ia.",
            "Rodar 30_AUDITORIA_TOTAL.bat.",
            "Rodar 31_TESTES_CONTRATO.bat.",
            "Rodar 32_SANDBOX_AUDITOR.bat.",
            "So depois considerar promocao para main.",
        ],
    }
    pasta = sistema_root() / "relatorios_auditoria"
    pasta.mkdir(parents=True, exist_ok=True)
    out = pasta / ("plano_correcao_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    out.write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(out), "plano": plano}


def main() -> int:
    r = gerar_plano()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
