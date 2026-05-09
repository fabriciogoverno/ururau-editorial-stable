from pathlib import Path
import json
import importlib

ROOT = Path(__file__).resolve().parent

checks = []

def ok(name, cond, detail=""):
    checks.append((name, bool(cond), detail))

# 1. módulos importáveis
mods = [
    "ururau.coleta.fontes_links_v43",
    "ururau.editorial.memoria_operacional_v43",
    "ururau.ui.patch_v43_premium",
]
for m in mods:
    try:
        importlib.import_module(m)
        ok(f"import {m}", True)
    except Exception as e:
        ok(f"import {m}", False, str(e))

# 2. fonte única
try:
    from ururau.coleta.fontes_links_v43 import consolidar_fontes_links_v43, fontes_links_path
    data = consolidar_fontes_links_v43()
    ok("fontes_links.json gerado", fontes_links_path().exists(), str(fontes_links_path()))
    ok("fontes_links possui itens", len(data.get("items", [])) > 0, data.get("summary"))
except Exception as e:
    ok("fonte única", False, str(e))

# 3. memória editorial
try:
    from ururau.editorial.memoria_operacional_v43 import registrar_decisao_v43, bonus_pauta_v43, path_memoria
    registrar_decisao_v43("aprovar", {"titulo_origem":"Teste Campos", "fonte_nome":"J3 News", "canal_forcado":"Polícia"})
    b = bonus_pauta_v43({"titulo_origem":"Campos", "fonte_nome":"J3 News", "canal_forcado":"Polícia"})
    ok("memória operacional criada", path_memoria().exists(), str(path_memoria()))
    ok("bonus memória inteiro", isinstance(b, int), b)
except Exception as e:
    ok("memória operacional", False, str(e))

# 4. painel importável com patch aplicado
try:
    import ururau.ui.painel as painel
    ok("PainelUrurau com V43", hasattr(painel.PainelUrurau, "_v43_build_top_header"))
except Exception as e:
    ok("painel importável", False, str(e))

fail = [c for c in checks if not c[1]]
print("VALIDAÇÃO V43 PREMIUM")
print("="*70)
for name, passed, detail in checks:
    print(("[OK] " if passed else "[ERRO] ") + name + (f" | {detail}" if detail else ""))
print("="*70)
if fail:
    raise SystemExit(1)
print("Tudo validado.")
