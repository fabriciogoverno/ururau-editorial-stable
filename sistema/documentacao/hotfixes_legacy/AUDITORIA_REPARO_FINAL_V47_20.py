# -*- coding: utf-8 -*-
"""
AUDITORIA_REPARO_FINAL_V47_20.py
Auditoria e reparo final dos dois problemas atuais:
1) Redigir quebrando com dict sem atributo .bloqueante/.score.
2) Monitor do painel ainda religando Google News/Kimi/Source Hunter e travando em 429.

Uso:
  python AUDITORIA_REPARO_FINAL_V47_20.py
  .\18_VALIDAR_REPARO_FINAL_V47_20.bat
  .\02_ABRIR_PAINEL.bat
"""
from pathlib import Path
import json, re, shutil, subprocess, sys, os, time


def base_dir():
    cwd = Path.cwd().resolve()
    if (cwd / 'sistema').is_dir():
        return cwd
    for p in [cwd] + list(cwd.parents):
        if (p / 'sistema').is_dir():
            return p
    raise SystemExit('ERRO: rode na raiz do projeto, no mesmo nível da pasta sistema.')

BASE = base_dir()
S = BASE / 'sistema'
print('[V47.20] Projeto:', BASE)


def read(p):
    return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ''


def backup(p):
    if p.exists():
        b = p.with_suffix(p.suffix + '.bak_v47_20')
        if not b.exists():
            shutil.copy2(p, b)


def write(p, content):
    p.parent.mkdir(parents=True, exist_ok=True)
    backup(p)
    p.write_text(content, encoding='utf-8')
    print('[OK]', p.relative_to(BASE))


def bat(name, content):
    write(BASE / name, content.replace('\n', '\r\n'))

REPORT = []
def rep(s):
    REPORT.append(s)
    print(s)

# -------------------------------------------------------------------
# A) AUDITORIA REAL DO QUE QUEBROU
# -------------------------------------------------------------------
rep('=== AUDITORIA V47.20 ===')
rep('1) Redação: erro atual é acesso por atributo em resultado dict: .bloqueante e antes .score.')
rep('2) Monitor: Google/Kimi continuam aparecendo porque patch do painel e scraper_defaults ainda forçam variáveis antigas.')
rep('3) Log mostrou RSS/fila funcionando; o bloqueio operacional está em Google/Kimi 429 e integração v111 com argumento janela.')
rep('4) A correção segura é: Redigir aceita dict/objeto; Monitor do painel usa RSS+AutoFontes+fila e NÃO religa Google/Kimi.')

# -------------------------------------------------------------------
# B) Compatibilidade robusta dict/objeto para Redigir
# -------------------------------------------------------------------
compat = S / 'ururau' / 'editorial' / 'compat_resultado_v47_20.py'
write(compat, r'''# -*- coding: utf-8 -*-
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
''')

HELPER = """
# PATCH_V47_20_DICT_ATTR_COMPAT
try:
    from ururau.editorial.compat_resultado_v47_20 import compat_obj as _v4720_compat_obj, getv as _v4720_getv, get_bool as _v4720_get_bool, get_score as _v4720_get_score
except Exception:
    def _v4720_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4720_get_bool(o,k,d=False): return bool(_v4720_getv(o,k,d))
    def _v4720_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4720_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4720_compat_obj(o): return o
""".strip() + "\n\n"

# Insere helper depois de future imports/docstring, sem quebrar Python.
def insert_helper_safely(text):
    if 'PATCH_V47_20_DICT_ATTR_COMPAT' in text:
        return text
    lines = text.splitlines(True)
    i = 0
    # encoding/shebang/comments iniciais
    while i < len(lines) and (lines[i].strip()=='' or lines[i].startswith('#')):
        i += 1
    # docstring simples
    if i < len(lines) and lines[i].lstrip().startswith(('"""', "'''")):
        q = '"""' if lines[i].lstrip().startswith('"""') else "'''"
        if lines[i].count(q) >= 2 and lines[i].strip() != q:
            i += 1
        else:
            i += 1
            while i < len(lines):
                if q in lines[i]:
                    i += 1
                    break
                i += 1
    # espaços e future imports
    while i < len(lines):
        s = lines[i].strip()
        if s == '' or s.startswith('from __future__ import'):
            i += 1
        else:
            break
    return ''.join(lines[:i]) + HELPER + ''.join(lines[i:])

