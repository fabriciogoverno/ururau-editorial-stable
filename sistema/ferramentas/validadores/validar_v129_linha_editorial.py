from __future__ import annotations

from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parent

arquivos = [
    ROOT / "ururau/coleta/linha_editorial_v129.py",
    ROOT / "ururau/coleta/termos_config_v98.py",
    ROOT / "ururau/coleta/source_policy_v114.py",
    ROOT / "ururau/coleta/scoring.py",
    ROOT / "ururau/coleta/coleta_auditoria_v126.py",
    ROOT / "ururau/ui/painel.py",
]

for arq in arquivos:
    ast.parse(arq.read_text(encoding="utf-8", errors="ignore"), filename=str(arq))

painel = (ROOT / "ururau/ui/painel.py").read_text(encoding="utf-8", errors="ignore")
assert "Fontes Especiais" in painel
assert "baixo_score" in painel
assert "bypass_score" in painel
assert "Baixo score para avaliação" in painel

scoring = (ROOT / "ururau/coleta/scoring.py").read_text(encoding="utf-8", errors="ignore")
assert "analisar_texto_linha_editorial_v129" in scoring

termos = json.loads((ROOT / "termos_watchlist_v98.json").read_text(encoding="utf-8"))
assert len(termos.get("termos", [])) >= 100
for termo in ["Rodrigo Bacellar", "Wladimir Garotinho", "Campos dos Goytacazes", "Alerj", "STF", "Senado"]:
    assert termo in termos.get("termos", [])

fontes = json.loads((ROOT / "fontes_especiais_v129.json").read_text(encoding="utf-8"))
assert len(fontes.get("fontes", [])) >= 4
for nome in ["STF", "TSE", "Gov.br", "Senado"]:
    assert any(f.get("nome") == nome for f in fontes.get("fontes", []))

print("[OK] v129 validada: linha editorial ampliada, Fontes Especiais e baixo score auditável.")
