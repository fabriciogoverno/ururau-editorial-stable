# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

EXCLUIR_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "env",
    "ENV",
    "node_modules",
    "sistema/data",
    "sistema/logs",
    "sistema/credenciais",
    "sistema/relatorios_auditoria",
    "ghostwriter_images",
}

EXCLUIR_SUFFIX = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".zip",
    ".rar",
    ".7z",
}

EXCLUIR_NOMES = {
    ".env",
    "env_principal.env",
    "auditoria_saida.txt",
}


def raiz_projeto() -> Path:
    return Path(__file__).resolve().parents[2]


def rel_path(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def deve_excluir(path: Path, root: Path) -> bool:
    rel = rel_path(path, root)
    partes = set(path.parts)
    if path.name in EXCLUIR_NOMES:
        return True
    if path.suffix.lower() in EXCLUIR_SUFFIX:
        return True
    if rel in EXCLUIR_DIRS:
        return True
    for item in EXCLUIR_DIRS:
        if rel.startswith(item.rstrip("/") + "/"):
            return True
    if "credenciais" in partes:
        return True
    return False


def copiar_sandbox(root: Path, destino: Path, limpar: bool = True) -> dict:
    if destino.exists() and limpar:
        # Protecao basica contra rm em diretorio errado.
        if "sandbox" not in destino.name.lower() and "auditor" not in destino.name.lower():
            raise RuntimeError(f"Destino inseguro para limpar: {destino}")
        shutil.rmtree(destino)
    destino.mkdir(parents=True, exist_ok=True)
    copiados = 0
    ignorados = 0
    for src in root.rglob("*"):
        if src == destino or destino in src.parents:
            continue
        if deve_excluir(src, root):
            ignorados += 1
            continue
        dst = destino / src.relative_to(root)
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copiados += 1
    return {"destino": str(destino), "copiados": copiados, "ignorados": ignorados}


def run_cmd(cmd: list[str], cwd: Path, timeout: int = 300) -> dict:
    ini = time.time()
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": p.returncode,
            "stdout": p.stdout[-10000:],
            "stderr": p.stderr[-10000:],
            "segundos": round(time.time() - ini, 2),
        }
    except Exception as e:
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": 999,
            "stdout": "",
            "stderr": str(e),
            "segundos": round(time.time() - ini, 2),
        }


def rodar_validacoes(sandbox: Path) -> dict:
    sistema = sandbox / "sistema"
    return {
        "auditoria_total": run_cmd([sys.executable, "-m", "ururau_ai_auditor.run_auditoria"], sistema, timeout=420),
        "testes_contrato": run_cmd([sys.executable, "-m", "unittest", "discover", "-s", "tests_contrato", "-p", "test_*.py", "-v"], sistema, timeout=300),
    }


def salvar_relatorio(root: Path, dados: dict) -> Path:
    pasta = root / "sistema" / "relatorios_auditoria"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / ("sandbox_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return arq


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cria sandbox do projeto e roda auditoria/testes de contrato.")
    parser.add_argument("--destino", default="", help="Pasta de destino do sandbox. Padrao: ao lado do projeto.")
    parser.add_argument("--sem-validar", action="store_true", help="Apenas cria sandbox, sem rodar testes.")
    args = parser.parse_args(argv)

    root = raiz_projeto()
    destino = Path(args.destino).resolve() if args.destino else root.parent / (root.name + "_SANDBOX_AUDITOR")

    dados = {
        "root": str(root),
        "sandbox": str(destino),
        "copia": copiar_sandbox(root, destino),
        "validacoes": {},
    }
    if not args.sem_validar:
        dados["validacoes"] = rodar_validacoes(destino)
    relatorio = salvar_relatorio(root, dados)
    print(json.dumps({
        "sandbox": str(destino),
        "relatorio": str(relatorio),
        "auditoria_returncode": dados.get("validacoes", {}).get("auditoria_total", {}).get("returncode"),
        "testes_returncode": dados.get("validacoes", {}).get("testes_contrato", {}).get("returncode"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
