# -*- coding: utf-8 -*-
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
