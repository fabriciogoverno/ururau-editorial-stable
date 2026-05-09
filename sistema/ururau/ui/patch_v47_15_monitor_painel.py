# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, threading
from pathlib import Path


def _sistema_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if parent.name == 'sistema':
            return parent
    return Path.cwd()


def _cfg() -> dict:
    try:
        p = _sistema_root() / 'config' / 'monitor_24h.json'
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except Exception:
        return {}


def _int_cfg(name: str, default: int) -> int:
    try:
        c = _cfg()
        v = c.get(name)
        if v is None:
            for sec in ('coleta','extracao','gates_monitor_24h','seo'):
                sub = c.get(sec) or {}
                if isinstance(sub, dict) and name in sub:
                    v = sub.get(name); break
        return int(v) if int(v) > 0 else int(default)
    except Exception:
        return int(default)


def _set_env_monitor_painel():
    env = {
        'URURAU_MONITOR_MODO_CMS': 'rascunho',
        'URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR': '1',
        'URURAU_PUBLICAR_DIRETO': '0',
        'URURAU_CMS_PUBLICACAO_DIRETA': '0',
        'SCORE_MIN_MONITOR': str(_int_cfg('score_minimo_monitor', 35)),
        'URURAU_MONITOR_SCORE_MINIMO': str(_int_cfg('score_minimo_monitor', 35)),
        'URURAU_SCORE_MINIMO_RASCUNHO': str(_int_cfg('score_minimo_rascunho', 35)),
        'URURAU_SCORE_MINIMO_DIRETA': str(_int_cfg('seo_minimo_publicacao_direta', 90)),
        'URURAU_MIN_CHARS_FONTE_MONITOR': str(_int_cfg('min_chars_fonte_monitor_rascunho', 350)),
        'URURAU_V104_MIN_CHARS_ARTIGO': str(_int_cfg('texto_minimo_rascunho_chars', 350)),
        'URURAU_V105_MIN_CHARS_FONTE_OK': str(_int_cfg('texto_minimo_rascunho_chars', 350)),
        'URURAU_GNEWS_JANELA_HORAS': str(_int_cfg('janela_horas_google_news', 12)),
        'URURAU_V111_GNEWS_JANELA_HORAS': str(_int_cfg('janela_horas_google_news', 12)),
        'URURAU_V111_SCORE_MINIMO_PAUTA': str(_int_cfg('score_minimo_gnews', 35)),
        'URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO': str(_int_cfg('max_resultados_gnews_por_termo', 6)),
        'URURAU_V111_GNEWS_MIN_CHARS_FONTE': str(_int_cfg('min_chars_fonte_gnews', 350)),
        'URURAU_V111_GNEWS_INTEGRADO': '0',
        'URURAU_V111_USAR_EXTRACAO_COMPLETA': '0',
        'URURAU_V111_USAR_CICLO_COMBINADO': '0',
        'URURAU_V110_MONITOR_GNEWS_LEGADO': '0',
        'URURAU_V108_GNEWS_TERMOS': '0',
        'URURAU_SOURCE_HUNTER_ATIVO': '0',
        'URURAU_AUTOFONTES_V131_ATIVO': '1',
        'URURAU_AUTO_DIAGNOSTICO_FONTE': '1',
        'URURAU_MONITOR_USAR_FILA_PAINEL': '1',
        'URURAU_GNEWS_DESLIGADO_NO_MONITOR': '1',
    }
    for k, v in env.items():
        os.environ[str(k)] = str(v)
    try:
        from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers
        try:
            aplicar_defaults_scrapers(forcar=True)
        except TypeError:
            aplicar_defaults_scrapers()
    except Exception:
        pass