# Remove helper antigo inserido no topo antes de __future__ se ainda existir.
def strip_old_top_helper(text):
    if text.startswith('# PATCH_V47_18_DICT_SCORE_COMPAT'):
        idx = text.find('# -*- coding', 5)
        if idx > 0:
            return text[idx:]
        idx = text.find('from __future__ import')
        if idx > 0:
            return text[idx:]
    return text

TARGETS = [
    S/'ururau'/'ui'/'painel.py',
    S/'ururau'/'editorial'/'redacao.py',
    S/'ururau'/'editorial'/'engine.py',
    S/'ururau'/'publisher'/'workflow.py',
    S/'ururau'/'editorial'/'quality_gate_v103.py',
    S/'ururau'/'editorial'/'auditoria_v78c.py',
    S/'ururau'/'editorial'/'copydesk.py',
]

VAR_RE = r'(resultado|result|res|ret|saida|out|resp|auditoria|validacao|avaliacao|qualidade|gate|diagnostico|analise|seo|quality_result|seo_result|r)'
for p in TARGETS:
    if not p.exists():
        continue
    txt = strip_old_top_helper(read(p))
    backup(p)
    txt = insert_helper_safely(txt)
    # Acessos de leitura comuns que estavam quebrando no painel.
    txt = re.sub(r'\b' + VAR_RE + r'\.score\b', lambda m: f"_v4720_get_score({m.group(1)}, 0)", txt)
    txt = re.sub(r'\b' + VAR_RE + r'\.bloqueante\b', lambda m: f"_v4720_get_bool({m.group(1)}, 'bloqueante', False)", txt)
    txt = re.sub(r'\b' + VAR_RE + r'\.aprovado\b', lambda m: f"_v4720_get_bool({m.group(1)}, 'aprovado', False)", txt)
    txt = re.sub(r"getattr\(([^,\)]+),\s*['\"]score['\"]\s*,\s*([^\)]+)\)", r"_v4720_get_score(\1, \2)", txt)
    txt = re.sub(r"getattr\(([^,\)]+),\s*['\"]bloqueante['\"]\s*,\s*([^\)]+)\)", r"_v4720_get_bool(\1, 'bloqueante', \2)", txt)
    p.write_text(txt, encoding='utf-8')
    rep('[REDAÇÃO] Compat dict/obj aplicado em ' + str(p.relative_to(BASE)))

# -------------------------------------------------------------------
# C) Monitor do painel: desligar Google/Kimi/SourceHunter de verdade
# -------------------------------------------------------------------
FORCE_OFF = {
    'URURAU_V111_GNEWS_INTEGRADO': '0',
    'URURAU_V111_USAR_CICLO_COMBINADO': '0',
    'URURAU_V111_USAR_EXTRACAO_COMPLETA': '0',
    'URURAU_V110_MONITOR_GNEWS_LEGADO': '0',
    'URURAU_V108_GNEWS_TERMOS': '0',
    'URURAU_SOURCE_HUNTER_ATIVO': '0',
    'URURAU_GNEWS_DESLIGADO_NO_MONITOR': '1',
}

# Config JSON
cfgp = S/'config'/'monitor_24h.json'
try:
    cfg = json.loads(read(cfgp)) if cfgp.exists() else {}
except Exception:
    cfg = {}
if not isinstance(cfg, dict):
    cfg = {}
coleta = cfg.get('coleta') if isinstance(cfg.get('coleta'), dict) else {}
coleta.update({
    'rss_configurado': True,
    'autofontes_diagnostico_v131': True,
    'fila_painel_monitor': True,
    'diagnostico_fonte_aplicado': True,
    'google_news_integrado_v111': False,
    'google_news_ciclo_combinado_v111': False,
    'google_news_hidratacao_v111': False,
    'google_news_fallback_v110': False,
    'google_news_rss_legado_v108': False,
    'source_hunter': False,
})
cfg['coleta'] = coleta
cfg.update({'modo_cms_padrao':'rascunho','intervalo_normal_segundos':120,'intervalo_sem_pauta_segundos':120,'score_minimo_monitor':35})
write(cfgp, json.dumps(cfg, ensure_ascii=False, indent=2))

