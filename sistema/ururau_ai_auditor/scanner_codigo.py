# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
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

IGNORAR_ARQUIVOS = {
    "auditoria_saida.txt",
}


@dataclass
class ArquivoAnalise:
    caminho: str
    linhas: int
    imports: list[str]
    funcoes: list[str]
    classes: list[str]
    erros: list[str]


def deve_ignorar(path: Path) -> bool:
    partes = set(path.parts)
    if partes & IGNORAR_PARTES:
        return True
    if path.name in IGNORAR_ARQUIVOS:
        return True
    return False


def analisar_arquivo(path: Path, root: Path) -> ArquivoAnalise:
    texto = path.read_text(encoding="utf-8", errors="ignore")
    imports: list[str] = []
    funcoes: list[str] = []
    classes: list[str] = []
    erros: list[str] = []
    try:
        tree = ast.parse(texto)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
            elif isinstance(node, ast.FunctionDef):
                funcoes.append(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                funcoes.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
    except SyntaxError as e:
        erros.append(f"SyntaxError: {e}")
    except Exception as e:
        erros.append(f"Erro AST: {e}")
    return ArquivoAnalise(
        caminho=str(path.relative_to(root)).replace("\\", "/"),
        linhas=texto.count("\n") + 1,
        imports=sorted(set(i for i in imports if i)),
        funcoes=sorted(set(funcoes)),
        classes=sorted(set(classes)),
        erros=erros,
    )


def escanear(root: str = ".") -> list[dict]:
    raiz = Path(root).resolve()
    resultados = []
    for path in raiz.rglob("*.py"):
        if deve_ignorar(path):
            continue
        resultados.append(asdict(analisar_arquivo(path, raiz)))
    return resultados
