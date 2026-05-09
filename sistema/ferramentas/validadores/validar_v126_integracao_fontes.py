from pathlib import Path
import json
import py_compile

ROOT = Path.cwd()

criticos = [
    ROOT / "ururau" / "ui" / "painel.py",
    ROOT / "ururau" / "coleta" / "rss.py",
    ROOT / "ururau" / "coleta" / "fonte_registry_v126.py",
    ROOT / "ururau" / "coleta" / "coleta_auditoria_v126.py",
    ROOT / "ururau" / "coleta" / "adapters" / "campos24horas_v126.py",
]
for p in criticos:
    py_compile.compile(str(p), doraise=True)

painel = (ROOT / "ururau" / "ui" / "painel.py").read_text(encoding="utf-8", errors="ignore")
assert "_diagnostico_coleta_txt_v126" in painel
assert "coleta_auditoria_v126" in painel
assert "campos24horas_v126" in painel

feeds = json.loads((ROOT / "fontes_rss.json").read_text(encoding="utf-8"))
urls = [f.get("url") for f in feeds]
assert "https://mancheterj.com/feed/" in urls
assert "https://campos.rj.gov.br/rss" in urls
assert "https://campos24horas.com.br/portal/feed/" in urls

from ururau.coleta.fonte_registry_v126 import normalizar_nome_fonte_v126
assert normalizar_nome_fonte_v126("https://mancheterj.com/feed/", "errado") == "Manchete RJ"
assert normalizar_nome_fonte_v126("https://mancheterio.com.br/feed/", "errado") == "Manchete Rio"
assert normalizar_nome_fonte_v126("https://campos.rj.gov.br/rss", "errado") == "Prefeitura de Campos"

print("[OK] v126 validado: registry, nomes fixos, Campos24 especial e diagnóstico visual")
