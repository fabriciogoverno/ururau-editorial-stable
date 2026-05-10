# -*- coding: utf-8 -*-
"""
Sandbox inteligente para validar patches antes de aplicar.
Roda testes de contrato e compara métricas antes/depois.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union


class SandboxML:
    """Valida patch em ambiente isolado antes de merge."""

    def __init__(self, root: Union[str, Path] = "."):
        self.root = Path(root)
        self.sandbox_dir = self.root / "sandbox_ml"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._relatorio_path = self.root / "dados_ml" / "sandbox_relatorios.jsonl"
        self._relatorio_path.parent.mkdir(parents=True, exist_ok=True)

    def _snapshot_projeto(self, destino: Path):
        """Copia o projeto inteiro para a sandbox."""
        import shutil
        for item in self.root.iterdir():
            if item.name in ("sandbox_ml", "dados_ml", "modelos_ml", ".git", "__pycache__"):
                continue
            dst = destino / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)

    def _run_tests(self, sandbox: Path) -> Dict[str, any]:
        """Roda os testes de contrato na sandbox."""
        bat = sandbox / "31_TESTES_CONTRATO.bat"
        if not bat.exists():
            return {"testes_existem": False, "passou": False, "output": "31_TESTES_CONTRATO.bat nao encontrado"}

        try:
            r = subprocess.run(
                [str(bat)],
                cwd=str(sandbox),
                capture_output=True,
                text=True,
                timeout=300,
                shell=True,
                encoding="utf-8",
                errors="replace"
            )
            passou = r.returncode == 0 and "PASSOU" in r.stdout.upper()
            return {
                "testes_existem": True,
                "passou": passou,
                "returncode": r.returncode,
                "stdout": r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout,
                "stderr": r.stderr[-1000:] if len(r.stderr) > 1000 else r.stderr
            }
        except subprocess.TimeoutExpired:
            return {"testes_existem": True, "passou": False, "output": "TIMEOUT apos 300s"}
        except Exception as e:
            return {"testes_existem": True, "passou": False, "output": str(e)}

    def _run_syntax_check(self, sandbox: Path) -> Dict[str, any]:
        """Verifica sintaxe Python de todos os .py na sandbox."""
        erros = []
        for pyfile in sandbox.rglob("*.py"):
            try:
                compile(pyfile.read_text(encoding="utf-8"), str(pyfile), "exec")
            except SyntaxError as e:
                erros.append({"arquivo": str(pyfile.relative_to(sandbox)), "erro": str(e)})
        return {"sintaxe_ok": len(erros) == 0, "erros": erros}

    def validar_patch(self, filepath: Union[str, Path], patch: Dict[str, str]) -> Dict[str, any]:
        """
        Aplica patch em sandbox, valida e retorna laudo.
        patch = {"original": str, "patched": str, "explicacao": str, "fonte": str}
        """
        import shutil
        import time

        ts = int(time.time())
        sandbox = self.sandbox_dir / f"run_{ts}"
        sandbox.mkdir(parents=True, exist_ok=True)

        laudo = {
            "timestamp": ts,
            "arquivo": str(filepath),
            "explicacao_patch": patch.get("explicacao", ""),
            "fonte_patch": patch.get("fonte", ""),
            "sintaxe_pre": None,
            "sintaxe_pos": None,
            "testes_pre": None,
            "testes_pos": None,
            "aprovado": False,
            "motivo_rejeicao": None
        }

        # 1. Snapshot
        self._snapshot_projeto(sandbox)

        # 2. Sintaxe PRE (original)
        laudo["sintaxe_pre"] = self._run_syntax_check(sandbox)

        # 3. Testes PRE (original)
        laudo["testes_pre"] = self._run_tests(sandbox)

        # 4. Aplica patch
        target = sandbox / Path(filepath).relative_to(self.root)
        if target.exists():
            target.write_text(patch["patched"], encoding="utf-8")
        else:
            laudo["motivo_rejeicao"] = "Arquivo alvo nao encontrado na sandbox"
            self._log(laudo)
            shutil.rmtree(sandbox, ignore_errors=True)
            return laudo

        # 5. Sintaxe POS (patched)
        laudo["sintaxe_pos"] = self._run_syntax_check(sandbox)
        if not laudo["sintaxe_pos"]["sintaxe_ok"]:
            laudo["motivo_rejeicao"] = "Patch introduziu erro de sintaxe"
            self._log(laudo)
            shutil.rmtree(sandbox, ignore_errors=True)
            return laudo

        # 6. Testes POS (patched)
        laudo["testes_pos"] = self._run_tests(sandbox)
        if not laudo["testes_pos"].get("passou", False):
            laudo["motivo_rejeicao"] = "Testes de contrato falharam apos patch"
            self._log(laudo)
            shutil.rmtree(sandbox, ignore_errors=True)
            return laudo

        # 7. Aprovado
        laudo["aprovado"] = True
        self._log(laudo)
        shutil.rmtree(sandbox, ignore_errors=True)
        return laudo

    def _log(self, laudo: Dict):
        with open(self._relatorio_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(laudo, ensure_ascii=False, default=str) + "
")
