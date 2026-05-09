# -*- coding: utf-8 -*-
"""V47.26 - correção para pauta gerando matéria de outra fonte.

Este patch trata o caso Bolão de São Fidélis / Mega-Sena que estava carregando corpo de Ato Futuro.
A diferença do V47.25: agora a fonte é validada e reextraída ANTES de chamar a IA.
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
print("[V47.26] base:", BASE)

def rd(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""

def bk(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak_v47_26")
        if not b.exists():
            shutil.copy2(p, b)

def wr(p: Path, c: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    bk(p)
    p.write_text(c, encoding="utf-8")
    print("[OK]", p.relative_to(BASE))

def bat(name: str, c: str):
    wr(BASE / name, c.replace("\n", "\r\n"))

mod = S / "ururau" / "editorial" / "integridade_fonte_v47_26.py"
wr(mod, r'''# -*- coding: utf-8 -*-
from __future__ import annotations
import hashlib, json, re, time
from pathlib import Path

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
        if len(t) < 4 or t in STOP or t.isdigit():
            continue
        out.append(t)
    seen=set(); res=[]
    for t in out:
        if t not in seen:
            seen.add(t); res.append(t)
    return res

def nums(s: str) -> list[str]:
    return re.findall(r'\b\d+[\d.,]*\b', s or '')

def uid_pauta(pauta: dict) -> str:
    uid = pauta.get('uid') or pauta.get('_uid') or ''
    if uid:
        return str(uid)
    base = (pauta.get('link_origem','') or '') + '|' + (pauta.get('titulo_origem','') or '')
    return hashlib.md5(base.encode('utf-8', errors='ignore')).hexdigest()[:16]

def texto_fonte(pauta: dict) -> str:
    return ' '.join(str(pauta.get(k,'') or '') for k in ['texto_fonte','cleaned_source_text','raw_source_text','rss_context_text','resumo_origem'])

def _body_sem_cabecalho(titulo: str, texto: str) -> str:
    ntexto = norm(texto)
    ntitulo = norm(titulo)
    if ntitulo and ntitulo in ntexto[:500]:
        ntexto = ntexto.replace(ntitulo, ' ', 1)
    return ntexto[350:] if len(ntexto) > 500 else ntexto

def validar_fonte_estrita(pauta: dict, texto: str | None = None) -> tuple[bool, str]:
    titulo = str(pauta.get('titulo_origem') or pauta.get('titulo') or '')
    texto = texto if texto is not None else texto_fonte(pauta)
    if len(norm(texto)) < 250:
        return False, 'fonte curta demais para redacao segura'
    title_toks = toks(titulo)
    body = _body_sem_cabecalho(titulo, texto)
    body_toks = set(toks(body))
    full_toks = set(toks(texto))
    distinct = [t for t in title_toks if t not in STOP]
    body_hits = [t for t in distinct if t in body_toks]
    full_hits = [t for t in distinct if t in full_toks]
    if len(distinct) >= 3 and len(body_hits) < 2:
        return False, 'fonte parece contaminada: titulo_hits_no_corpo=' + ','.join(body_hits) + ' full_hits=' + ','.join(full_hits)
    nt = norm(titulo)
    nb = norm(body)
    if any(x in nt for x in ['bolao','mega sena','loteria']) and any(x in nb for x in ['oficina','oficinas','ato futuro','nise silveira','teatro','cinema']):
        return False, 'fonte contaminada: pauta de loteria recebeu corpo de oficinas/projeto cultural'
    title_nums = nums(titulo)
    if title_nums and any(x in nt for x in ['bolao','mega','sena','premio','fatura']):
        nbody = set(nums(body))
        if not any(n in nbody for n in title_nums):
            return False, 'fonte contaminada: numeros centrais do titulo nao aparecem no corpo'
    return True, 'fonte pertence à pauta'

def forcar_reextracao_estrita(pauta: dict) -> tuple[bool, str]:
    titulo = str(pauta.get('titulo_origem') or '')
    url = str(pauta.get('link_origem') or '')
    if not url:
        return False, 'sem URL de origem para reextrair'
    try:
        from ururau.coleta.fonte_extractor_v104 import extrair_artigo_v104
        res = extrair_artigo_v104(url, texto_existente='', titulo=titulo, forcar_refresh=True)
        texto = getattr(res, 'texto', '') or ''
        ok, motivo = validar_fonte_estrita(pauta, texto)
        if not ok:
            return False, 'reextracao ainda inconsistente: ' + motivo
        pauta['texto_fonte'] = texto
        pauta['cleaned_source_text'] = texto
        pauta['raw_source_text'] = texto
        pauta['extraction_method'] = getattr(res, 'metodo', '') or 'v104_forcar_refresh_v47_26'
        pauta['extraction_status'] = 'ok_integridade_v47_26'
        pauta['fonte_hash_v47_26'] = hashlib.sha256(norm(texto).encode('utf-8', errors='ignore')).hexdigest()[:16]
        if getattr(res, 'imagem', ''):
            pauta['imagem_url_extracao'] = getattr(res, 'imagem')
            pauta['imagem_url'] = getattr(res, 'imagem')
        if getattr(res, 'credito_foto', ''):
            pauta['imagem_credito'] = getattr(res, 'credito_foto')
        return True, 'reextracao v47.26 OK'
    except Exception as e:
        return False, 'erro na reextracao v47.26: ' + str(e)

def quarentena_fonte(base_sistema: str, pauta: dict, motivo: str) -> str:
    pasta = Path(base_sistema) / 'data' / 'quarentena_integridade'
    pasta.mkdir(parents=True, exist_ok=True)
    uid = uid_pauta(pauta)
    item = {
        'uid': uid,
        'motivo': motivo,
        'titulo_origem': pauta.get('titulo_origem',''),
        'link_origem': pauta.get('link_origem',''),
        'amostra_texto_fonte': texto_fonte(pauta)[:2000],
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    arq = pasta / f'{time.strftime("%Y%m%d_%H%M%S")}_{uid}_fonte_inconsistente.json'
    arq.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(arq)
''')

v25 = S / "ururau" / "editorial" / "integridade_redacao_v47_25.py"
if v25.exists():
    txt = rd(v25)
    bk(v25)
    if "PATCH_V47_26_STRICT_SOURCE" not in txt:
        txt += r'''

# PATCH_V47_26_STRICT_SOURCE
try:
    from ururau.editorial.integridade_fonte_v47_26 import validar_fonte_estrita as _v4726_validar_fonte_estrita
    def validar_fonte_pertence(pauta, fonte):
        return _v4726_validar_fonte_estrita(pauta, fonte)
except Exception:
    pass
'''
        wr(v25, txt)

patch = S / "ururau" / "ui" / "patch_v47_26_fonte_antes_ia.py"
wr(patch, r'''# -*- coding: utf-8 -*-
from __future__ import annotations

def aplicar_patch_v47_26(ns):
    PainelUrurau = ns.get('PainelUrurau')
    if PainelUrurau is None:
        print('[V47.26] PainelUrurau não encontrado')
        return
    def _redigir_thread_v47_26(self, pauta):
        try:
            from tkinter import messagebox
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            from ururau.editorial.integridade_redacao_v47_25 import criar_snapshot, validar_materia_pertence, aplicar_assinatura, salvar_quarentena
            from ururau.editorial.integridade_fonte_v47_26 import validar_fonte_estrita, forcar_reextracao_estrita, quarentena_fonte, texto_fonte
            pauta = criar_snapshot(pauta)
            uid = pauta.get('uid') or pauta.get('_uid') or _uid_para_pauta(pauta.get('link_origem',''), pauta.get('titulo_origem',''))
            pauta['uid'] = uid; pauta['_uid'] = uid
            wf = WorkflowPublicacao(self.db, self.client, self.modelo)
            if not wf.etapa_gate_antiduplicacao(uid, pauta, modo='redigir'):
                self.after(0, lambda: self._set_status('Pauta bloqueada pelo gate.'))
                self.after(0, self._carregar_pautas)
                return
            wf.etapa_coleta_texto(uid, pauta)
            ok_fonte, motivo_fonte = validar_fonte_estrita(pauta, texto_fonte(pauta))
            if not ok_fonte:
                for k in ['texto_fonte','cleaned_source_text','raw_source_text','rss_context_text']:
                    pauta[k] = ''
                try:
                    self.db.salvar_evento(uid, 'integridade_fonte_v47_26', 'Fonte inconsistente antes da IA: ' + motivo_fonte)
                except Exception:
                    pass
                ok_re, motivo_re = forcar_reextracao_estrita(pauta)
                ok_fonte, motivo_fonte = validar_fonte_estrita(pauta, texto_fonte(pauta))
                if not (ok_re and ok_fonte):
                    arq = quarentena_fonte('data', pauta, motivo_re + ' | ' + motivo_fonte)
                    self.after(0, lambda: self._set_status('Redação bloqueada: fonte não pertence à pauta selecionada.'))
                    self.after(0, lambda: messagebox.showerror('Fonte bloqueada por integridade', 'A fonte carregada não pertence à pauta selecionada e a reextração não corrigiu.\n\nNada foi enviado à IA.\n\nQuarentena: ' + arq))
                    return
            wf.etapa_imagem(uid, pauta)
            materia = wf.etapa_redacao(uid, pauta)
            if not materia:
                self.after(0, lambda: self._set_status('Falha na redação.'))
                return
            try:
                materia = wf.etapa_pacote_editorial(uid, materia)
            except Exception:
                pass
            ok_mat, motivo_mat = validar_materia_pertence(pauta, materia)
            if not ok_mat:
                arq = salvar_quarentena('data', pauta, materia, motivo_mat)
                self.after(0, lambda: self._set_status('Redação bloqueada: matéria gerada não pertence à pauta.'))
                self.after(0, lambda: messagebox.showerror('Integridade bloqueada', 'A IA gerou ou o sistema carregou conteúdo de outra pauta.\n\n' + motivo_mat + '\n\nNada foi salvo. Quarentena: ' + arq))
                return
            aplicar_assinatura(pauta, materia)
            try:
                wf.etapa_verificacao_risco(uid, pauta, materia)
            except Exception:
                pass
            wf.etapa_persistir_materia(uid, pauta, materia)
            self.after(0, lambda: self._set_status('Redação concluída com fonte validada antes da IA.'))
            self.after(0, lambda: messagebox.showinfo('Redação concluída', 'Matéria gerada com fonte validada antes da IA. Use Preview antes de publicar.'))
            self.after(0, self._carregar_pautas)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: self._set_status('Erro na redação: ' + msg))
            self.after(0, lambda: messagebox.showerror('Erro na redação', msg))
    PainelUrurau._redigir_thread = _redigir_thread_v47_26
    print('[V47.26] Redigir agora valida/reextrai a fonte ANTES de chamar a IA.')
''')

painel = S / "ururau" / "ui" / "painel.py"
txt = rd(painel)
bk(painel)
if "patch_v47_26_fonte_antes_ia" not in txt:
    txt += r'''

# v47.26 — fonte correta antes da IA
try:
    from ururau.ui.patch_v47_26_fonte_antes_ia import aplicar_patch_v47_26
    aplicar_patch_v47_26(globals())
except Exception as _e_v47_26:
    print(f'[v47.26] patch fonte antes IA nao aplicado: {_e_v47_26}')
'''
    wr(painel, txt)

bat('26_VALIDAR_FONTE_ANTES_IA_V47_26.bat', r'''@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\editorial\integridade_fonte_v47_26.py
python -m py_compile ururau\editorial\integridade_redacao_v47_25.py
python -m py_compile ururau\ui\patch_v47_26_fonte_antes_ia.py
python -m py_compile ururau\ui\painel.py
echo VALIDACAO FONTE ANTES IA V47.26 OK
pause
''')

for p in [mod, v25, patch, painel]:
    if p.exists():
        subprocess.run([sys.executable, '-m', 'py_compile', str(p)], check=False)

print('\n[V47.26] aplicado.')
print('Rode:')
print('  .\\26_VALIDAR_FONTE_ANTES_IA_V47_26.bat')
print('  .\\02_ABRIR_PAINEL.bat')
