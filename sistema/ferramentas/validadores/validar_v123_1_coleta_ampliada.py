from pathlib import Path
import py_compile

ROOT = Path.cwd()
py_compile.compile(str(ROOT / "ururau" / "coleta" / "rss.py"), doraise=True)
py_compile.compile(str(ROOT / "ururau" / "ui" / "painel.py"), doraise=True)
py_compile.compile(str(ROOT / "ururau" / "coleta" / "sitemap_xml_coletor_v123.py"), doraise=True)

rss = (ROOT / "ururau" / "coleta" / "rss.py").read_text(encoding="utf-8", errors="ignore")
painel = (ROOT / "ururau" / "ui" / "painel.py").read_text(encoding="utf-8", errors="ignore")

assert 'URURAU_RSS_MAX_POR_LINK", "10"' in rss
assert "fallback_fora_janela_v123" in rss
assert "_excecao_fora_janela_v123" in rss
assert "permitir_excecao_final_v123" in painel
assert 'URURAU_V92_MAX_POR_FONTE", 10' in painel

print("[OK] v123.1 validado: max 10 por fonte + exceção de 1 fora da janela + sitemap integrado")
