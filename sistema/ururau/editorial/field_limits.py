from __future__ import annotations
try:
    from ururau.editorial.regras_editoriais import limites as _limites
    _L=_limites()
except Exception: _L={}
def _i(k,d):
    try: return int(_L.get(k,d))
    except Exception: return d
def _f(k,d):
    try: return float(_L.get(k,d))
    except Exception: return d
TITULO_SEO_MAX=_i('titulo_seo_max',89); TITULO_SEO_MIN=_i('titulo_seo_min',40); TITULO_CAPA_MAX=_i('titulo_capa_max',60); TITULO_CAPA_MIN=_i('titulo_capa_min',20)
SUBTITULO_CURTO_MAX=_i('subtitulo_curto_max',200); LEGENDA_CURTA_MAX=_i('legenda_curta_max',100)
TAGS_MIN=_i('tags_min',5); TAGS_MAX=_i('tags_max',12)
META_DESCRIPTION_MIN=_i('meta_description_min',120); META_DESCRIPTION_MAX=_i('meta_description_max',160)
RETRANCA_MAX_WORDS=_i('retranca_max_words',3); CORPO_MIN_CHARS=_i('corpo_min_chars',500); CORPO_PARAGRAFOS_MIN=_i('corpo_paragrafos_min',3)
NOME_FONTE_MAX=_i('nome_fonte_max_words',4); CREDITOS_FOTO_MAX=_i('creditos_foto_max_words',6)
COVERAGE_PANEL_MIN=_f('coverage_panel_min',0.85); COVERAGE_MONITOR_MIN=_f('coverage_monitor_min',0.90); SCORE_QUALIDADE_PANEL_MIN=_i('score_qualidade_panel_min',90); SCORE_QUALIDADE_MONITOR_MIN=_i('score_qualidade_monitor_min',92); SCORE_RISCO_MAX=_i('score_risco_max',10)
