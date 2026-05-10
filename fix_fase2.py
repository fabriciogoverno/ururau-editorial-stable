# -*- coding: utf-8 -*-
"""
fix_fase2.py — Corrige strings multilinha nos arquivos da Fase 2 Neural.
Rode: python fix_fase2.py
"""
from pathlib import Path

BASE = Path(r"C:\Users\fabri\Downloads\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL\PURAL_EDITORIAL_V47_12_PREMIUM_OPERACIONAL")

# ============================================================
# 1. patch_generator.py
# ============================================================
patch_gen = r"""# -*- coding: utf-8 -*-
"""
Gerador de patches usando LLM local (Ollama) ou regex heuristica.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional, Union


class PatchGenerator:
    def __init__(self, ollama_model="qwen2.5-coder:1.5b"):
        self.ollama_model = ollama_model
        self._ollama_available = self._check_ollama()

    def _check_ollama(self):
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def _ollama_generate(self, prompt):
        if not self._ollama_available:
            return ""
        try:
            r = subprocess.run(
                ["ollama", "run", self.ollama_model],
                input=prompt, capture_output=True, text=True, timeout=120, encoding="utf-8"
            )
            return r.stdout.strip()
        except Exception:
            return ""

    def generate_for_syntax_error(self, filepath, error_msg, line_content):
        path = Path(filepath)
        if not path.exists():
            return None
        original = path.read_text(encoding="utf-8")

        fix = self._heuristic_brackets(original, error_msg)
        if fix:
            return {"original": original, "patched": fix, "explicacao": "Heuristica: balanceamento de brackets", "fonte": "heuristica"}

        fix = self._heuristic_indent(original, error_msg)
        if fix:
            return {"original": original, "patched": fix, "explicacao": "Heuristica: correcao de indentacao", "fonte": "heuristica"}

        fix = self._heuristic_quotes(original, error_msg)
        if fix:
            return {"original": original, "patched": fix, "explicacao": "Heuristica: fechamento de aspas", "fonte": "heuristica"}

        if self._ollama_available:
            prompt = (
                "Voce e um assistente de correcao de codigo Python.\n"
                "Apenas responda com o codigo corrigido completo, sem explicacoes extras.\n\n"
                + f"ARQUIVO: {path.name}\n"
                + f"ERRO: {error_msg}\n"
                + f"LINHA COM ERRO: {line_content}\n\n"
                + "CODIGO COMPLETO:\n"
                + "```python\n"
                + original
                + "\n```\n\n"
                + "Corrija o erro e retorne APENAS o codigo Python corrigido completo."
            )
            patched = self._ollama_generate(prompt)
            if patched and "```python" in patched:
                try:
                    match = re.search(r"```python\r?\n(.*?)\r?\n```", patched, re.DOTALL)
                    if match:
                        patched = match.group(1)
                except Exception:
                    pass
            if patched and len(patched) > 50:
                return {
                    "original": original,
                    "patched": patched,
                    "explicacao": f"Gerado por LLM local ({self.ollama_model})",
                    "fonte": "llm"
                }
        return None

    def _heuristic_brackets(self, code, error_msg):
        if "unexpected EOF" in error_msg.lower() or "expected ')'" in error_msg.lower():
            counts = {
                "(": code.count("("),
                ")": code.count(")"),
                "[": code.count("["),
                "]": code.count("]"),
                "{": code.count("{"),
                "}": code.count("}"),
            }
            missing = ""
            if counts["("] > counts[")"]: missing += ")" * (counts["("] - counts[")"])
            if counts["["] > counts["]"]: missing += "]" * (counts["["] - counts["]"])
            if counts["{"] > counts["}"]: missing += "}" * (counts["{"] - counts["}"])
            if missing:
                return code.rstrip() + "\n" + missing
        return None

    def _heuristic_indent(self, code, error_msg):
        if "indent" in error_msg.lower():
            lines = code.split("\n")
            fixed = []
            prev_indent = 0
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("if ") or stripped.startswith("for ") or stripped.startswith("while "):
                    fixed.append(line)
                    prev_indent = len(line) - len(stripped)
                elif stripped and not stripped.startswith("#"):
                    curr_indent = len(line) - len(stripped)
                    if curr_indent != prev_indent and curr_indent != prev_indent + 4:
                        fixed.append(" " * prev_indent + stripped)
                    else:
                        fixed.append(line)
                        if curr_indent > 0:
                            prev_indent = curr_indent
                else:
                    fixed.append(line)
            return "\n".join(fixed)
        return None

    def _heuristic_quotes(self, code, error_msg):
        if "eol" in error_msg.lower() or "string" in error_msg.lower():
            lines = code.split("\n")
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                if line.strip():
                    counts = {
                        "\"": line.count("\"") - line.count("\\\""),
                        "'": line.count("'") - line.count("\\'")
                    }
                    if counts["\""] % 2 == 1:
                        lines[i] = line + "\""
                        return "\n".join(lines)
                    if counts["'"] % 2 == 1:
                        lines[i] = line + "'"
                        return "\n".join(lines)
                    break
        return None
