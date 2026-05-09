"""virtual_queue_v44.py — virtualizacao incremental da Fila de Pautas.

Esta camada nao reescreve a classe ``FilaPautas`` original. Ela injeta uma
versao otimizada de ``_redraw_visible`` e ``_request_redraw`` que:

1. Renderiza apenas as linhas visiveis no Canvas (ja era o caso) PORM
2. Mantem cada linha com um tag ``row_<idx>`` proprio.
3. Em cada redraw apenas REMOVE linhas que sairam da viewport e ADICIONA
   linhas que entraram. Linhas que continuam visiveis NAO sao redesenhadas.
4. Aplica debouncing real ao scroll para nao acionar redraw a cada tick do
   mouse wheel.
5. Forca redraw completo apenas quando os dados mudam (``popular``,
   ``_repaint_all``).

Resultado esperado:
- Scroll fluido com 500/1000/2000 pautas.
- Redraw quase instantaneo (1-2 linhas por evento).
- Console e detalhe nao sao bloqueados pela fila.
"""

from __future__ import annotations


def install_window_virtualization(FilaPautas_cls):
    """Instala a virtualizacao incremental por janela em ``FilaPautas``.

    Monkey-patch seguro: preserva as funcoes originais como fallback.
    """
    if FilaPautas_cls is None:
        return False

    if getattr(FilaPautas_cls, "_v44_window_virt_installed", False):
        return True

    # Buffer reduzido: como nao redesenhamos a cada scroll, nao precisamos
    # de margem grande. 2 linhas a mais cobrem qualquer transicao.
    try:
        FilaPautas_cls._BUFFER = max(2, int(getattr(FilaPautas_cls, "_BUFFER", 3)))
    except Exception:
        pass

    _orig_request_redraw = getattr(FilaPautas_cls, "_request_redraw", None)
    _orig_redraw_visible = getattr(FilaPautas_cls, "_redraw_visible", None)
    _orig_popular = getattr(FilaPautas_cls, "popular", None)

    def _v44_visible_indices(self):
        c = self._canvas
        try:
            h = max(1, c.winfo_height())
            top = float(c.canvasy(0))
            bottom = top + h
            row_h = max(1, int(getattr(self, "_ROW_H", 96)))
            ini = max(0, int(top // row_h) - int(getattr(self, "_BUFFER", 2)))
            fim = min(len(self._itens) - 1,
                      int(bottom // row_h) + int(getattr(self, "_BUFFER", 2)))
            if fim < ini:
                return ini, ini - 1
            return ini, fim
        except Exception:
            return 0, min(len(self._itens) - 1, 20)

    def _v44_full_repaint(self):
        """Redesenha tudo do zero (quando dados ou tamanho mudam)."""
        c = self._canvas
        try:
            w = max(1, c.winfo_width())
            total_h = self._total_h()
            c.configure(scrollregion=(0, 0, w, total_h))
            c.delete("row")
            self._hit_actions = []
            self._v44_drawn_rows = set()
            if not self._itens:
                return
            ini, fim = _v44_visible_indices(self)
            for idx in range(ini, fim + 1):
                try:
                    self._draw_row(idx, w)
                    self._v44_drawn_rows.add(idx)
                except Exception:
                    pass
            # Re-tag itens recem-desenhados com row_<idx> para diff incremental
            self._v44_apply_per_row_tags(ini, fim)
        except Exception:
            try:
                if _orig_redraw_visible:
                    _orig_redraw_visible(self)
            except Exception:
                pass

    def _v44_apply_per_row_tags(self, ini, fim):
        """Adiciona o tag ``row_<idx>`` em cima do tag generico ``row``."""
        c = self._canvas
        row_h = max(1, int(getattr(self, "_ROW_H", 96)))
        try:
            for idx in range(ini, fim + 1):
                y0 = idx * row_h
                y1 = y0 + row_h
                # find_overlapping pega tudo que cai naquela linha
                items = c.find_overlapping(0, y0, c.winfo_width(), y1 - 1)
                tag = f"row_{idx}"
                for item in items:
                    tags = c.gettags(item)
                    if "row" in tags and tag not in tags:
                        c.addtag_withtag(tag, item)
        except Exception:
            pass

    def _v44_redraw_window(self):
        """Diff visual: remove apenas linhas que sairam, adiciona as que entraram."""
        self._redraw_after_id = None
        c = self._canvas
        try:
            w = max(1, c.winfo_width())
            total_h = self._total_h()
            # Atualiza scrollregion apenas se mudou
            try:
                cur = c.cget("scrollregion") or "0 0 0 0"
                cur_parts = [int(float(x)) for x in cur.split()] if cur else [0, 0, 0, 0]
                if (len(cur_parts) >= 4 and
                        (cur_parts[2] != w or cur_parts[3] != total_h)):
                    c.configure(scrollregion=(0, 0, w, total_h))
            except Exception:
                c.configure(scrollregion=(0, 0, w, total_h))

            if not self._itens:
                c.delete("row")
                self._hit_actions = []
                self._v44_drawn_rows = set()
                return

            ini, fim = _v44_visible_indices(self)
            visible_set = set(range(ini, fim + 1))
            drawn = getattr(self, "_v44_drawn_rows", None)
            if drawn is None:
                drawn = set()
                self._v44_drawn_rows = drawn

            # Remove linhas que sairam
            to_remove = drawn - visible_set
            for idx in to_remove:
                try:
                    c.delete(f"row_{idx}")
                except Exception:
                    pass
            if to_remove:
                drawn -= to_remove
                # Limpa hit_actions referentes a linhas removidas
                self._hit_actions = [
                    h for h in (self._hit_actions or [])
                    if h[5] not in to_remove
                ]

            # Adiciona linhas que entraram
            to_add = visible_set - drawn
            if to_add:
                for idx in sorted(to_add):
                    if idx < 0 or idx >= len(self._itens):
                        continue
                    try:
                        # Captura quantos hit_actions ja existem para mapear depois
                        before = len(self._hit_actions or [])
                        self._draw_row(idx, w)
                        after = len(self._hit_actions or [])
                        # Aplica tag row_<idx> aos itens recem-criados.
                        # Como o draw_row sempre desenha com tag "row", marcamos
                        # nessa linha apenas os items dentro do bounding box.
                        y0 = idx * int(getattr(self, "_ROW_H", 96))
                        y1 = y0 + int(getattr(self, "_ROW_H", 96))
                        items = c.find_overlapping(0, y0, w, y1 - 1)
                        tag = f"row_{idx}"
                        for it in items:
                            tags = c.gettags(it)
                            if "row" in tags and tag not in tags:
                                c.addtag_withtag(tag, it)
                        drawn.add(idx)
                    except Exception:
                        pass
        except Exception:
            # fallback seguro
            try:
                if _orig_redraw_visible:
                    _orig_redraw_visible(self)
            except Exception:
                pass

    def _v44_request_redraw(self, delay=16):
        """Debouncing real: agenda apenas se nao houver agendamento pendente."""
        try:
            if getattr(self, "_redraw_after_id", None) is not None:
                return
            self._redraw_after_id = self.after(max(8, int(delay)),
                                                _v44_redraw_window.__get__(self))
        except Exception:
            try:
                _v44_redraw_window(self)
            except Exception:
                pass

    def _v44_popular(self, itens):
        """Popular preserva ancora visual e marca dados como sujos."""
        # Reaproveita popular original (mantem semantica de ancora/selecao)
        if _orig_popular:
            try:
                _orig_popular(self, itens)
            except Exception:
                pass
        # Forca repaint completo: novos uids = tudo invalido
        try:
            self._v44_drawn_rows = set()
            # forca proximo redraw a desenhar tudo da janela
            try:
                if getattr(self, "_redraw_after_id", None) is not None:
                    self.after_cancel(self._redraw_after_id)
            except Exception:
                pass
            self._redraw_after_id = None
            self.after_idle(_v44_full_repaint.__get__(self))
        except Exception:
            pass

    def _v44_repaint_all(self):
        """API publica para forcar repaint total (uso interno do patch)."""
        try:
            self._v44_drawn_rows = set()
            _v44_full_repaint(self)
        except Exception:
            pass

    # Conecta os helpers a classe
    FilaPautas_cls._v44_visible_indices = _v44_visible_indices
    FilaPautas_cls._v44_full_repaint = _v44_full_repaint
    FilaPautas_cls._v44_apply_per_row_tags = _v44_apply_per_row_tags
    FilaPautas_cls._v44_redraw_window = _v44_redraw_window
    FilaPautas_cls._request_redraw = _v44_request_redraw
    FilaPautas_cls._redraw_visible = _v44_full_repaint  # mantem compat
    FilaPautas_cls.popular = _v44_popular
    FilaPautas_cls.repaint_all = _v44_repaint_all
    FilaPautas_cls._v44_window_virt_installed = True
    return True


__all__ = ["install_window_virtualization"]
