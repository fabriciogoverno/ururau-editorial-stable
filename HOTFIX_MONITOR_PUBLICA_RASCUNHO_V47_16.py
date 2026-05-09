# -*- coding: utf-8 -*-
"""
HOTFIX_MONITOR_PUBLICA_RASCUNHO_V47_16.py
Correção para o Monitor 24h do PAINEL realmente concluir rascunho/publicação.

Problema observado:
- O log chega em "v82 RASCUNHO CMS" ou inicia o monitor em RASCUNHO CMS real,
  mas não aparece confirmação final de rascunho salvo.
- Em modo rascunho, o monitor continuava usando coleta rígida de monitor e podia travar/bloquear
  antes de gerar rascunho revisável.

O que faz:
1) Em modo RASCUNHO, a coleta textual usa regra de painel/revisão, não gate rígido de autopublicação.
2) Reduz mínimos de texto para rascunho revisável, sem liberar publicação direta.
3) Adiciona logs obrigatórios depois da decisão v82 e depois da chamada CMS.
4) Cria spool local de rascunhos em sistema/dados/rascunhos_monitor/ quando o CMS falha.
5) Mantém publicação ao vivo rígida: só modo direto + gates + SEO + CMS.

Uso:
  python HOTFIX_MONITOR_PUBLICA_RASCUNHO_V47_16.py
  .\14_VALIDAR_MONITOR_PUBLICA_RASCUNHO_V47_16.bat
  .\02_ABRIR_PAINEL.bat
"""
from pathlib import Path
import json, re, shutil, subprocess, sys


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
print("[V47.16] Projeto:", BASE)


def backup(p: Path):
    if p.exists():
        b = p.with_suffix(p.suffix + ".bak_v47_16")
        if not b.exists():
            try: shutil.copy2(p, b)
            except Exception as e: print("[WARN] backup falhou", p, e)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    backup(p)
    p.write_text(content, encoding="utf-8")
    print("[OK]", p.relative_to(BASE))


def bat(name: str, content: str):
    write(BASE / name, content.replace("\n", "\r\n"))

# 1) Config: modo rascunho mais flexível; direta continua rígida.
cfg_path = S / "config" / "monitor_24h.json"
try:
    cfg = json.loads(read(cfg_path)) if cfg_path.exists() else {}
except Exception:
    cfg = {}
if not isinstance(cfg, dict): cfg = {}
cfg.update({
    "modo_cms_padrao": "rascunho",
    "score_minimo_monitor": 30,
    "score_minimo_rascunho": 30,
    "score_minimo_gnews": 30,
    "texto_minimo_rascunho_chars": 350,
    "texto_minimo_util_chars": 350,
    "min_chars_fonte_gnews": 250,
    "min_chars_fonte_monitor_rascunho": 350,
    "permitir_rascunho_com_texto_minimo": True,
    "salvar_spool_local_se_cms_falhar": True,
    "seo_minimo_publicacao_direta": 90,
})
coleta = cfg.get("coleta") if isinstance(cfg.get("coleta"), dict) else {}
coleta.update({
    "google_news_integrado_v111": True,
    "google_news_fallback_v110": True,
    "google_news_rss_legado_v108": True,
    "autofontes_diagnostico_v131": True,
    "source_hunter": True,
    "fila_painel_monitor": True,
    "score_minimo_gnews": 30,
    "min_chars_fonte_gnews": 250,
})
cfg["coleta"] = coleta
write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2))