"""

# ============================================================
# 2. sandbox_ml.py
# ============================================================
sandbox = r"""# -*- coding: utf-8 -*-
"""
Sandbox inteligente para validar patches antes de aplicar.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Union


class SandboxML:
    def __init__(self, root="."):
        self.root = Path(root)
        self.sandbox_dir = self.root / "sandbox_ml"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._relatorio_path = self.root / "dados_ml" / "sandbox_relatorios.jsonl"
        self._relatorio_path.parent.mkdir(parents=True, exist_ok=True)

    def _snapshot_projeto(self, destino):
        import shutil
        for item in self.root.iterdir():
            if item.name in ("sandbox_ml", "dados_ml", "modelos_ml", ".git", "__pycache__"):
                continue
            dst = destino / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)

    def _run_tests(self, sandbox):
        bat = sandbox / "31_TESTES_CONTRATO.bat"
        if not bat.exists():
            return {"testes_existem": False, "passou": False, "output": "31_TESTES_CONTRATO.bat nao encontrado"}
        try:
            r = subprocess.run(
                [str(bat)], cwd=str(sandbox), capture_output=True, text=True,
                timeout=300, shell=True, encoding="utf-8", errors="replace"
            )
            passou = r.returncode == 0 and "PASSOU" in r.stdout.upper()
            return {
                "testes_existem": True, "passou": passou, "returncode": r.returncode,
                "stdout": r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout,
                "stderr": r.stderr[-1000:] if len(r.stderr) > 1000 else r.stderr
            }
        except subprocess.TimeoutExpired:
            return {"testes_existem": True, "passou": False, "output": "TIMEOUT apos 300s"}
        except Exception as e:
            return {"testes_existem": True, "passou": False, "output": str(e)}

    def _run_syntax_check(self, sandbox):
        erros = []
        for pyfile in sandbox.rglob("*.py"):
            try:
                compile(pyfile.read_text(encoding="utf-8"), str(pyfile), "exec")
            except SyntaxError as e:
                erros.append({"arquivo": str(pyfile.relative_to(sandbox)), "erro": str(e)})
        return {"sintaxe_ok": len(erros) == 0, "erros": erros}

    def validar_patch(self, filepath, patch):
        import shutil
        import time
        ts = int(time.time())
        sandbox = self.sandbox_dir / f"run_{ts}"
        sandbox.mkdir(parents=True, exist_ok=True)

        laudo = {
            "timestamp": ts, "arquivo": str(filepath),
            "explicacao_patch": patch.get("explicacao", ""),
            "fonte_patch": patch.get("fonte", ""),
            "sintaxe_pre": None, "sintaxe_pos": None,
            "testes_pre": None, "testes_pos": None,
            "aprovado": False, "motivo_rejeicao": None
        }

        self._snapshot_projeto(sandbox)
        laudo["sintaxe_pre"] = self._run_syntax_check(sandbox)
        laudo["testes_pre"] = self._run_tests(sandbox)

        target = sandbox / Path(filepath).relative_to(self.root)
        if target.exists():
            target.write_text(patch["patched"], encoding="utf-8")
        else:
            laudo["motivo_rejeicao"] = "Arquivo alvo nao encontrado na sandbox"
            self._log(laudo)
            shutil.rmtree(sandbox, ignore_errors=True)
            return laudo

        laudo["sintaxe_pos"] = self._run_syntax_check(sandbox)
        if not laudo["sintaxe_pos"]["sintaxe_ok"]:
            laudo["motivo_rejeicao"] = "Patch introduziu erro de sintaxe"
            self._log(laudo)
            shutil.rmtree(sandbox, ignore_errors=True)
            return laudo

        laudo["testes_pos"] = self._run_tests(sandbox)
        if not laudo["testes_pos"].get("passou", False):
            laudo["motivo_rejeicao"] = "Testes de contrato falharam apos patch"
            self._log(laudo)
            shutil.rmtree(sandbox, ignore_errors=True)
            return laudo

        laudo["aprovado"] = True
        self._log(laudo)
        shutil.rmtree(sandbox, ignore_errors=True)
        return laudo

    def _log(self, laudo):
        with open(self._relatorio_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(laudo, ensure_ascii=False, default=str) + "\n")
"""

