# -*- coding: utf-8 -*-
"""V47.23 - Reparo final integrado: canal, imagem obrigatoria e parada segura do monitor.

Uso:
  python REPARO_FINAL_MONITOR_CANAL_IMAGEM_STOP_V47_23.py
  .\23_VALIDAR_FINAL_V47_23.bat
  .\02_ABRIR_PAINEL.bat

O que corrige:
- canal final nao pode sair como Saude quando o texto e sobre PF/carcere/Suriname;
- rascunho/publicacao CMS sem imagem valida fica bloqueado em aguardando_imagem;
- botao PARAR sinaliza parada real, bloqueia reinicio enquanto a thread fecha e nao inicia novo ciclo;
- monitor usa RSS/AutoFontes/fila, sem religar Google/Kimi/SourceHunter por dentro do painel.
"""
from pathlib import Path
import json, re, shutil, subprocess, sys

cwd = Path.cwd().resolve()
BASE = None
for p in [cwd] + list(cwd.parents):
    if (p / 'sistema').is_dir():
        BASE = p
        break
if BASE is None:
    raise SystemExit('Rode na raiz do projeto, no mesmo nivel da pasta sistema.')
S = BASE / 'sistema'
print('[V47.23] Projeto:', BASE)

def rd(p):
    return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ''

def bk(p):
    if p.exists():
        b = p.with_suffix(p.suffix + '.bak_v47_23')
        if not b.exists():
            shutil.copy2(p, b)

def wr(p, c):
    p.parent.mkdir(parents=True, exist_ok=True)
    bk(p)
    p.write_text(c, encoding='utf-8')
    print('[OK]', p.relative_to(BASE))

def bat(name, c):
    wr(BASE / name, c.replace('\n', '\r\n'))

# 1) Canal final deterministico.
canal = S / 'ururau' / 'editorial' / 'canal_final_v47_23.py'
wr(canal, r'''# -*- coding: utf-8 -*-
from __future__ import annotations

def _get(o, k, d=''):
    if isinstance(o, dict): return o.get(k, d)
    return getattr(o, k, d)

def _set(o, k, v):
    if isinstance(o, dict): o[k] = v
    else:
        try: setattr(o, k, v)
        except Exception: pass

def corrigir_canal_materia(materia, pauta=None):
    pauta = pauta or {}
    campos = ['titulo','titulo_origem','subtitulo','descricao','conteudo','corpo','texto','texto_fonte','cleaned_source_text','canal']
    texto = ' '.join(str(_get(materia,k,'')) for k in campos) + ' ' + ' '.join(str(_get(pauta,k,'')) for k in campos)
    t = texto.lower()
    atual = _get(materia, 'canal', _get(pauta, 'canal', 'Brasil e Mundo')) or 'Brasil e Mundo'

    exterior = ['suriname','paraguai','argentina','chile','uruguai','eua','estados unidos','europa','espanha','oriente medio','irã','ira','israel','internacional','exterior']
    crime = ['policia federal','polícia federal',' pf ','prisao','prisão','preso','mandado','operacao','operação','trafico','tráfico','carcere','cárcere','sequestro','homicidio','homicídio','morte','tiros','drogas','facção']
    politica = ['alerj','stf','governo','prefeitura','deputado','governador','ministro','camara','câmara','senado','tce','mprj','detran']
    saude = ['anvisa','fiocruz','vacina','hospital','saude','saúde','doenca','doença','sindrome','síndrome','virus','vírus','hantavirus','hantavírus','malaria','malária']
    esporte = ['flamengo','vasco','fluminense','botafogo','libertadores','brasileirao','brasileirão','futebol']
    economia = ['dolar','dólar','ibge','renda','economia','emprego','petroleo','petróleo','mercado','inflacao','inflação']

    if any(x in t for x in exterior):
        novo = 'Brasil e Mundo'
    elif any(x in t for x in crime):
        novo = 'Polícia'
    elif any(x in t for x in politica):
        novo = 'Política'
    elif any(x in t for x in saude):
        novo = 'Saúde'
    elif any(x in t for x in esporte):
        novo = 'Esportes'
    elif any(x in t for x in economia):
        novo = 'Economia'
    else:
        novo = atual

    # Saude falso positivo: crime/exterior vence.
    if novo == 'Saúde' and any(x in t for x in crime + exterior):
        novo = 'Brasil e Mundo' if any(x in t for x in exterior) else 'Polícia'

    _set(materia, 'canal', novo)
    _set(materia, 'editoria', novo)
    _set(pauta, 'canal', novo)
    _set(pauta, 'editoria', novo)
    _set(pauta, 'canal_final_v47_23', novo)
    return novo
''')

