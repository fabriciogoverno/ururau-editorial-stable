"""console_v45.py - Console interno premium estilo terminal.

- header proprio com pontos coloridos (red/yellow/green) + label
- corpo com fonte mono, line-height generoso, padding consistente
- cores por severidade (info/ok/warn/err)
- botao Limpar mantido
- preserva a bufferizacao do v44 (deque + flush em lote + limite de linhas)
"""

from __future__ import annotations

from collections import deque

try:
    from .theme_v45_design_system import COLORS, FONTS, HEIGHTS, color, font, height
    from .widgets_v45 import rounded_rect
except Exception:
    COLORS = {}
    FONTS = {}
    HEIGHTS = {}
    rounded_rect = None
    def color(k, fb="#000"): return fb
    def font(k, fb=None): return fb or ("Consolas", 10)
    def height(k, fb=380): return fb


_CONSOLE_LIMIT = 1200
_CONSOLE_FLUSH_MS = 80


def apply_console_v45(PainelUrurau, tk, ttk):
    """Substitui ``_construir_console`` por uma versao com terminal-look."""
    old_construir = getattr(PainelUrurau, "_construir_console", None)

    def _v45_construir_console(self):
        # destroi console anterior se existir
        try:
            old = getattr(self, "_console_frame", None)
            if old is not None and old.winfo_exists():
                old.destroy()
        except Exception:
            pass

        H = height("console", 420)
        outer = tk.Frame(
            self,
            bg=color("bg"),
            height=H,
            highlightbackground=color("border"),
            highlightthickness=1,
        )
        outer.pack_propagate(False)
        self._console_frame = outer

        # Header (barra superior estilo terminal)
        header = tk.Frame(outer, bg=color("surface_hi"),
                          height=height("console_header", 26))
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        # bolinhas
        bullets = tk.Canvas(header, width=68, height=20,
                            bg=color("surface_hi"),
                            highlightthickness=0, bd=0)
        bullets.pack(side="left", padx=(10, 8), pady=3)
        for i, c in enumerate([color("danger"), color("warn"), color("success")]):
            bullets.create_oval(8 + i * 18, 4, 16 + i * 18, 12,
                                fill=c, outline=c)
        tk.Label(header, text="CONSOLE  -  ururau-shell  -  ativo",
                 bg=color("surface_hi"), fg=color("text_muted"),
                 font=font("label_caps")).pack(side="left", pady=4)

        # Botoes do header
        right = tk.Frame(header, bg=color("surface_hi"))
        right.pack(side="right", padx=8, pady=2)
        tk.Button(right, text="Limpar",
                  command=getattr(self, "_limpar_console", lambda: None),
                  bg=color("surface_max"), fg=color("text_dim"),
                  activebackground=color("surface_max"),
                  activeforeground=color("text"),
                  relief="flat", bd=0, padx=10, pady=2,
                  font=font("label_sm"), cursor="hand2").pack(side="left", padx=2)
        tk.Button(right, text="Fechar",
                  command=getattr(self, "_toggle_console", lambda: None),
                  bg=color("surface_max"), fg=color("text_dim"),
                  activebackground=color("surface_max"),
                  activeforeground=color("text"),
                  relief="flat", bd=0, padx=10, pady=2,
                  font=font("label_sm"), cursor="hand2").pack(side="left", padx=2)

        # Corpo do console
        body = tk.Frame(outer, bg="#02060d")
        body.pack(fill="both", expand=True)

        from tkinter import scrolledtext
        txt = scrolledtext.ScrolledText(
            body, bg="#02060d", fg=color("text_dim"),
            font=("Consolas", 10),
            state="disabled", wrap="word",
            padx=14, pady=12,
            insertbackground=color("text"),
            height=22, borderwidth=0, highlightthickness=0,
        )
        txt.pack(fill="both", expand=True)
        # cores por severidade
        txt.tag_configure("ok",   foreground="#86efac", spacing1=1, spacing3=1)
        txt.tag_configure("err",  foreground="#fca5a5", spacing1=1, spacing3=1)
        txt.tag_configure("warn", foreground="#fde68a", spacing1=1, spacing3=1)
        txt.tag_configure("info", foreground="#cbd5e1", spacing1=1, spacing3=1)
        txt.tag_configure("dim",  foreground=color("text_muted"))
        txt.tag_configure("prompt", foreground=color("accent"), font=("Consolas", 10, "bold"))
        self._console_txt = txt

        # buffer leve
        self._v45_console_buffer = deque(maxlen=4000)
        self._v45_console_pending = False
        self._v45_console_lines_drawn = 0

        # Imprime banner inicial
        try:
            txt.config(state="normal")
            txt.insert("end", "ururau> ", "prompt")
            txt.insert("end", "console pronto - logs do sistema serao exibidos aqui\n", "info")
            txt.config(state="disabled")
            self._v45_console_lines_drawn += 1
        except Exception:
            pass

    def _v45_toggle_console(self):
        try:
            visible = not getattr(self, "_console_visible", False)
        except Exception:
            visible = True
        try:
            self._console_visible = visible
            if visible:
                try:
                    self._console_frame.pack_forget()
                except Exception:
                    pass
                try:
                    self._statusbar_frame.pack_forget()
                except Exception:
                    pass
                self._console_frame.pack(fill="x", side="bottom")
                try:
                    self._statusbar_frame.pack(fill="x", side="bottom")
                except Exception:
                    pass
                btn = getattr(self, "_btn_console", None)
                if btn is not None:
                    try:
                        btn.configure(bg=color("success_dim"), fg=color("success"))
                    except Exception:
                        pass
            else:
                try:
                    self._console_frame.pack_forget()
                except Exception:
                    pass
                btn = getattr(self, "_btn_console", None)
                if btn is not None:
                    try:
                        btn.configure(bg=color("surface_hi"), fg=color("text_muted"))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[V45][CONSOLE][toggle] {e}")

    def _v45_console_flush(self):
        try:
            self._v45_console_pending = False
            buf = getattr(self, "_v45_console_buffer", None)
            txt_widget = getattr(self, "_console_txt", None)
            if not buf or txt_widget is None:
                return
            chunk = []
            while buf:
                try:
                    chunk.append(buf.popleft())
                except Exception:
                    break
            if not chunk:
                return
            txt_widget.config(state="normal")
            for line, tag in chunk:
                txt_widget.insert("end", line, tag)
                self._v45_console_lines_drawn = (
                    getattr(self, "_v45_console_lines_drawn", 0) + 1
                )
            # poda
            if self._v45_console_lines_drawn > _CONSOLE_LIMIT + 200:
                try:
                    excess = self._v45_console_lines_drawn - _CONSOLE_LIMIT
                    txt_widget.delete("1.0", f"{excess + 1}.0")
                    self._v45_console_lines_drawn = _CONSOLE_LIMIT
                except Exception:
                    pass
            txt_widget.see("end")
            txt_widget.config(state="disabled")
        except Exception:
            pass

    def _v45_append_console(self, texto):
        try:
            txt_widget = getattr(self, "_console_txt", None)
            if txt_widget is None:
                return
            tl = (texto or "").lower()
            if "[ok]" in tl or "sucesso" in tl:
                tag = "ok"
            elif "erro" in tl or "error" in tl or "falha" in tl or "[xx]" in tl:
                tag = "err"
            elif "aviso" in tl or "warn" in tl or "[!]" in tl or "bloq" in tl:
                tag = "warn"
            elif "[v" in tl or "[debug]" in tl:
                tag = "info"
            else:
                tag = "info"
            buf = getattr(self, "_v45_console_buffer", None)
            if buf is None:
                buf = deque(maxlen=4000)
                self._v45_console_buffer = buf
            buf.append((texto.rstrip() + "\n", tag))
            if not getattr(self, "_v45_console_pending", False):
                self._v45_console_pending = True
                try:
                    self.after(_CONSOLE_FLUSH_MS, _v45_console_flush.__get__(self))
                except Exception:
                    _v45_console_flush(self)
        except Exception:
            pass

    setattr(PainelUrurau, "_construir_console", _v45_construir_console)
    setattr(PainelUrurau, "_toggle_console", _v45_toggle_console)
    setattr(PainelUrurau, "_append_console", _v45_append_console)
    setattr(PainelUrurau, "_v45_console_flush", _v45_console_flush)
    return True


__all__ = ["apply_console_v45"]