# 2) Módulo de spool local para nunca sumir rascunho quando CMS falha.
spool = S / "ururau" / "publisher" / "rascunho_spool_v47_16.py"
write(spool, r'''# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import json, time, re

def _sistema_root():
    p = Path(__file__).resolve()
    for parent in p.parents:
        if parent.name == 'sistema': return parent
    return Path.cwd()

def _safe(obj):
    try:
        if hasattr(obj, 'to_dict'): return obj.to_dict()
        if isinstance(obj, dict): return obj
        return {k: getattr(obj, k) for k in dir(obj) if not k.startswith('_') and k in {'titulo','subtitulo','corpo','canal','tags','retranca','chamada_social','score_risco'}}
    except Exception:
        return {'repr': repr(obj)}

def salvar_rascunho_spool(uid, pauta, materia, imagem=None, motivo='cms_falhou'):
    root = _sistema_root()
    pasta = root / 'dados' / 'rascunhos_monitor'
    pasta.mkdir(parents=True, exist_ok=True)
    m = _safe(materia)
    p = dict(pauta or {})
    titulo = str(m.get('titulo') or p.get('titulo_origem') or 'rascunho').strip()
    slug = re.sub(r'[^a-zA-Z0-9_-]+','-', titulo)[:80].strip('-') or str(uid)[:8]
    item = {
        'uid': uid,
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'motivo': motivo,
        'titulo': titulo,
        'link_origem': p.get('link_origem'),
        'fonte_nome': p.get('fonte_nome') or p.get('nome_fonte'),
        'pauta': p,
        'materia': m,
        'imagem': _safe(imagem) if imagem else None,
        'status_pipeline': 'rascunho_spool_local',
    }
    json_path = pasta / f'{time.strftime("%Y%m%d_%H%M%S")}_{slug}.json'
    json_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
    index = pasta / 'index.jsonl'
    with index.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'uid': uid, 'titulo': titulo, 'arquivo': str(json_path), 'motivo': motivo, 'ts': item['ts']}, ensure_ascii=False) + '\n')
    return str(json_path)
''')

# 3) Patch defaults de env.
scraper = S / "ururau" / "coleta" / "scraper_defaults_v47_10.py"
if scraper.exists():
    txt = read(scraper)
    backup(scraper)
    if "URURAU_V104_MIN_CHARS_ARTIGO" not in txt:
        txt = txt.replace("'URURAU_MIN_CHARS_FONTE_MONITOR':'350',", "'URURAU_MIN_CHARS_FONTE_MONITOR':'350',\n    'URURAU_V104_MIN_CHARS_ARTIGO':'350',\n    'URURAU_V105_MIN_CHARS_FONTE_OK':'350',")
    if "URURAU_MONITOR_COLETA_RASCUNHO_FLEXIVEL" not in txt:
        txt = txt.replace("'URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR':'1',", "'URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR':'1',\n    'URURAU_MONITOR_COLETA_RASCUNHO_FLEXIVEL':'1',")
    scraper.write_text(txt, encoding="utf-8")
    print("[OK] scraper defaults ajustado")

# 4) Patch do monitor: em modo rascunho, usa coleta flexível e spool se CMS falhar.
monitor = S / "ururau" / "publisher" / "monitor.py"
texto = read(monitor)
backup(monitor)

# 4a) troca chamada de coleta rígida.
old = 'if not wf.etapa_coleta_texto(uid, pauta, modo="monitor"):'
new = 'modo_coleta_v47_16 = "monitor" if self.permitir_publicacao_direta else "panel"\n        self._log.info(f"  [V47.16] Coleta textual em modo={modo_coleta_v47_16} para destino={self.modo_cms}")\n        if not wf.etapa_coleta_texto(uid, pauta, modo=modo_coleta_v47_16):'
if old in texto and 'modo_coleta_v47_16' not in texto:
    texto = texto.replace(old, new)

# 4b) status rascunho local conta como processado.
texto = texto.replace('elif status_pipeline == "rascunho_cms":', 'elif status_pipeline in {"rascunho_cms", "rascunho_spool_local", "rascunho_local"}:')
texto = texto.replace('[RASCUNHO CMS] Matéria cadastrada como rascunho no painel do Ururau:', '[RASCUNHO] Matéria cadastrada/salva para revisão:')

# 4c) quando falha CMS no destino salvar_rascunho, salva spool local antes de retornar.
old2 = 'self._log.warning("  [v82][CMS] Falha ao salvar rascunho no painel; backup local já foi persistido.")\n                return {"ok": False, "status_pipeline": "erro_cms", "erro": "falha ao salvar rascunho no CMS"}'
new2 = '''self._log.warning("  [v82][CMS] Falha ao salvar rascunho no painel; salvando spool local operacional.")
                try:
                    from ururau.publisher.rascunho_spool_v47_16 import salvar_rascunho_spool
                    arq_spool = salvar_rascunho_spool(uid, pauta, materia, imagem, motivo="falha ao salvar rascunho no CMS")
                    self._log.info(f"  [V47.16][SPOOL] Rascunho salvo localmente para revisão: {arq_spool}")
                    return {"ok": True, "status_pipeline": "rascunho_spool_local", "erro": "CMS falhou; rascunho salvo em spool local", "spool": arq_spool, "publicado": False, "rascunho": True}
                except Exception as _e_spool:
                    self._log.warning(f"  [V47.16][SPOOL] Falhou também: {_e_spool}")
                return {"ok": False, "status_pipeline": "erro_cms", "erro": "falha ao salvar rascunho no CMS"}'''
