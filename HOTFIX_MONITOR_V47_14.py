# -*- coding: utf-8 -*-
"""
HOTFIX_MONITOR_V47_14.py
Correção operacional do monitor 24h após V47.13.

Objetivo:
- corrigir aplicar_defaults_scrapers(forcar=True);
- alinhar score mínimo real do monitor com config;
- deixar o modo RASCUNHO realmente voltado a cadastrar rascunhos;
- restaurar launchers corretos do painel;
- criar teste de ciclo único e visualizador de log.

Uso:
  python HOTFIX_MONITOR_V47_14.py
  .\10_TESTAR_MONITOR_CICLO_UNICO.bat
  .\04_MONITOR_24H_RASCUNHO.bat
"""
from pathlib import Path
import json, os, re, shutil, subprocess, sys


def detectar_base() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "sistema").is_dir():
        return cwd
    if cwd.name.lower() == "sistema" and (cwd / "ururau").is_dir():
        return cwd.parent
    for p in [cwd] + list(cwd.parents):
        if (p / "sistema").is_dir():
            return p
    raise SystemExit("ERRO: rode na raiz do projeto, no mesmo nível da pasta sistema.")


BASE = detectar_base()
S = BASE / "sistema"
print("[V47.14] Projeto:", BASE)


def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak_v47_14")
        if not b.exists():
            try:
                shutil.copy2(p, b)
            except Exception as e:
                print("[WARN] backup falhou", p, e)


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    backup(p)
    p.write_text(content, encoding="utf-8")
    print("[OK]", p.relative_to(BASE))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def bat(name: str, content: str):
    write(BASE / name, content.replace("\n", "\r\n"))


# 1) Config real do monitor: inclui chaves antigas e novas para evitar leitura errada.
cfg_path = S / "config" / "monitor_24h.json"
try:
    cfg = json.loads(read(cfg_path)) if cfg_path.exists() else {}
except Exception:
    cfg = {}
if not isinstance(cfg, dict):
    cfg = {}

cfg.update({
    "modo_cms_padrao": "rascunho",
    "intervalo_normal_segundos": 180,
    "intervalo_sem_pauta_segundos": 180,
    "max_materias_por_hora": 24,
    "max_publicacoes_hora": 24,
    "score_minimo_monitor": 35,
    "score_minimo_rascunho": 35,
    "score_minimo_gnews": 35,
    "janela_horas_coleta": 12,
    "janela_horas_google_news": 12,
    "janela_horas_gnews": 12,
    "texto_minimo_util_chars": 700,
    "min_chars_fonte_gnews": 350,
    "usar_fila_painel_no_monitor": True,
    "limite_fila_painel_monitor": 160,
    "limite_varredura_fila": 320,
    "max_itens_por_fonte_rss": 18,
    "max_google_news_por_termo": 6,
    "max_resultados_gnews_por_termo": 6,
    "max_google_news_total": 100,
    "max_source_hunter": 180,
    "seo_minimo_publicacao_direta": 90,
    "permitir_rascunho_com_texto_minimo": True,
})
coleta = cfg.get("coleta") if isinstance(cfg.get("coleta"), dict) else {}
coleta.update({
    "rss_configurado": True,
    "autofontes_diagnostico_v131": True,
    "autofontes_v131": True,
    "google_news_integrado_v111": True,
    "google_news_ciclo_combinado_v111": True,
    "ciclo_combinado_v111": True,
    "google_news_hidratacao_v111": True,
    "hidratar_google_news": True,
    "google_news_fallback_v110": True,
    "google_news_legado_fallback": True,
    "google_news_rss_legado_v108": True,
    "google_news_rss_legado_fallback": True,
    "source_hunter": True,
    "fila_painel_monitor": True,
    "diagnostico_fonte_aplicado": True,
    "max_resultados_gnews_por_termo": 6,
    "score_minimo_gnews": 35,
    "janela_horas_gnews": 12,
    "min_chars_fonte_gnews": 350,
})
cfg["coleta"] = coleta
extracao = cfg.get("extracao") if isinstance(cfg.get("extracao"), dict) else {}
extracao.update({
    "v104_orquestrador_canonico": True,
    "v86_multiestrategia": True,
    "requests_canonical_variantes": True,
    "json_ld_articlebody_nextdata": True,
    "kimi_article_extractor_v110": True,
    "trafilatura_readability_v108": True,
    "wordpress_rest_publico": True,
    "pipeline_v90_adapters": True,
    "playwright_publico_se_falhar": True,
    "preextraido_longo_ultimo_recurso": True,
})
cfg["extracao"] = extracao
write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2))

