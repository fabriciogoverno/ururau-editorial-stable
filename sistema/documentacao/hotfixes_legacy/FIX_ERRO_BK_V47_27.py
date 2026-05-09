# -*- coding: utf-8 -*-
"""Corrige o erro NameError: bk is not defined no REPARO_LIMPAR_MATERIA_CONTAMINADA_V47_27.py."""
from pathlib import Path
import subprocess
import sys

cwd = Path.cwd().resolve()
base = None
for p in [cwd] + list(cwd.parents):
    if (p / 'sistema').is_dir():
        base = p
        break
if base is None:
    raise SystemExit('Rode na raiz do projeto, acima da pasta sistema.')

arquivo = base / 'REPARO_LIMPAR_MATERIA_CONTAMINADA_V47_27.py'
if not arquivo.exists():
    raise SystemExit('Arquivo REPARO_LIMPAR_MATERIA_CONTAMINADA_V47_27.py nao encontrado na raiz do projeto.')

txt = arquivo.read_text(encoding='utf-8', errors='ignore')
novo = txt.replace('bk(painel)', 'bk_file(painel)').replace('bk(', 'bk_file(')
if novo != txt:
    arquivo.write_text(novo, encoding='utf-8')
    print('[OK] Corrigido:', arquivo)
else:
    print('[OK] Nada a corrigir ou ja corrigido:', arquivo)

subprocess.run([sys.executable, str(arquivo)], check=False)
