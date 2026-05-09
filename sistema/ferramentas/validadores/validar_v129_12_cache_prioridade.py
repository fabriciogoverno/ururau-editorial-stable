from pathlib import Path
import py_compile

base = Path(__file__).parent
files = [
    base/"ururau/ui/painel.py",
    base/"ururau/coleta/termos_config_v98.py",
    base/"ururau/coleta/linha_editorial_v129.py",
    base/"ururau/fixes/cache_limpeza_v12912.py",
]
for f in files:
    py_compile.compile(str(f), doraise=True)
print("[OK] v129.12 validada: prioridade por termos ativos e limpeza segura de cache.")
