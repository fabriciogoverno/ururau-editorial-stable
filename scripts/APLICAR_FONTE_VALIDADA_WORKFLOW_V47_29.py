# -*- coding: utf-8 -*-
"""Instala o gate FonteValidada V47.29 no workflow real.

Este script altera localmente `sistema/ururau/publisher/workflow.py` adicionando,
ao final do arquivo, uma chamada para instalar o patch runtime.
"""
from pathlib import Path
import shutil
import subprocess
import sys

cwd = Path.cwd().resolve()
base = None
for p in [cwd] + list(cwd.parents):
    if (p / "sistema").is_dir():
        base = p
        break
if base is None:
    raise SystemExit("Rode na raiz do projeto, acima da pasta sistema.")

workflow = base / "sistema" / "ururau" / "publisher" / "workflow.py"
if not workflow.exists():
    raise SystemExit("workflow.py nao encontrado: " + str(workflow))

texto = workflow.read_text(encoding="utf-8", errors="ignore")
marcador = "# PATCH_V47_29_FONTE_VALIDADA_WORKFLOW"
bloco = r'''

# PATCH_V47_29_FONTE_VALIDADA_WORKFLOW
try:
    from ururau.publisher.workflow_fonte_validada_v47_29 import instalar_workflow_fonte_validada_v47_29 as _v4729_install_fonte_validada
    _v4729_install_fonte_validada(WorkflowPublicacao)
except Exception as _e_v4729_fonte_validada:
    try:
        print(f"[V47.29][FONTE_VALIDADA][AVISO] patch nao aplicado: {_e_v4729_fonte_validada}")
    except Exception:
        pass
'''

if marcador not in texto:
    backup = workflow.with_suffix(workflow.suffix + ".bak_v47_29")
    if not backup.exists():
        shutil.copy2(workflow, backup)
    workflow.write_text(texto.rstrip() + bloco + "\n", encoding="utf-8")
    print("[OK] workflow.py atualizado com FonteValidada V47.29")
else:
    print("[OK] workflow.py ja tinha FonteValidada V47.29")

r = subprocess.run([sys.executable, "-m", "py_compile", str(workflow)])
if r.returncode != 0:
    raise SystemExit(r.returncode)
print("[OK] workflow.py compila")