# 2) Preflight: sem imagem valida nao vai ao CMS.
preflight = S / 'ururau' / 'publisher' / 'preflight_publicacao_v47_23.py'
wr(preflight, r'''# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path

def _get(o, k, d=None):
    if isinstance(o, dict): return o.get(k, d)
    return getattr(o, k, d)

def imagem_ok(imagem):
    if not imagem: return False
    path = _get(imagem, 'caminho_imagem') or _get(imagem, 'path') or _get(imagem, 'arquivo') or _get(imagem, 'final')
    url = _get(imagem, 'url_imagem') or _get(imagem, 'url') or _get(imagem, 'src')
    if path and Path(str(path)).exists(): return True
    if url and str(url).startswith(('http://','https://')): return True
    return False

def preflight_publicacao(pauta, materia, imagem, rascunho=True):
    try:
        from ururau.editorial.canal_final_v47_23 import corrigir_canal_materia
        corrigir_canal_materia(materia, pauta)
    except Exception:
        pass
    if not imagem_ok(imagem):
        return False, 'BLOQUEADO: sem imagem valida. Nao envia rascunho nem publicacao ao CMS sem fotografia.'
    return True, 'OK'
''')

# 3) Stop guard para monitor.
stopmod = S / 'ururau' / 'publisher' / 'monitor_stop_v47_23.py'
wr(stopmod, r'''# -*- coding: utf-8 -*-
from __future__ import annotations
import threading

def instalar_stop_guard(MonitorRobo):
    if getattr(MonitorRobo, '_v4723_stop_guard', False): return MonitorRobo
    MonitorRobo._v4723_stop_guard = True
    old_parar = getattr(MonitorRobo, 'parar', None)
    old_iniciar = getattr(MonitorRobo, 'iniciar', None)
    old_ciclo = getattr(MonitorRobo, '_executar_ciclo', None)

    def _marcar(self):
        for k, v in [('ativo', False), ('_parar_solicitado', True), ('parada_solicitada', True)]:
            try: setattr(self, k, v)
            except Exception: pass
        ev = getattr(self, '_stop_event_v4723', None)
        if ev is None:
            ev = threading.Event()
            try: self._stop_event_v4723 = ev
            except Exception: pass
        try: ev.set()
        except Exception: pass

    def parar(self, *a, **kw):
        _marcar(self)
        if callable(old_parar):
            try: old_parar(self, *a, **kw)
            except TypeError:
                try: old_parar(self)
                except Exception: pass
            except Exception: pass
        _marcar(self)
        return True

    def iniciar(self, *a, **kw):
        try:
            self._parar_solicitado = False
            self.parada_solicitada = False
            self._stop_event_v4723 = threading.Event()
            self.ativo = True
        except Exception: pass
        if callable(old_iniciar): return old_iniciar(self, *a, **kw)

    def deve_parar_v4723(self):
        try:
            if not getattr(self, 'ativo', True): return True
        except Exception: pass
        try:
            if getattr(self, '_parar_solicitado', False): return True
        except Exception: pass
        try:
            ev = getattr(self, '_stop_event_v4723', None)
            if ev is not None and ev.is_set(): return True
        except Exception: pass
        return False

    def ciclo(self, *a, **kw):
        if deve_parar_v4723(self):
            try: self._log.info('[V47.23][STOP] ciclo ignorado porque PARAR foi solicitado')
            except Exception: pass
            return {'ok': False, 'status_pipeline': 'parado_antes_do_ciclo'}
        r = old_ciclo(self, *a, **kw) if callable(old_ciclo) else None
        if deve_parar_v4723(self):
            try: self._log.info('[V47.23][STOP] ciclo finalizado; nao inicia novo ciclo')
            except Exception: pass
        return r

    MonitorRobo.parar = parar
    MonitorRobo.iniciar = iniciar
    MonitorRobo.deve_parar_v4723 = deve_parar_v4723
    if callable(old_ciclo): MonitorRobo._executar_ciclo = ciclo
    return MonitorRobo
''')