# ============================================================
# 3. integrador.py
# ============================================================
integrador = r"""# -*- coding: utf-8 -*-
"""
Integrador Fase 2: Liga scanner_codigo.py -> patch_generator -> sandbox -> rollback_guard -> long_term_memory.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ururau_ai_auditor.scanner_codigo import escanear
from ururau_ai_auditor.nn_engine.patch_generator import PatchGenerator
from ururau_ai_auditor.nn_engine.sandbox_ml import SandboxML
from ururau_ai_auditor.nn_engine.rollback_guard import RollbackGuard
from ururau_ai_auditor.nn_engine.long_term_memory import LongTermMemory


class NeuralRepairPipeline:
    def __init__(self, root=None):
        if root is None:
            root = BASE_DIR
        self.root = Path(root)
        self.generator = PatchGenerator()
        self.sandbox = SandboxML(root)
        self.guard = RollbackGuard(root)
        self.memory = LongTermMemory(root)

    def run(self):
        print("=" * 60)
        print("NEURAL REPAIR PIPELINE — FASE 2")
        print("=" * 60)

        print("[1/5] Escaneando codigo...")
        resultados = escanear(str(self.root / "sistema"))
        sintaxe = []
        for r in resultados:
            for erro in r.get("erros", []):
                if "SyntaxError" in erro:
                    sintaxe.append({
                        "arquivo": str(self.root / "sistema" / r["caminho"]),
                        "caminho_rel": r["caminho"],
                        "mensagem": erro,
                        "linhas": r["linhas"]
                    })
        if not sintaxe:
            print("[OK] Nenhum SyntaxError encontrado.")
            return {"acao": "NADA_A_FAZER"}

        print(f"[OK] {len(sintaxe)} SyntaxError(s) detectado(s).")

        erro = sintaxe[0]
        problema = f"{erro['caminho_rel']}: {erro['mensagem']}"
        print(f"[2/5] Buscando memoria para: {problema[:80]}...")
        similares = self.memory.buscar(problema, top_k=1)
        if similares and similares[0]["similaridade"] > 0.85:
            print(f"[OK] Solucao similar encontrada (sim={similares[0]['similaridade']}). Reutilizando...")
            patch = {"original": "", "patched": similares[0]["solucao"], "explicacao": "Reutilizado da memoria", "fonte": "memory"}
        else:
            print("[3/5] Gerando patch novo...")
            patch = self.generator.generate_for_syntax_error(erro["arquivo"], erro["mensagem"], "")

        if not patch:
            print("[ERRO] Nao foi possivel gerar patch.")
            return {"acao": "FALHA_GERACAO"}

        print("[4/5] Validando em sandbox...")
        laudo = self.sandbox.validar_patch(erro["arquivo"], patch)
        if not laudo["aprovado"]:
            print(f"[REJEITADO] {laudo.get('motivo_rejeicao', 'Sem motivo')}")
            return {"acao": "REJEITADO_SANDBOX", "laudo": laudo}

        print("[OK] Sandbox aprovou.")

        safe_name = erro["caminho_rel"].replace("/", "_").replace("\\", "_").replace(":", "_")
        patch_id = f"patch_{safe_name}_{int(time.time())}"
        print(f"[5/5] Aplicando patch ({patch_id})...")
        resultado = self.guard.aplicar_patch(erro["arquivo"], patch, patch_id)
        self.memory.adicionar(problema, patch["patched"], "aplicado", erro["arquivo"], patch_id)

        print("[OK] Patch aplicado. Aguarde 24h para fechamento.")
        return {"acao": "APLICADO", "patch_id": patch_id, "laudo": laudo}


def main() -> int:
    pipe = NeuralRepairPipeline(BASE_DIR)
    r = pipe.run()
    print("=" * 60)
    print(f"RESULTADO: {r['acao']}")
    print("=" * 60)
    return 0 if r["acao"] in ("NADA_A_FAZER", "APLICADO") else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""

# ============================================================
# ESCREVER ARQUIVOS
# ============================================================
def escrever(caminho_relativo, conteudo):
    caminho = BASE / caminho_relativo
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    print(f"[OK] {caminho_relativo} ({len(conteudo)} bytes)")

if __name__ == "__main__":
    print("=" * 60)
    print("FIX FASE 2 — Corrigindo arquivos neural")
    print("=" * 60)
    escrever("sistema/ururau_ai_auditor/nn_engine/patch_generator.py", patch_gen)
    escrever("sistema/ururau_ai_auditor/nn_engine/sandbox_ml.py", sandbox)
    escrever("sistema/ururau_ai_auditor/nn_engine/integrador.py", integrador)
    print("=" * 60)
    print("CONCLUIDO. Rode agora: .\\47_REPARO_NEURAL.bat")
    print("=" * 60)
