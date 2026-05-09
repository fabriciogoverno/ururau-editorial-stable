# -*- coding: utf-8 -*-
from __future__ import annotations

import py_compile
from pathlib import Path

IGNORAR_PARTES = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "ENV",
    ".git",
    "hotfixes_legacy",
    "relatorios_auditoria",
}


def deve_ignorar(path: Path) -> bool:
    return bool(set(path.parts) & IGNORAR_PARTES)


def compilar_python(root: str = ".") -> dict:
    raiz = Path(root).resolve()
    falhas = []
    total = 0
    for path in raiz.rglob("*.py"):
        if deve_ignorar(path):
            continue
        total += 1
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as e:
            falhas.append({"arquivo": str(path.relative_to(raiz)).replace("\\", "/"), "erro": str(e)})
    return {"total": total, "falhas": falhas, "ok": not falhas}


def checar_arquivos_criticos(root: str = ".") -> dict:
    raiz = Path(root).resolve()
    criticos = [
        "sistema/ururau/ui/painel.py",
        "sistema/ururau/publisher/workflow.py",
        "sistema/ururau/publisher/monitor.py",
        "sistema/ururau/publisher/cms_playwright_v81.py",
        "sistema/ururau/editorial/redacao.py",
        "sistema/ururau/editorial/engine.py",
        "sistema/ururau/imaging/processamento.py",
        "sistema/ururau/imaging/busca.py",
    ]
    faltando = [p for p in criticos if not (raiz / p).exists()]
    return {"criticos": criticos, "faltando": faltando, "ok": not faltando}


def rodar_regressao(root: str = ".") -> dict:
    return {
        "compilacao": compilar_python(root),
        "arquivos_criticos": checar_arquivos_criticos(root),
    }
