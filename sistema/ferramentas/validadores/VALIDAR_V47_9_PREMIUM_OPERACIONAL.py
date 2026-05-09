
from __future__ import annotations
import json, os, sys, py_compile
from pathlib import Path
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
ok = True
def check(cond, msg):
    global ok
    print('[OK]' if cond else '[ERRO]', msg)
    ok = ok and bool(cond)
cfg=json.loads((BASE/'config'/'monitor_24h.json').read_text(encoding='utf-8'))
co=cfg.get('coleta',{})
check(co.get('usar_fila_painel_no_monitor') is True, 'monitor usa fila do painel')
check(co.get('google_news_integrado_v111') is True, 'Google News v111 ativo no JSON')
check(co.get('auto_diagnostico_fonte_apos_falha') is True, 'auto diagnóstico de fonte ativo')
from ururau.publisher.monitor_capacidade_v47_9 import aplicar_defaults_coleta_monitor, mesclar_fila_com_candidatas
aplicar_defaults_coleta_monitor(forcar=True)
check(os.environ.get('URURAU_V111_GNEWS_INTEGRADO') == '1', 'Google News v111 ativo no processo')
check(os.environ.get('URURAU_V110_MONITOR_GNEWS_LEGADO') == '1', 'fallback legado ativo')
check(os.environ.get('URURAU_AUTOFONTES_V131_ATIVO') == '1', 'AutoFontes ativo')
m=mesclar_fila_com_candidatas([{'link_origem':'b'}],[{'link_origem':'a'},{'link_origem':'b'}])
check([x['link_origem'] for x in m]==['a','b'], 'fila entra antes e deduplica')
from ururau.coleta.fail_closed_v83 import _metodo_tem_url_real_v104
check(_metodo_tem_url_real_v104('v110_kimi_article_extractor'), 'v110_kimi_article_extractor reconhecido')
check(_metodo_tem_url_real_v104('v108_readability'), 'v108_readability reconhecido')
for rel in ['ururau/publisher/monitor.py','ururau/publisher/monitor_capacidade_v47_9.py','ururau/coleta/auto_reparo_fontes_v47_9.py','ururau/coleta/fail_closed_v83.py','ururau/ui/patch_v46_layout_definitivo.py','ururau/ui/patch_v47_6_monitor_24h.py','ururau/ui/queue_v45.py']:
    py_compile.compile(str(BASE/rel), doraise=True); print('[OK] sintaxe', rel)
if not ok: sys.exit(1)
print('[OK] V47.9 Premium Operacional validado')
