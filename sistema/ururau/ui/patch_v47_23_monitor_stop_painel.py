# -*- coding: utf-8 -*-
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