if old2 in texto:
    texto = texto.replace(old2, new2)

# 4d) similar no bloco de direta convertida para rascunho.
old3 = 'return {"ok": False, "status_pipeline": "erro_cms", "erro": "falha ao salvar rascunho no CMS"}\n            return {"ok": True, "status_pipeline": "rascunho_local", "publicado": False, "rascunho": True}'
new3 = '''try:
                    from ururau.publisher.rascunho_spool_v47_16 import salvar_rascunho_spool
                    arq_spool = salvar_rascunho_spool(uid, pauta, materia, imagem, motivo="falha ao salvar rascunho no CMS")
                    self._log.info(f"  [V47.16][SPOOL] Rascunho salvo localmente para revisão: {arq_spool}")
                    return {"ok": True, "status_pipeline": "rascunho_spool_local", "erro": "CMS falhou; rascunho salvo em spool local", "spool": arq_spool, "publicado": False, "rascunho": True}
                except Exception:
                    pass
                return {"ok": False, "status_pipeline": "erro_cms", "erro": "falha ao salvar rascunho no CMS"}
            return {"ok": True, "status_pipeline": "rascunho_local", "publicado": False, "rascunho": True}'''
if old3 in texto:
    texto = texto.replace(old3, new3)

# 4e) marcador env de thresholds no final.
if '# PATCH_V47_16_MONITOR_RASCUNHO' not in texto:
    texto += r'''

# PATCH_V47_16_MONITOR_RASCUNHO
try:
    import os as _os_v4716
    _os_v4716.environ.setdefault('URURAU_MONITOR_COLETA_RASCUNHO_FLEXIVEL', '1')
    _os_v4716.environ.setdefault('URURAU_V104_MIN_CHARS_ARTIGO', '350')
    _os_v4716.environ.setdefault('URURAU_V105_MIN_CHARS_FONTE_OK', '350')
    _os_v4716.environ.setdefault('URURAU_MIN_CHARS_FONTE_MONITOR', '350')
except Exception:
    pass
'''
monitor.write_text(texto, encoding="utf-8")
print("[OK] monitor.py corrigido para rascunho operacional")

# 5) Patch workflow: se rascunho/panel, min 350; não afeta direta monitor.
workflow = S / "ururau" / "publisher" / "workflow.py"
w = read(workflow)
backup(workflow)
# Garante que defaults são 350 quando env não define.
w = w.replace('os.getenv("URURAU_MIN_CHARS_TEXTO_FONTE", "900")', 'os.getenv("URURAU_MIN_CHARS_TEXTO_FONTE", "350")')
w = w.replace('"900")) or "900")', '"350")) or "350")')
w = w.replace('"900") or "900")', '"350") or "350")')
workflow.write_text(w, encoding="utf-8")
print("[OK] workflow.py thresholds de rascunho ajustados")

# 6) Patch painel V47.15 para setar env de min chars e score.
patch_painel = S / "ururau" / "ui" / "patch_v47_15_monitor_painel.py"
if patch_painel.exists():
    ptxt = read(patch_painel)
    backup(patch_painel)
    if "URURAU_V104_MIN_CHARS_ARTIGO" not in ptxt:
        ptxt = ptxt.replace("'URURAU_MIN_CHARS_FONTE_MONITOR': str(_int_cfg('min_chars_fonte_gnews', 350)),", "'URURAU_MIN_CHARS_FONTE_MONITOR': str(_int_cfg('min_chars_fonte_monitor_rascunho', 350)),\n        'URURAU_V104_MIN_CHARS_ARTIGO': str(_int_cfg('texto_minimo_rascunho_chars', 350)),\n        'URURAU_V105_MIN_CHARS_FONTE_OK': str(_int_cfg('texto_minimo_rascunho_chars', 350)),")
    patch_painel.write_text(ptxt, encoding="utf-8")
    print("[OK] patch painel v47.15 recebeu thresholds v47.16")

