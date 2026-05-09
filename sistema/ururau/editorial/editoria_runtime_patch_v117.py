
from __future__ import annotations
import inspect, os
from typing import Any
_PATCHED=False
def _env_bool(k,d=True):
    v=os.getenv(k); return d if v is None else str(v).strip().lower() in {'1','true','yes','sim','on'}
def _aplicar(result: Any) -> Any:
    if not _env_bool('URURAU_EDITORIA_CONTEXTUAL_ATIVA', True): return result
    try:
        from ururau.editorial.classificador_editorial_contextual_v117 import aplicar_editoria_contextual
        if isinstance(result, list):
            return [aplicar_editoria_contextual(x) if isinstance(x, dict) else x for x in result]
        if isinstance(result, tuple) and result and isinstance(result[0], list):
            return ([aplicar_editoria_contextual(x) if isinstance(x, dict) else x for x in result[0]],)+result[1:]
        if isinstance(result, dict):
            if isinstance(result.get('pautas'), list):
                r=dict(result); r['pautas']=[aplicar_editoria_contextual(x) if isinstance(x,dict) else x for x in r['pautas']]; return r
            if 'titulo' in result or 'titulo_origem' in result:
                return aplicar_editoria_contextual(result)
    except Exception as exc:
        print(f'[EDITORIA_V117][AVISO] falha ao classificar: {exc}')
    return result
def _wrap(fn):
    if getattr(fn,'__editoria_v117_wrapped__',False): return fn
    if inspect.iscoroutinefunction(fn):
        async def aw(*a,**kw): return _aplicar(await fn(*a,**kw))
        aw.__editoria_v117_wrapped__=True; return aw
    def sw(*a,**kw): return _aplicar(fn(*a,**kw))
    sw.__editoria_v117_wrapped__=True; return sw
def aplicar_patch_editoria_contextual_v117():
    global _PATCHED
    if _PATCHED: return
    _PATCHED=True
    total=0
    for name in ['ururau.coleta.rss','ururau.coleta.gnews_v111_integrado','ururau.publisher.workflow']:
        try: mod=__import__(name,fromlist=['*'])
        except Exception: continue
        for attr in dir(mod):
            if attr.startswith('_'): continue
            obj=getattr(mod,attr)
            if callable(obj) and any(x in attr.lower() for x in ('colet','pauta','rss','gnews','workflow')):
                try: setattr(mod,attr,_wrap(obj)); total+=1
                except Exception: pass
    print(f'[EDITORIA_V117] classificador contextual ativo; funções envolvidas: {total}')
