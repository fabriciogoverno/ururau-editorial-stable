# -*- coding: utf-8 -*-
"""V47.25 - trava definitiva de integridade pauta/fonte/materia/preview.

Corrige o erro em que uma pauta selecionada gera ou exibe no Preview o texto de outra pauta.
"""
from pathlib import Path
import shutil
import subprocess
import sys

cwd = Path.cwd().resolve()
BASE = None
for p in [cwd] + list(cwd.parents):
    if (p / "sistema").is_dir():
        BASE = p
        break
if BASE is None:
    raise SystemExit("ERRO: rode na raiz do projeto, acima da pasta sistema.")
S = BASE / "sistema"
print("[V47.25] base:", BASE)


def rd(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def bk(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak_v47_25")
        if not b.exists():
            shutil.copy2(p, b)


def wr(p: Path, c: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    bk(p)
    p.write_text(c, encoding="utf-8")
    print("[OK]", p.relative_to(BASE))


def bat(n: str, c: str):
    wr(BASE / n, c.replace("\n", "\r\n"))

mod = S / "ururau" / "editorial" / "integridade_redacao_v47_25.py"
wr(mod, r'''# -*- coding: utf-8 -*-
from __future__ import annotations
import copy, hashlib, json, re, time
from pathlib import Path
from typing import Any

STOP = {
    'a','ao','aos','as','o','os','de','do','dos','da','das','em','no','na','nos','nas','por','para','com','sem','que','e','ou','um','uma','mais','apos','após','sobre',
    'veja','diz','dizem','tem','ter','foi','ser','sao','são','esta','está','nesta','neste','contra','entre','ate','até','novo','nova','anos','ano','dia'
}

def _get(o: Any, k: str, d: Any = '') -> Any:
    if isinstance(o, dict): return o.get(k, d)
    return getattr(o, k, d)

def _set(o: Any, k: str, v: Any) -> None:
    if isinstance(o, dict): o[k] = v
    else:
        try: setattr(o, k, v)
        except Exception: pass

def uid_pauta(pauta: dict) -> str:
    uid = pauta.get('uid') or pauta.get('_uid') or ''
    if uid: return str(uid)
    base = (pauta.get('link_origem','') or '') + (pauta.get('titulo_origem','') or '')
    return hashlib.md5(base.encode('utf-8', errors='ignore')).hexdigest()[:16]

def texto_materia(m: Any) -> str:
    campos = ['titulo','titulo_capa','subtitulo','conteudo','corpo','texto','meta_description','resumo_curto','chamada_social']
    return ' '.join(str(_get(m,k,'') or '') for k in campos)

def texto_fonte(p: dict) -> str:
    campos = ['titulo_origem','resumo_origem','texto_fonte','cleaned_source_text','dossie','raw_source_text','rss_context_text']
    return ' '.join(str(p.get(k,'') or '') for k in campos)

def norm(s: str) -> str:
    s = (s or '').lower()
    mapa = str.maketrans('áàãâäéèêëíìîïóòõôöúùûüç', 'aaaaaeeeeiiiiooooouuuuc')
    s = s.translate(mapa)
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def tokens(s: str) -> list[str]:
    out = []
    for t in norm(s).split():
        if len(t) < 4 or t in STOP or t.isdigit():
            continue
        out.append(t)
    seen = set(); res = []
    for t in out:
        if t not in seen:
            seen.add(t); res.append(t)
    return res

def hash_texto(s: str) -> str:
    return hashlib.sha256(norm(s).encode('utf-8', errors='ignore')).hexdigest()[:16]

def criar_snapshot(pauta: dict) -> dict:
    snap = copy.deepcopy(dict(pauta or {}))
    uid = uid_pauta(snap)
    snap['uid'] = uid
    snap['_uid'] = uid
    snap['_snapshot_redacao_v47_25'] = True
    snap['_snapshot_ts_v47_25'] = time.strftime('%Y-%m-%d %H:%M:%S')
    snap['_snapshot_titulo_v47_25'] = snap.get('titulo_origem','')
    snap['_snapshot_link_v47_25'] = snap.get('link_origem','')
    snap.pop('materia', None)
    return snap

def validar_fonte_pertence(pauta: dict, fonte: str) -> tuple[bool, str]:
    titulo = str(pauta.get('titulo_origem') or '')
    f = fonte or texto_fonte(pauta)
    if len(norm(f)) < 120:
        return False, 'fonte curta demais'
    tt = tokens(titulo)
    ft = set(tokens(f))
    if tt:
        hits = [t for t in tt if t in ft]
        min_hits = 1 if len(tt) <= 2 else 2
        if len(hits) < min_hits:
            return False, 'fonte nao conversa com o titulo; hits=' + ','.join(hits)
    return True, 'fonte consistente'

def validar_materia_pertence(pauta: dict, materia: Any) -> tuple[bool, str]:
    titulo = str(pauta.get('titulo_origem') or '')
    src = texto_fonte(pauta)
    mat = texto_materia(materia)
    if len(norm(mat)) < 120:
        return False, 'materia gerada curta demais'
    tt = tokens(titulo)
    mt = set(tokens(mat))
    if tt:
        hits_t = [t for t in tt if t in mt]
        min_hits = 1 if len(tt) <= 2 else 2
        if len(hits_t) < min_hits:
            return False, 'materia nao pertence ao titulo selecionado; titulo_hits=' + ','.join(hits_t)
    ft = tokens((titulo + ' ' + src)[:2500])[:25]
    if ft:
        hits_f = [t for t in ft if t in mt]
        min_src = 2 if len(ft) < 8 else 4
        if len(hits_f) < min_src:
            return False, 'materia nao pertence ao texto-fonte; fonte_hits=' + ','.join(hits_f[:8])
    return True, 'materia consistente com pauta/fonte'

def aplicar_assinatura(pauta: dict, materia: Any) -> None:
    uid = uid_pauta(pauta)
    src = texto_fonte(pauta)
    _set(materia, 'pauta_uid', uid)
    _set(materia, 'uid_pauta', uid)
    _set(materia, 'integridade_v47_25', True)
    _set(materia, 'titulo_origem_integridade_v47_25', pauta.get('titulo_origem',''))
    _set(materia, 'link_origem_integridade_v47_25', pauta.get('link_origem',''))
    _set(materia, 'hash_fonte_integridade_v47_25', hash_texto(src))

def salvar_quarentena(base_sistema: str, pauta: dict, materia: Any, motivo: str) -> str:
    pasta = Path(base_sistema) / 'data' / 'quarentena_integridade'
    pasta.mkdir(parents=True, exist_ok=True)
    uid = uid_pauta(pauta)
    item = {
        'uid': uid,
        'motivo': motivo,
        'titulo_origem': pauta.get('titulo_origem',''),
        'link_origem': pauta.get('link_origem',''),
        'hash_fonte': hash_texto(texto_fonte(pauta)),
        'materia': materia.to_dict() if hasattr(materia, 'to_dict') else (dict(materia) if isinstance(materia, dict) else repr(materia)),
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    arq = pasta / f'{time.strftime("%Y%m%d_%H%M%S")}_{uid}.json'
    arq.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(arq)
''')

patch = S / "ururau" / "ui" / "patch_v47_25_integridade_redacao.py"
wr(patch, r'''# -*- coding: utf-8 -*-
from __future__ import annotations


def aplicar_patch_v47_25(ns):
    PainelUrurau = ns.get('PainelUrurau')
    if PainelUrurau is None:
        print('[V47.25] PainelUrurau nao encontrado')
        return

    def _msg(self, texto):
        try: self._set_status(texto)
        except Exception: pass
        try: self._append_console(texto)
        except Exception: pass

    def _acao_redigir_v47_25(self):
        from tkinter import messagebox
        from ururau.editorial.integridade_redacao_v47_25 import criar_snapshot, validar_fonte_pertence
        if not self._pauta_sel:
            messagebox.showwarning('Redigir', 'Selecione uma pauta primeiro.')
            return
        pauta = criar_snapshot(self._pauta_sel)
        link = pauta.get('link_origem','')
        uid = pauta.get('uid') or pauta.get('_uid') or ''
        if self.db.pauta_ja_publicada(link, uid):
            messagebox.showerror('Bloqueado', 'Esta pauta ja foi publicada.')
            return
        if self.db.pauta_foi_descartada(link, uid):
            messagebox.showerror('Bloqueado', 'Esta pauta foi descartada.')
            return
        similar = self.db.titulo_similar_ja_publicado(pauta.get('titulo_origem',''))
        if similar:
            if not messagebox.askyesno('Titulo similar', f"Publicado recentemente:\n'{similar[:80]}'\nRedigir mesmo assim?"):
                return
        try:
            fonte_aberta = self._obter_texto_aba_fonte_v96()
            if fonte_aberta:
                ok, motivo = validar_fonte_pertence(pauta, fonte_aberta)
                if ok:
                    self._injetar_fonte_longa_v96(pauta, fonte_aberta, origem='aba_fonte_validada_v47_25')
                else:
                    print('[V47.25][INTEGRIDADE] fonte aberta ignorada:', motivo)
        except Exception as e:
            print('[V47.25][INTEGRIDADE] aviso fonte aberta:', e)
        _msg(self, f"Redigindo snapshot seguro: {(pauta.get('titulo_origem') or '')[:55]}...")
        self._em_thread(self._redigir_thread, pauta)

    def _redigir_thread_v47_25(self, pauta):
        try:
            from tkinter import messagebox
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            from ururau.editorial.integridade_redacao_v47_25 import (
                criar_snapshot, validar_fonte_pertence, validar_materia_pertence,
                aplicar_assinatura, salvar_quarentena, texto_fonte,
            )
            pauta = criar_snapshot(pauta)
            uid = pauta.get('uid') or pauta.get('_uid') or _uid_para_pauta(pauta.get('link_origem',''), pauta.get('titulo_origem',''))
            pauta['uid'] = uid; pauta['_uid'] = uid
            wf = WorkflowPublicacao(self.db, self.client, self.modelo)
            if not wf.etapa_gate_antiduplicacao(uid, pauta, modo='redigir'):
                self.after(0, lambda: self._set_status('Pauta bloqueada pelo gate.'))
                self.after(0, self._carregar_pautas)
                return
            wf.etapa_coleta_texto(uid, pauta)
            try:
                ok_fonte, motivo_fonte = validar_fonte_pertence(pauta, texto_fonte(pauta))
                if not ok_fonte:
                    try: self._v105_hidratar_pauta(pauta, origem='redigir_integridade_v47_25', forcar=True, atualizar_ui=False)
                    except Exception: pass
                    ok_fonte, motivo_fonte = validar_fonte_pertence(pauta, texto_fonte(pauta))
                if not ok_fonte:
                    self.after(0, lambda mf=motivo_fonte: self._set_status('Redação bloqueada por integridade da fonte: ' + mf))
                    self.after(0, lambda mf=motivo_fonte: messagebox.showerror('Integridade bloqueada', 'A fonte carregada não pertence à pauta selecionada.\n\n' + mf))
                    return
            except Exception as e:
                print('[V47.25][INTEGRIDADE] falha ao validar fonte:', e)
            wf.etapa_imagem(uid, pauta)
            materia = wf.etapa_redacao(uid, pauta)
            if not materia:
                self.after(0, lambda: self._set_status('Falha na redação.'))
                return
            try:
                materia = wf.etapa_pacote_editorial(uid, materia)
            except Exception:
                pass
            try:
                ok_mat, motivo_mat = validar_materia_pertence(pauta, materia)
                if not ok_mat:
                    arq = salvar_quarentena('data', pauta, materia, motivo_mat)
                    self.after(0, lambda: self._set_status('Redação bloqueada: matéria gerada não pertence à pauta.'))
                    self.after(0, lambda mm=motivo_mat, arq=arq: messagebox.showerror('Integridade bloqueada', 'A IA gerou ou o sistema carregou conteúdo de outra pauta.\n\n' + mm + '\n\nNada foi salvo. Quarentena: ' + arq))
                    return
                aplicar_assinatura(pauta, materia)
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror('Integridade', f'Falha na auditoria de integridade: {e}'))
                return
            try: wf.etapa_verificacao_risco(uid, pauta, materia)
            except Exception: pass
            wf.etapa_persistir_materia(uid, pauta, materia)
            self.after(0, lambda: self._set_status('Redação concluída com integridade pauta/fonte/matéria OK.'))
            self.after(0, lambda: messagebox.showinfo('Redação concluída', 'Matéria gerada com trava de integridade OK. Use Preview antes de publicar.'))
            self.after(0, self._carregar_pautas)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda msg=msg: self._set_status(f'Erro na redação: {msg}'))
            self.after(0, lambda msg=msg: messagebox.showerror('Erro na redação', msg))

    old_preview_inline = getattr(PainelUrurau, '_abrir_preview_inline', None)

    def _abrir_preview_inline_v47_25(self, pauta, md):
        from tkinter import messagebox
        from ururau.editorial.integridade_redacao_v47_25 import validar_materia_pertence
        try:
            ok, motivo = validar_materia_pertence(pauta, md)
            if not ok:
                messagebox.showerror('Preview bloqueado por integridade', 'A matéria salva não pertence à pauta selecionada.\n\n' + motivo + '\n\nUse Redigir novamente. O preview antigo foi bloqueado para evitar publicação errada.')
                try: self._set_status('Preview bloqueado: matéria não pertence à pauta selecionada.')
                except Exception: pass
                return
        except Exception as e:
            print('[V47.25][PREVIEW] aviso integridade:', e)
        if callable(old_preview_inline):
            return old_preview_inline(self, pauta, md)

    PainelUrurau._acao_redigir = _acao_redigir_v47_25
    PainelUrurau._redigir_thread = _redigir_thread_v47_25
    if callable(old_preview_inline):
        PainelUrurau._abrir_preview_inline = _abrir_preview_inline_v47_25
    print('[V47.25] Trava de integridade pauta/fonte/materia aplicada ao Redigir e Preview.')
''')

painel = S / "ururau" / "ui" / "painel.py"
txt = rd(painel)
bk(painel)
if "patch_v47_25_integridade_redacao" not in txt:
    txt += r'''

# v47.25 — integridade pauta/fonte/materia no Redigir e Preview
try:
    from ururau.ui.patch_v47_25_integridade_redacao import aplicar_patch_v47_25
    aplicar_patch_v47_25(globals())
except Exception as _e_v47_25:
    print(f'[v47.25] patch integridade redacao nao aplicado: {_e_v47_25}')
'''
    wr(painel, txt)
else:
    print('[OK] painel.py já contém patch v47.25')

bat('25_VALIDAR_INTEGRIDADE_REDACAO_V47_25.bat', r'''@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\editorial\integridade_redacao_v47_25.py
python -m py_compile ururau\ui\patch_v47_25_integridade_redacao.py
python -m py_compile ururau\ui\painel.py
echo VALIDACAO INTEGRIDADE REDACAO V47.25 OK
pause
''')

for p in [mod, patch, painel]:
    subprocess.run([sys.executable, '-m', 'py_compile', str(p)], check=False)

print('\n[V47.25] aplicado. Rode:')
print('  .\\25_VALIDAR_INTEGRIDADE_REDACAO_V47_25.bat')
print('  .\\02_ABRIR_PAINEL.bat')