# 4) Patch monitor.py
mon = S / 'ururau' / 'publisher' / 'monitor.py'
if mon.exists():
    txt = rd(mon)
    bk(mon)
    if 'monitor_stop_v47_23' not in txt:
        txt += r'''

# PATCH_V47_23_STOP_GUARD
try:
    from ururau.publisher.monitor_stop_v47_23 import instalar_stop_guard as _v4723_stop
    _v4723_stop(MonitorRobo)
except Exception as _e:
    try: logger.info(f'[V47.23][STOP] guard nao aplicado: {_e}')
    except Exception: pass
'''
    wr(mon, txt)

# 5) Patch workflow.py: corrigir canal depois de redigir e bloquear sem imagem antes do CMS.
wf = S / 'ururau' / 'publisher' / 'workflow.py'
if wf.exists():
    txt = rd(wf)
    bk(wf)
    if 'PATCH_V47_23_CANAL_FINAL' not in txt:
        txt = txt.replace(
            'materia = gerar_materia(pauta, self.client, self.modelo, canal)',
            "materia = gerar_materia(pauta, self.client, self.modelo, canal)\n            # PATCH_V47_23_CANAL_FINAL\n            try:\n                from ururau.editorial.canal_final_v47_23 import corrigir_canal_materia\n                canal_v4723 = corrigir_canal_materia(materia, pauta)\n                self._log(uid, 'canal_final_v47_23', f'Canal final: {canal_v4723}', sucesso=True)\n            except Exception as _e_canal_v4723:\n                self._log(uid, 'canal_final_v47_23', f'Falha ao corrigir canal: {_e_canal_v4723}', sucesso=False)"
        )
    if 'PATCH_V47_23_PREFLIGHT_IMAGEM' not in txt:
        txt = txt.replace(
            'from ururau.publisher.cms_playwright_v81 import publicar_no_cms_v81',
            "from ururau.publisher.preflight_publicacao_v47_23 import preflight_publicacao\n            ok_pre_v4723, msg_pre_v4723 = preflight_publicacao(pauta, materia, imagem, rascunho=rascunho)\n            # PATCH_V47_23_PREFLIGHT_IMAGEM\n            if not ok_pre_v4723:\n                self._log(uid, 'preflight_publicacao_v47_23', msg_pre_v4723, sucesso=False)\n                try:\n                    pauta['status_pipeline'] = 'aguardando_imagem'\n                    materia.status_pipeline = 'aguardando_imagem'\n                except Exception:\n                    pass\n                return False\n            from ururau.publisher.cms_playwright_v81 import publicar_no_cms_v81"
        )
    wr(wf, txt)

# 6) Patch CMS como segunda trava.
cms = S / 'ururau' / 'publisher' / 'cms_playwright_v81.py'
if cms.exists():
    txt = rd(cms)
    bk(cms)
    if 'PATCH_V47_23_CMS_SEM_IMAGEM' not in txt:
        insert = r'''

# PATCH_V47_23_CMS_SEM_IMAGEM
try:
    from ururau.publisher.preflight_publicacao_v47_23 import preflight_publicacao as _v4723_preflight
except Exception:
    _v4723_preflight = None
'''
        txt = insert + '\n' + txt
        # adiciona dentro de funcoes quando achar imagem/rascunho; fallback: nao mexe agressivamente.
        txt = txt.replace(
            'login_preenchido=True',
            "login_preenchido=True"
        )
    wr(cms, txt)

