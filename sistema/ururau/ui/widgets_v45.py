"""widgets_v45.py - Widgets premium reaproveitaveis do Ururau v45.

Ferramentas pensadas para evitar criar centenas de Frames + Labels:
- ``rounded_rect``: desenha um retangulo de cantos arredondados num Canvas.
- ``PillButton``: botao Tk com tema Ururau, hover/pressed/disabled, raio fixo.
- ``KPIHeroCard``: cartao KPI com label, numero grande, sublinha (delta) e barra
  acentuada na lateral.
- ``RingV45``: ring liso (track + arco) com cache compartilhado.
- ``StatusPill``: pequena pill colorida (status, badges).

Pillow e usado quando disponivel para anti-aliasing dos rings; ha fallback
nativo via Canvas.create_arc para qualquer caso.

Compartilha o cache global de PhotoImage com ``widgets_v44`` quando esta
disponivel; assim o painel todo sofre menos pressao de imagens.
"""

from __future__ import annotations

import math

try:
    from .theme_v45_design_system import COLORS, FONTS, RADII, SPACING, HEIGHTS, color, font
except Exception:  # pragma: no cover
    COLORS = {}
    FONTS = {}
    RADII = {}
    SPACING = {}
    HEIGHTS = {}
    def color(k, fb="#000"):
        return COLORS.get(k, fb)
    def font(k, fb=None):
        return FONTS.get(k, fb) or ("Segoe UI", 9)


# Compartilha cache de rings com a v44 (chave determinista por cor/tamanho)
try:
    from .widgets_v44 import ScoreRingCache
except Exception:
    ScoreRingCache = None


# ---------------------------------------------------------------------------
# Util: rounded rectangle no Canvas
# ---------------------------------------------------------------------------

