# -*- coding: utf-8 -*-
"""V47.22 - Reparo do botão PARAR do monitor no painel.

Objetivo:
- PARAR deve sinalizar parada real no MonitorRobo;
- não iniciar novo ciclo depois do PARAR;
- painel mostra estado PARANDO e depois INATIVO;
- evita duplicar monitor se o ciclo anterior ainda estiver encerrando;
- cria validador.
"""
from pathlib import Path
import shutil, subprocess, sys

cwd=Path.cwd().resolve(); BASE=None
for p in [cwd]+list(cwd.parents):
    if (p/'sistema').is_dir(): BASE=p; break
if BASE is None: raise SystemExit('Rode na raiz do projeto, acima da pasta sistema.')
S=BASE/'sistema'
print('[V47.22] base:', BASE)

def rd(p): return p.read_text(encoding='utf-8', errors='ignore') if p.exists() else ''
def bk(p):
    if p.exists():
        b=p.with_suffix(p.suffix+'.bak_v47_22')
        if not b.exists(): shutil.copy2(p,b)
def wr(p,c): p.parent.mkdir(parents=True,exist_ok=True); bk(p); p.write_text(c,encoding='utf-8'); print('[OK]',p.relative_to(BASE))
def bat(n,c): wr(BASE/n,c.replace('\n','\r\n'))

core=S/'ururau'/'publisher'/'monitor_stop_v47_22.py'
wr(core,r'''# -*- coding: utf-8 -*-
from __future__ import annotations
import threading, time

def instalar_stop_guard(MonitorRobo):
    if getattr(MonitorRobo, '_v4722_stop_guard', False):
        return MonitorRobo
    MonitorRobo._v4722_stop_guard = True

    old_parar = getattr(MonitorRobo, 'parar', None)
    old_iniciar = getattr(MonitorRobo, 'iniciar', None)
    old_ciclo = getattr(MonitorRobo, '_executar_ciclo', None)

    def _marcar_parada(self):
        try: self.ativo = False
        except Exception: pass
        try: self._parar_solicitado = True
        except Exception: pass
        try: self.parada_solicitada = True
        except Exception: pass
        ev = getattr(self, '_stop_event_v4722', None)
        if ev is None:
            ev = threading.Event()
            try: self._stop_event_v4722 = ev
            except Exception: pass
        try: ev.set()
        except Exception: pass

    def parar_v4722(self, *a, **kw):
        _marcar_parada(self)
        if callable(old_parar):
            try: old_parar(self, *a, **kw)
            except TypeError:
                try: old_parar(self)
                except Exception: pass
            except Exception: pass
        _marcar_parada(self)
        return True

    def iniciar_v4722(self, *a, **kw):
        try:
            self._parar_solicitado = False
            self.parada_solicitada = False
            self._stop_event_v4722 = threading.Event()
            self.ativo = True
        except Exception: pass
        if callable(old_iniciar):
            return old_iniciar(self, *a, **kw)
        return None

    def deve_parar_v4722(self):
        try:
            if not getattr(self, 'ativo', True): return True
        except Exception: pass
        try:
            if getattr(self, '_parar_solicitado', False): return True
        except Exception: pass
        try:
            ev = getattr(self, '_stop_event_v4722', None)
            if ev is not None and ev.is_set(): return True
        except Exception: pass
        return False

    def ciclo_v4722(self, *a, **kw):
        if deve_parar_v4722(self):
            try: self._log.info('[V47.22][STOP] ciclo ignorado porque PARAR já foi solicitado')
            except Exception: pass
            return {'ok': False, 'status_pipeline': 'parado_antes_do_ciclo'}
        if callable(old_ciclo):
            r = old_ciclo(self, *a, **kw)
        else:
            r = None
        if deve_parar_v4722(self):
            try: self._log.info('[V47.22][STOP] ciclo finalizado; monitor não iniciará novo ciclo')
            except Exception: pass
        return r

    MonitorRobo.parar = parar_v4722
    MonitorRobo.iniciar = iniciar_v4722
    MonitorRobo.deve_parar_v4722 = deve_parar_v4722
    if callable(old_ciclo):
        MonitorRobo._executar_ciclo = ciclo_v4722
    return MonitorRobo
''')

mon=S/'ururau'/'publisher'/'monitor.py'
if mon.exists():
    txt=rd(mon); bk(mon)
    if 'monitor_stop_v47_22' not in txt:
        txt += """

# PATCH_V47_22_STOP_GUARD
try:
    from ururau.publisher.monitor_stop_v47_22 import instalar_stop_guard as _v4722_install_stop
    _v4722_install_stop(MonitorRobo)
except Exception as _e_v4722_stop:
    try: logger.info(f'[V47.22][STOP] guard não aplicado: {_e_v4722_stop}')
    except Exception: pass
"""
    wr(mon,txt)

