# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ururau_ai_auditor.patch_sandbox import copiar_sandbox, rodar_validacoes


def projeto_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run(cmd: list[str], cwd: Path, timeout: int = 600) -> dict:
    try:
        p = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        return {
            "cmd": cmd,
            "cwd": str(cwd),
            "returncode": p.returncode,
            "stdout": p.stdout[-12000:],
            "stderr": p.stderr[-12000:],
        }
    except Exception as e:
        return {"cmd": cmd, "cwd": str(cwd), "returncode": 999, "stdout": "", "stderr": str(e)}


def copiar_script_para_sandbox(script: Path, sandbox: Path) -> Path:
    destino = sandbox / "_patch_sandbox" / script.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(script, destino)
    return destino


def executar_script(script: Path, sandbox: Path) -> dict:
    if script.suffix.lower() == ".py":
        return run([sys.executable, str(script)], sandbox)
    if script.suffix.lower() == ".ps1":
        return run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)], sandbox)
    if script.suffix.lower() in {".bat", ".cmd"}:
        return run(["cmd", "/c", str(script)], sandbox)
    return {"cmd": [str(script)], "cwd": str(sandbox), "returncode": 998, "stdout": "", "stderr": "tipo de script nao suportado"}


def salvar_relatorio(root: Path, dados: dict) -> Path:
    pasta = root / "sistema" / "relatorios_auditoria"
    pasta.mkdir(parents=True, exist_ok=True)
    out = pasta / ("patch_sandbox_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    out.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aplica um patch somente em sandbox e roda validacoes.")
    parser.add_argument("--script", required=True, help="Script .py, .ps1 ou .bat a testar em sandbox")
    parser.add_argument("--destino", default="", help="Diretorio do sandbox")
    args = parser.parse_args(argv)

    root = projeto_root()
    script = Path(args.script).resolve()
    if not script.exists():
        raise SystemExit("Script nao encontrado: " + str(script))

    sandbox = Path(args.destino).resolve() if args.destino else root.parent / (root.name + "_PATCH_SANDBOX")
    dados = {
        "root": str(root),
        "sandbox": str(sandbox),
        "script": str(script),
        "copia": copiar_sandbox(root, sandbox, limpar=True),
        "execucao_patch": {},
        "validacoes": {},
    }
    script_sandbox = copiar_script_para_sandbox(script, sandbox)
    dados["script_sandbox"] = str(script_sandbox)
    dados["execucao_patch"] = executar_script(script_sandbox, sandbox)
    dados["validacoes"] = rodar_validacoes(sandbox)
    rel = salvar_relatorio(root, dados)
    print(json.dumps({
        "relatorio": str(rel),
        "patch_returncode": dados["execucao_patch"].get("returncode"),
        "auditoria_returncode": dados["validacoes"].get("auditoria_total", {}).get("returncode"),
        "testes_returncode": dados["validacoes"].get("testes_contrato", {}).get("returncode"),
    }, ensure_ascii=False, indent=2))
    return 0 if dados["execucao_patch"].get("returncode") == 0 and dados["validacoes"].get("auditoria_total", {}).get("returncode") == 0 and dados["validacoes"].get("testes_contrato", {}).get("returncode") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
