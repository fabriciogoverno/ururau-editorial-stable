# -*- coding: utf-8 -*-
from __future__ import annotations
import threading


def instalar_stop_guard(MonitorRobo):
    if getattr(MonitorRobo, '_v4722_stop_guard', False):
        return MonitorRobo
    MonitorRobo._v4722_stop_guard = True

    old_parar = getattr(MonitorRobo, 'parar', None)
    old_iniciar = getattr(MonitorRobo, 'iniciar', None)
    old_ciclo = getattr(MonitorRobo, '_executar_ciclo', None)

    def _marcar_parada(self):
        try:
            self.ativo = False
        except Exception:
            pass
        try:
            self._parar_solicitado = True
        except Exception:
            pass
        try:
            self.parada_solicitada = True
        except Exception:
            pass
        ev = getattr(self, '_stop_event_v4722', None)
        if ev is None:
            ev = threading.Event()
            try:
                self._stop_event_v4722 = ev
            except Exception:
                pass
        try:
            ev.set()
        except Exception:
            pass

    def parar_v4722(self, *a, **kw):
        _marcar_parada(self)
        if callable(old_parar):
            try:
                old_parar(self, *a, **kw)
            except TypeError:
                try:
                    old_parar(self)
                except Exception:
                    pass
            except Exception:
                pass
        _marcar_parada(self)
        return True

    def iniciar_v4722(self, *a, **kw):
        try:
            self._parar_solicitado = False
            self.parada_solicitada = False
            self._stop_event_v4722 = threading.Event()
            self.ativo = True
        except Exception:
            pass
        if callable(old_iniciar):
            return old_iniciar(self, *a, **kw)
        return None

    def deve_parar_v4722(self):
        try:
            if not getattr(self, 'ativo', True):
                return True
        except Exception:
            pass
        try:
            if getattr(self, '_parar_solicitado', False):
                return True
        except Exception:
            pass
        try:
            ev = getattr(self, '_stop_event_v4722', None)
            if ev is not None and ev.is_set():
                return True
        except Exception:
            pass
        return False

    def ciclo_v4722(self, *a, **kw):
        if deve_parar_v4722(self):
            try:
                self._log.info('[V47.22][STOP] ciclo ignorado porque PARAR já foi solicitado')
            except Exception:
                pass
            return {'ok': False, 'status_pipeline': 'parado_antes_do_ciclo'}
        if callable(old_ciclo):
            r = old_ciclo(self, *a, **kw)
        else:
            r = None
        if deve_parar_v4722(self):
            try:
                self._log.info('[V47.22][STOP] ciclo finalizado; monitor não iniciará novo ciclo')
            except Exception:
                pass
        return r

    MonitorRobo.parar = parar_v4722
    MonitorRobo.iniciar = iniciar_v4722
    MonitorRobo.deve_parar_v4722 = deve_parar_v4722
    if callable(old_ciclo):
        MonitorRobo._executar_ciclo = ciclo_v4722
    return MonitorRobo