# 2) Corrige scraper_defaults para aceitar forcar=True e sobrescrever env quando necessário.
scraper = S / "ururau" / "coleta" / "scraper_defaults_v47_10.py"
write(scraper, r'''# -*- coding: utf-8 -*-
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
    'URURAU_V111_GNEWS_INTEGRADO':'1',
    'URURAU_V111_USAR_EXTRACAO_COMPLETA':'1',
    'URURAU_V111_USAR_CICLO_COMBINADO':'1',
    'URURAU_V110_MONITOR_GNEWS_LEGADO':'1',
    'URURAU_V108_GNEWS_TERMOS':'1',
    'URURAU_SOURCE_HUNTER_ATIVO':'1',
    'URURAU_AUTOFONTES_V131_ATIVO':'1',
    'URURAU_AUTO_DIAGNOSTICO_FONTE':'1',
    'URURAU_MONITOR_USAR_FILA_PAINEL':'1',
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
    'URURAU_V111_SCORE_MINIMO_PAUTA':'35',
    'URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO':'6',
    'URURAU_V111_GNEWS_MIN_CHARS_FONTE':'350',
    'URURAU_MIN_CHARS_FONTE_MONITOR':'350',
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
''')

# 3) Patch monitor.py: corrige chave de score, melhora log e contabiliza rascunho_local.
monitor = S / "ururau" / "publisher" / "monitor.py"
if monitor.exists():
    txt = read(monitor)
    backup(monitor)
    txt = txt.replace(
        'SCORE_MIN_MONITOR   = int(os.getenv("SCORE_MIN_MONITOR", str(_cfg_int_v47_12("score_minimo_rascunho", 55))))',
        'SCORE_MIN_MONITOR   = int(os.getenv("SCORE_MIN_MONITOR", str(_cfg_int_v47_12("score_minimo_monitor", _cfg_int_v47_12("score_minimo_rascunho", 35)))))'
    )
    txt = txt.replace(
        'f"    → v82 RASCUNHO CMS — score={score_ed} confiança={score_ap} "',
        'f"    → v82 RASCUNHO APROVADO PARA REVISÃO — score={score_ed} confiança={score_ap} "'
    )
    txt = txt.replace(
        'elif status_pipeline == "rascunho_cms":',
        'elif status_pipeline in {"rascunho_cms", "rascunho_local"}:'
    )
    txt = txt.replace(
        'f"    [RASCUNHO CMS] Matéria cadastrada como rascunho no painel do Ururau: {titulo}\\n"',
        'f"    [RASCUNHO] Matéria cadastrada/persistida para revisão: {titulo}\\n"'
    )
    marker = '# PATCH_V47_14_MONITOR_ENV'
    if marker not in txt:
        txt += r'''

# PATCH_V47_14_MONITOR_ENV
try:
    from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers as _v4714_defaults
    _v4714_defaults(globals().get('logger'), forcar=True)
except Exception:
    pass
'''
    monitor.write_text(txt, encoding="utf-8")
    print("[OK] patch monitor.py")

# 4) Patch decision_v82: rascunho mais flexível; direta continua rígida.
decision = S / "ururau" / "editorial" / "decision_v82.py"
if decision.exists():
    txt = read(decision)
    backup(decision)
    txt = txt.replace('score_min_rascunho = _int_env("URURAU_SCORE_MINIMO_RASCUNHO", 50)', 'score_min_rascunho = _int_env("URURAU_SCORE_MINIMO_RASCUNHO", 35)')
    txt = txt.replace('min_chars = _int_env("URURAU_MIN_CHARS_FONTE_MONITOR", 500)', 'min_chars = _int_env("URURAU_MIN_CHARS_FONTE_MONITOR", 350)')
    decision.write_text(txt, encoding="utf-8")
    print("[OK] patch decision_v82.py")

