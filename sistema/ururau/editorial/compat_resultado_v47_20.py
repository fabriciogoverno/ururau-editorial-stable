# -*- coding: utf-8 -*-
from __future__ import annotations

class AttrDict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as e:
            raise AttributeError(key) from e
    def __setattr__(self, key, value):
        self[key] = value

def compat_obj(v):
    if isinstance(v, AttrDict):
        return v
    if isinstance(v, dict):
        return AttrDict({k: compat_obj(x) for k, x in v.items()})
    if isinstance(v, list):
        return [compat_obj(x) for x in v]
    return v

def getv(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def get_bool(obj, key, default=False):
    v = getv(obj, key, default)
    if isinstance(v, str):
        return v.strip().lower() in {'1','true','sim','yes','aprovado','bloqueado'}
    return bool(v)

def get_score(obj, default=0):
    for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
        v = getv(obj, k, None)
        if v is not None and str(v).strip() != '':
            try:
                return int(float(v))
            except Exception:
                pass
    return int(default)