def rounded_rect(canvas, x1, y1, x2, y2, radius=8, **kw):
    """Desenha um retangulo de cantos arredondados retornando o id do polygon.

    Compatibilidade total com create_polygon: aceita fill, outline, width, tags.
    Eficiencia: gera 1 unico item de canvas (smooth polygon) em vez de varias
    primitivas.
    """
    r = max(0, int(radius))
    points = [
        x1 + r, y1,
        x1 + r, y1,
        x2 - r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


# ---------------------------------------------------------------------------
# PillButton - botao Tk customizado com hover, pressed e disabled
# ---------------------------------------------------------------------------

class PillButton:
    """Constroi um Button Tk estilizado como pill premium.

    Nao herda de tk.Button (para minimizar acoplamento). Devolve o Button
    real com bindings de hover/pressed configurados.
    """

    @staticmethod
    def build(parent, text, command, *, tone="accent", tk_module=None,
              size="md", icon=None):
        if tk_module is None:
            import tkinter as tk_module

        bg_map = {
            "accent":  (color("accent"),       color("accent_dim"),  "#ffffff"),
            "primary": (color("info"),         "#1d3a8a",            "#ffffff"),
            "success": (color("success"),      color("success_dim"), "#ffffff"),
            "warn":    (color("warn"),         color("warn_dim"),    "#1a1305"),
            "danger":  (color("danger"),       color("danger_dim"),  "#ffffff"),
            "purple":  (color("purple"),       color("purple_dim"),  "#1a1230"),
            "ghost":   (color("surface_hi"),   color("surface_max"), color("text_dim")),
            "outline": (color("surface"),      color("surface_hi"),  color("text_dim")),
        }
        bg, hover, fg = bg_map.get(tone, bg_map["ghost"])
        padx = {"sm": 10, "md": 16, "lg": 22}.get(size, 16)
        pady = {"sm":  5, "md":  8, "lg": 11}.get(size, 8)
        font_key = {"sm": "label_sm", "md": "label", "lg": "body_bold"}.get(size, "label")
        label = (icon + "  " + text) if icon else text
        btn = tk_module.Button(
            parent, text=label, command=command,
            bg=bg, fg=fg,
            activebackground=hover, activeforeground=fg,
            relief="flat", bd=0, highlightthickness=0,
            padx=padx, pady=pady,
            cursor="hand2",
            font=font(font_key),
        )
        # Hover via bind: muda o bg sem chamar config caro repetidamente
        try:
            btn._v45_bg_normal = bg
            btn._v45_bg_hover  = hover
            def _enter(_e=None, b=btn): b.configure(bg=b._v45_bg_hover)
            def _leave(_e=None, b=btn): b.configure(bg=b._v45_bg_normal)
            btn.bind("<Enter>", _enter)
            btn.bind("<Leave>", _leave)
        except Exception:
            pass
        return btn


# ---------------------------------------------------------------------------
# KPIHeroCard - card de KPI com numero grande
# ---------------------------------------------------------------------------

class KPIHeroCard:
    """Card de KPI premium: label pequeno, numero grande, sub-linha discreta,
    com accent stripe lateral colorido.

    Devolve um Frame com helpers ``set_value(value, sub=None)`` e
    ``set_tone(tone_key)`` ja anexados.
    """

    @staticmethod
    def build(parent, *, label, value="--", sub="", tone="info", width=110,
              tk_module=None):
        if tk_module is None:
            import tkinter as tk_module
        accent = color(tone, color("info"))
        f = tk_module.Frame(
            parent,
            bg=color("surface_hi"),
            highlightbackground=color("border"),
            highlightthickness=1,
            width=width, height=58,
        )
        f.pack_propagate(False)
        # Stripe lateral com 3px da cor de tom
        stripe = tk_module.Frame(f, bg=accent, width=3)
        stripe.pack(side="left", fill="y")
        body = tk_module.Frame(f, bg=color("surface_hi"))
        body.pack(side="left", fill="both", expand=True, padx=10, pady=6)
        lbl = tk_module.Label(
            body, text=str(label).upper(),
            bg=color("surface_hi"), fg=color("text_subtle"),
            font=font("label_caps"), anchor="w",
        )
        lbl.pack(fill="x")
        val = tk_module.Label(
            body, text=str(value),
            bg=color("surface_hi"), fg=color("text"),
            font=font("kpi"), anchor="w",
        )
        val.pack(fill="x", pady=(1, 0))
        sub_lbl = tk_module.Label(
            body, text=str(sub),
            bg=color("surface_hi"), fg=color("text_muted"),
            font=font("label_xs"), anchor="w",
        )
        sub_lbl.pack(fill="x")

        # API leve
        def set_value(v, sub_text=None):
            try:
                val.configure(text=str(v))
                if sub_text is not None:
                    sub_lbl.configure(text=str(sub_text))
            except Exception:
                pass

        def set_tone(t):
            try:
                stripe.configure(bg=color(t, color("info")))
            except Exception:
                pass

        f._v45_set_value = set_value
        f._v45_set_tone = set_tone
        f._v45_label = lbl
        f._v45_value_lbl = val
        f._v45_sub_lbl = sub_lbl
        f._v45_stripe = stripe
        return f


# ---------------------------------------------------------------------------
# RingV45 - ring liso com track + arco. Cache compartilhado.
# ---------------------------------------------------------------------------

class RingV45:
    """Ring premium para metricas (IA, Risco, Score da fila).

    - Cache global compartilhado (via widgets_v44.ScoreRingCache se disponivel).
    - Cor por valor com mapa proprio (verde / ambar / vermelho).
    - Track sutil de fundo, arco grosso, numero centralizado.
    """

    @staticmethod
    def color_for(value, inverse=False):
        try:
            v = int(float(value))
        except Exception:
            v = 0
        if inverse:
            if v <= 25:
                return color("success", "#22c55e")
            if v <= 60:
                return color("warn", "#f5a524")
            return color("danger", "#ef4444")
        if v >= 80:
            return color("success", "#22c55e")
        if v >= 55:
            return color("warn", "#f5a524")
        return color("danger", "#ef4444")

    @classmethod
    def get_photo(cls, value, inverse=False, size=46, thickness=4):
        if ScoreRingCache is not None:
            return ScoreRingCache.get_photo(
                value, inverse=inverse, size=size, thickness=thickness,
                base_ring=color("ring_track"),
            )
        # Fallback proprio sem cache externa
        try:
            from PIL import Image, ImageDraw, ImageTk
            try:
                v = max(0, min(100, int(float(value))))
            except Exception:
                v = 0
            ring_color = cls.color_for(v, inverse)
            scale = 4
            s = max(24, int(size)) * scale
            t = max(2, int(thickness)) * scale
            pad = max(t + 2, 4 * scale)
            img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            bbox = (pad, pad, s - pad, s - pad)
            track = color("ring_track", "#1c2845").lstrip("#")
            tr = (int(track[0:2], 16), int(track[2:4], 16),
                  int(track[4:6], 16), 255)
            d.ellipse(bbox, outline=tr, width=t)
            if v > 0:
                end = -90 + min(359.5, 360.0 * v / 100.0)
                rc = ring_color.lstrip("#")
                rc_rgb = (int(rc[0:2], 16), int(rc[2:4], 16),
                          int(rc[4:6], 16), 255)
                d.arc(bbox, start=-90, end=end, fill=rc_rgb, width=t)
            try:
                resample = Image.Resampling.LANCZOS
            except Exception:
                resample = Image.LANCZOS
            img = img.resize((int(size), int(size)), resample)
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    @classmethod
    def create_card(cls, parent, *, label, value="--", inverse=False,
                    size=46, tk_module=None):
        """Cria um card vertical: ring no topo, label embaixo."""
        if tk_module is None:
            import tkinter as tk_module
        outer = tk_module.Frame(
            parent, bg=color("surface_hi"),
            highlightbackground=color("border"),
            highlightthickness=1,
            width=size + 24, height=58,
        )
        outer.pack_propagate(False)
        cv = tk_module.Canvas(
            outer, width=size + 8, height=size + 8,
            bg=color("surface_hi"),
            highlightthickness=0, bd=0,
        )
        cv.pack(side="left", padx=(8, 4), pady=5)

        try:
            v = max(0, min(100, int(float(value))))
        except Exception:
            v = 0
        ring_color = cls.color_for(v, inverse)
        cx = (size + 8) // 2
        cy = (size + 8) // 2

        photo = cls.get_photo(v, inverse, size=size, thickness=4)
        if photo is not None:
            cv.create_image(cx, cy, image=photo, tags="ring_img")
            outer._v45_ring_photo = photo
        else:
            pad = 4
            cv.create_oval(pad, pad, size + pad, size + pad,
                           outline=color("ring_track"), width=4, tags="track")
            cv.create_arc(pad, pad, size + pad, size + pad,
                          start=90,
                          extent=-max(1, int(359 * v / 100)),
                          style="arc", outline=ring_color, width=4, tags="arc")
        cv.create_text(cx, cy - 2, text=str(v), fill=ring_color,
                       font=("Segoe UI Semibold", 11), tags="value")

        meta = tk_module.Frame(outer, bg=color("surface_hi"))
        meta.pack(side="left", fill="both", expand=True, padx=(2, 8), pady=8)
        tk_module.Label(meta, text=str(label).upper(),
                        bg=color("surface_hi"), fg=color("text_subtle"),
                        font=font("label_caps"), anchor="w").pack(fill="x")
        sub_lbl = tk_module.Label(
            meta, text="--", bg=color("surface_hi"),
            fg=color("text_muted"), font=font("label_xs"),
            anchor="w",
        )
        sub_lbl.pack(fill="x", pady=(1, 0))

        outer._v45_canvas = cv
        outer._v45_inverse = inverse
        outer._v45_size = size
        outer._v45_sub = sub_lbl

        def update(value, sub=None):
            try:
                vv = max(0, min(100, int(float(value))))
            except Exception:
                vv = 0
            try:
                rc = cls.color_for(vv, inverse)
                photo2 = cls.get_photo(vv, inverse, size=size, thickness=4)
                imgs = cv.find_withtag("ring_img")
                if photo2 is not None and imgs:
                    cv.itemconfigure(imgs[0], image=photo2)
                    outer._v45_ring_photo = photo2
                else:
                    arcs = cv.find_withtag("arc")
                    if arcs:
                        cv.itemconfigure(arcs[0], outline=rc,
                                         extent=-max(1, int(359 * vv / 100)))
                vals = cv.find_withtag("value")
                if vals:
                    cv.itemconfigure(vals[0], text=str(vv), fill=rc)
                if sub is not None:
                    sub_lbl.configure(text=str(sub))
            except Exception:
                pass

        outer._v45_update = update
        return outer


# ---------------------------------------------------------------------------
# StatusPill - badge pequeno colorido para status / categoria
# ---------------------------------------------------------------------------

def draw_status_pill(canvas, x, y, text, *, tone="info", tags=("row",)):
    """Desenha uma pill de status no Canvas e retorna a largura ocupada."""
    txt = str(text)
    pad_x = 8
    width = max(40, 7 * len(txt) + pad_x * 2)
    height = 18
    fill = color(tone + "_dim", color("surface_hi")) if tone != "info" else color("info_dim")
    fg = color(tone, color("text"))
    rounded_rect(canvas, x, y, x + width, y + height,
                 radius=6, fill=fill, outline=fill, tags=tags)
    canvas.create_text(x + width / 2, y + height / 2, text=txt,
                       fill=fg, font=("Segoe UI Semibold", 7, "bold"),
                       tags=tags)
    return width + 4


__all__ = [
    "rounded_rect",
    "PillButton",
    "KPIHeroCard",
    "RingV45",
    "draw_status_pill",
]