def aplicar_patch_v47_15(ns: dict):
    AbaMonitor = ns.get('AbaMonitor')
    if AbaMonitor is None:
        print('[V47.15][AVISO] AbaMonitor nÃ£o encontrada; patch nÃ£o aplicado.')
        return

    def _append_safe(self, msg, tag='info'):
        try:
            self._append_log(msg, tag)
        except Exception:
            try: print(msg)
            except Exception: pass

    def _iniciar_v47_15(self):
        from tkinter import messagebox
        _set_env_monitor_painel()

        if not getattr(self, '_client', None):
            _append_safe(self, '[Monitor] OPENAI_API_KEY ausente: usando fallback local identificado.', 'warn')

        robo_atual = getattr(self, '_robo', None)
        th_atual = getattr(self, '_thread', None)
        if robo_atual and getattr(robo_atual, 'ativo', False):
            messagebox.showinfo('Monitor', 'O monitor jÃ¡ estÃ¡ ativo no painel.', parent=self)
            return
        if th_atual and getattr(th_atual, 'is_alive', lambda: False)():
            messagebox.showinfo('Monitor', 'O ciclo anterior ainda estÃ¡ finalizando. Aguarde alguns segundos e tente novamente.', parent=self)
            return

        try:
            intervalo = int(getattr(self, '_var_intervalo').get())
        except Exception:
            intervalo = _int_cfg('intervalo_normal_segundos', 180)
        try:
            max_hora = int(getattr(self, '_var_max_hora').get())
        except Exception:
            max_hora = _int_cfg('max_publicacoes_hora', 24)

        publicar_direto = False
        try:
            publicar_direto = bool(getattr(self, '_var_publicar').get())
        except Exception:
            publicar_direto = False

        modo_cms = 'direto' if publicar_direto else 'rascunho'
        permitir_direta = bool(publicar_direto)

        # Se o usuÃ¡rio marcou direta, o monitor ainda passa pelos gates do prÃ³prio monitor.
        # Se nÃ£o marcou, sempre salva/cadastra rascunho CMS, nunca LOCAL/BANCO.
        from ururau.publisher.monitor import MonitorRobo
        self._robo = MonitorRobo(
            db=getattr(self, '_db', None),
            client=getattr(self, '_client', None),
            modelo=getattr(self, '_modelo', None),
            intervalo_segundos=intervalo,
            max_por_hora=max_hora,
            publicar_no_cms=True,
            permitir_publicacao_direta=permitir_direta,
            modo_cms=modo_cms,
            intervalo_sem_pauta_segundos=intervalo,
        )

        def _run():
            try:
                self._robo.iniciar()
            except Exception as e:
                msg = str(e)
                try:
                    self.after(0, lambda msg=msg: _append_safe(self, f'[ERRO MONITOR] {msg}', 'err'))
                except Exception:
                    print('[ERRO MONITOR]', msg)
            finally:
                try: self.after(0, self._atualizar_ui)
                except Exception: pass

        self._thread = threading.Thread(target=_run, daemon=True, name='MonitorRoboPainelV4715')
        self._thread.start()
        try: self._atualizar_ui()
        except Exception: pass
        try: self._cb_atualizado(self._robo, self._thread)
        except Exception: pass

        if modo_cms == 'rascunho':
            _append_safe(self, f'[Monitor Painel V47.15] Iniciado em RASCUNHO CMS real. Intervalo={intervalo}s Sem pauta={intervalo}s Max/hora={max_hora} Score rascunho={os.environ.get("SCORE_MIN_MONITOR")}.', 'ok')
            _append_safe(self, '[Monitor Painel V47.15] Nada serÃ¡ publicado ao vivo; matÃ©rias aprovÃ¡veis serÃ£o enviadas como rascunho para revisÃ£o.', 'warn')
        else:
            _append_safe(self, f'[Monitor Painel V47.15] Iniciado em modo DIRETO solicitado. Direta ainda depende de gates, SEO e seguranÃ§a. Intervalo={intervalo}s.', 'warn')

    def _parar_v47_15(self):
        robo = getattr(self, '_robo', None)
        if robo:
            try: robo.parar()
            except Exception: pass
        try: self._atualizar_ui()
        except Exception: pass
        try: self._cb_atualizado(getattr(self, '_robo', None), getattr(self, '_thread', None))
        except Exception: pass
        _append_safe(self, '[Monitor Painel V47.15] Parada solicitada. O ciclo atual serÃ¡ fechado em ponto seguro; depois o botÃ£o Iniciar poderÃ¡ ser usado novamente.', 'warn')

    def _atualizar_ui_v47_15(self):
        ativo = bool(getattr(self, '_robo', None) and getattr(self._robo, 'ativo', False))
        try:
            if ativo:
                n = getattr(self._robo, 'publicacoes_na_hora', 0)
                modo = getattr(self._robo, 'modo_cms', 'rascunho').upper()
                self._lbl_status.config(text=f'â— ATIVO â€” modo {modo} â€” {n} processada(s)/h', fg='#22c55e')
                self._btn_start.config(state='disabled')
                self._btn_stop.config(state='normal')
            else:
                self._lbl_status.config(text='â— INATIVO â€” pronto para iniciar em RASCUNHO CMS', fg='#9ca3af')
                self._btn_start.config(state='normal')
                self._btn_stop.config(state='disabled')
        except Exception:
            pass

    AbaMonitor._iniciar = _iniciar_v47_15
    AbaMonitor._parar = _parar_v47_15
    AbaMonitor._atualizar_ui = _atualizar_ui_v47_15
    print('[V47.15] Monitor do painel corrigido: RASCUNHO CMS real, defaults aplicados e log coerente.')


