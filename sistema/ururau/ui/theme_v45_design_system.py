"""theme_v45_design_system.py - Design system real do Ururau v45.

Substitui o tema chapado das versoes anteriores por um sistema em camadas
inspirado em painel profissional moderno (estilo Linear / Vercel / Stripe
dashboard, mas em modo escuro denso).

Tudo aqui e DECLARATIVO. Os patches v45 leem essas constantes para aplicar
estilo de forma consistente e nao espalhar literais de cor pelo codigo.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Cores em CAMADAS (z-index visual). bg < surface < surface_hi < surface_max.
# ---------------------------------------------------------------------------
COLORS = {
    # superficies em camadas
    "bg":           "#06101e",   # canvas principal (mais profundo)
    "surface":      "#0a1628",   # painel base
    "surface_hi":   "#0e1c33",   # cards e divisorias
    "surface_max":  "#13243f",   # destaque / hover
    "overlay":      "#1a2e4d",   # selecao / focus

    # bordas em escala
    "border":         "#1a2640",
    "border_strong":  "#243454",
    "divider":        "#152138",
    "focus_ring":     "#3d63ff",

    # texto em escala
    "text":         "#f4f7fc",
    "text_dim":     "#cbd5e1",
    "text_muted":   "#7f8ba3",
    "text_subtle":  "#5a6478",

    # marca / acento
    "accent":         "#ff7a1a",   # laranja Ururau
    "accent_dim":     "#cc6214",
    "accent_glow":    "#ff9244",
    "accent_soft":    "#3a2010",   # superficie acento muito apagada

    # estados
    "success":       "#22c55e",
    "success_dim":   "#0f3d22",
    "success_soft":  "#11261a",

    "warn":          "#f5a524",
    "warn_dim":      "#5a3a0c",
    "warn_soft":     "#241c0c",

    "danger":        "#ef4444",
    "danger_dim":    "#5a1818",
    "danger_soft":   "#221010",

    "info":          "#3b82f6",
    "info_dim":      "#0f2a55",

    "purple":        "#a78bfa",
    "purple_dim":    "#2a1c50",

    # rings (neutro / liso)
    "ring_track":   "#1c2845",
    "ring_glow":    "#0a1628",
}


# ---------------------------------------------------------------------------
# Escala de raios (cantos)
# ---------------------------------------------------------------------------
RADII = {
    "none":  0,
    "xs":    3,
    "sm":    5,
    "md":    8,
    "lg":    12,
    "xl":    16,
    "pill":  999,
}


# ---------------------------------------------------------------------------
# Espacamentos (4px base)
# ---------------------------------------------------------------------------
SPACING = {
    "xxs":  2,
    "xs":   4,
    "sm":   6,
    "md":   8,
    "lg":   12,
    "xl":   16,
    "xxl":  24,
    "x3l":  32,
}


# ---------------------------------------------------------------------------
# Tipografia
# ---------------------------------------------------------------------------
FONTS = {
    # rotulos pequenos / metadata
    "label_xs":    ("Segoe UI",          7,  "normal"),
    "label_sm":    ("Segoe UI",          8,  "normal"),
    "label":       ("Segoe UI",          9,  "normal"),
    "label_caps":  ("Segoe UI Semibold", 7,  "bold"),

    # corpo
    "body":        ("Segoe UI",          10, "normal"),
    "body_bold":   ("Segoe UI Semibold", 10, "bold"),

    # titulos
    "title_xs":    ("Segoe UI Semibold", 10, "bold"),
    "title_sm":    ("Segoe UI Semibold", 11, "bold"),
    "title":       ("Segoe UI Semibold", 13, "bold"),
    "title_lg":    ("Segoe UI Semibold", 15, "bold"),
    "display":     ("Segoe UI Semibold", 18, "bold"),
    "display_lg":  ("Segoe UI Semibold", 22, "bold"),

    # numericos KPI
    "kpi":         ("Segoe UI Semibold", 19, "bold"),
    "kpi_sm":      ("Segoe UI Semibold", 14, "bold"),

    # mono
    "mono":        ("Consolas",          10, "normal"),
    "mono_sm":     ("Consolas",          9,  "normal"),
}


# ---------------------------------------------------------------------------
# Alturas de referencia (px)
# ---------------------------------------------------------------------------
HEIGHTS = {
    # header
    "header_total":   132,
    "header_brand":   46,
    "header_actions": 46,
    "header_strip":   32,
    "header_progress": 6,

    # fila
    "row":            104,
    "row_compact":    78,
    "filter_bar":     38,
    "tools_bar":      36,

    # console
    "console":        420,
    "console_min":    240,
    "console_max":    640,
    "console_header": 26,

    # statusbar
    "status":         30,

    # botoes
    "btn":            34,
    "btn_sm":         28,
    "btn_lg":         40,

    # rings
    "ring_sm":        38,
    "ring_md":        46,
    "ring_lg":        54,
    "ring_queue":     44,
}


# ---------------------------------------------------------------------------
# Larguras
# ---------------------------------------------------------------------------
WIDTHS = {
    "kpi_card":    102,
    "ring_card":   76,
    "brand_box":   190,
    "right_strip": 580,
    "btn_action":  104,
    "btn_pill":    96,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def color(key, fallback="#000000"):
    val = COLORS.get(key, fallback)
    return val if isinstance(val, str) else fallback


def font(key, fallback=None):
    f = FONTS.get(key, fallback)
    return f if f is not None else ("Segoe UI", 9)


def radius(key, fallback=4):
    return RADII.get(key, fallback)


def space(key, fallback=4):
    return SPACING.get(key, fallback)


def height(key, fallback=30):
    return HEIGHTS.get(key, fallback)


def width(key, fallback=80):
    return WIDTHS.get(key, fallback)


# ---------------------------------------------------------------------------
# Mapas de status -> cores
# Usado pelo desenho de badges e accent stripe na fila
# ---------------------------------------------------------------------------

STATUS_TONE = {
    "captada":      ("info",     "Captada"),
    "em_redacao":   ("warn",     "Em redacao"),
    "revisada":     ("info",     "Revisada"),
    "pronta":       ("success",  "Pronta"),
    "publicada":    ("success",  "Publicada"),
    "rejeitada":    ("danger",   "Rejeitada"),
    "bloqueada":    ("danger",   "Bloqueada"),
    "excluida":     ("text_subtle", "Excluida"),
    "baixo_score":  ("warn",     "Baixo score"),
}


def tone_for_status(status):
    """Retorna ((color_key, label)) para o status. Default: info."""
    if not status:
        return ("text_muted", "")
    return STATUS_TONE.get(str(status).lower(), ("info", str(status).title()))


__all__ = [
    "COLORS", "RADII", "SPACING", "FONTS", "HEIGHTS", "WIDTHS",
    "STATUS_TONE",
    "color", "font", "radius", "space", "height", "width", "tone_for_status",
]
