# -*- coding: utf-8 -*-
from __future__ import annotations


def aplicar_patch_v47_22(ns):
    AbaMonitor = ns.get('AbaMonitor')
    if AbaMonitor is None:
        print('[V47.22] AbaMonitor não encontrada; patch stop não aplicado')
        return

    old_iniciar = getattr(AbaMonitor, '_iniciar', None)

    def _log(self, msg, tag='warn'):
        try:
            self._append_log(msg, tag)
        except Exception:
            try:
                print(msg)
            except Exception:
                pass

    def _parar_v47_22(self):
        robo = getattr(self, '_robo', None)
        if robo:
            try:
                robo.parar()
            except Exception as e:
                _log(self, f'[V47.22][STOP] erro ao sinalizar parada: {e}', 'err')
            try:
                robo.ativo = False
            except Exception:
                pass
            try:
                robo._parar_solicitado = True
            except Exception:
                pass
        try:
            self._lbl_status.config(text='● PARANDO — aguardando fechamento seguro do ciclo atual', fg='#f59e0b')
            self._btn_stop.config(state='disabled')
            self._btn_start.config(state='disabled')
        except Exception:
            pass
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
                except Exception:
                    pass
                _log(self, '[V47.22][STOP] Monitor parado. Você pode iniciar novamente quando quiser.', 'ok')
                return
            if tent >= 60:
                _log(self, '[V47.22][STOP] O ciclo ainda está finalizando uma operação de rede. Aguarde; novo ciclo não será iniciado.', 'warn')
            try:
                self.after(1000, lambda: _verificar_fim(tent + 1))
            except Exception:
                pass

        try:
            self.after(500, _verificar_fim)
        except Exception:
            pass

    def _iniciar_v47_22(self):
        th = getattr(self, '_thread', None)
        if th and getattr(th, 'is_alive', lambda: False)():
            _log(self, '[V47.22][START] Existe ciclo anterior encerrando. Aguarde o status INATIVO antes de iniciar novamente.', 'warn')
            return
        if callable(old_iniciar):
            return old_iniciar(self)
        return None

    AbaMonitor._parar = _parar_v47_22
    if callable(old_iniciar):
        AbaMonitor._iniciar = _iniciar_v47_22
    print('[V47.22] Botão PARAR do monitor corrigido no painel.')
