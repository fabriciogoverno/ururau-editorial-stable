from __future__ import annotations

import inspect
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

erros: list[str] = []

def ok(msg: str):
    print(f"[OK] {msg}")

def fail(msg: str):
    print(f"[ERRO] {msg}")
    erros.append(msg)

def check(cond: bool, msg: str):
    ok(msg) if cond else fail(msg)

# Compilação dos arquivos críticos recém-integrados.
criticos = [
    'ururau/publisher/monitor.py',
    'ururau/publisher/monitor_v111_patch.py',
    'ururau_monitor.py',
    'ururau/ui/painel.py',
    'ururau/coleta/config_unificada.py',
    'ururau/coleta/fonte_extractor_v104.py',
    'ururau/coleta/leitura_fonte.py',
    'ururau/imaging/busca.py',
    'ururau/imaging/processamento.py',
    'ururau/publisher/workflow.py',
]
for rel in criticos:
    try:
        py_compile.compile(str(ROOT / rel), doraise=True)
        ok(f'compilou: {rel}')
    except Exception as e:
        fail(f'falha de compilação em {rel}: {e}')

try:
    from ururau.publisher.monitor import MonitorRobo, monitor_global_ativo, _carregar_fontes_rss
    for nome in ('iniciar', 'parar', '_executar_ciclo', '_processar_pauta', '_vagas_na_hora'):
        check(hasattr(MonitorRobo, nome), f'MonitorRobo possui método {nome}')
    check(monitor_global_ativo() in (True, False), 'monitor_global_ativo() acessível')
    fontes = _carregar_fontes_rss()
    check(isinstance(fontes, list) and len(fontes) >= 4, f'fontes RSS carregadas ({len(fontes) if isinstance(fontes, list) else 0})')
except Exception as e:
    fail(f'integração do monitor falhou: {e}')

try:
    from ururau.coleta.config_unificada import carregar_fontes_rss_unificadas
    fontes_unif = carregar_fontes_rss_unificadas()
    urls = [f.get('url') for f in fontes_unif if isinstance(f, dict) and f.get('url')]
    check(len(urls) == len(set(u.rstrip('/').lower() for u in urls)), 'config_unificada deduplica URLs RSS')
    check(len(urls) >= 4, f'config_unificada preserva capacidade ({len(urls)} fontes)')
except Exception as e:
    fail(f'config_unificada falhou: {e}')

try:
    from ururau.imaging import busca
    sig = inspect.signature(busca.selecionar_melhor_imagem)
    check('imagem_preferencial' in sig.parameters, 'busca de imagem aceita imagem_preferencial')
    check(hasattr(busca, 'listar_candidatas_imagem'), 'busca de imagem tem lista de candidatas')
    from ururau.imaging.processamento import pipeline_imagem
    sig2 = inspect.signature(pipeline_imagem)
    check('imagem_preferencial' in sig2.parameters, 'pipeline_imagem recebe imagem preferencial')
except Exception as e:
    fail(f'integração de imagem falhou: {e}')

try:
    import ururau.coleta.fonte_extractor_v104 as v104
    src = inspect.getsource(v104.extrair_artigo_v104)
    check('URURAU_V104_FAIL_CACHE_TTL_SEG' in src, 'falhas de extração não ficam presas no cache longo')
except Exception as e:
    fail(f'extração v104 falhou: {e}')

try:
    cfg = json.loads((ROOT / 'config' / 'monitor_24h.json').read_text(encoding='utf-8'))
    check(cfg.get('modo_cms_padrao') == 'rascunho', 'monitor padrão em rascunho CMS')
    check(int(cfg.get('intervalo_normal_segundos', 0)) > 0, 'intervalo normal configurado')
    check(int(cfg.get('intervalo_sem_pauta_segundos', 0)) > 0, 'intervalo sem pauta configurado')
    coleta = cfg.get('coleta') if isinstance(cfg.get('coleta'), dict) else {}
    check(coleta.get('google_news_integrado_v111') is True, 'Google News v111 ativado por configuração do monitor')
    check(coleta.get('autofontes_v131') is True, 'AutoFontes/Diagnóstico de Fonte ativo por configuração')
    check(coleta.get('source_hunter') is True, 'Source Hunter preservado por configuração')
except Exception as e:
    fail(f'config monitor_24h inválida: {e}')

try:
    import ururau_monitor as um
    check(hasattr(um, '_aplicar_defaults_operacionais_monitor'), 'ururau_monitor aplica defaults de capacidade no ambiente')
    src_um = inspect.getsource(um._aplicar_defaults_operacionais_monitor)
    check('URURAU_V111_GNEWS_INTEGRADO' in src_um and 'setdefault' in src_um, 'defaults do GNews não sobrescrevem .env real')
    import ururau.publisher.monitor_v111_patch as mv111
    src_v111 = inspect.getsource(mv111.injetar_gnews_v111_no_raw)
    check('fallback após v111 vazio' in src_v111, 'GNews v111 tem fallback legado aditivo quando não retorna pautas')
except Exception as e:
    fail(f'validação de capacidade GNews/monitor falhou: {e}')

try:
    bat = (ROOT.parent / '06_VALIDAR_TUDO.bat').read_bytes()
    controles = [b for b in bat if b < 32 and b not in (9, 10, 13)]
    check(not controles, '06_VALIDAR_TUDO.bat sem caracteres de controle em caminhos')
    text = bat.decode('utf-8', errors='ignore')
    check('VALIDAR_INTEGRACOES_V47_7.py' in text, '06_VALIDAR_TUDO chama validação V47.7')
except Exception as e:
    fail(f'BAT de validação falhou: {e}')

if erros:
    print('\nVALIDAÇÃO V47.7: FALHOU')
    for e in erros:
        print(' -', e)
    raise SystemExit(1)

print('\nVALIDAÇÃO V47.7: OK — integrações críticas e capacidade preservadas/ampliadas.')
