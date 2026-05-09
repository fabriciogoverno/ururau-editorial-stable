# -*- coding: utf-8 -*-
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
