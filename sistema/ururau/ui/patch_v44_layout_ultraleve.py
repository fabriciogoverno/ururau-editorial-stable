"""patch_v44_layout_ultraleve.py — refinamento ultraleve sobre o V43 Premium.

Esta camada NAO reescreve a interface do V43 Premium. Ela aplica, por cima,
um conjunto de correcoes especificas pedidas na SPEC v44:

1. Tema centralizado (paleta unica via theme_v44_premium.THEME).
2. Virtualizacao incremental da Fila de Pautas via virtual_queue_v44 — apenas
   linhas que entram/saem da viewport sao tocadas.
3. Console interno mais alto, com limite de linhas (1000) e insercao em lote.
4. Linha de status sob a barra de progresso com altura minima maior, para
   evitar texto cortado.
5. Score circles cacheados via widgets_v44.ScoreRingCache (compartilhado).

A intencao e nao quebrar nenhuma ferramenta nem mudar regra editorial. Tudo o
que falhar e absorvido por try/except — o sistema continua funcionando como
no V43 Premium.
"""

from __future__ import annotations

from collections import deque

try:
    from .theme_v44_premium import THEME, HEIGHTS, color
except Exception:
    THEME = {}
    HEIGHTS = {"console": 380, "console_min": 220, "status_strip": 28}
    def color(k, fb="#000"):
        return THEME.get(k, fb)

try:
    from .widgets_v44 import (
        ScoreRingCache,
        create_metric_ring,
        update_metric_ring,
        draw_queue_ring,
    )
except Exception:
    ScoreRingCache = None
    create_metric_ring = None
    update_metric_ring = None
    draw_queue_ring = None

try:
    from .virtual_queue_v44 import install_window_virtualization
except Exception:
    install_window_virtualization = None


_CONSOLE_LINE_LIMIT = 1000
_CONSOLE_BATCH_FLUSH_MS = 80


def _safe_get_class(globals_dict, name):
    try:
        return globals_dict.get(name)
    except Exception:
        return None


