from __future__ import annotations
import json, py_compile, sys
from pathlib import Path
base = Path(__file__).resolve().parent
ok = True
for rel in [
    'ururau/publisher/monitor.py',
    'ururau_monitor.py',
    'ururau/ui/painel.py',
    'ururau/ui/patch_v47_6_monitor_24h.py',
]:
    try:
        py_compile.compile(str(base/rel), doraise=True)
        print('[OK]', rel)
    except Exception as e:
        ok = False
        print('[ERRO]', rel, e)
cfg = json.loads((base/'config'/'monitor_24h.json').read_text(encoding='utf-8'))
checks = {
    'modo_cms_padrao=rascunho': cfg.get('modo_cms_padrao') == 'rascunho',
    'executar_continuamente=true': cfg.get('executar_continuamente') is True,
    'intervalo_normal_segundos>0': int(cfg.get('intervalo_normal_segundos', 0)) > 0,
    'intervalo_sem_pauta_segundos>0': int(cfg.get('intervalo_sem_pauta_segundos', 0)) > 0,
}
for name, passed in checks.items():
    print(('[OK]' if passed else '[ERRO]'), name)
    ok = ok and passed
print('\nVALIDACAO V47.6 MONITOR 24H:', 'OK' if ok else 'FALHOU')
sys.exit(0 if ok else 1)