# scraper_defaults: não pode religar Google no force.
scr = S/'ururau'/'coleta'/'scraper_defaults_v47_10.py'
if scr.exists():
    txt = read(scr)
    backup(scr)
    # Substitui chaves de Google/SourceHunter para 0 onde estiverem como 1.
    for k, v in FORCE_OFF.items():
        txt = re.sub(r"(['\"]" + re.escape(k) + r"['\"]\s*:\s*)['\"]1['\"]", r"\g<1>'" + v + "'", txt)
    if 'def aplicar_defaults_scrapers(logger=None):' in txt:
        txt = txt.replace('def aplicar_defaults_scrapers(logger=None):', 'def aplicar_defaults_scrapers(logger=None, forcar=False, **kwargs):')
    write(scr, txt)

# Patch do painel monitor: força OFF no processo da UI.
pp = S/'ururau'/'ui'/'patch_v47_15_monitor_painel.py'
if pp.exists():
    txt = read(pp)
    backup(pp)
    for k, v in FORCE_OFF.items():
        txt = re.sub(r"(['\"]" + re.escape(k) + r"['\"]\s*:\s*)['\"]1['\"]", r"\g<1>'" + v + "'", txt)
    # se o dicionário env não tinha a chave, injeta próximo de URURAU_MONITOR_USAR_FILA_PAINEL
    for k, v in FORCE_OFF.items():
        if k not in txt and "'URURAU_MONITOR_USAR_FILA_PAINEL'" in txt:
            txt = txt.replace("'URURAU_MONITOR_USAR_FILA_PAINEL': '1',", "'URURAU_MONITOR_USAR_FILA_PAINEL': '1',\n        '"+k+"': '"+v+"',")
    write(pp, txt)

# Monitor_v111_patch: se chamado por algum caminho antigo, retorna imediatamente.
gp = S/'ururau'/'publisher'/'monitor_v111_patch.py'
if gp.exists():
    txt = read(gp)
    backup(gp)
    guard = """

# PATCH_V47_20_GNEWS_HARD_OFF
try:
    import os as _os_v4720_g
    if _os_v4720_g.environ.get('URURAU_GNEWS_DESLIGADO_NO_MONITOR') == '1':
        def injetar_gnews_v111_no_raw(raw, logger=None, termos_legado=None):
            try:
                logger.info('[V47.20][GNEWS] desligado no monitor; ciclo segue com RSS/AutoFontes/fila')
            except Exception:
                pass
            return 0
        def coletar_gnews_para_monitor_v111(logger=None):
            return []
        def coletar_gnews_legado_v110(logger=None, termos_legado=None):
            return []
except Exception:
    pass
"""
    if 'PATCH_V47_20_GNEWS_HARD_OFF' not in txt:
        txt += guard
    write(gp, txt)

# BATs operacionais sem Google.
bat('04_MONITOR_24H_RASCUNHO.bat', '''@echo off
cd /d "%~dp0sistema"
set URURAU_MONITOR_MODO_CMS=rascunho
set URURAU_PUBLICAR_DIRETO=0
set URURAU_CMS_PUBLICACAO_DIRETA=0
set SCORE_MIN_MONITOR=35
set URURAU_MONITOR_SCORE_MINIMO=35
set URURAU_SCORE_MINIMO_RASCUNHO=35
set URURAU_MONITOR_USAR_FILA_PAINEL=1
set URURAU_V111_GNEWS_INTEGRADO=0
set URURAU_V111_USAR_CICLO_COMBINADO=0
set URURAU_V111_USAR_EXTRACAO_COMPLETA=0
set URURAU_V110_MONITOR_GNEWS_LEGADO=0
set URURAU_V108_GNEWS_TERMOS=0
set URURAU_SOURCE_HUNTER_ATIVO=0
set URURAU_GNEWS_DESLIGADO_NO_MONITOR=1
set URURAU_AUTOFONTES_V131_ATIVO=1
set URURAU_AUTO_DIAGNOSTICO_FONTE=1
python ururau_monitor.py --modo-cms rascunho
pause
''')

