from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

def _base_dir() -> Path:
    return Path(__file__).resolve().parents[2]

def _cfg_monitor() -> dict[str, Any]:
    p = _base_dir() / 'config' / 'monitor_24h.json'
    try:
        d = json.loads(p.read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def _bool_text(v: Any, default: bool = True) -> str:
    if v is None:
        v = default
    if isinstance(v, str):
        return '1' if v.strip().lower() in {'1','true','sim','yes','s','on'} else '0'
    return '1' if bool(v) else '0'

def aplicar_defaults_coleta_monitor(forcar: bool = True, logger: Any = None) -> dict[str, str]:
    try:
        from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers
        aplicar_defaults_scrapers(forcar=True, logger=logger)
    except Exception as _e_scrapers_v47_10:
        if logger is not None and hasattr(logger, 'info'):
            try: logger.info(f'[V47.10][SCRAPERS] aviso: {_e_scrapers_v47_10}')
            except Exception: pass
    if str(os.getenv('URURAU_MONITOR_RESPEITAR_ENV_COLETA','0')).lower() in {'1','true','sim','yes','s','on'}:
        forcar = False
    cfg = _cfg_monitor()
    coleta = cfg.get('coleta') if isinstance(cfg.get('coleta'), dict) else {}
    defaults = {
        'URURAU_V111_GNEWS_INTEGRADO': _bool_text(coleta.get('google_news_integrado_v111'), True),
        'URURAU_V111_USAR_EXTRACAO_COMPLETA': _bool_text(coleta.get('hidratar_google_news'), True),
        'URURAU_V111_USAR_CICLO_COMBINADO': _bool_text(coleta.get('ciclo_combinado_v111'), True),
        'URURAU_V110_MONITOR_GNEWS_LEGADO': _bool_text(coleta.get('google_news_legado_fallback'), True),
        'URURAU_V108_GNEWS_TERMOS': _bool_text(coleta.get('google_news_rss_legado_fallback'), True),
        'URURAU_SOURCE_HUNTER_ATIVO': _bool_text(coleta.get('source_hunter'), True),
        'URURAU_AUTOFONTES_V131_ATIVO': _bool_text(coleta.get('autofontes_v131'), True),
        'URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO': str(int(coleta.get('max_resultados_gnews_por_termo', 3) or 3)),
        'URURAU_V111_SCORE_MINIMO_PAUTA': str(int(coleta.get('score_minimo_gnews', 65) or 65)),
        'URURAU_V111_GNEWS_JANELA_HORAS': str(int(coleta.get('janela_horas_gnews', 4) or 4)),
        'URURAU_V111_GNEWS_MIN_CHARS_FONTE': str(int(coleta.get('min_chars_fonte_gnews', 500) or 500)),
        'URURAU_AUTO_DIAGNOSTICO_FONTE': _bool_text(coleta.get('auto_diagnostico_fonte_apos_falha'), True),
        'URURAU_BLOQUEAR_LINK_SEM_TEXTO': '0' if coleta.get('nao_bloquear_permanente_por_falha_tecnica_extracao', True) else '1',
    }
    applied = {}
    for k, v in defaults.items():
        if forcar or not os.getenv(k):
            os.environ[k] = v
            applied[k] = v
    if logger is not None and hasattr(logger, 'info'):
        try:
            logger.info('[V47.9][CAPACIDADE] Coletores ativos por config: %s', ', '.join(k for k,v in applied.items() if v == '1') or 'nenhum booleano alterado')
        except Exception:
            pass
    return applied

def _row_to_pauta(row: Any) -> dict[str, Any]:
    d = dict(row)
    try:
        extra = json.loads(d.get('dados_json') or '{}')
        if isinstance(extra, dict):
            d.update(extra)
    except Exception:
        pass
    d.setdefault('_uid', d.get('uid'))
    d.setdefault('link_origem', d.get('link') or d.get('url') or '')
    d.setdefault('titulo_origem', d.get('titulo') or '')
    d.setdefault('fonte_nome', d.get('fonte') or d.get('nome_fonte') or 'Fila do painel')
    d.setdefault('canal_forcado', d.get('canal') or '')
    d['_origem_monitor_fila'] = True
    d['origem_coleta'] = d.get('origem_coleta') or 'fila_painel'
    try:
        if int(d.get('score_editorial') or 0) <= 0:
            d['score_editorial'] = 65
    except Exception:
        d['score_editorial'] = 65
    return d

def carregar_pautas_fila_para_monitor(db: Any, limit: int | None = None) -> list[dict[str, Any]]:
    try:
        limit = int(limit or os.getenv('URURAU_MONITOR_MAX_PAUTAS_FILA','30') or 30)
    except Exception:
        limit = 30
    limit = max(1, min(limit, 100))
    conn = db._conectar()
    try:
        rows = conn.execute("""
            SELECT uid, titulo_origem, link_origem, fonte_nome, resumo_origem,
                   canal, score_editorial, status, urgente, captada_em, atualizada_em, dados_json
              FROM pautas
             WHERE COALESCE(status,'captada') NOT IN ('publicada','excluida','rejeitada')
               AND COALESCE(link_origem,'') <> ''
             ORDER BY atualizada_em DESC
             LIMIT ?
        """, (limit,)).fetchall()
    finally:
        conn.close()
    return [_row_to_pauta(r) for r in rows]

def mesclar_fila_com_candidatas(candidatas: list[dict[str, Any]], fila: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set(); out = []
    for p in list(fila or []) + list(candidatas or []):
        key = str(p.get('link_origem') or p.get('url') or p.get('_uid') or p.get('uid') or p.get('titulo_origem') or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key); out.append(p)
    return out
