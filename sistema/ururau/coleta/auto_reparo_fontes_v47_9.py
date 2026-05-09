from __future__ import annotations
import os, threading
from urllib.parse import urlparse
from typing import Any

_DOMS: set[str] = set()
_LOCK = threading.Lock()

def _dom(url: str) -> str:
    try: return (urlparse(url).netloc or '').lower().replace('www.','')
    except Exception: return ''

def agendar_diagnostico_fonte(pauta: dict[str, Any], motivo: str = '', logger: Any = None) -> bool:
    if str(os.getenv('URURAU_AUTO_DIAGNOSTICO_FONTE','1')).lower() not in {'1','true','sim','yes','s','on'}:
        return False
    url = str(pauta.get('link_origem') or pauta.get('url') or '').strip()
    dom = _dom(url)
    if not url or not dom: return False
    with _LOCK:
        if dom in _DOMS: return False
        _DOMS.add(dom)
    def run():
        try:
            if logger is not None and hasattr(logger,'info'):
                logger.info('[V47.9][AUTO-DIAG] Diagnosticando fonte após falha: %s | motivo=%s', dom, motivo)
            from ururau.coleta.diagnostico_fontes_v130 import diagnostico_rapido
            from ururau.coleta.aplicador_diagnostico_v130 import aplicar_sugestao_diagnostico_v130
            res = diagnostico_rapido(url, log_callback=(lambda msg: logger.info('[V47.9][AUTO-DIAG] %s', msg) if logger is not None and hasattr(logger,'info') else None))
            aplicar_sugestao_diagnostico_v130(res, nome_preferido=str(pauta.get('fonte_nome') or dom))
            if logger is not None and hasattr(logger,'info'):
                logger.info('[V47.9][AUTO-DIAG] Estratégia aplicada para próxima coleta: %s', dom)
        except Exception as exc:
            if logger is not None and hasattr(logger,'warning'):
                logger.warning('[V47.9][AUTO-DIAG] Falhou para %s: %s', dom, exc)
        finally:
            with _LOCK: _DOMS.discard(dom)
    threading.Thread(target=run, daemon=True, name=f'AutoDiagFonte-{dom[:24]}').start()
    return True