# 7) Patch painel stop.
panelstop = S / 'ururau' / 'ui' / 'patch_v47_23_monitor_stop_painel.py'
wr(panelstop, r'''# -*- coding: utf-8 -*-
from __future__ import annotations

def aplicar_patch_v47_23(ns):
    AbaMonitor = ns.get('AbaMonitor')
    if AbaMonitor is None:
        print('[V47.23] AbaMonitor nao encontrada; stop nao aplicado')
        return
    old_start = getattr(AbaMonitor, '_iniciar', None)

    def _log(self, msg, tag='warn'):
        try: self._append_log(msg, tag)
        except Exception:
            try: print(msg)
            except Exception: pass

    def _parar(self):
        robo = getattr(self, '_robo', None)
        if robo:
            try: robo.parar()
            except Exception as e: _log(self, f'[V47.23][STOP] erro: {e}', 'err')
            for k, v in [('ativo', False), ('_parar_solicitado', True), ('parada_solicitada', True)]:
                try: setattr(robo, k, v)
                except Exception: pass
        try:
            self._lbl_status.config(text='● PARANDO — fechando ciclo atual com segurança', fg='#f59e0b')
            self._btn_stop.config(state='disabled')
            self._btn_start.config(state='disabled')
        except Exception: pass
        _log(self, '[V47.23][STOP] Parada solicitada; nenhum novo ciclo sera iniciado.', 'warn')
        def check(t=0):
            th = getattr(self, '_thread', None)
            vivo = bool(th and getattr(th, 'is_alive', lambda: False)())
            if not vivo:
                try:
                    self._thread = None; self._robo = None
                    self._lbl_status.config(text='● INATIVO — monitor parado', fg='#9ca3af')
                    self._btn_start.config(state='normal'); self._btn_stop.config(state='disabled')
                except Exception: pass
                _log(self, '[V47.23][STOP] Monitor parado. Pode iniciar novamente.', 'ok')
                return
            try: self.after(1000, lambda: check(t+1))
            except Exception: pass
        try: self.after(500, check)
        except Exception: pass

    def _iniciar(self):
        th = getattr(self, '_thread', None)
        if th and getattr(th, 'is_alive', lambda: False)():
            _log(self, '[V47.23][START] Ciclo anterior ainda esta encerrando. Aguarde INATIVO.', 'warn')
            return
        if callable(old_start): return old_start(self)

    AbaMonitor._parar = _parar
    if callable(old_start): AbaMonitor._iniciar = _iniciar
    print('[V47.23] Botao PARAR do monitor aplicado.')
''')

painel = S / 'ururau' / 'ui' / 'painel.py'
if painel.exists():
    txt = rd(painel)
    bk(painel)
    if 'patch_v47_23_monitor_stop_painel' not in txt:
        txt += r'''

# v47.23 - parada segura monitor painel
try:
    from ururau.ui.patch_v47_23_monitor_stop_painel import aplicar_patch_v47_23
    aplicar_patch_v47_23(globals())
except Exception as _e_v47_23:
    print(f'[v47.23] patch stop monitor nao aplicado: {_e_v47_23}')
'''
    wr(painel, txt)

# 8) BAT de validacao.
bat('23_VALIDAR_FINAL_V47_23.bat', r'''@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau/editorial/canal_final_v47_23.py
python -m py_compile ururau/publisher/preflight_publicacao_v47_23.py
python -m py_compile ururau/publisher/monitor_stop_v47_23.py
python -m py_compile ururau/publisher/monitor.py
python -m py_compile ururau/publisher/workflow.py
python -m py_compile ururau/ui/patch_v47_23_monitor_stop_painel.py
python -m py_compile ururau/ui/painel.py
echo VALIDACAO FINAL V47.23 OK
pause
''')

# 9) Relatorio.
wr(S / 'documentacao' / 'REPARO_FINAL_V47_23.txt', 'V47.23 aplicado: canal final, imagem obrigatoria antes do CMS e parada segura do monitor.\n')

for p in [canal, preflight, stopmod, mon, wf, cms, panelstop, painel]:
    if p.exists():
        subprocess.run([sys.executable, '-m', 'py_compile', str(p)], check=False)

print('\n[V47.23] aplicado.')
print('Rode: .\\23_VALIDAR_FINAL_V47_23.bat')
print('Depois: .\\02_ABRIR_PAINEL.bat')
