"""queue_v45.py - Visual premium da Fila de Pautas (v45).

Substitui o ``_draw_row`` da classe ``FilaPautas`` por uma versao com:

- card sutil de fundo (rounded rectangle, accent stripe colorida);
- tipografia hierarquica (titulo grande, fonte/data em meta apagada);
- pills de status / canal / risco / TXT bem alinhadas;
- ring de score liso a direita (cache compartilhado RingV45);
- estado de selecao com elevacao visual (overlay claro + accent stripe forte).

NAO REESCREVE a virtualizacao por janela do v44: usa as mesmas estruturas
(``_v44_drawn_rows``, tags ``row`` e ``row_<idx>``).
"""

from __future__ import annotations

try:
    from .theme_v45_design_system import (
        COLORS, FONTS, HEIGHTS, color, font, height, tone_for_status,
    )
    from .widgets_v45 import rounded_rect, RingV45, draw_status_pill
except Exception:  # pragma: no cover
    COLORS = {}
    FONTS = {}
    HEIGHTS = {}
    rounded_rect = None
    RingV45 = None
    def color(k, fb="#000"): return fb
    def font(k, fb=None): return fb or ("Segoe UI", 9)
    def height(k, fb=30): return fb
    def tone_for_status(s): return ("info", str(s).title())


_ROW_H = 104
_PAD_X = 14
_CARD_RADIUS = 10



def _v47_9_texto_extraido_ok(p: dict) -> tuple[bool, int, int]:
    try: min_chars = int(__import__('os').getenv('URURAU_V105_MIN_CHARS_FONTE_OK', __import__('os').getenv('URURAU_MIN_CHARS_TEXTO_FONTE', '900')) or '900')
    except Exception: min_chars = 900
    texto = str(p.get('cleaned_source_text') or p.get('fonte_aba_texto') or p.get('leitura_fonte_texto') or p.get('dossie') or '')
    try: util = int(p.get('fonte_chars_v105') or p.get('chars_fonte') or p.get('fonte_chars_v111') or 0)
    except Exception: util = 0
    if util <= 0: util = len(texto.strip())
    st = str(p.get('status_fonte_v105') or p.get('status_fonte_v111') or p.get('extraction_status') or '').lower()
    return (util >= min_chars and (st in {'ok','complete','completo','success','sucesso'} or bool(texto.strip()))), util, min_chars


