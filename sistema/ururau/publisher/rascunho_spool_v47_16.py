# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import json, time, re

def _sistema_root():
    p = Path(__file__).resolve()
    for parent in p.parents:
        if parent.name == 'sistema': return parent
    return Path.cwd()

def _safe(obj):
    try:
        if hasattr(obj, 'to_dict'): return obj.to_dict()
        if isinstance(obj, dict): return obj
        return {k: getattr(obj, k) for k in dir(obj) if not k.startswith('_') and k in {'titulo','subtitulo','corpo','canal','tags','retranca','chamada_social','score_risco'}}
    except Exception:
        return {'repr': repr(obj)}

def salvar_rascunho_spool(uid, pauta, materia, imagem=None, motivo='cms_falhou'):
    root = _sistema_root()
    pasta = root / 'dados' / 'rascunhos_monitor'
    pasta.mkdir(parents=True, exist_ok=True)
    m = _safe(materia)
    p = dict(pauta or {})
    titulo = str(m.get('titulo') or p.get('titulo_origem') or 'rascunho').strip()
    slug = re.sub(r'[^a-zA-Z0-9_-]+','-', titulo)[:80].strip('-') or str(uid)[:8]
    item = {
        'uid': uid,
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'motivo': motivo,
        'titulo': titulo,
        'link_origem': p.get('link_origem'),
        'fonte_nome': p.get('fonte_nome') or p.get('nome_fonte'),
        'pauta': p,
        'materia': m,
        'imagem': _safe(imagem) if imagem else None,
        'status_pipeline': 'rascunho_spool_local',
    }
    json_path = pasta / f'{time.strftime("%Y%m%d_%H%M%S")}_{slug}.json'
    json_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
    index = pasta / 'index.jsonl'
    with index.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'uid': uid, 'titulo': titulo, 'arquivo': str(json_path), 'motivo': motivo, 'ts': item['ts']}, ensure_ascii=False) + '\n')
    return str(json_path)