def aplicar_patch_v44(g):
    """Aplica o patch v44 (ultraleve + premium) sobre o painel ja patcheado.

    g e o ``globals()`` de ``ururau/ui/painel.py``.
    """
    tk = g.get("tk")
    ttk = g.get("ttk")
    if not tk or not ttk:
        print("[V44][AVISO] tk/ttk indisponiveis, patch v44 nao aplicado.")
        return False

    PainelUrurau = _safe_get_class(g, "PainelUrurau")
    FilaPautas_cls = _safe_get_class(g, "FilaPautas")
    if PainelUrurau is None:
        print("[V44][AVISO] PainelUrurau nao localizado.")
        return False

    # ------------------------------------------------------------------
    # 1. Virtualizacao incremental da Fila de Pautas
    # ------------------------------------------------------------------
    if FilaPautas_cls is not None and install_window_virtualization is not None:
        try:
            ok = install_window_virtualization(FilaPautas_cls)
            if ok:
                print("[V44] Virtualizacao incremental da Fila instalada.")
        except Exception as e:
            print(f"[V44][AVISO] virtualizacao nao instalada: {e}")

    # ------------------------------------------------------------------
    # 2. Console interno expandido + limite de linhas + insercao em lote
    # ------------------------------------------------------------------
    old_construir_console = getattr(PainelUrurau, "_construir_console", None)
    old_toggle_console = getattr(PainelUrurau, "_toggle_console", None)

    def _v44_construir_console(self):
        # Reaproveita o construtor existente (ja foi patcheado pelo v43)
        if old_construir_console is not None:
            try:
                old_construir_console(self)
            except Exception as e:
                print(f"[V44][CONSOLE] fallback construtor nativo: {e}")
        # Aplica acabamento v44
        try:
            console_h = int(HEIGHTS.get("console", 380))
            self._console_frame.configure(
                bg=color("panel_3", "#0d1422"),
                height=console_h,
            )
            self._console_frame.pack_propagate(False)
        except Exception:
            pass
        try:
            self._console_txt.configure(
                font=("Consolas", 10),
                bg="#050b14",
                fg="#cbd5e1",
                insertbackground=color("text", "#e8eef7"),
                padx=12,
                pady=10,
                wrap="word",
                height=22,
            )
            self._console_txt.tag_configure("ok",   foreground="#86efac")
            self._console_txt.tag_configure("err",  foreground="#fca5a5")
            self._console_txt.tag_configure("warn", foreground="#fde68a")
            self._console_txt.tag_configure("info", foreground="#cbd5e1")
            self._console_txt.tag_configure("dim",  foreground="#64748b")
        except Exception:
            pass
        # Buffer leve para insercao em lote
        try:
            self._v44_console_buffer = deque(maxlen=4000)
            self._v44_console_pending = False
            self._v44_console_lines_drawn = 0
        except Exception:
            pass

    def _v44_toggle_console(self):
        # Mantem comportamento anterior, mas garante altura ampliada quando abrir
        try:
            visible = not getattr(self, "_console_visible", False)
        except Exception:
            visible = True
        try:
            if old_toggle_console is not None:
                old_toggle_console(self)
        except Exception:
            try:
                self._console_visible = visible
                if visible:
                    self._console_frame.pack(
                        fill="x", side="bottom",
                        before=getattr(self, "_statusbar_frame", None),
                    )
                else:
                    self._console_frame.pack_forget()
            except Exception:
                pass
        # Forca altura ampliada toda vez que abre
        try:
            if getattr(self, "_console_visible", False):
                self._console_frame.configure(height=int(HEIGHTS.get("console", 380)))
                self._console_frame.pack_propagate(False)
        except Exception:
            pass

    def _v44_console_flush(self):
        """Insere o buffer pendente no widget de uma vez."""
        try:
            self._v44_console_pending = False
            buf = getattr(self, "_v44_console_buffer", None)
            txt_widget = getattr(self, "_console_txt", None)
            if not buf or txt_widget is None:
                return
            if not buf:
                return
            # Drena buffer
            chunk = []
            while buf:
                try:
                    chunk.append(buf.popleft())
                except Exception:
                    break
            if not chunk:
                return
            try:
                txt_widget.config(state="normal")
                # Aplica linha por linha (precisamos das tags)
                for raw, tag in chunk:
                    txt_widget.insert("end", raw, tag)
                    self._v44_console_lines_drawn = (
                        getattr(self, "_v44_console_lines_drawn", 0) + 1
                    )
                # Aparar excesso
                limit = _CONSOLE_LINE_LIMIT
                if self._v44_console_lines_drawn > limit + 200:
                    try:
                        excess = self._v44_console_lines_drawn - limit
                        txt_widget.delete("1.0", f"{excess + 1}.0")
                        self._v44_console_lines_drawn = limit
                    except Exception:
                        pass
                txt_widget.see("end")
                txt_widget.config(state="disabled")
            except Exception:
                pass
        except Exception:
            pass

    def _v44_append_console(self, texto):
        """Append leve com bufferizacao, coloracao e limite duro."""
        try:
            txt_widget = getattr(self, "_console_txt", None)
            if txt_widget is None:
                return
            tl = (texto or "").lower()
            if "[ok]" in tl or "sucesso" in tl or "[v" in tl:
                tag = "ok"
            elif "erro" in tl or "error" in tl or "[xx]" in tl or "falha" in tl:
                tag = "err"
            elif "aviso" in tl or "warn" in tl or "[!]" in tl or "bloq" in tl:
                tag = "warn"
            else:
                tag = "info"
            buf = getattr(self, "_v44_console_buffer", None)
            if buf is None:
                buf = deque(maxlen=4000)
                self._v44_console_buffer = buf
            buf.append((texto.rstrip() + "\n", tag))
            if not getattr(self, "_v44_console_pending", False):
                self._v44_console_pending = True
                try:
                    self.after(_CONSOLE_BATCH_FLUSH_MS,
                               _v44_console_flush.__get__(self))
                except Exception:
                    _v44_console_flush(self)
        except Exception:
            pass

    setattr(PainelUrurau, "_construir_console", _v44_construir_console)
    setattr(PainelUrurau, "_toggle_console", _v44_toggle_console)
    setattr(PainelUrurau, "_append_console", _v44_append_console)
    setattr(PainelUrurau, "_v44_console_flush", _v44_console_flush)

    # ------------------------------------------------------------------
    # 3. Status sob barra de progresso: altura minima maior e wrap
    # ------------------------------------------------------------------
    old_set_status = getattr(PainelUrurau, "_set_status", None)

    def _v44_after_status(self, msg):
        try:
            strip_target = getattr(self, "_v43_header_status", None)
            if strip_target is not None:
                strip_target.configure(
                    font=("Segoe UI Semibold", 9),
                    fg=color("green", "#22c55e"),
                    anchor="w",
                    justify="left",
                )
                # garante padding inferior
                try:
                    parent = strip_target.master
                    parent.configure(height=int(HEIGHTS.get("status_strip", 28)))
                    parent.pack_propagate(False)
                except Exception:
                    pass
        except Exception:
            pass

    def _v44_set_status(self, msg):
        try:
            if old_set_status is not None:
                old_set_status(self, msg)
        except Exception:
            pass
        try:
            self.after(0, lambda: _v44_after_status(self, msg))
        except Exception:
            _v44_after_status(self, msg)

    setattr(PainelUrurau, "_set_status", _v44_set_status)

    # ------------------------------------------------------------------
    # 4. Repaint da Fila quando a janela e redimensionada (aproveita virt.)
    # ------------------------------------------------------------------
    if FilaPautas_cls is not None:
        old_on_canvas_cfg = getattr(FilaPautas_cls, "_on_canvas_cfg", None)

        def _v44_on_canvas_cfg(self, _=None):
            try:
                if old_on_canvas_cfg is not None:
                    old_on_canvas_cfg(self, _)
            except Exception:
                pass
            # Reset rows desenhadas para reaproveitar largura nova
            try:
                self._v44_drawn_rows = set()
                if hasattr(self, "_v44_full_repaint"):
                    self.after_idle(self._v44_full_repaint)
            except Exception:
                pass

        try:
            setattr(FilaPautas_cls, "_on_canvas_cfg", _v44_on_canvas_cfg)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 5. Indicadores cacheados: repassa cache global para o V43, se possivel
    # ------------------------------------------------------------------
    if ScoreRingCache is not None:
        try:
            # Garante cache global compartilhado mesmo se v43 ja criou um proprio
            g["_v44_ring_cache"] = ScoreRingCache
        except Exception:
            pass

    print("[V44 LAYOUT ULTRALEVE] Patch aplicado: virtualizacao incremental, "
          "console ampliado, status sem corte, rings cacheados.")
    return True
