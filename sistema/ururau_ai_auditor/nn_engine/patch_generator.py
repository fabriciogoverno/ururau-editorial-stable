# -*- coding: utf-8 -*-
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
            r = subprocess.run(["ollama", "run", self.ollama_model], input=prompt, capture_output=True, text=True, timeout=120, encoding="utf-8")
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
            return {"original": original, "patched": fix, "explicacao": "Heuristica: brackets", "fonte": "heuristica"}
        fix = self._heuristic_indent(original, error_msg)
        if fix:
            return {"original": original, "patched": fix, "explicacao": "Heuristica: indent", "fonte": "heuristica"}
        fix = self._heuristic_quotes(original, error_msg)
        if fix:
            return {"original": original, "patched": fix, "explicacao": "Heuristica: quotes", "fonte": "heuristica"}
        if self._ollama_available:
            prompt = "Voce e um assistente de correcao de codigo Python. Apenas responda com o codigo corrigido completo. ARQUIVO: " + path.name + " ERRO: " + error_msg + " CODIGO: " + original[:500] + " Corrija e retorne APENAS o codigo Python corrigido."
            patched = self._ollama_generate(prompt)
            if patched and len(patched) > 50:
                return {"original": original, "patched": patched, "explicacao": "LLM local", "fonte": "llm"}
        return None

    def _heuristic_brackets(self, code, error_msg):
        if "unexpected EOF" in error_msg.lower() or "expected" in error_msg.lower():
            counts = {"(": code.count("("), ")": code.count(")"), "[": code.count("["), "]": code.count("]"), "{": code.count("{"), "}": code.count("}")}
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
                    counts = {"\"": line.count("\"") - line.count("\\\""), "'": line.count("'") - line.count("\\'")}
                    if counts["\""] % 2 == 1:
                        lines[i] = line + "\""
                        return "\n".join(lines)
                    if counts["'"] % 2 == 1:
                        lines[i] = line + "'"
                        return "\n".join(lines)
                    break
        return None
