"""patch_v45_redesign.py - Redesign visual real do Ururau v45.

Esta camada roda DEPOIS dos patches v43 Premium e v44 Layout Ultraleve. Ela
substitui a camada visual principal (header, fila, detalhe, console) por uma
versao premium baseada no design system v45, mas SEM remover o motor
funcional anterior.

Ordem de aplicacao:
    1. Statusbar inferior reestilizada (cores tema v45)
    2. Detalhe da Pauta (Notebook estilo pill)
    3. Console interno (terminal-look)
    4. Header (3 linhas, KPI heroes, rings, status sem corte)
    5. Fila de Pautas (_draw_row premium)

A virtualizacao incremental do v44 e PRESERVADA (apenas o draw mudou).
"""

from __future__ import annotations

try:
    from .theme_v45_design_system import COLORS, color, font
except Exception:
    COLORS = {}
    def color(k, fb="#000"): return fb
    def font(k, fb=None): return fb or ("Segoe UI", 9)

try:
    from .header_v45 import (
        apply_header_v45,
        apply_header_kpi_updater,
        apply_header_status_updater,
    )
except Exception:
    apply_header_v45 = None
    apply_header_kpi_updater = None
    apply_header_status_updater = None

try:
    from .queue_v45 import apply_queue_v45
except Exception:
    apply_queue_v45 = None

try:
    from .detail_v45 import apply_detail_v45, apply_ttk_styles
except Exception:
    apply_detail_v45 = None
    apply_ttk_styles = None

try:
    from .console_v45 import apply_console_v45
except Exception:
    apply_console_v45 = None


def _safe_get(g, name):
    try:
        return g.get(name)
    except Exception:
        return None


def _patch_root_bg(PainelUrurau, tk):
    """Garante que o fundo da janela use a paleta v45."""
    old_construir_interface = getattr(PainelUrurau, "_construir_interface", None)
    if old_construir_interface is None:
        return False

    def _v45_construir_interface(self):
        try:
            self.configure(bg=color("bg"))
        except Exception:
            pass
        try:
            old_construir_interface(self)
        except Exception as e:
            print(f"[V45][ROOT] fallback interface: {e}")
        try:
            self.configure(bg=color("bg"))
        except Exception:
            pass

    setattr(PainelUrurau, "_construir_interface", _v45_construir_interface)
    return True


def _patch_statusbar(PainelUrurau, tk):
    """Estiliza a statusbar inferior com cores v45 sem mudar layout."""
    old_construir = getattr(PainelUrurau, "_construir_statusbar", None)
    if old_construir is None:
        return False

    def _v45_construir_statusbar(self):
        try:
            old_construir(self)
        except Exception:
            pass
        try:
            self._statusbar_frame.configure(
                bg=color("surface"),
                height=30,
            )
            self._statusbar_frame.pack_propagate(False)
            for child in self._statusbar_frame.winfo_children():
                try:
                    if isinstance(child, tk.Label):
                        child.configure(bg=color("surface"),
                                        fg=color("text_muted"),
                                        font=font("label"))
                except Exception:
                    pass
            # divisoria sutil
            try:
                self._statusbar_frame.configure(
                    highlightbackground=color("border"),
                    highlightthickness=1,
                )
            except Exception:
                pass
        except Exception:
            pass

    setattr(PainelUrurau, "_construir_statusbar", _v45_construir_statusbar)
    return True


