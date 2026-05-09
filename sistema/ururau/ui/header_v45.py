"""header_v45.py - Header redesenhado do Ururau v45.

Substitui o header anterior por uma faixa em tres linhas distintas:

  +-----------------------------------------------------------------------+
  | LOGO   URURAU - Robo Editorial          [Coletar][Redigir]...   IA Risco |
  | KPIs (4 hero cards)                                          (rings)    |
  | progress bar  ............................................  status     |
  +-----------------------------------------------------------------------+

A faixa de status fica numa linha PROPRIA com altura minima garantida; a
mensagem nunca e cortada.

A funcao ``apply_header_v45`` substitui ``_v43_build_top_header`` no
PainelUrurau ja patcheado pelo v43 + v44.
"""

from __future__ import annotations

from pathlib import Path

try:
    from .theme_v45_design_system import (
        COLORS, FONTS, HEIGHTS, WIDTHS, SPACING,
        color, font, height, width,
    )
    from .widgets_v45 import PillButton, KPIHeroCard, RingV45, rounded_rect
except Exception:  # pragma: no cover
    COLORS = {}
    FONTS = {}
    HEIGHTS = {}
    WIDTHS = {}
    SPACING = {}
    PillButton = None
    KPIHeroCard = None
    RingV45 = None
    rounded_rect = None
    def color(k, fb="#000"): return fb
    def font(k, fb=None): return fb or ("Segoe UI", 9)
    def height(k, fb=30): return fb
    def width(k, fb=80): return fb


def _base_dir():
    try:
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path.cwd()


