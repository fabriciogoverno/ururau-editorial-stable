# -*- coding: utf-8 -*-
"""Hotfix V47.17 REAL - monitor continua a busca e não fica preso em coletores lentos."""
from pathlib import Path
import json, os, shutil, subprocess, sys

cwd = Path.cwd().resolve()
base = cwd if (cwd / 'sistema').is_dir() else None
if base is None:
    for p in [cwd] + list(cwd.parents):
        if (p / 'sistema').is_dir():
            base = p
            break
if base is None:
    raise SystemExit('Rode na raiz do projeto, acima da pasta sistema.')
S = base / 'sistema'
print('[V47.17 REAL] base:', base)

def backup(p):
    if p.exists():
        b = p.with_suffix(p.suffix + '.bak_v47_17_real')
        if not b.exists(): shutil.copy2(p, b)

def read(p): return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ''
def write(p, c):
    p.parent.mkdir(parents=True, exist_ok=True); backup(p); p.write_text(c, encoding='utf-8'); print('[OK]', p.relative_to(base))
def bat(name, c): write(base/name, c.replace('\n','\r\n'))

cfgp = S/'config'/'monitor_24h.json'
try: cfg = json.loads(read(cfgp)) if cfgp.exists() else {}
except Exception: cfg = {}
if not isinstance(cfg, dict): cfg = {}
cfg.update({
  'modo_cms_padrao':'rascunho', 'intervalo_normal_segundos':120, 'intervalo_sem_pauta_segundos':90,
  'score_minimo_monitor':30, 'score_minimo_rascunho':30,
  'texto_minimo_rascunho_chars':350, 'texto_minimo_util_chars':350,
  'timeout_kimi_v110_segundos':25, 'timeout_gnews_v111_segundos':35, 'timeout_source_hunter_segundos':20,
  'usar_fila_painel_no_monitor': True, 'salvar_spool_local_se_cms_falhar': True
})
coleta = cfg.get('coleta') if isinstance(cfg.get('coleta'), dict) else {}
for k in ['rss_configurado','autofontes_diagnostico_v131','google_news_integrado_v111','google_news_fallback_v110','google_news_rss_legado_v108','source_hunter','fila_painel_monitor','diagnostico_fonte_aplicado']:
    coleta[k] = True
coleta.update({'score_minimo_gnews':30,'timeout_kimi_v110_segundos':25,'timeout_source_hunter_segundos':20})
cfg['coleta'] = coleta
write(cfgp, json.dumps(cfg, ensure_ascii=False, indent=2))

scr = S/'ururau'/'coleta'/'scraper_defaults_v47_10.py'
if scr.exists():
    txt = read(scr)
    backup(scr)
    if 'URURAU_V110_KIMI_TIMEOUT_SEG' not in txt:
        txt = txt.replace("'URURAU_MONITOR_USAR_FILA_PAINEL':'1',", "'URURAU_MONITOR_USAR_FILA_PAINEL':'1',\n    'URURAU_V110_KIMI_TIMEOUT_SEG':'25',\n    'URURAU_V111_TIMEOUT_SEG':'35',\n    'URURAU_SOURCE_HUNTER_TIMEOUT_SEG':'20',")
    if 'def aplicar_defaults_scrapers(logger=None):' in txt:
        txt = txt.replace('def aplicar_defaults_scrapers(logger=None):', 'def aplicar_defaults_scrapers(logger=None, forcar=False, **kwargs):')
        txt = txt.replace('os.environ.setdefault(k,v)', "os.environ.__setitem__(k,v) if forcar else os.environ.setdefault(k,v)")
    write(scr, txt)

mon = S/'ururau'/'publisher'/'monitor.py'
if mon.exists():
    txt = read(mon)
    backup(mon)
    txt = txt.replace('SCORE_MIN_RASCUNHO = int(os.getenv("URURAU_SCORE_MINIMO_RASCUNHO", "50"))', 'SCORE_MIN_RASCUNHO = int(os.getenv("URURAU_SCORE_MINIMO_RASCUNHO", "30"))')
    txt = txt.replace('elif status_pipeline == "rascunho_cms":', 'elif status_pipeline in {"rascunho_cms", "rascunho_local", "rascunho_spool_local"}:')
    if 'PATCH_V47_17_REAL_ENV' not in txt:
        txt += """

# PATCH_V47_17_REAL_ENV
try:
    import os as _os_v4717
    _os_v4717.environ.setdefault('URURAU_V110_KIMI_TIMEOUT_SEG','25')
    _os_v4717.environ.setdefault('URURAU_V111_TIMEOUT_SEG','35')
    _os_v4717.environ.setdefault('URURAU_SOURCE_HUNTER_TIMEOUT_SEG','20')
    _os_v4717.environ.setdefault('URURAU_MONITOR_COLETA_RASCUNHO_FLEXIVEL','1')
except Exception:
    pass
"""
    write(mon, txt)

spool = S/'ururau'/'publisher'/'rascunho_spool_v47_16.py'
if not spool.exists():
    write(spool, """# -*- coding: utf-8 -*-
from pathlib import Path
import json, time, re

def salvar_rascunho_spool(uid, pauta, materia, imagem=None, motivo='cms_falhou'):
    root=Path(__file__).resolve()
    for p in root.parents:
        if p.name=='sistema': root=p; break
    pasta=root/'dados'/'rascunhos_monitor'; pasta.mkdir(parents=True, exist_ok=True)
    titulo=str((getattr(materia,'titulo',None) or (materia.get('titulo') if isinstance(materia,dict) else None) or (pauta or {}).get('titulo_origem') or 'rascunho'))
    slug=re.sub(r'[^a-zA-Z0-9_-]+','-',titulo)[:80].strip('-') or str(uid)[:8]
    arq=pasta/f'{time.strftime('%Y%m%d_%H%M%S')}_{slug}.json'
    arq.write_text(json.dumps({'uid':uid,'titulo':titulo,'pauta':pauta,'materia':str(materia),'motivo':motivo},ensure_ascii=False,indent=2),encoding='utf-8')
    return str(arq)
""")

bat('15_TESTAR_MONITOR_BUSCA_CONTINUA.bat', '''@echo off
cd /d "%~dp0sistema"
set URURAU_MONITOR_MODO_CMS=rascunho
set URURAU_PUBLICAR_DIRETO=0
set URURAU_CMS_PUBLICACAO_DIRETA=0
set SCORE_MIN_MONITOR=30
set URURAU_SCORE_MINIMO_RASCUNHO=30
set URURAU_V110_KIMI_TIMEOUT_SEG=25
set URURAU_V111_TIMEOUT_SEG=35
set URURAU_SOURCE_HUNTER_TIMEOUT_SEG=20
python ururau_monitor.py --modo-cms rascunho --ciclo-unico --intervalo 90 --max-hora 24
pause
''')
bat('15_VALIDAR_MONITOR_BUSCA_CONTINUA_V47_17.bat', '''@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\publisher\monitor.py
python -m py_compile ururau\coleta\scraper_defaults_v47_10.py
echo VALIDACAO MONITOR BUSCA CONTINUA V47.17 OK
pause
''')

for p in [scr, mon, spool]:
    if p.exists(): subprocess.run([sys.executable,'-m','py_compile',str(p)],check=False)
print('[V47.17 REAL] pronto. Rode .\\15_VALIDAR_MONITOR_BUSCA_CONTINUA_V47_17.bat e .\\15_TESTAR_MONITOR_BUSCA_CONTINUA.bat')
