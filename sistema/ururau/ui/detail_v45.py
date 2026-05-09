"""detail_v45.py - Estilizacao premium do Detalhe da Pauta + abas pill.

Esta camada nao reescreve as abas (Info / Checagem / Risco / Materia /
Auditoria / Leitura) — elas ficam exatamente como estao. Estilizamos:

- o cabecalho do painel ("Detalhe da Pauta") em alta hierarquia
- o ttk.Notebook com tabs em formato pill (paddings maiores, cores claras)
- divisoes internas mais limpas
- o painel-pai recebe um padding consistente

Principios:
- nao destruir nada do existente;
- aplicar via ttk.Style + ajuste de pack do frame;
- absorver erros silenciosamente.
"""

from __future__ import annotations

try:
    from .theme_v45_design_system import COLORS, FONTS, color, font
except Exception:
    COLORS = {}
    FONTS = {}
    def color(k, fb="#000"): return fb
    def font(k, fb=None): return fb or ("Segoe UI", 9)


def apply_ttk_styles(root, ttk):
    """Aplica estilos ttk premium para Notebook, Combobox, etc."""
    try:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        # Notebook com tabs pill
        style.configure(
            "V45.TNotebook",
            background=color("surface"),
            borderwidth=0,
            tabmargins=(8, 4, 4, 0),
        )
        style.configure(
            "V45.TNotebook.Tab",
            background=color("surface_hi"),
            foreground=color("text_muted"),
            padding=(16, 8),
            font=font("label_caps"),
            borderwidth=0,
        )
        style.map(
            "V45.TNotebook.Tab",
            background=[
                ("selected", color("accent")),
                ("active", color("surface_max")),
            ],
            foreground=[
                ("selected", "#ffffff"),
                ("active", color("text")),
            ],
        )
        # Combobox premium
        style.configure(
            "V45.TCombobox",
            fieldbackground=color("surface"),
            background=color("surface_hi"),
            foreground=color("text"),
            arrowcolor=color("text_muted"),
            borderwidth=1,
            padding=4,
        )
        style.map(
            "V45.TCombobox",
            fieldbackground=[("readonly", color("surface"))],
            background=[("readonly", color("surface_hi"))],
        )
        # PanedWindow
        style.configure(
            "V45.TPanedwindow",
            background=color("bg"),
            borderwidth=0,
            sashthickness=4,
        )
        # Scrollbar
        style.configure(
            "V45.Vertical.TScrollbar",
            background=color("surface_hi"),
            troughcolor=color("bg"),
            bordercolor=color("bg"),
            arrowcolor=color("text_muted"),
        )
    except Exception:
        pass


def apply_detail_v45(PainelUrurau, tk, ttk):
    """Re-estiliza o Detalhe da Pauta via wrapper de ``_construir_detalhe``."""
    old_construir_detalhe = getattr(PainelUrurau, "_construir_detalhe", None)
    if old_construir_detalhe is None:
        return False

    def _v45_construir_detalhe(self, frame):
        # Aplica estilos ttk antes de construir o conteudo
        try:
            apply_ttk_styles(self, ttk)
        except Exception:
            pass

        # cabeca do detalhe (substituida pelo wrapper visual)
        head = tk.Frame(frame, bg=color("surface"))
        head.pack(fill="x", padx=14, pady=(12, 6))
        # marker laranja a esquerda
        marker = tk.Frame(head, bg=color("accent"), width=4, height=24)
        marker.pack(side="left", padx=(0, 10))
        title = tk.Frame(head, bg=color("surface"))
        title.pack(side="left")
        tk.Label(title, text="DETALHE DA PAUTA",
                 bg=color("surface"), fg=color("text_muted"),
                 font=font("label_caps")).pack(anchor="w")
        tk.Label(title, text="Materia, fonte e auditoria",
                 bg=color("surface"), fg=color("text"),
                 font=font("title_sm")).pack(anchor="w")

        # divisor sutil
        sep = tk.Frame(frame, bg=color("border"), height=1)
        sep.pack(fill="x", padx=14, pady=(4, 8))

        # Container do notebook (apenas: chama original mas sem o titulo
        # que ele cria internamente). Como nao conseguimos remover esse
        # Label sem reescrever o construtor, optamos por chamar o original
        # e depois esconder o seu Label "Detalhe da Pauta" (o primeiro
        # filho com texto identico).
        try:
            old_construir_detalhe(self, frame)
        except Exception as e:
            print(f"[V45][DETAIL] fallback nativo: {e}")

        # Procura o label "Detalhe da Pauta" criado pelo construtor original
        # (esta dentro de ``frame``, nao do novo head). Esconde com pack_forget.
        try:
            for child in frame.winfo_children():
                if (isinstance(child, tk.Label) and
                        getattr(child, "cget", lambda *_: "")("text") in
                        ("Detalhe da Pauta", "DETALHE DA PAUTA")):
                    # nao toca nos novos labels
                    if child not in (marker,) and child.master is frame:
                        child.pack_forget()
                        break
        except Exception:
            pass

        # Aplica estilo V45 ao notebook recem-criado
        try:
            nb = getattr(self, "_notebook", None)
            if nb is not None and isinstance(nb, ttk.Notebook):
                nb.configure(style="V45.TNotebook")
        except Exception:
            pass

    setattr(PainelUrurau, "_construir_detalhe", _v45_construir_detalhe)
    return True


__all__ = [
    "apply_ttk_styles",
    "apply_detail_v45",
]
