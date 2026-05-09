"""theme_v44_premium.py — tokens de design premium do Ururau v44.

Fornece uma paleta única, fontes e espacamentos consistentes para o painel.
Esta camada e puramente declarativa: nao importa Tkinter nem aplica nada por
si so. Os patches v44 leem este modulo para aplicar estilos sem espalhar
literais de cor pelo codigo.

Criterios da SPEC v44:
- tema escuro leve, limpo e consistente
- divisorias discretas
- hierarquia visual clara
- evitar estilos espalhados no codigo
"""

from __future__ import annotations

# Paleta unificada (compativel com a paleta usada em patch_v43_premium).
THEME = {
    # superficies
    "bg":        "#07111f",
    "panel":     "#0b1728",
    "panel_2":   "#101d31",
    "panel_3":   "#0d1422",
    "surface":   "#101827",
    "surface2":  "#151f32",
    "surface3":  "#0d1422",
    "surface4":  "#0b1220",

    # bordas e divisorias
    "border":         "#203149",
    "border_strong":  "#2a3a55",
    "divider":        "#1a2740",

    # texto
    "text":      "#e8eef7",
    "text_dim":  "#cbd5e1",
    "muted":     "#94a3b8",
    "muted_2":   "#64748b",

    # cores de marca
    "brand":     "#ff7a1a",
    "brand_dim": "#cc6214",

    # estados / score
    "green":     "#22c55e",
    "green_dim": "#14532d",
    "blue":      "#3b82f6",
    "cyan":      "#38bdf8",
    "purple":    "#8b5cf6",
    "amber":     "#f59e0b",
    "red":       "#ef4444",

    # tipografia padrao
    "font":            ("Segoe UI", 9),
    "font_bold":       ("Segoe UI Semibold", 9),
    "font_title":      ("Segoe UI Semibold", 11),
    "font_kpi":        ("Segoe UI Semibold", 14),
    "font_mono":       ("Consolas", 10),
    "font_mono_small": ("Consolas", 9),
}


def color(key, fallback="#000000"):
    """Lookup tolerante a chaves ausentes."""
    val = THEME.get(key, fallback)
    if isinstance(val, str):
        return val
    return fallback


def font(key, fallback=None):
    f = THEME.get(key, fallback)
    if f is None:
        return ("Segoe UI", 9)
    return f


# Espacamentos (tokens consistentes)
PAD = {
    "xs": 2,
    "sm": 4,
    "md": 8,
    "lg": 12,
    "xl": 20,
}


# Alturas de referencia usadas pela camada visual v44
HEIGHTS = {
    "row":           96,
    "header":        118,
    "console":       380,
    "console_min":   220,
    "console_max":   600,
    "status":        34,
    "status_strip":  28,
}


__all__ = ["THEME", "PAD", "HEIGHTS", "color", "font"]
