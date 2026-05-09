# -*- coding: utf-8 -*-
"""V47.27 - limpa matérias já salvas que não pertencem à pauta.

Uso:
  python REPARO_LIMPAR_MATERIA_CONTAMINADA_V47_27.py
  .\27_VALIDAR_LIMPEZA_CONTAMINADAS_V47_27.bat
  .\02_ABRIR_PAINEL.bat

Por que existe:
O V47.25/V47.26 passam a bloquear novas redações contaminadas, mas não apagam
matérias erradas que já tinham sido salvas antes no banco. O Preview continua
mostrando o conteúdo antigo se ele permanecer persistido.
"""
from pathlib import Path
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time

cwd = Path.cwd().resolve()
BASE = None
for p in [cwd] + list(cwd.parents):
    if (p / "sistema").is_dir():
        BASE = p
        break
if BASE is None:
    raise SystemExit("ERRO: rode na raiz do projeto, acima da pasta sistema.")
S = BASE / "sistema"
print("[V47.27] base:", BASE)


def rd(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def bk_file(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak_v47_27")
        if not b.exists():
            shutil.copy2(p, b)


def wr(p: Path, c: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    bk_file(p)
    p.write_text(c, encoding="utf-8")
    print("[OK]", p.relative_to(BASE))


def bat(name: str, c: str):
    wr(BASE / name, c.replace("\n", "\r\n"))

mod = S / "ururau" / "editorial" / "limpar_contaminadas_v47_27.py"
wr(mod, r'''# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import json, re, shutil, sqlite3, time

STOP = {'a','ao','aos','as','o','os','de','do','dos','da','das','em','no','na','nos','nas','por','para','com','sem','que','e','ou','um','uma','mais','apos','após','sobre','foi','sao','são','esta','está','nesta','neste','vai','ter','tem','abre','inscricoes','inscrições'}

def norm(s: str) -> str:
    s = (s or '').lower()
    mapa = str.maketrans('áàãâäéèêëíìîïóòõôöúùûüç', 'aaaaaeeeeiiiiooooouuuuc')
    s = s.translate(mapa)
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def toks(s: str) -> list[str]:
    out=[]
    for t in norm(s).split():
        if len(t) < 4 or t in STOP or t.isdigit(): continue
        out.append(t)
    seen=set(); res=[]
    for t in out:
        if t not in seen:
            seen.add(t); res.append(t)
    return res

def nums(s: str) -> list[str]:
    return re.findall(r'\b\d+[\d.,]*\b', s or '')

def materia_texto(obj) -> str:
    if isinstance(obj, dict):
        return ' '.join(str(obj.get(k,'') or '') for k in ['titulo','titulo_capa','subtitulo','conteudo','corpo','texto','meta_description','chamada_social','tags'])
    return str(obj or '')

def esta_contaminada(titulo_origem: str, materia: dict | str) -> tuple[bool, str]:
    mt = materia_texto(materia)
    nt = norm(titulo_origem)
    nm = norm(mt)
    # Caso explícito visto no print.
    if any(x in nt for x in ['bolao','mega sena','loteria']) and any(x in nm for x in ['ato futuro','oficina','oficinas','nise silveira','artaud','imersao','pratica cinematografica']):
        return True, 'pauta de loteria com matéria de oficinas/Ato Futuro'
    title_toks = toks(titulo_origem)
    mat_toks = set(toks(mt))
    distinct = [t for t in title_toks if t not in STOP]
    if len(distinct) >= 3:
        hits = [t for t in distinct if t in mat_toks]
        if len(hits) < 2:
            return True, 'matéria não conversa com título; hits=' + ','.join(hits)
    ns = nums(titulo_origem)
    if ns and any(x in nt for x in ['bolao','mega','sena','premio','fatura']):
        if not any(n in set(nums(mt)) for n in ns):
            return True, 'números centrais da pauta não aparecem na matéria'
    return False, 'ok'

def _parse_json(s):
    if not s: return None
    if isinstance(s, dict): return s
    try: return json.loads(s)
    except Exception: return None

def limpar_banco(db_path: str = 'data/ururau.db') -> dict:
    p = Path(db_path)
    if not p.exists():
        return {'ok': False, 'erro': 'db não encontrado: ' + str(p)}
    backup = p.with_suffix('.db.bak_v47_27_' + time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(p, backup)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("select name from sqlite_master where type='table'").fetchall()]
    alteradas=[]; analisadas=0
    for table in tables:
        cols = [r[1] for r in cur.execute(f'PRAGMA table_info({table})').fetchall()]
        if not cols: continue
        titulo_cols = [c for c in cols if c in {'titulo_origem','titulo','titulo_fonte'}]
        materia_cols = [c for c in cols if c in {'materia','materia_json','conteudo','corpo','texto','preview','dados','json'}]
        status_cols = [c for c in cols if c in {'status','status_pipeline'}]
        if not titulo_cols or not materia_cols: continue
        pk = 'uid' if 'uid' in cols else ('id' if 'id' in cols else None)
        select_cols = list(dict.fromkeys(([pk] if pk else []) + titulo_cols + materia_cols + status_cols))
        try:
            rows = cur.execute(f"select {', '.join(select_cols)} from {table}").fetchall()
        except Exception:
            continue
        for row in rows:
            analisadas += 1
            titulo = ''
            for c in titulo_cols:
                titulo = str(row[c] or '')
                if titulo: break
            mat_obj = None; mat_raw = ''
            mat_col = None
            for c in materia_cols:
                val = row[c]
                if val:
                    mat_col = c
                    mat_raw = val if isinstance(val, str) else str(val)
                    mat_obj = _parse_json(mat_raw) or mat_raw
                    break
            if not titulo or not mat_raw: continue
            bad, motivo = esta_contaminada(titulo, mat_obj)
            if not bad: continue
            # Não apaga a pauta, só limpa a matéria/preview/conteúdo contaminado e volta status.
            sets=[]; params=[]
            for c in materia_cols:
                sets.append(f'{c}=?'); params.append('')
            if 'status' in cols:
                sets.append('status=?'); params.append('captada')
            if 'status_pipeline' in cols:
                sets.append('status_pipeline=?'); params.append('aguardando_redacao')
            ident = row[pk] if pk else None
            if pk:
                params.append(ident)
                cur.execute(f"update {table} set {', '.join(sets)} where {pk}=?", params)
            else:
                continue
            alteradas.append({'tabela': table, 'id': ident, 'titulo': titulo[:120], 'motivo': motivo})
    con.commit(); con.close()
    out = {'ok': True, 'backup': str(backup), 'analisadas': analisadas, 'limpas': len(alteradas), 'alteradas': alteradas[:200]}
    Path('data').mkdir(exist_ok=True)
    Path('data/limpeza_contaminadas_v47_27.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return out
''')

runner = S / "LIMPAR_MATERIAS_CONTAMINADAS_V47_27.py"
wr(runner, r'''# -*- coding: utf-8 -*-
from ururau.editorial.limpar_contaminadas_v47_27 import limpar_banco
import json
r = limpar_banco('data/ururau.db')
print(json.dumps(r, ensure_ascii=False, indent=2))
''')

# Patch preview to refuse old contaminated materials.
patch = S / "ururau" / "ui" / "patch_v47_27_preview_guard.py"
wr(patch, r'''# -*- coding: utf-8 -*-
from __future__ import annotations

def aplicar_patch_v47_27(ns):
    PainelUrurau = ns.get('PainelUrurau')
    if PainelUrurau is None:
        print('[V47.27] PainelUrurau não encontrado')
        return
    old_preview = getattr(PainelUrurau, '_abrir_preview_inline', None)
    def _preview_guard(self, pauta, md):
        from tkinter import messagebox
        try:
            from ururau.editorial.limpar_contaminadas_v47_27 import esta_contaminada
            titulo = (pauta or {}).get('titulo_origem') or (pauta or {}).get('titulo') or ''
            bad, motivo = esta_contaminada(titulo, md)
            if bad:
                messagebox.showerror('Preview bloqueado', 'A matéria salva pertence a outra pauta.\n\n' + motivo + '\n\nUse Limpar Contaminadas ou Redigir novamente após limpar.')
                try: self._set_status('Preview bloqueado: matéria contaminada de outra pauta.')
                except Exception: pass
                return
        except Exception as e:
            print('[V47.27][PREVIEW] aviso:', e)
        if callable(old_preview): return old_preview(self, pauta, md)
    if callable(old_preview):
        PainelUrurau._abrir_preview_inline = _preview_guard
    print('[V47.27] Preview agora bloqueia matéria contaminada persistida.')
''')

painel = S / "ururau" / "ui" / "painel.py"
txt = rd(painel)
bk_file(painel)
if "patch_v47_27_preview_guard" not in txt:
    txt += r'''

# v47.27 — bloqueia preview contaminado ja persistido
try:
    from ururau.ui.patch_v47_27_preview_guard import aplicar_patch_v47_27
    aplicar_patch_v47_27(globals())
except Exception as _e_v47_27:
    print(f'[v47.27] patch preview contaminado nao aplicado: {_e_v47_27}')
'''
    wr(painel, txt)

bat('27_VALIDAR_LIMPEZA_CONTAMINADAS_V47_27.bat', r'''@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\editorial\limpar_contaminadas_v47_27.py
python -m py_compile ururau\ui\patch_v47_27_preview_guard.py
python -m py_compile LIMPAR_MATERIAS_CONTAMINADAS_V47_27.py
python -m py_compile ururau\ui\painel.py
echo VALIDACAO LIMPEZA CONTAMINADAS V47.27 OK
pause
''')

bat('27_LIMPAR_MATERIAS_CONTAMINADAS.bat', r'''@echo off
cd /d "%~dp0sistema"
python LIMPAR_MATERIAS_CONTAMINADAS_V47_27.py
pause
''')

for p in [mod, runner, patch, painel]:
    if p.exists():
        subprocess.run([sys.executable, '-m', 'py_compile', str(p)], check=False)

print('\n[V47.27] aplicado.')
print('Rode:')
print('  .\\27_VALIDAR_LIMPEZA_CONTAMINADAS_V47_27.bat')
print('  .\\27_LIMPAR_MATERIAS_CONTAMINADAS.bat')
print('  .\\02_ABRIR_PAINEL.bat')