def apply_queue_v45(FilaPautas_cls):
    """Instala o novo desenho de linha. Retorna True/False."""
    if FilaPautas_cls is None or rounded_rect is None or RingV45 is None:
        return False

    try:
        FilaPautas_cls._ROW_H = _ROW_H
    except Exception:
        pass

    def _v45_draw_row(self, idx, w):
        if idx < 0 or idx >= len(self._itens):
            return
        p = self._itens[idx]
        c = self._canvas
        y = idx * _ROW_H
        status = str(p.get("status") or "")
        uid = self._uid(p, idx)
        sep = bool(p.get("_separador_coleta_v123"))
        selecionado = (idx == self._sel_idx)

        # ----- Cores por estado -----
        if sep:
            card_bg     = "#071c2c"
            border_clr  = color("info")
            stripe_clr  = color("info")
        elif selecionado:
            card_bg     = color("overlay", "#1a2e4d")
            border_clr  = color("accent", "#ff7a1a")
            stripe_clr  = color("accent")
        elif status == "excluida":
            card_bg     = "#0a0e16"
            border_clr  = color("border")
            stripe_clr  = color("text_subtle")
        elif status == "baixo_score":
            card_bg     = color("surface_hi")
            border_clr  = color("warn_dim")
            stripe_clr  = color("warn")
        elif status in ("publicada", "pronta"):
            card_bg     = color("surface_hi")
            border_clr  = color("success_dim")
            stripe_clr  = color("success")
        elif status in ("em_redacao", "revisada"):
            card_bg     = color("surface_hi")
            border_clr  = color("info_dim")
            stripe_clr  = color("info")
        else:
            # alterna sutilmente a luminosidade entre linhas
            card_bg     = color("surface", "#0a1628") if idx % 2 == 0 else color("surface_hi", "#0e1c33")
            border_clr  = color("border")
            stripe_clr  = color("border_strong")

        # margem interna do card
        x0 = _PAD_X
        x1 = max(x0 + 50, w - _PAD_X)
        y0 = y + 6
        y1 = y + _ROW_H - 6

        # background completo da linha (para nao mostrar surface debaixo)
        c.create_rectangle(0, y, w, y + _ROW_H,
                           fill=color("bg"), outline=color("bg"),
                           tags=("row",))

        # card arredondado
        rounded_rect(c, x0, y0, x1, y1, radius=_CARD_RADIUS,
                     fill=card_bg, outline=border_clr, width=1,
                     tags=("row",))

        # accent stripe (3px)
        rounded_rect(c, x0, y0, x0 + 3, y1, radius=_CARD_RADIUS,
                     fill=stripe_clr, outline=stripe_clr, tags=("row",))

        # separador especial (rotulos de coleta)
        if sep:
            titulo = str(p.get("titulo_origem") or "Coleta")
            sub = str(p.get("_subtitulo_separador_v123") or "Separador visual.")
            c.create_text(x0 + 16, y0 + 24, anchor="w",
                          text=titulo, fill=color("info"),
                          font=("Segoe UI Semibold", 11, "bold"),
                          tags=("row",))
            c.create_text(x0 + 16, y0 + 50, anchor="w",
                          text=sub, fill=color("text_muted"),
                          font=font("body"),
                          tags=("row",))
            return

        # checkbox (lado esquerdo, no topo)
        checked = uid in self._selecionados
        cb_x = x0 + 14
        cb_y = y0 + 8
        cb_size = 14
        cb_fill = color("info_dim") if checked else card_bg
        rounded_rect(c, cb_x, cb_y, cb_x + cb_size, cb_y + cb_size, radius=3,
                     fill=cb_fill, outline=color("border_strong"),
                     tags=("row",))
        if checked:
            c.create_text(cb_x + cb_size / 2, cb_y + cb_size / 2 + 1,
                          text="OK", fill=color("info"),
                          font=("Segoe UI Semibold", 6, "bold"),
                          tags=("row",))

        # ring de score a direita
        try:
            score = max(0, min(100, int(float(
                p.get("score_editorial") or p.get("score") or
                p.get("score_final") or 0
            ))))
        except Exception:
            score = 0
        texto_ok_v47_9, util_v47_9, min_v47_9 = _v47_9_texto_extraido_ok(p)
        ring_size = 44
        ring_cx = x1 - 30
        ring_cy = (y0 + y1) / 2
        if w > 360:
            photo = RingV45.get_photo(score, inverse=False, size=ring_size, thickness=4) if texto_ok_v47_9 else None
            if photo is not None:
                c.create_image(ring_cx, ring_cy, image=photo, tags=("row",))
                try:
                    c._v45_last_ring = photo
                except Exception:
                    pass
            else:
                r = ring_size // 2 - 2
                c.create_oval(ring_cx - r, ring_cy - r, ring_cx + r, ring_cy + r,
                              outline=color("ring_track"), width=4, tags=("row",))
                c.create_arc(ring_cx - r, ring_cy - r, ring_cx + r, ring_cy + r,
                             start=90,
                             extent=-max(1, int(359 * score / 100)),
                             style="arc", outline=RingV45.color_for(score),
                             width=4, tags=("row",))
            c.create_text(ring_cx, ring_cy, text=(str(score) if texto_ok_v47_9 else "--"),
                          fill=(RingV45.color_for(score) if texto_ok_v47_9 else color("text_muted")),
                          font=("Segoe UI Semibold", 11),
                          tags=("row",))
            c.create_text(ring_cx, ring_cy + ring_size / 2 + 8,
                          text=("SCORE" if texto_ok_v47_9 else f"TXT {util_v47_9}/{min_v47_9}"), fill=color("text_muted"),
                          font=font("label_caps"),
                          tags=("row",))
            content_right = ring_cx - ring_size / 2 - 12
        else:
            content_right = x1 - 16

        # area de botoes (lado interno do ring, parte superior)
        actions_used = 0
        if status == "excluida":
            bx2 = int(content_right)
            bx1 = bx2 - 96
            _draw_pill_button(self, c, bx1, y0 + 8, bx2, y0 + 28,
                              "Reativar", color("text_subtle"), color("surface_hi"),
                              "reativar", idx)
            actions_used = bx2 - bx1
        elif status == "baixo_score":
            bx2 = int(content_right)
            bx1 = bx2 - 88
            _draw_pill_button(self, c, bx1, y0 + 8, bx2, y0 + 28,
                              "Aprovar", "white", color("warn_dim"),
                              "aprovar_baixo", idx)
            bx3 = bx1 - 6
            bx0 = bx3 - 88
            _draw_pill_button(self, c, bx0, y0 + 8, bx3, y0 + 28,
                              "Reprovar", "white", color("danger_dim"),
                              "reprovar_baixo", idx)
            actions_used = bx2 - bx0
        elif p.get("materia"):
            bx2 = int(content_right)
            bx1 = bx2 - 110
            _draw_pill_button(self, c, bx1, y0 + 8, bx2, y0 + 28,
                              "Ver Materia", "white", color("success_dim"),
                              "abrir", idx)
            actions_used = bx2 - bx1
        else:
            bx2 = int(content_right)
            bx1 = bx2 - 90
            _draw_pill_button(self, c, bx1, y0 + 8, bx2, y0 + 28,
                              "Gerar", "white", color("info_dim"),
                              "gerar", idx)
            actions_used = bx2 - bx1

        # area textual (titulo + meta + pills) - x esquerda fixa, x direita dinamica
        text_x0 = x0 + 38
        text_x1 = max(text_x0 + 40, content_right - actions_used - 12)
        # Titulo
        titulo = self._titulo(p)
        # Corte simples por largura disponivel (~7px por char Segoe UI 11)
        max_chars = max(20, int((text_x1 - text_x0) / 6.8))
        if len(titulo) > max_chars:
            titulo = titulo[:max_chars - 1] + "."
        title_color = "#ffffff" if selecionado else color("text", "#f4f7fc")
        title_font = ("Segoe UI Semibold", 11, "bold") if selecionado else ("Segoe UI", 11, "normal")
        c.create_text(text_x0, y0 + 22, anchor="w", text=titulo,
                      fill=title_color, font=title_font, tags=("row",))

        # Meta linha (fonte / data)
        fonte_n = self._fonte(p)[:48]
        data_pub = str(p.get("data_pub_fonte") or p.get("data_pub_fonte_br") or "")[:18]
        meta_parts = []
        if fonte_n:
            meta_parts.append(fonte_n)
        if data_pub:
            meta_parts.append(data_pub)
        meta_line = "  |  ".join(meta_parts)
        if meta_line:
            c.create_text(text_x0, y0 + 44, anchor="w", text=meta_line,
                          fill=color("text_muted"), font=font("body"),
                          tags=("row",))

        # Pills de status / canal / TXT / risco / prioridade
        px = text_x0
        py = y0 + 64
        for txt, tone in _build_pills(self, p, status):
            if px + 90 > text_x1:
                break
            used = draw_status_pill(c, px, py, txt, tone=tone, tags=("row",))
            px += used

        # Linha divisoria entre cards
        c.create_line(x0 + 4, y + _ROW_H - 1, x1 - 4, y + _ROW_H - 1,
                      fill=color("divider"), tags=("row",))

    def _draw_pill_button(self, canvas, x1, y1, x2, y2, text, fg, bg, action, idx):
        rounded_rect(canvas, x1, y1, x2, y2, radius=10,
                     fill=bg, outline=bg, tags=("row",))
        canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2 + 1,
                           text=text, fill=fg,
                           font=("Segoe UI Semibold", 8, "bold"),
                           tags=("row",))
        # registra hit area
        try:
            self._hit_actions.append((x1, y1, x2, y2, action, idx))
        except Exception:
            pass

    def _build_pills(self, p, status):
        """Gera lista [(texto, tom)] para as pills da linha."""
        out = []
        if status:
            tone, label = tone_for_status(status)
            out.append((label.upper()[:14], tone))
        canal = p.get("canal_forcado") or p.get("canal")
        if canal:
            out.append((str(canal).upper()[:14], "info"))
        # texto fonte
        st_fonte = str(
            p.get("status_fonte_v105") or
            ("ok" if p.get("cleaned_source_text") else "pendente")
        ).lower()
        if st_fonte == "ok":
            out.append(("TXT OK", "success"))
        elif st_fonte in ("buscando", "pendente"):
            out.append(("TXT...", "info"))
        elif st_fonte in ("aguardando_429", "curta"):
            out.append(("TXT 429", "warn"))
        else:
            out.append(("TXT --", "danger"))
        # risco
        try:
            sc_risco = int(p.get("score_risco") or p.get("risco_score") or 0)
        except Exception:
            sc_risco = 0
        if sc_risco >= 60:
            out.append(("RISCO", "danger"))
        elif sc_risco >= 30:
            out.append(("REVISAR", "warn"))
        # urgente
        if p.get("urgente"):
            out.append(("URGENTE", "danger"))
        # prioridade
        try:
            termos = self._termos_prioridade(p)
        except Exception:
            termos = []
        if termos:
            out.append((f"PRIORIDADE: {termos[0][:18]}", "purple"))
        return out

    setattr(FilaPautas_cls, "_draw_row", _v45_draw_row)
    # Helpers anexos (caso queiram chamar diretamente)
    setattr(FilaPautas_cls, "_v45_draw_pill_button", _draw_pill_button)
    setattr(FilaPautas_cls, "_v45_build_pills", _build_pills)
    return True


__all__ = ["apply_queue_v45"]
