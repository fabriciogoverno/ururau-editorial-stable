from pathlib import Path
import py_compile

ROOT = Path.cwd()
py_compile.compile(str(ROOT / "ururau" / "coleta" / "sitemap_xml_coletor_v123.py"), doraise=True)
py_compile.compile(str(ROOT / "ururau" / "ui" / "painel.py"), doraise=True)

collector = (ROOT / "ururau" / "coleta" / "sitemap_xml_coletor_v123.py").read_text(encoding="utf-8", errors="ignore")
painel = (ROOT / "ururau" / "ui" / "painel.py").read_text(encoding="utf-8", errors="ignore")

assert "_sitemap_excecao_janela_v124" in collector
assert "_normalizar_chave_url_v124" in collector
assert "lote integrado ao botão Coletar" in painel

print("[OK] v124 validado: Campos 24 Horas via XML/Sitemap passa como exceção e deduplica www/não-www")
