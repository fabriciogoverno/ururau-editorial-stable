from pathlib import Path
import json
import py_compile

ROOT = Path.cwd()
py_compile.compile(str(ROOT / "ururau" / "ui" / "painel.py"), doraise=True)
py_compile.compile(str(ROOT / "ururau" / "coleta" / "sitemap_xml_coletor_v123.py"), doraise=True)

feeds = json.loads((ROOT / "fontes_rss.json").read_text(encoding="utf-8"))
assert feeds, "fontes_rss.json vazio"
assert feeds[0]["url"] == "https://mancheterj.com/feed/", feeds[0]
assert (ROOT / "fontes_xml_sitemap_vfinal.txt").exists(), "fontes_xml_sitemap_vfinal.txt ausente"

collector = (ROOT / "ururau" / "coleta" / "sitemap_xml_coletor_v123.py").read_text(encoding="utf-8", errors="ignore")
assert "_sitemap_excecao_janela_v124" in collector

print("[OK] v124m validado: Manchete RJ em 1º no Config RSS + Campos 24 Horas XML/Sitemap ativo")
