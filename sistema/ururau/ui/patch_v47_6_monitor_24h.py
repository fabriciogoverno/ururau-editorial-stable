"""patch_v47_6_monitor_24h.py
Correções operacionais do Monitor 24h no painel:
- painel sempre inicia em RASCUNHO CMS por padrão, não LOCAL/BANCO;
- checkbox passa a significar autorização explícita de AO VIVO;
- intervalo sem pauta segue o intervalo configurado no painel/config;
- evita partida duplicada quando outro monitor ainda está rodando;
- mensagens deixam claro se o robô está ativo, parando, em rascunho ou ao vivo.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path


def _cfg_monitor_default() -> dict:
    base = Path(__file__).resolve().parents[2]
    p = base / "config" / "monitor_24h.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _int_cfg(chave: str, default: int) -> int:
    try:
        val = int(_cfg_monitor_default().get(chave, default))
        return val if val > 0 else default
    except Exception:
        return default


def _modo_por_checkbox(var_publicar) -> tuple[str, bool, bool]:
    """Retorna (modo_cms, publicar_no_cms, permitir_direta)."""
    try:
        direto = bool(var_publicar.get())
    except Exception:
        direto = False
    if direto:
        return "direto", True, True
    return "rascunho", True, False


def _patch_classe_monitor(cls, messagebox=None):
    old_build = getattr(cls, "_build", None)
    old_tick = getattr(cls, "_tick", None)

    def _build_v47_6(self, *a, **kw):
        if old_build:
            old_build(self, *a, **kw)
        # Ajusta defaults a partir de config/monitor_24h.json.
        try:
            self._var_intervalo.set(str(_int_cfg("intervalo_normal_segundos", int(self._var_intervalo.get() or 60))))
        except Exception:
            pass
        try:
            self._var_max_hora.set(str(_int_cfg("max_materias_por_hora", int(self._var_max_hora.get() or 4))))
        except Exception:
            pass
        try:
            self._var_publicar.set(False)  # padrão seguro: rascunho CMS
        except Exception:
            pass
        # Renomeia o checkbutton antigo para não induzir LOCAL/BANCO.
        try:
            def walk(w):
                for ch in w.winfo_children():
                    try:
                        if ch.winfo_class() == "Checkbutton":
                            txt = str(ch.cget("text"))
                            if "Publicar diretamente" in txt or "CMS" in txt:
                                ch.config(text="Permitir publicação AO VIVO (cuidado). Desmarcado = RASCUNHO CMS")
                    except Exception:
                        pass
                    walk(ch)
            walk(self)
        except Exception:
            pass

    def _iniciar_v47_6(self):
        if not self._client:
            self._append_log("[Monitor v47.6] OPENAI_API_KEY ausente: usando fallback local identificado.", "warn")
        try:
            from ururau.publisher.monitor_capacidade_v47_9 import aplicar_defaults_coleta_monitor
            aplicar_defaults_coleta_monitor(forcar=True)
        except Exception as _e_cap_v47_9:
            self._append_log(f"[V47.9][CAPACIDADE] Aviso ao ativar coletores: {_e_cap_v47_9}", "warn")
        try:
            from ururau.publisher.monitor import MonitorRobo, monitor_global_ativo
        except Exception as exc:
            self._append_log(f"[ERRO] Falha ao importar MonitorRobo: {exc}", "err")
            return

        if self._robo and getattr(self._robo, "ativo", False):
            self._append_log("[Monitor] Já existe monitor ativo nesta aba.", "warn")
            try:
                if messagebox:
                    messagebox.showinfo("Monitor", "O monitor já está ativo.")
            except Exception:
                pass
            return
        if monitor_global_ativo():
            self._append_log("[Monitor] Já existe um ciclo ativo em outra aba/janela. Aguarde terminar ou clique PARAR.", "warn")
            try:
                if messagebox:
                    messagebox.showwarning("Monitor", "Já existe um monitor 24h ativo. Não foi criada outra instância.")
            except Exception:
                pass
            return
        try:
            intervalo = max(10, int(self._var_intervalo.get()))
            max_hora = max(1, int(self._var_max_hora.get()))
        except Exception:
            try:
                if messagebox:
                    messagebox.showerror("Erro", "Valores inválidos nos campos do monitor.")
            except Exception:
                pass
            self._append_log("[ERRO] Valores inválidos nos campos do monitor.", "err")
            return

        modo_cms, publicar_no_cms, permitir_direta = _modo_por_checkbox(self._var_publicar)
        if modo_cms == "direto":
            self._append_log("[Monitor] Modo AO VIVO solicitado. Ainda depende das travas do .env e dos gates editoriais.", "warn")
        else:
            self._append_log("[Monitor] Modo seguro: RASCUNHO CMS. Nada será publicado ao vivo pelo monitor.", "ok")

        self._robo = MonitorRobo(
            db=self._db,
            client=self._client,
            modelo=self._modelo,
            intervalo_segundos=intervalo,
            intervalo_sem_pauta_segundos=intervalo,
            max_por_hora=max_hora,
            publicar_no_cms=publicar_no_cms,
            permitir_publicacao_direta=permitir_direta,
            modo_cms=modo_cms,
        )

        def _run():
            try:
                self._robo.iniciar()
            except Exception as e:
                msg = str(e)
                try:
                    self.after(0, lambda msg=msg: self._append_log(f"[ERRO] {msg}", "err"))
                except Exception:
                    pass
            finally:
                try:
                    self.after(0, self._atualizar_ui)
                except Exception:
                    pass

        self._thread = threading.Thread(target=_run, daemon=True, name="MonitorRobo")
        self._thread.start()
        self._atualizar_ui()
        try:
            self._cb_atualizado(self._robo, self._thread)
        except Exception:
            pass
        self._append_log(
            f"[Monitor] Iniciado. Modo={modo_cms.upper()} Intervalo={intervalo}s "
            f"Intervalo sem pauta={intervalo}s Max/hora={max_hora}", "ok"
        )

    def _parar_v47_6(self):
        if self._robo and getattr(self._robo, "ativo", False):
            self._robo.parar()
            self._append_log("[Monitor] Parada/reinício solicitado. O ciclo atual será interrompido no primeiro ponto seguro; depois o botão INICIAR fica liberado para religar.", "warn")
        else:
            self._append_log("[Monitor] Nenhum monitor ativo nesta aba.", "warn")
        self._atualizar_ui()
        try:
            self._cb_atualizado(self._robo, self._thread)
        except Exception:
            pass

    def _atualizar_ui_v47_6(self):
        ativo = bool(self._robo and getattr(self._robo, "ativo", False))
        parando = bool(self._robo and getattr(self._robo, "_parar", None) and self._robo._parar.is_set() and self._thread and self._thread.is_alive())
        if parando:
            try:
                self._lbl_status.config(text="● PARANDO/REINÍCIO — finalizando ponto seguro", fg="#fde68a")
                self._btn_start.config(state="disabled")
                self._btn_stop.config(state="disabled")
            except Exception:
                pass
            return
        if ativo:
            try:
                n = self._robo.publicacoes_na_hora
                modo = getattr(self._robo, "modo_cms", "rascunho").upper()
                self._lbl_status.config(text=f"● ATIVO — modo {modo} — {n} ao vivo na última hora", fg="#22c55e")
                self._btn_start.config(state="disabled")
                self._btn_stop.config(state="normal")
            except Exception:
                pass
        else:
            try:
                self._lbl_status.config(text="● INATIVO", fg="#94a3b8")
                self._btn_start.config(state="normal")
                self._btn_stop.config(state="disabled")
            except Exception:
                pass

    def _tick_v47_6(self):
        try:
            self._atualizar_ui()
            log_path = Path("logs") / "monitor.log"
            if log_path.exists():
                linhas = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if len(linhas) > getattr(self, "_log_ultimas", 0):
                    novas = linhas[getattr(self, "_log_ultimas", 0):]
                    self._log_ultimas = len(linhas)
                    for ln in novas:
                        self._append_log(ln, self._tag_linha(ln) if hasattr(self, "_tag_linha") else "info")
        except Exception:
            pass
        try:
            self.after(20_000, self._tick)
        except Exception:
            pass

    cls._build = _build_v47_6
    cls._iniciar = _iniciar_v47_6
    cls._parar = _parar_v47_6
    cls._atualizar_ui = _atualizar_ui_v47_6
    cls._tick = _tick_v47_6


def aplicar_patch_v47_6(g: dict) -> None:
    mb = g.get("messagebox")
    if "AbaMonitor" in g:
        _patch_classe_monitor(g["AbaMonitor"], messagebox=mb)
    if "JanelaMonitor" in g:
        _patch_classe_monitor(g["JanelaMonitor"], messagebox=mb)
