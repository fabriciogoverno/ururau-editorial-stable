from pathlib import Path
import json
root=Path(__file__).resolve().parent

def load(rel):
    data=json.loads((root/rel).read_text(encoding="utf-8"))
    return data.get("fontes", data) if isinstance(data, dict) else data

rss=load("fontes_rss.json")
esp=load("fontes_especiais_v129.json")
assert any("nfnoticias.com.br" in (f.get("url","").lower()) and f.get("tipo") == "rss_regional_prioritario_v1304" for f in rss if isinstance(f,dict)), "NF Notícias não está em Fontes RSS como regional prioritário"
assert not any("nfnoticias.com.br" in (f.get("url","").lower()) for f in esp if isinstance(f,dict)), "NF Notícias ainda está em Fontes Especiais genéricas"
text=(root/"ururau/coleta/rss.py").read_text(encoding="utf-8")
assert "_v1304_aplicar_flags_fonte_rss" in text, "flags v130.4 ausentes no RSS"
text2=(root/"ururau/ui/painel.py").read_text(encoding="utf-8")
assert "rss_regional_prioritario_v1304" in text2, "painel não reconhece RSS regional prioritário"
print("[OK] v130.4 validada: NF Notícias usa RSS normal regional prioritário, com bypass de score.")
