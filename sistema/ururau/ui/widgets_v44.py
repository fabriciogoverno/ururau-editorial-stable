"""widgets_v44.py — widgets premium leves do Ururau v44.

Implementa os componentes visuais reaproveitaveis usados pelo patch v44:

- ScoreRingCache: cache global de PhotoImages para circulos de score (IA, Risco
  e score editorial da fila de pautas), evitando que o sistema redesenhe e
  realoque imagens a cada refresh.
- create_metric_ring / update_metric_ring: helpers para os indicadores
  circulares do header (IA / Risco) lisos e anti-aliased.
- draw_queue_ring: helper para desenhar o circulo de score dentro da fila
  reutilizando a mesma cache.

Tudo aqui depende apenas de Tkinter + Pillow (opcional, com fallback nativo).
"""

from __future__ import annotations

import math

try:
    from .theme_v44_premium import THEME, color, font
except Exception:  # pragma: no cover - fallback se import falhar
    THEME = {
        "bg": "#07111f",
        "border": "#203149",
        "border_strong": "#2a3a55",
        "text": "#e8eef7",
        "muted": "#94a3b8",
        "green": "#22c55e",
        "amber": "#f59e0b",
        "red": "#ef4444",
        "blue": "#3b82f6",
    }
    def color(k, fb="#000"):
        return THEME.get(k, fb)
    def font(k, fb=None):
        return ("Segoe UI", 9)


# ----------------------------------------------------------------------------
# Cache global de circulos (compartilhado entre header e fila de pautas)
# ----------------------------------------------------------------------------

