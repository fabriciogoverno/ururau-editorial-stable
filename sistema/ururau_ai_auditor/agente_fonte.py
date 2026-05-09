# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path

ARQUIVOS_FONTE = [
    "sistema/ururau/coleta/fonte_extractor_v104.py",
    "sistema/ururau/coleta/fonte_extractor_v86.py",
    "sistema/ururau/coleta/leitura_fonte.py",
    "sistema/ururau/coleta/rss.py",
    "sistema/ururau/editorial/integridade_fonte_v47_26.py",
    "sistema/ururau/editorial/integridade_redacao_v47_25.py",
]

PADROES_RISCO = [
    "rss_fallback",
    "fallback HTML",
    "texto útil insuficiente",
    "fonte curta",
    "fonte contaminada",
    "AttributeError",
    "NoneType",
    "403",
    "429",
    "v104_preextraido_longo",
]


def sistema_root() -> Path:
    return Path(__file__).resolve().parents[1]


def projeto_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ultimo_relatorio() -> Path | None:
    pasta = sistema_root() / "relatorios_auditoria"
    arquivos = sorted(pasta.glob("auditoria_*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if pasta.exists() else []
    return arquivos[0] if arquivos else None


def ler_json(path: Path | None, default):
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def filtrar_achados_fonte(relatorio: dict) -> list[dict]:
    achados = relatorio.get("classificacao", {}).get("logs", [])
    saida = []
    for item in achados:
        agente = (((item.get("classificacao") or {}).get("principal") or {}).get("agente") or "")
        texto = str(item.get("texto") or "")
        if agente == "fonte" or any(p.lower() in texto.lower() for p in PADROES_RISCO):
            saida.append(item)
    return saida


def gerar_plano_fonte() -> dict:
    rel_path = ultimo_relatorio()
    rel = ler_json(rel_path, {})
    achados = filtrar_achados_fonte(rel)
    plano = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "relatorio_base": str(rel_path) if rel_path else "",
        "agente": "fonte",
        "arquivos_alvo": ARQUIVOS_FONTE,
        "achados_fonte": len(achados),
        "amostras": achados[-40:],
        "diagnostico": [
            "O fluxo de fonte ainda concentra a maior parte dos achados classificados.",
            "O risco principal é usar snippet, rss_fallback ou texto preextraido como se fosse corpo integral confiavel.",
            "A correcao deve fortalecer fronteira entre preconteudo de fila e fonte validada para redacao.",
        ],
        "acoes_recomendadas": [
            "Criar um contrato unico de ResultadoFonteValidada.",
            "Separar campos: resumo_origem, pre_texto_rss, texto_fonte_validado, raw_source_text.",
            "Impedir redacao com extraction_method rss_fallback quando nao houver validacao estrita.",
            "Persistir hash_fonte e uid_pauta junto com o texto validado.",
            "Criar teste de contrato para fonte preextraida longa contaminada.",
            "Criar teste de contrato para fonte correta extraida por v104_v86:rss_fallback.",
            "Rodar sandbox antes de aplicar qualquer patch estrutural.",
        ],
        "nao_fazer": [
            "Nao mexer no CMS nesta etapa.",
            "Nao religar Google/Kimi como requisito para monitor.",
            "Nao remover fail-closed de fonte.",
        ],
    }
    pasta = sistema_root() / "relatorios_auditoria"
    pasta.mkdir(parents=True, exist_ok=True)
    out = pasta / ("plano_fonte_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    out.write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(out), "plano": plano}


def main() -> int:
    print(json.dumps(gerar_plano_fonte(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
