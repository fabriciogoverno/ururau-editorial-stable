# -*- coding: utf-8 -*-
class AttrDict(dict):
    def __getattr__(self,k):
        try: return self[k]
        except KeyError as e: raise AttributeError(k) from e
    def __setattr__(self,k,v): self[k]=v

def compat_obj(v):
    if isinstance(v,dict): return AttrDict({k:compat_obj(x) for k,x in v.items()})
    if isinstance(v,list): return [compat_obj(x) for x in v]
    return v

def getv(o,k,d=None):
    if isinstance(o,dict): return o.get(k,d)
    return getattr(o,k,d)

def get_score(o,d=0):
    for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
        v=getv(o,k,None)
        if v not in (None,''):
            try: return int(float(v))
            except Exception: pass
    return int(d)