# 5) Launchers corretos: painel usa ururau_painel.py; monitor força env real de rascunho.
bat("02_ABRIR_PAINEL.bat", '@echo off\ncd /d "%~dp0sistema"\npython ururau_painel.py\npause\n')
bat("03_ABRIR_PAINEL_COM_LOG_VISIVEL.bat", '@echo off\ncd /d "%~dp0sistema"\npython ururau_painel.py\npause\n')
bat("04_MONITOR_24H_RASCUNHO.bat", '''@echo off
cd /d "%~dp0sistema"
set URURAU_MONITOR_MODO_CMS=rascunho
set URURAU_PUBLICAR_DIRETO=0
set URURAU_CMS_PUBLICACAO_DIRETA=0
set URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR=1
set SCORE_MIN_MONITOR=35
set URURAU_MONITOR_SCORE_MINIMO=35
set URURAU_SCORE_MINIMO_RASCUNHO=35
set URURAU_SCORE_MINIMO_DIRETA=90
set URURAU_MIN_CHARS_FONTE_MONITOR=350
set URURAU_V111_SCORE_MINIMO_PAUTA=35
set URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO=6
set URURAU_V111_GNEWS_JANELA_HORAS=12
set URURAU_V111_GNEWS_MIN_CHARS_FONTE=350
set URURAU_V111_GNEWS_INTEGRADO=1
set URURAU_V111_USAR_EXTRACAO_COMPLETA=1
set URURAU_V111_USAR_CICLO_COMBINADO=1
set URURAU_V110_MONITOR_GNEWS_LEGADO=1
set URURAU_V108_GNEWS_TERMOS=1
set URURAU_SOURCE_HUNTER_ATIVO=1
set URURAU_AUTOFONTES_V131_ATIVO=1
set URURAU_AUTO_DIAGNOSTICO_FONTE=1
python ururau_monitor.py --modo-cms rascunho
pause
''')
bat("10_TESTAR_MONITOR_CICLO_UNICO.bat", '''@echo off
cd /d "%~dp0sistema"
set URURAU_MONITOR_MODO_CMS=rascunho
set URURAU_PUBLICAR_DIRETO=0
set URURAU_CMS_PUBLICACAO_DIRETA=0
set URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR=1
set SCORE_MIN_MONITOR=35
set URURAU_SCORE_MINIMO_RASCUNHO=35
set URURAU_MIN_CHARS_FONTE_MONITOR=350
set URURAU_V111_SCORE_MINIMO_PAUTA=35
set URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO=6
set URURAU_V111_GNEWS_JANELA_HORAS=12
set URURAU_V111_GNEWS_INTEGRADO=1
set URURAU_V110_MONITOR_GNEWS_LEGADO=1
set URURAU_SOURCE_HUNTER_ATIVO=1
set URURAU_AUTOFONTES_V131_ATIVO=1
python ururau_monitor.py --modo-cms rascunho --ciclo-unico --intervalo 120 --max-hora 24
pause
''')
bat("11_VER_LOG_MONITOR.bat", '''@echo off
cd /d "%~dp0sistema"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path logs\\monitor.log) { Get-Content logs\\monitor.log -Tail 120 } else { Write-Host 'logs\\monitor.log ainda nao existe' }"
pause
''')

# 6) Validador rápido.
val = S / "ferramentas" / "validadores" / "VALIDAR_MONITOR_V47_14.py"
write(val, r'''# -*- coding: utf-8 -*-
from pathlib import Path
import json, os, sys
S = Path(__file__).resolve()
for p in S.parents:
    if p.name == 'sistema': ROOT=p; break
else: ROOT=Path.cwd()
errors=[]
def ok(c,m):
    print(('OK   ' if c else 'ERRO ') + m)
    if not c: errors.append(m)
cfg=json.loads((ROOT/'config'/'monitor_24h.json').read_text(encoding='utf-8'))
ok(cfg.get('score_minimo_monitor') == 35, 'score_minimo_monitor=35')
ok(cfg.get('score_minimo_rascunho') == 35, 'score_minimo_rascunho=35')
text=(ROOT/'ururau'/'coleta'/'scraper_defaults_v47_10.py').read_text(encoding='utf-8')
ok('forcar=False' in text and '**kwargs' in text, 'aplicar_defaults_scrapers aceita forcar')
mon=(ROOT/'ururau'/'publisher'/'monitor.py').read_text(encoding='utf-8')
ok('score_minimo_monitor' in mon, 'monitor.py lê chave score_minimo_monitor')
ok((ROOT.parent/'10_TESTAR_MONITOR_CICLO_UNICO.bat').exists(), 'BAT de teste ciclo único existe')
if errors:
    print('FALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO MONITOR V47.14 OK')
''')
bat("12_VALIDAR_MONITOR_V47_14.bat", '@echo off\ncd /d "%~dp0sistema"\npython ferramentas\\validadores\\VALIDAR_MONITOR_V47_14.py\npause\n')

# 7) Compilar críticos.
for p in [scraper, monitor, decision, val]:
    try:
        subprocess.run([sys.executable, "-m", "py_compile", str(p)], check=False)
    except Exception as e:
        print("[WARN] compile", p, e)

print("\n[V47.14] Hotfix aplicado.")
print("Rode agora:")
print("  .\\12_VALIDAR_MONITOR_V47_14.bat")
print("  .\\10_TESTAR_MONITOR_CICLO_UNICO.bat")
print("Depois, se o ciclo salvar rascunho ou bloquear com motivo claro:")
print("  .\\04_MONITOR_24H_RASCUNHO.bat")