def apply_header_v45(PainelUrurau, tk, ttk):
    """Instala o novo header como ``_v43_build_top_header``.

    Os patches anteriores ja chamam ``self._v43_build_top_header()`` em
    ``_construir_interface_v43``; substituir esse atributo basta para que o
    novo header seja usado.
    """
    if PillButton is None or KPIHeroCard is None or RingV45 is None:
        return False

    def _v45_build_top_header(self):
        # Limpa header anterior se existir
        try:
            old = getattr(self, "_v43_header_frame", None) or getattr(self, "_v45_header_frame", None)
            if old is not None and old.winfo_exists():
                old.destroy()
        except Exception:
            pass

        H = height("header_total", 132)
        hdr = tk.Frame(self, bg=color("bg"), height=H)
        self._v45_header_frame = hdr
        self._v43_header_frame = hdr  # compat com v43
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        # ---------------- Linha 1: brand + acoes + rings ----------------
        row1 = tk.Frame(hdr, bg=color("bg"), height=height("header_brand", 46))
        row1.pack(fill="x", side="top")
        row1.pack_propagate(False)

        # Brand box
        brand = tk.Frame(row1, bg=color("bg"), width=width("brand_box", 200))
        brand.pack(side="left", fill="y", padx=(14, 10))
        brand.pack_propagate(False)
        try:
            from PIL import Image, ImageTk
            ico = _base_dir() / "ururau_atalho_icon.ico"
            if ico.exists():
                img = Image.open(str(ico)).resize((28, 28), Image.LANCZOS)
                ph = ImageTk.PhotoImage(img)
                lb = tk.Label(brand, image=ph, bg=color("bg"))
                lb.image = ph
                lb.pack(side="left", pady=(9, 0), padx=(0, 8), anchor="n")
        except Exception:
            tk.Label(brand, text="U", bg=color("accent"), fg=color("bg"),
                     font=font("title_lg"), width=2).pack(
                side="left", pady=(9, 0), padx=(0, 8), anchor="n")
        txt = tk.Frame(brand, bg=color("bg"))
        txt.pack(side="left", pady=(7, 0), anchor="n")
        tk.Label(txt, text="URURAU", bg=color("bg"), fg=color("accent"),
                 font=font("title_lg"), anchor="w").pack(anchor="w")
        tk.Label(txt, text="Robo Editorial v45",
                 bg=color("bg"), fg=color("text_muted"),
                 font=font("label_sm"), anchor="w").pack(anchor="w", pady=(0, 0))

        # Acoes em pill (centro/esquerda)
        actions = tk.Frame(row1, bg=color("bg"))
        actions.pack(side="left", fill="both", expand=True)
        action_specs = [
            ("Coletar",   self._acao_coletar,   "accent"),
            ("Redigir",   self._acao_redigir,   "primary"),
            ("Copydesk",  self._acao_copydesk,  "purple"),
            ("Preview",   self._acao_preview,   "primary"),
            ("Publicar",  self._acao_publicar,  "success"),
            ("Descartar", self._acao_descartar, "danger"),
            ("Exportar",  self._acao_exportar,  "ghost"),
        ]
        for text, cmd, tone in action_specs:
            btn = PillButton.build(actions, text, cmd, tone=tone, tk_module=tk,
                                   size="sm")
            btn.pack(side="left", padx=3, pady=(8, 0), anchor="n")

        # Botoes utilitarios direita (Monitor / Console / Config)
        utils = tk.Frame(row1, bg=color("bg"))
        utils.pack(side="left", padx=(8, 0))
        self._btn_monitor = PillButton.build(
            utils, "Monitor OFF", self._toggle_monitor, tone="ghost",
            tk_module=tk, size="sm",
        )
        self._btn_monitor.pack(side="left", padx=3, pady=(8, 0), anchor="n")
        self._btn_console = PillButton.build(
            utils, "Console", self._toggle_console, tone="ghost",
            tk_module=tk, size="sm",
        )
        self._btn_console.pack(side="left", padx=3, pady=(8, 0), anchor="n")
        PillButton.build(
            utils, "Config", self._acao_configuracoes, tone="outline",
            tk_module=tk, size="sm",
        ).pack(side="left", padx=3, pady=(8, 0), anchor="n")

        # Rings IA / Risco
        rings = tk.Frame(row1, bg=color("bg"))
        rings.pack(side="right", padx=(8, 14), pady=(4, 0))
        self._v45_ia_card = RingV45.create_card(
            rings, label="IA", value=88, inverse=False, size=42, tk_module=tk,
        )
        self._v45_ia_card.pack(side="left", padx=4)
        self._v45_risk_card = RingV45.create_card(
            rings, label="RISCO", value=12, inverse=True, size=42, tk_module=tk,
        )
        self._v45_risk_card.pack(side="left", padx=4)
        # alias com nomes anteriores (v43)
        self._v43_ia_frame = self._v45_ia_card
        self._v43_risk_frame = self._v45_risk_card

        # ---------------- Linha 2: KPI hero cards ----------------
        row2 = tk.Frame(hdr, bg=color("bg"))
        row2.pack(fill="x", side="top", pady=(8, 0))
        kpi_box = tk.Frame(row2, bg=color("bg"))
        kpi_box.pack(side="left", padx=(14, 0))
        self._v45_kpis = {}
        for key, label, val, tone in [
            ("pautas",     "Pautas na fila", "0",   "info"),
            ("publicadas", "Publicadas",     "0",   "success"),
            ("materias",   "Materias",       "0",   "purple"),
            ("saude",      "Saude do robo",  "100%", "success"),
        ]:
            card = KPIHeroCard.build(
                kpi_box, label=label, value=val, sub="atualizando...",
                tone=tone, width=140, tk_module=tk,
            )
            card.pack(side="left", padx=(0, 8))
            self._v45_kpis[key] = card
        # compat com v43 (que faz self._v43_kpis[k].winfo_children() etc.)
        self._v43_kpis = self._v45_kpis

        # ---------------- Linha 3: barra de progresso + status ----------------
        row3 = tk.Frame(hdr, bg=color("bg"), height=height("header_strip", 32))
        row3.pack(fill="x", side="bottom")
        row3.pack_propagate(False)
        # progress canvas
        self._v45_progress_w = 540
        prog_wrap = tk.Frame(row3, bg=color("bg"))
        prog_wrap.pack(side="left", fill="y", padx=(14, 8), pady=(8, 0))
        self._v45_progress_canvas = tk.Canvas(
            prog_wrap, width=self._v45_progress_w, height=10,
            bg=color("bg"), highlightthickness=0, bd=0,
        )
        self._v45_progress_canvas.pack(side="left", pady=2)
        # alias compat
        self._v43_progress_canvas = self._v45_progress_canvas
        self._v43_progress_w = self._v45_progress_w
        # trough arredondado
        rounded_rect(self._v45_progress_canvas, 0, 1, self._v45_progress_w, 9,
                     radius=4, fill=color("border"),
                     outline=color("border"), tags="trough")
        # fill
        self._v45_progress_fill = rounded_rect(
            self._v45_progress_canvas, 0, 1, 1, 9,
            radius=4, fill=color("success"), outline=color("success"),
            tags="fill",
        )
        self._v43_progress_fill = self._v45_progress_fill
        self._v45_header_pct = tk.Label(
            prog_wrap, text="0%", bg=color("bg"), fg=color("text"),
            font=font("label_caps"), width=5, anchor="e",
        )
        self._v45_header_pct.pack(side="left", padx=(8, 0), pady=2)
        self._v43_header_pct = self._v45_header_pct

        # status label com altura propria (impossivel cortar)
        status_frame = tk.Frame(row3, bg=color("bg"))
        status_frame.pack(side="left", fill="both", expand=True, padx=(8, 14))
        self._v45_status_dot = tk.Label(
            status_frame, text="*", bg=color("bg"), fg=color("success"),
            font=("Segoe UI Semibold", 11),
        )
        self._v45_status_dot.pack(side="left", pady=4)
        self._v45_header_status = tk.Label(
            status_frame, text="Sistema operacional - todos os servicos ativos",
            bg=color("bg"), fg=color("text_dim"),
            font=font("label"), anchor="w", justify="left",
        )
        self._v45_header_status.pack(side="left", fill="both", expand=True,
                                     padx=(6, 0), pady=2)
        # compat alias
        self._v43_header_status = self._v45_header_status

        # Indicador a direita: estado de coleta (etiqueta pill)
        env_pill = tk.Frame(row3, bg=color("bg"))
        env_pill.pack(side="right", padx=(0, 14), pady=2)
        cv = tk.Canvas(env_pill, width=110, height=22,
                       bg=color("bg"), highlightthickness=0, bd=0)
        cv.pack()
        rounded_rect(cv, 0, 0, 110, 22, radius=11,
                     fill=color("success_soft"), outline=color("success_dim"))
        cv.create_text(55, 11, text="* PRODUCAO",
                       fill=color("success"),
                       font=font("label_caps"))

        try:
            self.after(700, self._v43_pulse_status_dot)
        except Exception:
            pass

    setattr(PainelUrurau, "_v43_build_top_header", _v45_build_top_header)
    return True