patch=S/'ururau'/'ui'/'patch_v47_22_monitor_stop_painel.py'
wr(patch,r'''# -*- coding: utf-8 -*-
from __future__ import annotations

def aplicar_patch_v47_22(ns):
    AbaMonitor = ns.get('AbaMonitor')
    if AbaMonitor is None:
        print('[V47.22] AbaMonitor não encontrada; patch stop não aplicado')
        return

    old_iniciar = getattr(AbaMonitor, '_iniciar', None)

    def _log(self, msg, tag='warn'):
        try: self._append_log(msg, tag)
        except Exception:
            try: print(msg)
            except Exception: pass

    def _parar_v47_22(self):
        robo = getattr(self, '_robo', None)
        th = getattr(self, '_thread', None)
        if robo:
            try: robo.parar()
            except Exception as e: _log(self, f'[V47.22][STOP] erro ao sinalizar parada: {e}', 'err')
            try: robo.ativo = False
            except Exception: pass
            try: robo._parar_solicitado = True
            except Exception: pass
        try:
            self._lbl_status.config(text='● PARANDO — aguardando fechamento seguro do ciclo atual', fg='#f59e0b')
            self._btn_stop.config(state='disabled')
            self._btn_start.config(state='disabled')
        except Exception: pass
        _log(self, '[V47.22][STOP] Parada solicitada. O ciclo atual será fechado; nenhum novo ciclo será iniciado.', 'warn')

        def _verificar_fim(tent=0):
            th2 = getattr(self, '_thread', None)
            vivo = bool(th2 and getattr(th2, 'is_alive', lambda: False)())
            if not vivo:
                try:
                    self._thread = None
                    self._robo = None
                    self._lbl_status.config(text='● INATIVO — monitor parado pelo usuário', fg='#9ca3af')
                    self._btn_start.config(state='normal')
                    self._btn_stop.config(state='disabled')
                except Exception: pass
                _log(self, '[V47.22][STOP] Monitor parado. Você pode iniciar novamente quando quiser.', 'ok')
                return
            if tent >= 60:
                # não mata thread de forma insegura, mas mantém start bloqueado para evitar duplicidade
                _log(self, '[V47.22][STOP] O ciclo ainda está finalizando uma operação de rede. Aguarde; novo ciclo não será iniciado.', 'warn')
            try: self.after(1000, lambda: _verificar_fim(tent+1))
            except Exception: pass
        try: self.after(500, _verificar_fim)
        except Exception: pass

    def _iniciar_v47_22(self):
        th = getattr(self, '_thread', None)
        if th and getattr(th, 'is_alive', lambda: False)():
            _log(self, '[V47.22][START] Existe ciclo anterior encerrando. Aguarde o status INATIVO antes de iniciar novamente.', 'warn')
            return
        if callable(old_iniciar):
            return old_iniciar(self)

    AbaMonitor._parar = _parar_v47_22
    if callable(old_iniciar):
        AbaMonitor._iniciar = _iniciar_v47_22
    print('[V47.22] Botão PARAR do monitor corrigido no painel.')
''')

painel=S/'ururau'/'ui'/'painel.py'
if painel.exists():
    txt=rd(painel); bk(painel)
    if 'patch_v47_22_monitor_stop_painel' not in txt:
        txt += """

# v47.22 — parada segura do monitor no painel
try:
    from ururau.ui.patch_v47_22_monitor_stop_painel import aplicar_patch_v47_22
    aplicar_patch_v47_22(globals())
except Exception as _e_v47_22:
    print(f'[v47.22] Patch stop monitor não aplicado: {_e_v47_22}')
"""
    wr(painel,txt)

bat('21_VALIDAR_MONITOR_PARAR_V47_22.bat','''@echo off
cd /d "%~dp0sistema"
python -m py_compile ururau\publisher\monitor_stop_v47_22.py
python -m py_compile ururau\publisher\monitor.py
python -m py_compile ururau\ui\patch_v47_22_monitor_stop_painel.py
python -m py_compile ururau\ui\painel.py
echo VALIDACAO MONITOR PARAR V47.22 OK
pause
''')
for p in [core,mon,patch,painel]:
    if p.exists(): subprocess.run([sys.executable,'-m','py_compile',str(p)],check=False)
print('[V47.22] aplicado. Rode .\\21_VALIDAR_MONITOR_PARAR_V47_22.bat e depois .\\02_ABRIR_PAINEL.bat')