bat('19_TESTAR_MONITOR_ESTAVEL_SEM_GOOGLE.bat', '''@echo off
cd /d "%~dp0sistema"
set URURAU_MONITOR_MODO_CMS=rascunho
set URURAU_PUBLICAR_DIRETO=0
set URURAU_CMS_PUBLICACAO_DIRETA=0
set SCORE_MIN_MONITOR=35
set URURAU_MONITOR_USAR_FILA_PAINEL=1
set URURAU_V111_GNEWS_INTEGRADO=0
set URURAU_V111_USAR_CICLO_COMBINADO=0
set URURAU_V111_USAR_EXTRACAO_COMPLETA=0
set URURAU_V110_MONITOR_GNEWS_LEGADO=0
set URURAU_V108_GNEWS_TERMOS=0
set URURAU_SOURCE_HUNTER_ATIVO=0
set URURAU_GNEWS_DESLIGADO_NO_MONITOR=1
python ururau_monitor.py --modo-cms rascunho --ciclo-unico --intervalo 90 --max-hora 24
pause
''')

# Validador
val = S/'ferramentas'/'validadores'/'VALIDAR_REPARO_FINAL_V47_20.py'
write(val, r'''# -*- coding: utf-8 -*-
from pathlib import Path
import json, py_compile, sys
S=Path(__file__).resolve()
for p in S.parents:
    if p.name=='sistema': ROOT=p; break
else: ROOT=Path.cwd()
errors=[]
def ok(c,m):
    print(('OK   ' if c else 'ERRO ') + m)
    if not c: errors.append(m)
for rel in ['ururau/ui/painel.py','ururau/editorial/redacao.py','ururau/editorial/engine.py','ururau/publisher/workflow.py']:
    f=ROOT/rel
    py_compile.compile(str(f), doraise=True)
    t=f.read_text(encoding='utf-8',errors='ignore')
    ok('PATCH_V47_20_DICT_ATTR_COMPAT' in t, rel+' com compat dict/obj')
cfg=json.loads((ROOT/'config'/'monitor_24h.json').read_text(encoding='utf-8'))
coleta=cfg.get('coleta',{})
ok(coleta.get('google_news_integrado_v111') is False, 'Google News v111 desligado no monitor')
ok(coleta.get('google_news_fallback_v110') is False, 'Kimi/Google legado desligado no monitor')
ok(coleta.get('source_hunter') is False, 'Source Hunter desligado no monitor')
pp=(ROOT/'ururau/ui/patch_v47_15_monitor_painel.py').read_text(encoding='utf-8',errors='ignore')
ok('URURAU_GNEWS_DESLIGADO_NO_MONITOR' in pp, 'painel força GNEWS off no monitor')
if errors:
    print('\nFALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO REPARO FINAL V47.20 OK')
''')

bat('18_VALIDAR_REPARO_FINAL_V47_20.bat', '@echo off\ncd /d "%~dp0sistema"\npython ferramentas\\validadores\\VALIDAR_REPARO_FINAL_V47_20.py\npause\n')

# Relatório salvo
report_path = S/'documentacao'/'AUDITORIA_REPARO_FINAL_V47_20.txt'
write(report_path, '\n'.join(REPORT) + '\n')

# Compilação
for p in TARGETS + [compat, gp, pp, scr, val]:
    if p and p.exists():
        subprocess.run([sys.executable, '-m', 'py_compile', str(p)], check=False)

print('\n[V47.20] Reparo final aplicado.')
print('Rode:')
print('  .\\18_VALIDAR_REPARO_FINAL_V47_20.bat')
print('  .\\02_ABRIR_PAINEL.bat')
print('Teste do monitor estável:')
print('  .\\19_TESTAR_MONITOR_ESTAVEL_SEM_GOOGLE.bat')
