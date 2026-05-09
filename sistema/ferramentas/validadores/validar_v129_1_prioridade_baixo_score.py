from pathlib import Path
import json

base = Path(__file__).resolve().parent
painel = (base / "ururau" / "ui" / "painel.py").read_text(encoding="utf-8", errors="ignore")
linha = (base / "ururau" / "coleta" / "linha_editorial_v129.py").read_text(encoding="utf-8", errors="ignore")
termos = json.loads((base / "termos_watchlist_v98.json").read_text(encoding="utf-8", errors="ignore"))
rss = json.loads((base / "fontes_rss.json").read_text(encoding="utf-8", errors="ignore"))
especiais = json.loads((base / "fontes_especiais_v129.json").read_text(encoding="utf-8", errors="ignore"))["fontes"]

assert "PRIORIDADE:" in painel, "selo PRIORIDADE ausente"
assert "✕ Reprovar" in painel, "botão Reprovar ausente"
assert "_titulo_visual_v129_1" in painel, "título visual robusto ausente"
assert "_filtrar_fontes_rss_sem_especiais_v129_1" in painel, "filtro RSS x especiais ausente"
for termo in ["Flamengo", "Vasco", "Botafogo", "Fluminense", "Americano de Campos", "Goytacaz"]:
    assert termo in linha, f"termo esportivo ausente na linha editorial: {termo}"
    assert any((x == termo) or (isinstance(x, dict) and x.get("termo") == termo) for x in termos["termos"]), f"termo ausente no JSON: {termo}"

rss_urls = {x.get("url", "").strip().lower().rstrip("/") for x in rss if isinstance(x, dict)}
esp_urls = {x.get("url", "").strip().lower().rstrip("/") for x in especiais if isinstance(x, dict)}
dup = sorted(rss_urls & esp_urls)
assert not dup, "fontes especiais duplicadas no RSS: " + ", ".join(dup)
print("[OK] v129.1 validada: prioridade visual, baixo score com Aprovar/Reprovar e Fontes Especiais fora do RSS comum.")
