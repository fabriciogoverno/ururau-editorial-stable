# -*- coding: utf-8 -*-
from pathlib import Path
import json
import py_compile

BASE = Path(__file__).resolve().parent
painel = BASE / "ururau" / "ui" / "painel.py"
py_compile.compile(str(painel), doraise=True)
py_compile.compile(str(BASE / "CORRIGIR_V129_2_FILA_RSS.py"), doraise=True)

rss = json.loads((BASE / "fontes_rss.json").read_text(encoding="utf-8"))
esp = json.loads((BASE / "fontes_especiais_v129.json").read_text(encoding="utf-8")).get("fontes", [])

assert len(rss) >= 20, f"RSS comum baixo demais: {len(rss)}"
urls_rss = {str(f.get("url","")).strip().lower().rstrip("/") for f in rss}
urls_esp = {str(f.get("url","")).strip().lower().rstrip("/") for f in esp}
dup = urls_rss & urls_esp
assert not dup, f"Fontes especiais duplicadas no RSS: {dup}"

txt = painel.read_text(encoding="utf-8")
assert "import unicodedata" in txt
assert "PRIORIDADE:" in txt
assert "Reprovar" in txt
assert "_fontes_rss_default_v129_2" in txt

print(f"[OK] v129.2 validada: {len(rss)} RSS comuns, {len(esp)} Fontes Especiais, fila corrigida.")