# 7) BATs corretos.
bat("02_ABRIR_PAINEL.bat", '@echo off\ncd /d "%~dp0sistema"\npython ururau_painel.py\npause\n')
bat("04_MONITOR_24H_RASCUNHO.bat", '''@echo off
cd /d "%~dp0sistema"
set URURAU_MONITOR_MODO_CMS=rascunho
set URURAU_PUBLICAR_DIRETO=0
set URURAU_CMS_PUBLICACAO_DIRETA=0
set URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR=1
set URURAU_MONITOR_COLETA_RASCUNHO_FLEXIVEL=1
set SCORE_MIN_MONITOR=30
set URURAU_MONITOR_SCORE_MINIMO=30
set URURAU_SCORE_MINIMO_RASCUNHO=30
set URURAU_SCORE_MINIMO_DIRETA=90
set URURAU_MIN_CHARS_FONTE_MONITOR=350
set URURAU_V104_MIN_CHARS_ARTIGO=350
set URURAU_V105_MIN_CHARS_FONTE_OK=350
set URURAU_V111_SCORE_MINIMO_PAUTA=30
set URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO=6
set URURAU_V111_GNEWS_JANELA_HORAS=12
set URURAU_V111_GNEWS_MIN_CHARS_FONTE=250
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

# 8) Validador.
val = S / "ferramentas" / "validadores" / "VALIDAR_MONITOR_PUBLICA_RASCUNHO_V47_16.py"
write(val, r'''# -*- coding: utf-8 -*-
from pathlib import Path
import json, sys
S=Path(__file__).resolve()
for p in S.parents:
    if p.name=='sistema': ROOT=p; break
else: ROOT=Path.cwd()
errors=[]
def ok(c,m):
    print(('OK   ' if c else 'ERRO ') + m)
    if not c: errors.append(m)
cfg=json.loads((ROOT/'config'/'monitor_24h.json').read_text(encoding='utf-8'))
ok(cfg.get('score_minimo_rascunho')==30,'score_minimo_rascunho=30')
ok(cfg.get('texto_minimo_rascunho_chars')==350,'texto_minimo_rascunho_chars=350')
mon=(ROOT/'ururau'/'publisher'/'monitor.py').read_text(encoding='utf-8')
ok('modo_coleta_v47_16' in mon,'monitor usa modo de coleta flexível para rascunho')
ok('rascunho_spool_v47_16' in mon,'monitor salva spool local se CMS falhar')
ok((ROOT/'ururau'/'publisher'/'rascunho_spool_v47_16.py').exists(),'spool de rascunhos existe')
wf=(ROOT/'ururau'/'publisher'/'workflow.py').read_text(encoding='utf-8')
ok('"350"' in wf,'workflow contém threshold 350 para rascunho')
if errors:
    print('\nFALHAS:', errors); sys.exit(1)
print('\nVALIDAÇÃO MONITOR PUBLICA/RASCUNHO V47.16 OK')
''')
bat("14_VALIDAR_MONITOR_PUBLICA_RASCUNHO_V47_16.bat", '@echo off\ncd /d "%~dp0sistema"\npython ferramentas\\validadores\\VALIDAR_MONITOR_PUBLICA_RASCUNHO_V47_16.py\npause\n')

# 9) Compilar críticos.
for p in [monitor, workflow, spool, patch_painel, val]:
    if p.exists():
        subprocess.run([sys.executable, "-m", "py_compile", str(p)], check=False)

print("\n[V47.16] Aplicado.")
print("Rode agora:")
print("  .\\14_VALIDAR_MONITOR_PUBLICA_RASCUNHO_V47_16.bat")
print("  .\\02_ABRIR_PAINEL.bat")
print("No painel: Monitor > Publicar diretamente DESMARCADO > Iniciar.")
print("Se CMS falhar, veja sistema\\dados\\rascunhos_monitor\\index.jsonl")
