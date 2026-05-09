# -*- coding: utf-8 -*-
"""Defaults aditivos de coleta/extração para manter todos os mecanismos ativos."""
from __future__ import annotations
import os

COLETORES_ATIVOS = {
    'rss_configurado': True,
    'autofontes_diagnostico_v131': True,
    'google_news_integrado_v111': True,
    'google_news_ciclo_combinado_v111': True,
    'google_news_hidratacao_v111': True,
    'google_news_fallback_v110': True,
    'google_news_rss_legado_v108': True,
    'source_hunter': True,
    'fila_painel_monitor': True,
}
EXTRATORES_ATIVOS = {
    'v104_orquestrador_canonico': True,
    'v86_multiestrategia': True,
    'requests_canonical_variantes': True,
    'json_ld_articlebody_nextdata': True,
    'kimi_article_extractor_v110': True,
    'trafilatura_readability_v108': True,
    'wordpress_rest_publico': True,
    'pipeline_v90_adapters': True,
    'playwright_publico_se_falhar_v104': True,
    'playwright_publico_se_falhar_v86': True,
    'preextraido_longo_ultimo_recurso': True,
}
ENV_TRUE = {
    'URURAU_V111_GNEWS_INTEGRADO': '0',
    'URURAU_V111_USAR_EXTRACAO_COMPLETA':'0',
    'URURAU_V111_USAR_CICLO_COMBINADO': '0',
    'URURAU_V110_MONITOR_GNEWS_LEGADO': '0',
    'URURAU_V108_GNEWS_TERMOS': '0',
    'URURAU_SOURCE_HUNTER_ATIVO': '0',
    'URURAU_AUTOFONTES_V131_ATIVO':'1',
    'URURAU_AUTO_DIAGNOSTICO_FONTE':'1',
    'URURAU_MONITOR_USAR_FILA_PAINEL':'1',
    'URURAU_V110_KIMI_TIMEOUT_SEG':'25',
    'URURAU_V111_TIMEOUT_SEG':'35',
    'URURAU_SOURCE_HUNTER_TIMEOUT_SEG':'20',
}
ENV_OPERACIONAL = {
    'URURAU_GNEWS_JANELA_HORAS':'12',
    'URURAU_V111_GNEWS_JANELA_HORAS':'12',
    'URURAU_RSS_MAX_POR_FONTE':'18',
    'SCORE_MIN_MONITOR':'35',
    'URURAU_MONITOR_SCORE_MINIMO':'35',
    'URURAU_SCORE_MINIMO_RASCUNHO':'35',
    'URURAU_SCORE_MINIMO_DIRETA':'90',
    'URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR':'1',
    'URURAU_MONITOR_COLETA_RASCUNHO_FLEXIVEL':'1',
    'URURAU_V111_SCORE_MINIMO_PAUTA':'35',
    'URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO':'6',
    'URURAU_V111_GNEWS_MIN_CHARS_FONTE':'350',
    'URURAU_MIN_CHARS_FONTE_MONITOR':'350',
    'URURAU_V104_MIN_CHARS_ARTIGO':'350',
    'URURAU_V105_MIN_CHARS_FONTE_OK':'350',
}

def aplicar_defaults_scrapers(logger=None, forcar=False, **kwargs):
    """Aceita forcar=True para compatibilidade com ururau_monitor.py."""
    for k,v in ENV_TRUE.items():
        if forcar: os.environ[k]=v
        else: os.environ.setdefault(k,v)
    for k,v in ENV_OPERACIONAL.items():
        if forcar: os.environ[k]=v
        else: os.environ.setdefault(k,v)
    if logger:
        try: logger.info('[V47.14][SCRAPERS] ativos=' + ', '.join(list(COLETORES_ATIVOS)+list(EXTRATORES_ATIVOS)))
        except Exception: pass
    return {'coletores': COLETORES_ATIVOS, 'extratores': EXTRATORES_ATIVOS}