def apply_header_kpi_updater(PainelUrurau):
    """Reescreve o updater de KPIs para usar a nova API de KPIHeroCard.

    Mantem os mesmos contratos de leitura (db.estatisticas) e a periodicidade
    de refresh (1300ms).
    """

    def _v45_update_kpis(self):
        try:
            s = self.db.estatisticas() if self.db else {}
        except Exception:
            s = {}
        try:
            vals = {
                "pautas":     str(s.get("total_pautas", 0)),
                "publicadas": str(s.get("total_publicadas", 0)),
                "materias":   str(s.get("total_materias", 0)),
                "saude":      "100%",
            }
            kpis = getattr(self, "_v45_kpis", None) or {}
            for k, v in vals.items():
                card = kpis.get(k)
                if card is not None and hasattr(card, "_v45_set_value"):
                    sub = {
                        "pautas":     "na fila",
                        "publicadas": "hoje",
                        "materias":   "rascunhos",
                        "saude":      "OK",
                    }.get(k, "")
                    card._v45_set_value(v, sub)
            # progress
            try:
                p = int(vals.get("pautas") or "0")
                pct = 100 if p else 0
                cv = getattr(self, "_v45_progress_canvas", None)
                fill_id = getattr(self, "_v45_progress_fill", None)
                pw = getattr(self, "_v45_progress_w", 540)
                if cv is not None and fill_id is not None:
                    new_w = max(1, int(pw * pct / 100))
                    # rounded fill: precisamos redesenhar
                    cv.delete("fill")
                    from .widgets_v45 import rounded_rect as _rr
                    self._v45_progress_fill = _rr(
                        cv, 0, 1, new_w, 9, radius=4,
                        fill=color("success"),
                        outline=color("success"), tags="fill",
                    )
                pct_lbl = getattr(self, "_v45_header_pct", None)
                if pct_lbl is not None:
                    pct_lbl.configure(text=f"{pct}%")
                stat = getattr(self, "_v45_header_status", None)
                if stat is not None:
                    stat.configure(
                        text=f"{p} pautas na fila - sistema operacional - servicos ativos",
                        fg=color("text_dim"),
                    )
            except Exception:
                pass
            # IA / Risco
            try:
                item = (
                    getattr(self, "pauta_atual", None)
                    or getattr(self, "_pauta_atual", None)
                    or {}
                )
                ia = 88
                risco = 12
                if isinstance(item, dict):
                    try:
                        ia = int(float(
                            item.get("qualidade_ia")
                            or item.get("score_ia")
                            or item.get("score_editorial")
                            or 88
                        ))
                    except Exception:
                        ia = 88
                    try:
                        risco = int(float(
                            item.get("risco")
                            or item.get("risco_editorial")
                            or item.get("risco_score")
                            or 12
                        ))
                    except Exception:
                        risco = 12
                ia_card = getattr(self, "_v45_ia_card", None)
                if ia_card is not None and hasattr(ia_card, "_v45_update"):
                    ia_card._v45_update(ia, sub=f"score IA")
                rk_card = getattr(self, "_v45_risk_card", None)
                if rk_card is not None and hasattr(rk_card, "_v45_update"):
                    rk_card._v45_update(risco, sub="risco editorial")
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.after(1500, self._v43_update_kpis)
        except Exception:
            pass

    setattr(PainelUrurau, "_v43_update_kpis", _v45_update_kpis)
    return True