def _patch_filter_bar(PainelUrurau, tk, ttk):
    """Reestiliza a barra de filtros da fila com paleta e botoes v45.

    Mantem comandos e variaveis intactos.
    """
    old_construir_lista = getattr(PainelUrurau, "_construir_lista", None)
    if old_construir_lista is None:
        return False

    def _v45_construir_lista(self, frame):
        # configura cor do frame antes de delegar
        try:
            frame.configure(bg=color("surface"))
        except Exception:
            pass
        try:
            old_construir_lista(self, frame)
        except Exception as e:
            print(f"[V45][LISTA] fallback nativo: {e}")
            return
        # Pos-pinta filhos diretos do frame com cores v45
        try:
            for child in frame.winfo_children():
                try:
                    cls = child.__class__.__name__
                    if cls in ("Label",):
                        # mantem o titulo "Fila de Pautas" mas com tipografia v45
                        try:
                            txt = child.cget("text")
                        except Exception:
                            txt = ""
                        if txt and "Fila" in txt:
                            child.configure(
                                bg=color("surface"),
                                fg=color("text"),
                                font=font("title_sm"),
                            )
                        else:
                            try:
                                child.configure(bg=color("surface"))
                            except Exception:
                                pass
                    elif cls == "Frame":
                        try:
                            child.configure(bg=color("surface"))
                        except Exception:
                            pass
                        # repinta filhos botoes / labels
                        for sub in child.winfo_children():
                            try:
                                sub_cls = sub.__class__.__name__
                                if sub_cls == "Label":
                                    sub.configure(
                                        bg=color("surface"),
                                        fg=color("text_muted"),
                                        font=font("label_sm"),
                                    )
                                elif sub_cls == "Entry":
                                    sub.configure(
                                        bg=color("surface_hi"),
                                        fg=color("text"),
                                        insertbackground=color("text"),
                                        relief="flat",
                                    )
                                elif sub_cls == "Button":
                                    # botoes ja vem com cores; suaviza apenas
                                    pass
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

    setattr(PainelUrurau, "_construir_lista", _v45_construir_lista)
    return True


def aplicar_patch_v45(g):
    """Aplica todo o redesign v45 sobre o painel ja patcheado pelo v43+v44."""
    tk = g.get("tk")
    ttk = g.get("ttk")
    if tk is None or ttk is None:
        print("[V45][AVISO] tk/ttk indisponiveis, redesign nao aplicado.")
        return False
    PainelUrurau = _safe_get(g, "PainelUrurau")
    FilaPautas_cls = _safe_get(g, "FilaPautas")
    if PainelUrurau is None:
        print("[V45][AVISO] PainelUrurau nao localizado.")
        return False

    print("[V45 REDESIGN] iniciando aplicacao do redesign visual premium...")

    # 0. fundo raiz e statusbar com tema v45
    try:
        _patch_root_bg(PainelUrurau, tk)
        _patch_statusbar(PainelUrurau, tk)
    except Exception as e:
        print(f"[V45][AVISO] root/statusbar nao patcheados: {e}")

    # 1. Detalhe da Pauta (estilo de notebook + cabecalho premium)
    if apply_detail_v45 is not None:
        try:
            apply_detail_v45(PainelUrurau, tk, ttk)
            print("[V45] Detalhe da Pauta restilizado.")
        except Exception as e:
            print(f"[V45][AVISO] detalhe nao restilizado: {e}")

    # 2. Console terminal-look
    if apply_console_v45 is not None:
        try:
            apply_console_v45(PainelUrurau, tk, ttk)
            print("[V45] Console interno terminal aplicado.")
        except Exception as e:
            print(f"[V45][AVISO] console nao aplicado: {e}")

    # 3. Filter bar / lista
    try:
        _patch_filter_bar(PainelUrurau, tk, ttk)
    except Exception as e:
        print(f"[V45][AVISO] filter bar nao restilizada: {e}")

    # 4. Header completo
    if apply_header_v45 is not None:
        try:
            apply_header_v45(PainelUrurau, tk, ttk)
            apply_header_kpi_updater(PainelUrurau)
            apply_header_status_updater(PainelUrurau)
            print("[V45] Header redesenhado: 3 linhas, KPI hero, rings, status sem corte.")
        except Exception as e:
            print(f"[V45][AVISO] header nao redesenhado: {e}")

    # 5. Fila de Pautas (linha premium)
    if apply_queue_v45 is not None and FilaPautas_cls is not None:
        try:
            apply_queue_v45(FilaPautas_cls)
            print("[V45] Fila de Pautas: row premium com card, accent stripe e ring liso.")
        except Exception as e:
            print(f"[V45][AVISO] fila nao restilizada: {e}")

    print("[V45 REDESIGN] aplicado: header novo, fila premium, detalhe, console terminal.")
    return True
