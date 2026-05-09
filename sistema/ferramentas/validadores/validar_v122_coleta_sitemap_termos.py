from pathlib import Path
import py_compile

ROOT = Path.cwd()
py_compile.compile(str(ROOT / "ururau" / "ui" / "painel.py"), doraise=True)
py_compile.compile(str(ROOT / "ururau" / "coleta" / "kimi_bridge_v110.py"), doraise=True)
py_compile.compile(str(ROOT / "ururau" / "coleta" / "sitemap_xml_coletor_v123.py"), doraise=True)

txt = (ROOT / "ururau" / "coleta" / "kimi_bridge_v110.py").read_text(encoding="utf-8", errors="ignore")
assert "_dentro_da_janela_compat_v122" in txt
assert "dentro_da_janela(dt, agora, janela=janela)" not in txt

painel = (ROOT / "ururau" / "ui" / "painel.py").read_text(encoding="utf-8", errors="ignore")
assert "fase XML/Sitemap" in painel
assert "_v123_inserir_separadores_coleta" in painel
assert "coleta_lote_label_v123" in painel

print("[OK] v122/v123 validado: Kimi, XML/Sitemap e separadores de coleta integrados")