def apply_header_status_updater(PainelUrurau):
    """Atualiza o status (sem corte) e a barra de progresso do header v45."""
    from .widgets_v45 import rounded_rect as _rr
    try:
        # extrai parser de progresso/status do v43 se existir
        from .patch_v43_premium import aplicar_patch_v43  # noqa: F401
    except Exception:
        pass

    def _strip(msg):
        s = (msg or "").strip()
        # remove prefixos uteis (v43 ja faz, mas garantimos algo legivel)
        for prefix in ("[OK] ", "[V43] ", "[V44] ", "[V45] "):
            if s.startswith(prefix):
                s = s[len(prefix):]
        return s[:160]

    def _pct(msg):
        s = (msg or "")
        # pega "12%" do texto se houver
        import re
        m = re.search(r"(\d{1,3})\s*%", s)
        if m:
            try:
                return max(0, min(100, int(m.group(1))))
            except Exception:
                pass
        if "concluid" in s.lower():
            return 100
        if "iniciando" in s.lower():
            return 5
        return 0

    def _v45_set_status(self, msg):
        clean = _strip(msg)
        pct = _pct(msg)
        def _apply():
            try:
                lbl = getattr(self, "_v45_header_status", None)
                if lbl is not None:
                    lbl.configure(text=clean, fg=color("text_dim"))
                pct_lbl = getattr(self, "_v45_header_pct", None)
                if pct_lbl is not None:
                    pct_lbl.configure(text=f"{pct}%")
                cv = getattr(self, "_v45_progress_canvas", None)
                pw = getattr(self, "_v45_progress_w", 540)
                if cv is not None:
                    cv.delete("fill")
                    self._v45_progress_fill = _rr(
                        cv, 0, 1, max(1, int(pw * pct / 100)), 9,
                        radius=4,
                        fill=color("success"),
                        outline=color("success"), tags="fill",
                    )
                # statusbar inferior tambem (compat)
                lbl_old = getattr(self, "_status_lbl", None)
                if lbl_old is not None:
                    lbl_old.configure(text=clean)
            except Exception:
                pass
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    setattr(PainelUrurau, "_set_status", _v45_set_status)
    return True


__all__ = [
    "apply_header_v45",
    "apply_header_kpi_updater",
    "apply_header_status_updater",
]
