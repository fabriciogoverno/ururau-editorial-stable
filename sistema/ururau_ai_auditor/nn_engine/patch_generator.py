# -*- coding: utf-8 -*-
"""
Gerador de patches usando LLM local (Ollama) ou regex heurística.
Gera diff sugerido para erros de sintaxe detectados pelo scanner_codigo.py.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Union


class PatchGenerator:
    """Gera correções para erros de código detectados."""

    def __init__(self, ollama_model: str = "qwen2.5-coder:1.5b"):
        self.ollama_model = ollama_model
        self._ollama_available = self._check_ollama()

    def _check_ollama(self) -> bool:
        try:
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def _ollama_generate(self, prompt: str) -> str:
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

    def generate_for_syntax_error(self, filepath: Union[str, Path], error_msg: str, line_content: str) -> Optional[dict]:
        """Gera patch para SyntaxError. Retorna dict com 'original', 'patched', 'explicacao'."""
        path = Path(filepath)
        if not path.exists():
            return None

        original = path.read_text(encoding="utf-8")

        # Heurística 1: parêntese/colchete/chave não fechado
        fix = self._heuristic_brackets(original, error_msg)
        if fix:
            return {"original": original, "patched": fix, "explicacao": "Heuristica: balanceamento de brackets", "fonte": "heuristica"}

        # Heurística 2: indentação inconsistente
        fix = self._heuristic_indent(original, error_msg)
        if fix:
            return {"original": original, "patched": fix, "explicacao": "Heuristica: correcao de indentacao", "fonte": "heuristica"}

        # Heurística 3: aspas não fechadas
        fix = self._heuristic_quotes(original, error_msg)
        if fix:
            return {"original": original, "patched": fix, "explicacao": "Heuristica: fechamento de aspas", "fonte": "heuristica"}

        # Fallback: LLM local via Ollama
        if self._ollama_available:
            prompt = f"""Voce e um assistente de correcao de codigo Python. 
Apenas responda com o codigo corrigido completo, sem explicacoes extras.

ARQUIVO: {path.name}
ERRO: {error_msg}
LINHA COM ERRO: {line_content}

CODIGO COMPLETO:
```python
{original}
```

Corrija o erro e retorne APENAS o codigo Python corrigido completo.
"""
            patched = self._ollama_generate(prompt)
            if patched and "```python" in patched:
                # Extrai código entre ```python e ```
                match = re.search(r"```python
(.*?)
```", patched, re.DOTALL)
                if match:
                    patched = match.group(1)
            if patched and len(patched) > 50:
                return {"original": original, "patched": patched, "explicacao": f"Gerado por LLM local ({self.ollama_model})", "fonte": "llm"}

        return None

    def _heuristic_brackets(self, code: str, error_msg: str) -> Optional[str]:
        if "unexpected EOF" in error_msg.lower() or "expected ')'" in error_msg.lower():
            # Tenta fechar parênteses/colchetes/chaves pendentes
            open_counts = {
                "(": code.count("("),
                ")": code.count(")"),
                "[": code.count("["),
                "]": code.count("]"),
                "{": code.count("{"),
                "}": code.count("}"),
            }
            missing = ""
            if open_counts["("] > open_counts[")"]: missing += ")" * (open_counts["("] - open_counts[")"])
            if open_counts["["] > open_counts["]"]: missing += "]" * (open_counts["["] - open_counts["]"])
            if open_counts["{"] > open_counts["}"]: missing += "}" * (open_counts["{"] - open_counts["}"])
            if missing:
                return code.rstrip() + "
" + missing
        return None

    def _heuristic_indent(self, code: str, error_msg: str) -> Optional[str]:
        if "indent" in error_msg.lower():
            lines = code.split("
")
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
            return "
".join(fixed)
        return None

    def _heuristic_quotes(self, code: str, error_msg: str) -> Optional[str]:
        if "eol" in error_msg.lower() or "string" in error_msg.lower():
            # Tenta detectar string não fechada na última linha não-vazia
            lines = code.split("
")
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                if line.strip():
                    counts = {""": line.count(""") - line.count("\""), "'": line.count("'") - line.count("\'")}
                    if counts["""] % 2 == 1:
                        lines[i] = line + """
                        return "
".join(lines)
                    if counts["'"] % 2 == 1:
                        lines[i] = line + "'"
                        return "
".join(lines)
                    break
        return None
