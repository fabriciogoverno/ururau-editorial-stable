# -*- coding: utf-8 -*-
"""
Launcher gráfico do painel Ururau.
Executado por pythonw.exe para abrir somente a interface visual, sem console externo.
Redireciona stdout/stderr para logs/painel_gui.log para não perder diagnóstico.
"""
from __future__ import annotations

import os
import runpy
import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
(BASE / "logs").mkdir(exist_ok=True)
log_path = BASE / "logs" / "painel_gui.log"

try:
    log = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log
    sys.stderr = log
    print("=" * 80)
    print("URURAU v132.2 - painel iniciado via pythonw sem console externo")
    print(f"Diretório: {BASE}")
    print(f"Python: {sys.executable}")
    runpy.run_path(str(BASE / "ururau_painel.py"), run_name="__main__")
except Exception:
    try:
        traceback.print_exc()
    except Exception:
        pass
    # Em modo pythonw não há console para pausar. O erro fica em logs/painel_gui.log.
