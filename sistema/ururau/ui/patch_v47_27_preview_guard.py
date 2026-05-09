# -*- coding: utf-8 -*-
from __future__ import annotations

def aplicar_patch_v47_27(ns):
    PainelUrurau = ns.get('PainelUrurau')
    if PainelUrurau is None:
        print('[V47.27] PainelUrurau não encontrado')
        return
    old_preview = getattr(PainelUrurau, '_abrir_preview_inline', None)
    def _preview_guard(self, pauta, md):
        from tkinter import messagebox
        try:
            from ururau.editorial.limpar_contaminadas_v47_27 import esta_contaminada
            titulo = (pauta or {}).get('titulo_origem') or (pauta or {}).get('titulo') or ''
            bad, motivo = esta_contaminada(titulo, md)
            if bad:
                messagebox.showerror('Preview bloqueado', 'A matéria salva pertence a outra pauta.\n\n' + motivo + '\n\nUse Limpar Contaminadas ou Redigir novamente após limpar.')
                try: self._set_status('Preview bloqueado: matéria contaminada de outra pauta.')
                except Exception: pass
                return
        except Exception as e:
            print('[V47.27][PREVIEW] aviso:', e)
        if callable(old_preview): return old_preview(self, pauta, md)
    if callable(old_preview):
        PainelUrurau._abrir_preview_inline = _preview_guard
    print('[V47.27] Preview agora bloqueia matéria contaminada persistida.')
