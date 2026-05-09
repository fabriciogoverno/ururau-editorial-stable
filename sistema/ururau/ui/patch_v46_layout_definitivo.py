"""patch_v46_layout_definitivo.py

Redesign definitivo do Ururau Editorial sobre a base v45.

Objetivos:
- header continuo, compacto e alinhado;
- botoes premium executivos por Canvas, com relevo discreto, borda e hover real;
- remocao da faixa verde de progresso/status abaixo dos botoes;
- layout principal em 3 colunas com sidebar operacional;
- fila de pautas mais legivel, com titulo quebrando linha;
- preservacao dos fluxos existentes de coleta, redacao, copydesk, preview e publicacao.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from .theme_v45_design_system import color, font
    from .widgets_v45 import rounded_rect, RingV45, draw_status_pill
except Exception:  # pragma: no cover
    def color(k, fb="#000000"):
        return fb
    def font(k, fb=None):
        return fb or ("Segoe UI", 9)
    rounded_rect = None
    RingV45 = None
    draw_status_pill = None


# ---------------------------------------------------------------------------
# Utilitarios visuais leves
# ---------------------------------------------------------------------------

_BTN_TONES = {
    # normal, hover, texto, acento lateral
    # Paleta menos infantil: base escura, acento controlado e texto limpo.
    "accent":  ("#1b2432", "#263347", "#fff7ed", "#f59e0b"),
    "primary": ("#13213a", "#1a2f52", "#dbeafe", "#3b82f6"),
    "purple":  ("#201733", "#2b2047", "#ede9fe", "#8b5cf6"),
    "success": ("#11291d", "#173725", "#dcfce7", "#22c55e"),
    "danger":  ("#311719", "#461f22", "#fee2e2", "#ef4444"),
    "ghost":   ("#0d1727", "#142238", "#cbd5e1", "#334155"),
    "outline": ("#0a1322", "#101d31", "#cbd5e1", "#475569"),
}

# Ícones removidos dos botões principais para deixar a barra menos caricata.
# A ação continua exatamente a mesma; muda apenas a apresentação visual.
_ICONS = {
    "Coletar": "",
    "Redigir": "",
    "Copydesk": "",
    "Preview": "",
    "Publicar": "",
    "Descartar": "",
    "Exportar": "",
    "Produção": "",
    "Monitor": "",
    "Console": "",
    "Config": "",
    "Atualizar F5": "",
}


def _safe_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default


def _short(txt, n=120):
    s = str(txt or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _premium_canvas_button(parent, tk, text, command, *, tone="ghost", w=104, h=34, icon=None):
    """Botão premium leve em Canvas.

    Mantém o mesmo tamanho externo usado no header v46, mas troca o visual
    chapado por uma peça mais sóbria: base escura, borda fina, sombra curta,
    trilho lateral de acento e hover/press sem criar widgets extras.
    """
    normal, hover, fg, accent = _BTN_TONES.get(tone, _BTN_TONES["ghost"])
    icon = icon if icon is not None else _ICONS.get(text, "")
    state = {"text": text, "fill": normal, "fg": fg, "accent": accent, "hover": hover, "pressed": False}

    cv = tk.Canvas(parent, width=w, height=h, bg=color("bg", "#06101e"), highlightthickness=0, bd=0)

    def _label() -> str:
        label = str(state.get("text") or "")
        ico = icon or ""
        return f"{ico}  {label}" if ico else label

    def draw(fill=None, *, lift=0, border=None):
        fill = fill or state["fill"]
        border = border or state.get("accent") or "#334155"
        cv.delete("all")
        shadow = "#020617"
        top_line = "#334155"
        bottom_line = "#050b16"
        accent_col = state.get("accent") or border
        if rounded_rect:
            rounded_rect(cv, 3, 5 + lift, w - 2, h - 1 + lift, radius=13,
                         fill=shadow, outline=shadow)
            rounded_rect(cv, 1, 1 + lift, w - 3, h - 5 + lift, radius=12,
                         fill=fill, outline=border, width=1)
            rounded_rect(cv, 5, 7 + lift, 8, h - 11 + lift, radius=2,
                         fill=accent_col, outline=accent_col)
            cv.create_line(14, 5 + lift, w - 14, 5 + lift, fill=top_line, width=1)
            cv.create_line(13, h - 7 + lift, w - 14, h - 7 + lift, fill=bottom_line, width=1)
        else:
            cv.create_rectangle(3, 5 + lift, w - 2, h - 1 + lift, fill=shadow, outline=shadow)
            cv.create_rectangle(1, 1 + lift, w - 3, h - 5 + lift, fill=fill, outline=border)
            cv.create_rectangle(5, 7 + lift, 8, h - 11 + lift, fill=accent_col, outline=accent_col)
        cv.create_text(w / 2 + 1, h / 2 - 1 + lift, text=_label(), fill="#020617",
                       font=("Segoe UI Semibold", 9, "bold"))
        cv.create_text(w / 2, h / 2 - 2 + lift, text=_label(), fill=state.get("fg") or fg,
                       font=("Segoe UI Semibold", 9, "bold"))

    def run(_e=None):
        draw(state["hover"], lift=1, border=state.get("accent"))
        try:
            command()
        except TypeError:
            command(None)
        except Exception as exc:
            print(f"[V46][BOTAO] falha ao executar {state.get('text')}: {exc}")

    def enter(_e=None):
        draw(state["hover"], lift=-1, border=state.get("accent"))

    def leave(_e=None):
        draw(state["fill"], lift=0, border=state.get("accent"))

    def press(_e=None):
        draw(state["hover"], lift=1, border=state.get("accent"))

    # Compatibilidade com chamadas antigas como self._btn_monitor.config(text=..., bg=..., fg=...).
    _tk_config = cv.configure

    def _config_compat(*args, **kwargs):
        if args:
            return _tk_config(*args)
        changed = False
        text = kwargs.pop("text", None)
        bg = kwargs.pop("bg", None) or kwargs.pop("background", None)
        new_fg = kwargs.pop("fg", None) or kwargs.pop("foreground", None)
        if text is not None:
            state["text"] = str(text)
            changed = True
        if bg is not None:
            state["fill"] = str(bg)
            state["hover"] = str(bg)
            state["accent"] = str(bg)
            changed = True
        if new_fg is not None:
            state["fg"] = str(new_fg)
            changed = True
        if kwargs:
            _tk_config(**kwargs)
        if changed:
            draw(state["fill"], lift=0, border=state.get("accent"))
        return None

    draw(normal)
    cv.bind("<Enter>", enter)
    cv.bind("<Leave>", leave)
    cv.bind("<ButtonPress-1>", press)
    cv.bind("<ButtonRelease-1>", run)
    cv.configure(cursor="hand2")
    cv._v46_set_text = lambda t: _config_compat(text=t)
    cv._v46_set_tone = lambda bg=None, fg=None: _config_compat(bg=bg, fg=fg)
    cv.config = _config_compat
    cv.configure = _config_compat
    return cv


def _kpi_chip(parent, tk, label, value="0", tone="info", w=86):
    accent = color(tone, color("info", "#3b82f6"))
    f = tk.Frame(parent, bg=color("surface", "#0a1628"), width=w, height=42,
                 highlightbackground=color("border", "#1a2640"), highlightthickness=1)
    f.pack_propagate(False)
    body = tk.Frame(f, bg=color("surface", "#0a1628"))
    body.pack(fill="both", expand=True, padx=8, pady=4)
    lbl = tk.Label(body, text=str(label), bg=color("surface"), fg=color("text_subtle"),
                   font=("Segoe UI Semibold", 7, "bold"), anchor="center")
    lbl.pack(fill="x")
    val = tk.Label(body, text=str(value), bg=color("surface"), fg=accent,
                   font=("Segoe UI Semibold", 12, "bold"), anchor="center")
    val.pack(fill="x")

    def set_value(v, sub_text=None):
        try:
            val.configure(text=str(v))
        except Exception:
            pass

    f._v45_set_value = set_value
    f._v46_set_value = set_value
    f._v45_value_lbl = val
    f._v46_value_lbl = val
    return f


def _metric_bar(parent, tk, label, value=0, tone="success"):
    row = tk.Frame(parent, bg=color("surface_hi"))
    row.pack(fill="x", pady=1)
    tk.Label(row, text=label, bg=color("surface_hi"), fg=color("text_muted"),
             font=font("label_sm"), anchor="w").pack(side="left")
    val_lbl = tk.Label(row, text=f"{int(value)}%", bg=color("surface_hi"), fg=color(tone),
                       font=("Segoe UI Semibold", 8, "bold"), anchor="e", width=8)
    val_lbl.pack(side="right")
    cv = tk.Canvas(parent, height=5, bg=color("surface_hi"), highlightthickness=0, bd=0)
    cv.pack(fill="x", pady=(0, 3))

    def update(v):
        try:
            cv.delete("all")
            ww = max(1, cv.winfo_width() or 220)
            if v is None or v == "--":
                val_lbl.configure(text="--", fg=color("text_muted"))
                if rounded_rect:
                    rounded_rect(cv, 0, 1, ww, 4, radius=3, fill=color("ring_track"), outline=color("ring_track"))
                else:
                    cv.create_rectangle(0, 1, ww, 4, fill=color("ring_track"), outline="")
                return
            v = max(0, min(100, int(float(v))))
            val_lbl.configure(text=f"{v}%", fg=color(tone))
            if rounded_rect:
                rounded_rect(cv, 0, 1, ww, 4, radius=3, fill=color("ring_track"), outline=color("ring_track"))
                if v > 0:
                    rounded_rect(cv, 0, 1, max(2, int(ww * v / 100)), 4, radius=3,
                                 fill=color(tone), outline=color(tone))
            else:
                cv.create_rectangle(0, 1, ww, 4, fill=color("ring_track"), outline="")
                if v > 0:
                    cv.create_rectangle(0, 1, int(ww * v / 100), 4, fill=color(tone), outline="")
        except Exception:
            pass

    cv.bind("<Configure>", lambda _e: update(value))
    update(value)
    return update


# ---------------------------------------------------------------------------
# Header compacto definitivo
# ---------------------------------------------------------------------------

def apply_header_v46(PainelUrurau, tk, ttk):
    def _v46_build_top_header(self):
        try:
            old = getattr(self, "_v43_header_frame", None) or getattr(self, "_v45_header_frame", None)
            if old is not None and old.winfo_exists():
                old.destroy()
        except Exception:
            pass

        try:
            self.title("Ururau Editorial v46 Premium")
        except Exception:
            pass

        H = 72
        hdr = tk.Frame(self, bg=color("bg"), height=H,
                       highlightbackground=color("border"), highlightthickness=0)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        self._v46_header_frame = hdr
        self._v45_header_frame = hdr
        self._v43_header_frame = hdr

        row = tk.Frame(hdr, bg=color("bg"), height=70)
        row.pack(fill="x", side="top")
        row.pack_propagate(False)

        # marca compacta
        brand = tk.Frame(row, bg=color("bg"), width=172, height=64)
        brand.pack(side="left", fill="y", padx=(14, 10))
        brand.pack_propagate(False)
        logo_loaded = False
        try:
            from PIL import Image, ImageTk
            ico = Path(__file__).resolve().parents[2] / "ururau_atalho_icon.ico"
            if ico.exists():
                img = Image.open(str(ico)).resize((30, 30), Image.LANCZOS)
                ph = ImageTk.PhotoImage(img)
                lb = tk.Label(brand, image=ph, bg=color("bg"))
                lb.image = ph
                lb.pack(side="left", padx=(0, 8), pady=(15, 0), anchor="n")
                logo_loaded = True
        except Exception:
            logo_loaded = False
        if not logo_loaded:
            cv_logo = tk.Canvas(brand, width=34, height=34, bg=color("bg"), highlightthickness=0, bd=0)
            cv_logo.pack(side="left", padx=(0, 8), pady=(15, 0), anchor="n")
            if rounded_rect:
                rounded_rect(cv_logo, 2, 2, 32, 32, radius=15, fill=color("accent_soft"), outline=color("accent"), width=1)
            else:
                cv_logo.create_oval(2, 2, 32, 32, fill=color("accent_soft"), outline=color("accent"))
            cv_logo.create_text(17, 17, text="U", fill=color("accent"), font=("Segoe UI Semibold", 13, "bold"))
        bt = tk.Frame(brand, bg=color("bg"))
        bt.pack(side="left", pady=(14, 0), anchor="n")
        tk.Label(bt, text="URURAU", bg=color("bg"), fg=color("text"),
                 font=("Segoe UI Semibold", 12, "bold"), anchor="w").pack(anchor="w")
        tk.Label(bt, text="Editorial", bg=color("bg"), fg=color("text_muted"),
                 font=("Segoe UI", 8), anchor="w").pack(anchor="w")

        # KPIs a direita primeiro para preservar espaco dos botoes
        kpis = tk.Frame(row, bg=color("bg"))
        kpis.pack(side="right", fill="y", padx=(8, 12), pady=(10, 0))
        self._v46_kpis = {}
        specs = [
            ("pautas", "Pautas", "0", "info", 70),
            ("publicadas", "Publicadas", "0", "text", 82),
            ("materias", "Matérias", "0", "purple", 74),
            ("saude", "Saúde", "100%", "success", 76),
            ("ia", "IA", "88", "info", 58),
            ("risco", "Risco", "12", "warn", 62),
        ]
        for key, label, value, tone, w in specs:
            chip = _kpi_chip(kpis, tk, label, value, tone=tone, w=w)
            chip.pack(side="left", padx=2)
            self._v46_kpis[key] = chip
        self._v45_kpis = self._v46_kpis
        self._v43_kpis = self._v46_kpis

        utils = tk.Frame(row, bg=color("bg"))
        utils.pack(side="right", fill="y", padx=(4, 8), pady=(14, 0))
        self._btn_producao = _premium_canvas_button(utils, tk, "Produção", lambda: None,
                                                    tone="outline", w=96, h=32, icon="●")
        self._btn_producao.pack(side="left", padx=2)
        self._btn_monitor = _premium_canvas_button(utils, tk, "Monitor", self._toggle_monitor,
                                                   tone="ghost", w=86, h=32)
        self._btn_monitor.pack(side="left", padx=2)
        self._btn_console = _premium_canvas_button(utils, tk, "Console", self._toggle_console,
                                                   tone="ghost", w=86, h=32)
        self._btn_console.pack(side="left", padx=2)
        _premium_canvas_button(
            utils, tk, "Atualizar F5",
            lambda: getattr(self, "_acao_atualizar_geral_v47_4", getattr(self, "_acao_atualizar_geral_v132", self._carregar_pautas))(),
            tone="ghost", w=112, h=32,
        ).pack(side="left", padx=2)
        _premium_canvas_button(utils, tk, "Config", self._acao_configuracoes,
                               tone="ghost", w=76, h=32).pack(side="left", padx=2)

        actions = tk.Frame(row, bg=color("bg"))
        actions.pack(side="left", fill="y", pady=(11, 0))
        for text, cmd, tone, w in [
            ("Coletar", self._acao_coletar, "accent", 96),
            ("Redigir", self._acao_redigir, "primary", 96),
            ("Copydesk", self._acao_copydesk, "purple", 104),
            ("Preview", self._acao_preview, "primary", 96),
            ("Publicar", self._acao_publicar, "success", 104),
            ("Descartar", self._acao_descartar, "danger", 112),
            ("Exportar", self._acao_exportar, "ghost", 98),
        ]:
            _premium_canvas_button(actions, tk, text, cmd, tone=tone, w=w, h=36).pack(side="left", padx=3)

        # A antiga faixa verde de progresso/status foi removida do topo.
        # O status operacional permanece na statusbar inferior e no painel lateral,
        # evitando duplicidade visual com o Monitor operacional.
        self._v46_progress_w = 1
        self._v45_progress_w = 1
        self._v43_progress_w = 1
        self._v46_progress_canvas = None
        self._v45_progress_canvas = None
        self._v43_progress_canvas = None
        self._v46_progress_fill = None
        self._v45_progress_fill = None
        self._v43_progress_fill = None
        self._v46_header_pct = None
        self._v45_header_pct = None
        self._v43_header_pct = None
        self._v46_header_status = None
        self._v45_header_status = None
        self._v43_header_status = None

        try:
            self.after(900, self._v43_update_kpis)
        except Exception:
            pass

    setattr(PainelUrurau, "_v43_build_top_header", _v46_build_top_header)
    return True



def _v47_9_texto_extraido_ok(p: dict) -> tuple[bool, int, int]:
    try:
        min_chars = int(__import__('os').getenv('URURAU_V105_MIN_CHARS_FONTE_OK', __import__('os').getenv('URURAU_MIN_CHARS_TEXTO_FONTE', '900')) or '900')
    except Exception:
        min_chars = 900
    texto = str(p.get('cleaned_source_text') or p.get('fonte_aba_texto') or p.get('leitura_fonte_texto') or p.get('raw_source_text') or p.get('original_source_text') or p.get('dossie') or '')
    try:
        util = int(p.get('fonte_chars_v105') or p.get('chars_fonte') or p.get('fonte_chars_v111') or 0)
    except Exception:
        util = 0
    if util <= 0:
        try:
            from ururau.coleta.limpeza_texto_v81 import texto_util_chars
            util = int(texto_util_chars(texto))
        except Exception:
            util = len(texto.strip())
    st = str(p.get('status_fonte_v105') or p.get('status_fonte_v111') or p.get('extraction_status') or '').lower()
    return (util >= min_chars and (st in {'ok','complete','completo','success','sucesso'} or bool(texto.strip()))), util, min_chars

def apply_header_updates_v46(PainelUrurau, tk):
    def _draw_progress(self, pct):
        try:
            pct = max(0, min(100, int(float(pct))))
            pw = getattr(self, "_v46_progress_w", 680)
            cv = getattr(self, "_v46_progress_canvas", None) or getattr(self, "_v45_progress_canvas", None)
            if cv is not None:
                cv.delete("fill")
                if rounded_rect:
                    self._v46_progress_fill = rounded_rect(cv, 0, 2, max(1, int(pw * pct / 100)), 8,
                                                           radius=3, fill=color("success"), outline=color("success"), tags="fill")
                else:
                    self._v46_progress_fill = cv.create_rectangle(0, 2, max(1, int(pw * pct / 100)), 8,
                                                                  fill=color("success"), outline="", tags="fill")
            lbl = getattr(self, "_v46_header_pct", None) or getattr(self, "_v45_header_pct", None)
            if lbl is not None:
                lbl.configure(text=f"{pct}%")
        except Exception:
            pass

    def _v46_update_kpis(self):
        try:
            s = self.db.estatisticas() if self.db else {}
        except Exception:
            s = {}
        vals = {
            "pautas": str(s.get("total_pautas", 0)),
            "publicadas": str(s.get("total_publicadas", 0)),
            "materias": str(s.get("total_materias", 0)),
            "saude": "100%",
        }
        item = getattr(self, "_pauta_sel", None) or {}
        texto_ok_v47_9, _util_v47_9, _min_v47_9 = _v47_9_texto_extraido_ok(item) if isinstance(item, dict) else (False, 0, 900)
        ia_raw = item.get("qualidade_ia") or item.get("score_ia") or item.get("score_qualidade")
        if ia_raw is None and str(item.get("status") or "") in {"redigida", "copydesk", "pronta", "publicada", "rascunho"}:
            ia_raw = item.get("score_editorial")
        vals["ia"] = str(max(0, min(100, _safe_int(ia_raw, 0)))) if (ia_raw is not None and texto_ok_v47_9) else "--"
        risco_raw = item.get("score_risco") or item.get("risco") or item.get("risco_score")
        vals["risco"] = str(max(0, min(100, _safe_int(risco_raw, 0)))) if (risco_raw is not None and texto_ok_v47_9) else "--"
        kpis = getattr(self, "_v46_kpis", None) or getattr(self, "_v45_kpis", {}) or {}
        for key, value in vals.items():
            card = kpis.get(key)
            try:
                if hasattr(card, "_v46_set_value"):
                    card._v46_set_value(value)
                elif hasattr(card, "_v45_set_value"):
                    card._v45_set_value(value)
            except Exception:
                pass
        try:
            p = _safe_int(vals.get("pautas"), 0)
            _draw_progress(self, 100 if p else 0)
            status = f"{p} pautas na fila · publicadas nas últimas 8h · sistema operacional · todos os serviços ativos"
            lbl = getattr(self, "_v46_header_status", None) or getattr(self, "_v45_header_status", None)
            if lbl is not None:
                lbl.configure(text=status, fg=color("text_muted"))
        except Exception:
            pass
        try:
            if hasattr(self, "_v46_update_sidebar"):
                self._v46_update_sidebar(getattr(self, "_pauta_sel", None))
        except Exception:
            pass
        try:
            self.after(1800, self._v43_update_kpis)
        except Exception:
            pass

    def _pct_from_msg(msg):
        import re
        s = str(msg or "")
        m = re.search(r"(\d{1,3})\s*%", s)
        if m:
            return max(0, min(100, _safe_int(m.group(1), 0)))
        low = s.lower()
        if "conclu" in low or "finaliz" in low or "publicad" in low:
            return 100
        if "colet" in low or "carreg" in low or "inici" in low:
            return 18
        if "erro" in low or "falha" in low:
            return 0
        return None

    def _v46_set_status(self, msg):
        clean = _short(msg, 180)
        pct = _pct_from_msg(clean)
        def _apply():
            try:
                lbl = getattr(self, "_v46_header_status", None) or getattr(self, "_v45_header_status", None)
                if lbl is not None:
                    lbl.configure(text=clean, fg=color("text_muted"))
                if pct is not None:
                    _draw_progress(self, pct)
                old = getattr(self, "_status_lbl", None) or getattr(self, "_lbl_status", None)
                if old is not None:
                    old.configure(text=clean)
                if hasattr(self, "_v46_update_sidebar_status"):
                    self._v46_update_sidebar_status(clean)
            except Exception:
                pass
        try:
            self.after(0, _apply)
        except Exception:
            _apply()

    setattr(PainelUrurau, "_v43_update_kpis", _v46_update_kpis)
    setattr(PainelUrurau, "_set_status", _v46_set_status)
    return True


# ---------------------------------------------------------------------------
# Sidebar operacional e layout 3 colunas
# ---------------------------------------------------------------------------

def apply_layout_v46(PainelUrurau, tk, ttk):
    def _card(parent, title, accent="info"):
        f = tk.Frame(parent, bg=color("surface_hi"), highlightbackground=color("border"), highlightthickness=1)
        # Cards mais compactos para evitar corte no rodape da sidebar.
        f.pack(fill="x", padx=8, pady=(0, 7))
        head = tk.Frame(f, bg=color("surface_hi"))
        head.pack(fill="x", padx=10, pady=(7, 4))
        tk.Label(head, text="●", bg=color("surface_hi"), fg=color(accent), font=("Segoe UI", 8)).pack(side="left")
        tk.Label(head, text=title, bg=color("surface_hi"), fg=color("text"), font=("Segoe UI Semibold", 9, "bold"), anchor="w").pack(side="left", padx=(6, 0))
        body = tk.Frame(f, bg=color("surface_hi"))
        body.pack(fill="x", padx=10, pady=(0, 8))
        return f, body

    def _check_row(parent, text="", ok=True):
        row = tk.Frame(parent, bg=color("surface_hi"))
        row.pack(fill="x", pady=1)
        ic = "✓" if ok else "!"
        fg = color("success") if ok else color("warn")
        l1 = tk.Label(row, text=ic, bg=color("surface_hi"), fg=fg, font=("Segoe UI Semibold", 9, "bold"), width=2)
        l1.pack(side="left")
        l2 = tk.Label(row, text=text, bg=color("surface_hi"), fg=color("text_dim"), font=font("label_sm"), anchor="w")
        l2.pack(side="left", fill="x", expand=True)
        def set_row(new_text, is_ok):
            try:
                l1.configure(text="✓" if is_ok else "!", fg=color("success") if is_ok else color("warn"))
                l2.configure(text=new_text)
            except Exception:
                pass
        row._v46_set = set_row
        return row

    def _build_sidebar(self, parent):
        parent.configure(bg=color("bg"))

        # Sidebar com área rolável de contingência: em resoluções menores o bloco
        # "Ações rápidas" não pode ser cortado pelo limite vertical da janela.
        # Quando tudo cabe, a barra de rolagem fica oculta e o visual segue limpo.
        try:
            shell = parent
            canvas = tk.Canvas(shell, bg=color("bg"), highlightthickness=0, bd=0)
            scrollbar = tk.Scrollbar(shell, orient="vertical", command=canvas.yview,
                                     bg=color("surface"), troughcolor=color("bg"),
                                     activebackground=color("surface_hi"),
                                     highlightthickness=0, bd=0, width=10)
            content = tk.Frame(canvas, bg=color("bg"))
            win = canvas.create_window((0, 0), window=content, anchor="nw")
            canvas.pack(side="left", fill="both", expand=True)

            def _sync_scroll(_e=None):
                try:
                    bbox = canvas.bbox("all")
                    canvas.configure(scrollregion=bbox)
                    need_scroll = bool(bbox and (bbox[3] - bbox[1]) > (canvas.winfo_height() + 2))
                    if need_scroll:
                        if not scrollbar.winfo_ismapped():
                            scrollbar.pack(side="right", fill="y")
                        canvas.configure(yscrollcommand=scrollbar.set)
                    else:
                        if scrollbar.winfo_ismapped():
                            scrollbar.pack_forget()
                        canvas.configure(yscrollcommand="")
                        canvas.yview_moveto(0)
                except Exception:
                    pass

            content.bind("<Configure>", _sync_scroll)
            canvas.bind("<Configure>", lambda e: (canvas.itemconfigure(win, width=e.width), _sync_scroll()))

            def _wheel(e):
                try:
                    bbox = canvas.bbox("all")
                    if bbox and (bbox[3] - bbox[1]) > canvas.winfo_height():
                        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
                except Exception:
                    pass

            canvas.bind("<MouseWheel>", _wheel)
            content.bind("<MouseWheel>", _wheel)
            parent = content
        except Exception:
            pass

        title = tk.Frame(parent, bg=color("bg"))
        title.pack(fill="x", padx=8, pady=(6, 6))
        tk.Label(title, text="Painel de inteligência", bg=color("bg"), fg=color("text"),
                 font=("Segoe UI Semibold", 11, "bold"), anchor="w").pack(side="left")
        tk.Label(title, text="ao vivo", bg=color("success_soft"), fg=color("success"),
                 font=("Segoe UI Semibold", 7, "bold"), padx=8, pady=2).pack(side="right")

        q_card, q_body = _card(parent, "Qualidade IA", "warn")
        self._v46_quality_score = tk.Label(q_body, text="--", bg=color("surface_hi"), fg=color("text_muted"),
                                           font=("Segoe UI Semibold", 24, "bold"))
        self._v46_quality_score.pack(anchor="center")
        tk.Label(q_body, text="/100 pontos", bg=color("surface_hi"), fg=color("text_muted"),
                 font=font("label_sm")).pack(anchor="center", pady=(0, 4))
        self._v46_bar_relevancia = _metric_bar(q_body, tk, "Relevância", 0, "success")
        self._v46_bar_originalidade = _metric_bar(q_body, tk, "Originalidade", 0, "warn")
        self._v46_bar_legibilidade = _metric_bar(q_body, tk, "Legibilidade", 0, "info")
        self._v46_bar_seo = _metric_bar(q_body, tk, "SEO estimado", 0, "success")

        v_card, v_body = _card(parent, "Verificações automáticas", "success")
        self._v46_checks = [
            _check_row(v_body, "Fonte identificada e ativa", False),
            _check_row(v_body, "Autor verificado", False),
            _check_row(v_body, "Data de publicação válida", False),
            _check_row(v_body, "Sem duplicatas detectadas", False),
            _check_row(v_body, "Texto mínimo suficiente", False),
            _check_row(v_body, "Imagem pronta ou pendente", False),
            _check_row(v_body, "Metadados completos", False),
        ]

        r_card, r_body = _card(parent, "Análise de risco", "danger")
        self._v46_risk_title = tk.Label(r_body, text="--/100", bg=color("surface_hi"), fg=color("text"),
                                        font=("Segoe UI Semibold", 11, "bold"), anchor="w")
        self._v46_risk_title.pack(fill="x", pady=(0, 3))
        self._v46_bar_desinfo = _metric_bar(r_body, tk, "Desinformação", 0, "success")
        self._v46_bar_vies = _metric_bar(r_body, tk, "Viés editorial", 0, "warn")
        self._v46_bar_sens = _metric_bar(r_body, tk, "Sensacionalismo", 0, "success")
        self._v46_bar_sensivel = _metric_bar(r_body, tk, "Conteúdo sensível", 0, "success")

        o_card, o_body = _card(parent, "Monitor operacional", "info")
        self._v46_sidebar_status = tk.Label(o_body, text="Sistema operacional. Aguardando ação.",
                                            bg=color("surface_hi"), fg=color("text_dim"),
                                            font=font("label_sm"), wraplength=285, justify="left", anchor="w")
        self._v46_sidebar_status.pack(fill="x")

        a_card, a_body = _card(parent, "Ações rápidas", "purple")
        # Antes eram duas linhas de botões grandes; em telas menores o card era cortado.
        # Agora cabe em uma linha compacta e ainda mantém os mesmos atalhos.
        row = tk.Frame(a_body, bg=color("surface_hi")); row.pack(fill="x")
        _premium_canvas_button(row, tk, "Redigir", self._acao_redigir, tone="purple", w=69, h=28, icon="").pack(side="left", padx=(0, 5))
        _premium_canvas_button(row, tk, "Checar", lambda: self._notebook.select(1), tone="ghost", w=67, h=28, icon="").pack(side="left", padx=(0, 5))
        _premium_canvas_button(row, tk, "Preview", self._acao_preview, tone="primary", w=70, h=28, icon="").pack(side="left", padx=(0, 5))
        _premium_canvas_button(row, tk, "Copydesk", self._acao_copydesk, tone="purple", w=78, h=28, icon="").pack(side="left")

    def _update_sidebar_status(self, msg):
        try:
            lbl = getattr(self, "_v46_sidebar_status", None)
            if lbl is not None:
                lbl.configure(text=_short(msg, 220))
        except Exception:
            pass

    def _update_sidebar(self, pauta=None):
        """v47.4: painel de inteligência baseado em dados reais disponíveis."""
        p = pauta or getattr(self, "_pauta_sel", None) or {}
        if not isinstance(p, dict):
            p = {}
        def _first(*keys, default=None):
            for k in keys:
                v = p.get(k)
                if v not in (None, "", [], {}):
                    return v
            return default
        def _clamp(v, lo=0, hi=100):
            try: return max(lo, min(hi, int(float(v))))
            except Exception: return lo
        texto = str(_first("cleaned_source_text", "fonte_aba_texto", "leitura_fonte_texto", "texto_fonte", "dossie", default="") or "")
        corpo = str(_first("materia_corpo", "texto_final", "artigo", "conteudo", "body", default="") or "")
        try:
            from ururau.coleta.limpeza_texto_v81 import texto_util_chars
            util_txt = int(texto_util_chars(texto)); util_corpo = int(texto_util_chars(corpo))
        except Exception:
            util_txt = len(texto.strip()); util_corpo = len(corpo.strip())
        try: min_chars = self._v105_min_chars_fonte()
        except Exception: min_chars = 900
        score_raw = _first("qualidade_ia", "score_ia", "score_qualidade", "nota_qualidade", "quality_score", "score_final")
        if score_raw is None and p.get("status") in {"redigida","copydesk","pronta","publicada","rascunho"}:
            score_raw = p.get("score_editorial")
        score = _clamp(score_raw) if score_raw is not None else None
        risco_raw = _first("score_risco", "risco", "risco_score", "risco_juridico", "risco_editorial")
        risco_detalhado_calc = None
        texto_para_risco = corpo if len(corpo.strip()) >= 300 else texto
        if risco_raw is None and len(texto_para_risco.strip()) >= 300:
            try:
                from ururau.editorial.risco import risco_detalhado_dict
                risco_detalhado_calc = risco_detalhado_dict(texto_para_risco, str(_first("canal", "editoria", default="") or ""))
                if risco_detalhado_calc.get("risco_analisado"):
                    risco_raw = risco_detalhado_calc.get("score_risco")
            except Exception:
                risco_detalhado_calc = None
        risco = _clamp(risco_raw) if risco_raw is not None else None
        try:
            if score is None: self._v46_quality_score.configure(text="--", fg=color("text_muted"))
            else: self._v46_quality_score.configure(text=str(score), fg=RingV45.color_for(score) if RingV45 else color("warn"))
            self._v46_risk_title.configure(text=(f"{risco}/100" if risco is not None else "--/100"))
        except Exception: pass
        title_ok = bool(_first("titulo", "titulo_final", "titulo_origem")); link_ok = bool(_first("link_origem", "url"))
        fonte_ok_nome = bool(_first("fonte_nome", "nome_fonte") or link_ok); data_ok = bool(_first("data_pub_fonte", "data_pub_fonte_br", "_data_pub_ordem"))
        dup = bool(_first("duplicada", "duplicate", "duplicidade_detectada", default=False))
        img_status = str(_first("imagem_status", default="") or "").lower()
        img_ok = bool(_first("imagem_caminho", "imagem_url_processada") or img_status in {"ok","baixada","pronta","aprovada"})
        img_pendente = bool(_first("imagem_url", "imagem_url_rss") or img_status in {"buscando","url_pendente","pendente_retry"})
        tags = _first("tags", "seo_tags", default=[])
        tags_count = len([x for x in tags.split(",") if x.strip()]) if isinstance(tags,str) else (len(tags) if isinstance(tags,(list,tuple)) else 0)
        meta_ok = bool(_first("meta_description", "subtitulo", "resumo"))
        seo_real = int(round((sum([title_ok, link_ok, meta_ok, tags_count >= 5]) / 4) * 100))
        relevancia = _clamp(_first("score_editorial", "relevancia", default=0)); originalidade = 0 if dup else (100 if link_ok else 0)
        legibilidade = 90 if util_corpo >= 1200 else (75 if util_txt >= min_chars else (max(20, min(60, int(util_txt / max(1,min_chars) * 60))) if util_txt else 0))
        try:
            self._v46_bar_relevancia(relevancia); self._v46_bar_originalidade(originalidade); self._v46_bar_legibilidade(legibilidade); self._v46_bar_seo(seo_real)
            def _risk_field(name, alt):
                val = _first(name, alt)
                if val is None and risco_detalhado_calc:
                    val = risco_detalhado_calc.get(name)
                return (_clamp(val) if val is not None else None)
            self._v46_bar_desinfo(_risk_field("risco_desinformacao", "desinformacao_score"))
            self._v46_bar_vies(_risk_field("vies_editorial", "risco_vies"))
            self._v46_bar_sens(_risk_field("sensacionalismo", "risco_sensacionalismo"))
            self._v46_bar_sensivel(_risk_field("conteudo_sensivel", "risco_conteudo_sensivel"))
        except Exception: pass
        checks=[
            ("Fonte identificada e ativa" if fonte_ok_nome else "Fonte ainda não confirmada", fonte_ok_nome),
            ("Autor verificado" if bool(_first("autor")) else "Autor ausente; usar fonte/Redação", bool(_first("autor") or _first("fonte_nome","nome_fonte"))),
            ("Data de publicação válida" if data_ok else "Data da fonte ausente", data_ok),
            ("Sem duplicatas detectadas" if not dup else "Possível duplicata detectada", not dup),
            (f"Texto fonte OK: {util_txt} chars" if util_txt >= min_chars else f"Texto fonte {util_txt}/{min_chars} chars", util_txt >= min_chars),
            ("Imagem pronta" if img_ok else ("Imagem em tentativa" if img_pendente else "Imagem ainda não localizada"), img_ok or img_pendente),
            ("Metadados completos" if (title_ok and link_ok and fonte_ok_nome and data_ok) else "Metadados incompletos", title_ok and link_ok and fonte_ok_nome and data_ok),]
        try:
            for row,(txt,ok) in zip(getattr(self,"_v46_checks",[]),checks): row._v46_set(txt,ok)
        except Exception: pass
        try:
            titulo=_short(_first("titulo_origem","titulo",default="sem pauta selecionada"),82); fonte_st=str(_first("status_fonte_v105",default="não iniciada") or "não iniciada"); img_st=str(_first("imagem_status",default="não iniciada") or "não iniciada")
            self._update_sidebar_status(f"Selecionado: {titulo} — texto {util_txt}/{min_chars}; fonte {fonte_st}; imagem {img_st}; fila em ordem cronológica, mais recentes primeiro.")
        except Exception: pass

    def _v46_build_main_panels(self):
        self._main_paned = ttk.PanedWindow(self, orient="horizontal")
        self._main_paned.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        fl = tk.Frame(self._main_paned, bg=color("surface"), highlightbackground=color("border"), highlightthickness=1)
        self._frame_lista_pai = fl
        self._frame_lista = tk.Frame(fl, bg=color("surface"))
        self._frame_lista.pack(fill="both", expand=True)
        self._construir_lista(self._frame_lista)
        self._painel_revisao_widget = None
        self._faixa_revisao = None
        self._main_paned.add(fl, weight=30)

        fd = tk.Frame(self._main_paned, bg=color("surface"), highlightbackground=color("border"), highlightthickness=1)
        self._frame_detalhe = fd
        self._construir_detalhe(fd)
        self._main_paned.add(fd, weight=56)

        fs = tk.Frame(self._main_paned, bg=color("bg"), width=340)
        self._v46_sidebar = fs
        _build_sidebar(self, fs)
        self._main_paned.add(fs, weight=18)
        self._paned = self._main_paned

    def _v46_apply_panes_saved(self):
        try:
            w = max(1100, self._main_paned.winfo_width())
            left = max(360, min(520, int(w * 0.27)))
            right = max(315, min(380, int(w * 0.20)))
            self._main_paned.sashpos(0, left)
            self._main_paned.sashpos(1, max(left + 520, w - right))
        except Exception:
            pass

    old_select = getattr(PainelUrurau, "_ao_selecionar", None)
    def _v46_ao_selecionar(self, pauta):
        ret = old_select(self, pauta) if old_select else None
        try:
            self._v46_update_sidebar(pauta)
        except Exception:
            pass
        return ret

    setattr(PainelUrurau, "_v43_build_main_panels", _v46_build_main_panels)
    setattr(PainelUrurau, "_v43_apply_panes_saved", _v46_apply_panes_saved)
    setattr(PainelUrurau, "_v46_update_sidebar", _update_sidebar)
    setattr(PainelUrurau, "_v46_update_sidebar_status", _update_sidebar_status)
    setattr(PainelUrurau, "_ao_selecionar", _v46_ao_selecionar)
    return True


# ---------------------------------------------------------------------------
# Fila compacta com titulo quebrando linha
# ---------------------------------------------------------------------------

def apply_queue_v46(FilaPautas_cls):
    if FilaPautas_cls is None or rounded_rect is None or RingV45 is None or draw_status_pill is None:
        return False

    ROW_H = 96
    try:
        FilaPautas_cls._ROW_H = ROW_H
    except Exception:
        pass

    def _build_pills(self, p, status):
        out = []
        if status:
            st = str(status).lower()
            tone = "success" if st in ("captada", "publicada", "pronta") else "warn" if st in ("baixo_score", "em_redacao") else "danger" if st in ("rejeitada", "bloqueada", "excluida") else "info"
            label = str(status).replace("_", " ").upper()[:12]
            out.append((label, tone))
        canal = p.get("canal_forcado") or p.get("canal")
        if canal:
            out.append((str(canal).upper()[:14], "info"))
        try:
            termos = self._termos_prioridade(p)
        except Exception:
            termos = []
        if termos:
            out.append((f"PRIO: {termos[0][:16]}", "warn"))
        st_fonte = str(p.get("status_fonte_v105") or ("ok" if p.get("cleaned_source_text") else "pendente")).lower()
        out.append(("TXT OK", "success") if st_fonte == "ok" else ("TXT…", "info") if st_fonte in ("buscando", "pendente") else ("TXT !", "warn"))
        return out

    def _draw_action(self, canvas, x1, y1, x2, y2, text, fg, bg, action, idx):
        try:
            rounded_rect(canvas, x1, y1, x2, y2, radius=9, fill=bg, outline=bg, tags=("row",))
            canvas.create_text((x1+x2)/2, (y1+y2)/2, text=text, fill=fg,
                               font=("Segoe UI Semibold", 8, "bold"), tags=("row",))
            self._hit_actions.append((x1, y1, x2, y2, action, idx))
        except Exception:
            pass

    def _draw_row(self, idx, w):
        if idx < 0 or idx >= len(self._itens):
            return
        p = self._itens[idx]
        c = self._canvas
        y = idx * ROW_H
        uid = self._uid(p, idx)
        status = str(p.get("status") or "")
        sep = bool(p.get("_separador_coleta_v123"))
        selected = idx == self._sel_idx
        x0 = 10
        x1 = max(x0 + 80, w - 10)
        y0 = y + 5
        y1 = y + ROW_H - 5
        c.create_rectangle(0, y, w, y + ROW_H, fill=color("bg"), outline=color("bg"), tags=("row",))

        if sep:
            rounded_rect(c, x0, y0, x1, y1, radius=10, fill="#071c2c", outline=color("info"), tags=("row",))
            c.create_text(x0 + 16, y0 + 24, anchor="w", text=str(p.get("titulo_origem") or "Coleta"),
                          fill=color("info"), font=("Segoe UI Semibold", 10, "bold"), tags=("row",))
            c.create_text(x0 + 16, y0 + 48, anchor="w", text=str(p.get("_subtitulo_separador_v123") or ""),
                          fill=color("text_muted"), font=font("label_sm"), width=max(100, w - 60), tags=("row",))
            return

        card_bg = color("overlay") if selected else (color("surface_hi") if idx % 2 else color("surface"))
        outline = color("purple") if selected else color("border")
        stripe = color("purple") if selected else color("border_strong")
        if status == "baixo_score":
            outline = color("warn_dim"); stripe = color("warn")
        elif status in ("publicada", "pronta"):
            outline = color("success_dim"); stripe = color("success")
        elif status == "excluida":
            card_bg = "#080d15"; stripe = color("text_subtle")

        rounded_rect(c, x0, y0, x1, y1, radius=10, fill=card_bg, outline=outline, width=1, tags=("row",))
        rounded_rect(c, x0, y0, x0 + 3, y1, radius=10, fill=stripe, outline=stripe, tags=("row",))

        cb_x, cb_y = x0 + 13, y0 + 13
        rounded_rect(c, cb_x, cb_y, cb_x + 14, cb_y + 14, radius=3,
                     fill=color("info_dim") if uid in self._selecionados else card_bg,
                     outline=color("border_strong"), tags=("row",))
        if uid in self._selecionados:
            c.create_text(cb_x + 7, cb_y + 7, text="✓", fill=color("info"), font=("Segoe UI", 8, "bold"), tags=("row",))

        texto_ok_v47_9, util_v47_9, min_v47_9 = _v47_9_texto_extraido_ok(p)
        score = max(0, min(100, _safe_int(p.get("score_editorial") or p.get("score") or p.get("score_final"), 0)))
        ring_size = 40
        ring_cx = x1 - 28
        ring_cy = (y0 + y1) / 2
        content_right = x1 - 56
        if w > 350:
            if texto_ok_v47_9:
                photo = RingV45.get_photo(score, inverse=False, size=ring_size, thickness=4)
                if photo:
                    c.create_image(ring_cx, ring_cy, image=photo, tags=("row",))
                    refs = getattr(c, "_v46_ring_refs", [])
                    refs.append(photo)
                    if len(refs) > 160:
                        refs = refs[-80:]
                    c._v46_ring_refs = refs
                c.create_text(ring_cx, ring_cy, text=str(score), fill=RingV45.color_for(score),
                              font=("Segoe UI Semibold", 10, "bold"), tags=("row",))
            else:
                r = ring_size // 2 - 2
                c.create_oval(ring_cx - r, ring_cy - r, ring_cx + r, ring_cy + r, outline=color("ring_track"), width=3, tags=("row",))
                c.create_text(ring_cx, ring_cy - 2, text="--", fill=color("text_muted"), font=("Segoe UI Semibold", 10, "bold"), tags=("row",))
                c.create_text(ring_cx, ring_cy + 13, text=f"TXT {util_v47_9}/{min_v47_9}", fill=color("text_muted"), font=("Segoe UI", 5), tags=("row",))

        bx2 = int(content_right)
        if status == "excluida":
            _draw_action(self, c, bx2 - 88, y0 + 10, bx2, y0 + 30, "Reativar", color("text_dim"), color("surface_max"), "reativar", idx)
            text_right = bx2 - 98
        elif status == "baixo_score":
            _draw_action(self, c, bx2 - 82, y0 + 10, bx2, y0 + 30, "Aprovar", "white", color("warn_dim"), "aprovar_baixo", idx)
            _draw_action(self, c, bx2 - 172, y0 + 10, bx2 - 90, y0 + 30, "Reprovar", "white", color("danger_dim"), "reprovar_baixo", idx)
            text_right = bx2 - 182
        elif p.get("materia"):
            _draw_action(self, c, bx2 - 100, y0 + 10, bx2, y0 + 30, "Ver matéria", "white", color("success_dim"), "abrir", idx)
            text_right = bx2 - 110
        else:
            _draw_action(self, c, bx2 - 76, y0 + 10, bx2, y0 + 30, "Gerar", "white", color("info_dim"), "gerar", idx)
            text_right = bx2 - 86

        tx0 = x0 + 38
        title_w = max(90, int(text_right - tx0))
        title = str(self._titulo(p) or "").strip()
        c.create_text(tx0, y0 + 20, anchor="w", text=title,
                      fill=color("text"), font=("Segoe UI Semibold", 10, "bold") if selected else ("Segoe UI", 10),
                      width=title_w, tags=("row",))

        fonte_n = str(self._fonte(p) or "")[:42]
        data_pub = str(p.get("data_pub_fonte") or p.get("data_pub_fonte_br") or "")[:18]
        meta = " · ".join([x for x in (fonte_n, data_pub) if x])
        if meta:
            c.create_text(tx0, y0 + 50, anchor="w", text=meta, fill=color("text_muted"),
                          font=font("label_sm"), width=title_w, tags=("row",))
        px = tx0
        py = y0 + 67
        for txt, tone in _build_pills(self, p, status):
            if px + 72 > text_right:
                break
            used = draw_status_pill(c, px, py, txt, tone=tone, tags=("row",))
            px += used

    setattr(FilaPautas_cls, "_ROW_H", ROW_H)
    setattr(FilaPautas_cls, "_draw_row", _draw_row)
    setattr(FilaPautas_cls, "_v46_build_pills", _build_pills)
    return True


# ---------------------------------------------------------------------------
# Entrada unica do patch
# ---------------------------------------------------------------------------

def aplicar_patch_v46(g):
    tk = g.get("tk")
    ttk = g.get("ttk")
    PainelUrurau = g.get("PainelUrurau")
    FilaPautas = g.get("FilaPautas")
    if tk is None or ttk is None or PainelUrurau is None:
        print("[V46][AVISO] Tk/Painel indisponivel. Patch nao aplicado.")
        return False
    print("[V46] Aplicando layout definitivo premium...")
    try:
        apply_header_v46(PainelUrurau, tk, ttk)
        apply_header_updates_v46(PainelUrurau, tk)
        print("[V46] Header compacto aplicado: botoes premium e faixa verde removida.")
    except Exception as e:
        print(f"[V46][AVISO] header nao aplicado: {e}")
    try:
        apply_layout_v46(PainelUrurau, tk, ttk)
        print("[V46] Layout em 3 colunas com sidebar operacional aplicado.")
    except Exception as e:
        print(f"[V46][AVISO] layout 3 colunas nao aplicado: {e}")
    try:
        if FilaPautas is not None:
            apply_queue_v46(FilaPautas)
            print("[V46] Fila compacta com quebra de linha aplicada.")
    except Exception as e:
        print(f"[V46][AVISO] fila nao aplicada: {e}")
    print("[V46] Redesign definitivo ativo.")
    return True


__all__ = ["aplicar_patch_v46"]
