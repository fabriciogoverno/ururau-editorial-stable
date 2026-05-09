from __future__ import annotations
import importlib, json, sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path: sys.path.insert(0, str(BASE))
def ok(msg): print(f"[OK] {msg}")
def fail(msg): print(f"[ERRO] {msg}"); raise SystemExit(1)
from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers, status_scrapers
aplicar_defaults_scrapers(forcar=True)
st = status_scrapers()
for grupo in ("coletores", "extratores"):
    desligados = [k for k, v in st[grupo].items() if not v]
    if desligados: fail(f"{grupo} desligados: {', '.join(desligados)}")
    ok(f"{grupo} ativos: {len(st[grupo])}")
mods = ["ururau.coleta.fonte_extractor_v104", "ururau.coleta.fonte_extractor_v86", "ururau.coleta.trafilatura_fallback_v108", "ururau.coleta.kimi_bridge_v110", "ururau.coleta.extract_pipeline_v90", "ururau.publisher.monitor_capacidade_v47_9", "ururau.publisher.monitor"]
for m in mods:
    importlib.import_module(m); ok(f"import {m}")
mod = importlib.import_module("ururau.coleta.fonte_extractor_v104")
for name in ["_extrair_pipeline_v90", "extrair_artigo_v104"]:
    if not hasattr(mod, name): fail(f"fonte_extractor_v104 sem {name}")
ok("v90 pipeline integrado ao v104")
cfg = json.loads((BASE / "config" / "monitor_24h.json").read_text(encoding="utf-8"))
formas = (((cfg.get("extracao_texto") or {}).get("formas_ativas")) or {})
if not formas or not all(bool(v) for v in formas.values()): fail("config/monitor_24h.json não declara todas as formas de extração ativas")
ok(f"config declara formas de extração ativas: {len(formas)}")
print("\nSCRAPERS V47.10: OK — todos os caminhos públicos estão ativos por padrão.")