class ScoreRingCache:
    """Cache global de PhotoImage para circulos.

    Chave: (valor, inverse, size, thickness, cor). Limite defensivo para nao
    crescer indefinidamente em sessoes longas.
    """

    _cache = {}
    _MAX = 320

    @classmethod
    def _hex_to_rgba(cls, hex_color, alpha=255):
        h = str(hex_color or "#000000").strip().lstrip("#")
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)
        except Exception:
            return (0, 0, 0, alpha)

    @classmethod
    def color_for(cls, value, inverse=False):
        try:
            v = int(float(value))
        except Exception:
            v = 0
        if inverse:
            if v <= 25:
                return color("green", "#22c55e")
            if v <= 60:
                return color("amber", "#f59e0b")
            return color("red", "#ef4444")
        if v >= 80:
            return color("green", "#22c55e")
        if v >= 55:
            return color("amber", "#f59e0b")
        return color("red", "#ef4444")

    @classmethod
    def get_photo(cls, value, inverse=False, size=44, thickness=3,
                  bg_color=None, base_ring="#263246"):
        """Retorna um PhotoImage para o ring (Pillow). Pode retornar None se
        Pillow nao estiver disponivel; nesse caso o caller deve cair em
        ``create_arc`` nativo do Tkinter.

        O resultado e cacheado por (valor, inverse, size, thickness, cor).
        """
        try:
            from PIL import Image, ImageDraw, ImageTk
            try:
                resample = Image.Resampling.LANCZOS
            except Exception:
                resample = Image.LANCZOS

            try:
                v = max(0, min(100, int(float(value))))
            except Exception:
                v = 0

            ring_color = cls.color_for(v, inverse=inverse)
            key = (v, bool(inverse), int(size), int(thickness),
                   str(ring_color), str(base_ring))
            if key in cls._cache:
                return cls._cache[key]

            scale = 4
            s = max(24, int(size)) * scale
            t = max(2, int(thickness)) * scale
            pad = max(t + 2, 4 * scale)
            img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            bbox = (pad, pad, s - pad, s - pad)
            draw.ellipse(bbox, outline=cls._hex_to_rgba(base_ring), width=t)
            if v > 0:
                end = -90 + min(359.5, 360.0 * v / 100.0)
                draw.arc(bbox, start=-90, end=end,
                         fill=cls._hex_to_rgba(ring_color), width=t)
            img = img.resize((int(size), int(size)), resample)
            photo = ImageTk.PhotoImage(img)
            cls._cache[key] = photo

            if len(cls._cache) > cls._MAX:
                # remove entradas antigas em bloco
                for old_key in list(cls._cache.keys())[: cls._MAX // 4]:
                    try:
                        del cls._cache[old_key]
                    except Exception:
                        pass
            return photo
        except Exception:
            return None

    @classmethod
    def clear(cls):
        cls._cache.clear()


# ----------------------------------------------------------------------------
# Helpers para o header (IA / Risco)
# ----------------------------------------------------------------------------

def create_metric_ring(parent, title, value="--", inverse=False, size=52,
                       tk_module=None, bg=None):
    """Cria um indicador circular (frame + canvas) liso e cacheado."""
    if tk_module is None:
        import tkinter as tk_module  # local import
    bg = bg or color("bg", "#07111f")

    f = tk_module.Frame(parent, bg=bg, width=size + 22, height=size + 24)
    f.pack_propagate(False)
    cv = tk_module.Canvas(f, width=size + 12, height=size + 18, bg=bg,
                          highlightthickness=0, bd=0)
    cv.pack(anchor="center", pady=(2, 0))

    try:
        val = max(0, min(100, int(float(value))))
    except Exception:
        val = 0
    ring_color = ScoreRingCache.color_for(val, inverse=inverse)
    cx = (size + 12) // 2
    cy = (size + 6) // 2

    photo = ScoreRingCache.get_photo(val, inverse, size=size, thickness=3)
    if photo is not None:
        cv.create_image(cx, cy, image=photo, tags="ring_img")
        f._v44_ring_photo = photo
    else:
        # fallback nativo: Canvas.create_arc
        pad = 5
        x0 = pad
        y0 = pad
        x1 = size + 5
        y1 = size + 5
        cv.create_oval(x0, y0, x1, y1, outline="#263246", width=3, tags="base")
        cv.create_arc(x0, y0, x1, y1, start=90,
                      extent=-max(1, int(359 * val / 100)),
                      style="arc", outline=ring_color, width=3, tags="arc")

    cv.create_text(cx, cy - 3, text=str(val), fill=ring_color,
                   font=("Segoe UI Semibold", 10), tags="value")
    cv.create_text(cx, cy + 14, text=str(title), fill=color("muted", "#94a3b8"),
                   font=("Segoe UI", 7), tags="label")

    f._v44_canvas = cv
    f._v44_inverse = inverse
    f._v44_size = size
    return f


def update_metric_ring(frame, value, label=None):
    """Atualiza um ring criado por ``create_metric_ring`` sem recria-lo."""
    try:
        val = max(0, min(100, int(float(value))))
    except Exception:
        val = 0
    try:
        cv = frame._v44_canvas
        inverse = getattr(frame, "_v44_inverse", False)
        size = int(getattr(frame, "_v44_size", 50))
        ring_color = ScoreRingCache.color_for(val, inverse=inverse)
        photo = ScoreRingCache.get_photo(val, inverse, size=size, thickness=3)
        imgs = cv.find_withtag("ring_img")
        if photo is not None and imgs:
            cv.itemconfigure(imgs[0], image=photo)
            frame._v44_ring_photo = photo
        else:
            arcs = cv.find_withtag("arc")
            if arcs:
                cv.itemconfigure(
                    arcs[0],
                    outline=ring_color,
                    extent=-max(1, int(359 * val / 100)),
                )
        vals = cv.find_withtag("value")
        if vals:
            cv.itemconfigure(vals[0], text=str(val), fill=ring_color)
        if label:
            labs = cv.find_withtag("label")
            if labs:
                cv.itemconfigure(labs[0], text=label)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Helper para a fila virtualizada
# ----------------------------------------------------------------------------

def draw_queue_ring(canvas, cx, cy, value, size=42, thickness=3, tags=("row",)):
    """Desenha um ring de score dentro do Canvas da fila.

    Reusa ``ScoreRingCache`` para nao recriar PhotoImages a cada redraw.
    Retorna o PhotoImage usado (ou None) para que o caller possa segurar a
    referencia e evitar garbage collection.
    """
    try:
        v = max(0, min(100, int(float(value))))
    except Exception:
        v = 70
    ring_color = ScoreRingCache.color_for(v, inverse=False)
    photo = ScoreRingCache.get_photo(v, False, size=size, thickness=thickness)
    if photo is not None:
        canvas.create_image(cx, cy, image=photo, tags=tags)
        try:
            canvas._v44_last_ring = photo
        except Exception:
            pass
    else:
        r = size // 2 - 2
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                           outline="#263246", width=thickness, tags=tags)
        canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                          start=90,
                          extent=-max(1, int(359 * v / 100)),
                          style="arc", outline=ring_color,
                          width=thickness, tags=tags)
    canvas.create_text(cx, cy, text=str(v), fill=ring_color,
                       font=("Segoe UI Semibold", 9), tags=tags)
    return photo


__all__ = [
    "ScoreRingCache",
    "create_metric_ring",
    "update_metric_ring",
    "draw_queue_ring",
]
