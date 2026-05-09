# -*- coding: utf-8 -*-
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


# PATCH_V47_26_STRICT_SOURCE
try:
    from ururau.editorial.integridade_fonte_v47_26 import validar_fonte_estrita as _v4726_validar_fonte_estrita
    def validar_fonte_pertence(pauta, fonte):
        return _v4726_validar_fonte_estrita(pauta, fonte)
except Exception:
    pass
