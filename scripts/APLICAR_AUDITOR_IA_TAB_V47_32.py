# -*- coding: utf-8 -*-
from pathlib import Path
import shutil
import subprocess
import sys

BASE = None
for p in [Path.cwd().resolve()] + list(Path.cwd().resolve().parents):
    if (p / 'sistema').is_dir():
        BASE = p
        break
if BASE is None:
    raise SystemExit('Rode na raiz do projeto, acima da pasta sistema.')

painel = BASE / 'sistema' / 'ururau' / 'ui' / 'painel.py'
if not painel.exists():
    raise SystemExit('painel.py nao encontrado')

texto = painel.read_text(encoding='utf-8', errors='ignore')
marcador = 'patch_auditor_ia_tab_v47_32'
bloco = r'''

# v47.32 — aba Auditor IA integrada ao painel principal
try:
    from ururau.ui.patch_auditor_ia_tab_v47_32 import aplicar_patch_auditor_ia_tab_v47_32
    aplicar_patch_auditor_ia_tab_v47_32(globals())
except Exception as _e_v47_32:
    print(f'[v47.32] patch Auditor IA nao aplicado: {_e_v47_32}')
'''

if marcador not in texto:
    backup = painel.with_suffix(painel.suffix + '.bak_v47_32')
    if not backup.exists():
        shutil.copy2(painel, backup)
    painel.write_text(texto.rstrip() + bloco + '\n', encoding='utf-8')
    print('[OK] Aba Auditor IA integrada em painel.py')
else:
    print('[OK] painel.py ja contem Auditor IA V47.32')

for target in [painel, BASE / 'sistema' / 'ururau' / 'ui' / 'patch_auditor_ia_tab_v47_32.py']:
    r = subprocess.run([sys.executable, '-m', 'py_compile', str(target)])
    if r.returncode != 0:
        raise SystemExit(r.returncode)
print('[V47.32] instalador concluido')
