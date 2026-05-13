# -*- coding: utf-8 -*-
from __future__ import annotations


def aplicar_patch_v47_25(ns):
    PainelUrurau = ns.get('PainelUrurau')
    if PainelUrurau is None:
        print('[V47.25] PainelUrurau nao encontrado')
        return

    def _msg(self, texto):
        try: self._set_status(texto)
        except Exception: pass
        try: self._append_console(texto)
        except Exception: pass

    def _acao_redigir_v47_25(self):
        from tkinter import messagebox
        from ururau.editorial.integridade_redacao_v47_25 import criar_snapshot, validar_fonte_pertence
        if not self._pauta_sel:
            messagebox.showwarning('Redigir', 'Selecione uma pauta primeiro.')
            return
        pauta = criar_snapshot(self._pauta_sel)
        link = pauta.get('link_origem','')
        uid = pauta.get('uid') or pauta.get('_uid') or ''
        if self.db.pauta_ja_publicada(link, uid):
            messagebox.showerror('Bloqueado', 'Esta pauta ja foi publicada.')
            return
        # fix/auditoria-fila-scrapling-v136 + spec_claudio_reverter_bloqueio:
        # nao bloqueia mais cegamente quando pauta_foi_descartada. Delega
        # decisao ao painel.py canonico via fallback: se houver texto valido,
        # reativa; senao, pede confirmacao para tentar reidratar.
        if self.db.pauta_foi_descartada(link, uid):
            try:
                from ururau.core.source_text_contract import source_text_is_valid, source_text_len
                _tem_txt = source_text_is_valid(pauta)
                _chars = source_text_len(pauta)
            except Exception:
                _tem_txt = False
                _chars = 0
            if _tem_txt:
                if not messagebox.askyesno(
                    'Pauta descartada com texto valido',
                    f'Esta pauta esta marcada como descartada, mas tem texto fonte '
                    f'completo ({_chars} chars uteis).\n\nReativar e redigir?'
                ):
                    return
                try:
                    self.db.reativar_pauta_para_redacao(uid, motivo='v47_25_texto_fonte_valido')
                except Exception as _e_reat:
                    messagebox.showerror('Erro ao reativar', str(_e_reat))
                    return
            else:
                if not messagebox.askyesno(
                    'Pauta descartada sem texto',
                    'Pauta descartada e sem texto valido. Tentar reidratar e redigir?'
                ):
                    return
                try:
                    self.db.reativar_pauta_para_redacao(uid, motivo='v47_25_reidratacao_usuario', novo_status='redacao_pendente')
                except Exception as _e_reat2:
                    messagebox.showerror('Erro ao reativar', str(_e_reat2))
                    return
        similar = self.db.titulo_similar_ja_publicado(pauta.get('titulo_origem',''))
        if similar:
            if not messagebox.askyesno('Titulo similar', f"Publicado recentemente:\n'{similar[:80]}'\nRedigir mesmo assim?"):
                return
        try:
            fonte_aberta = self._obter_texto_aba_fonte_v96()
            if fonte_aberta:
                ok, motivo = validar_fonte_pertence(pauta, fonte_aberta)
                if ok:
                    self._injetar_fonte_longa_v96(pauta, fonte_aberta, origem='aba_fonte_validada_v47_25')
                else:
                    print('[V47.25][INTEGRIDADE] fonte aberta ignorada:', motivo)
        except Exception as e:
            print('[V47.25][INTEGRIDADE] aviso fonte aberta:', e)
        _msg(self, f"Redigindo snapshot seguro: {(pauta.get('titulo_origem') or '')[:55]}...")
        self._em_thread(self._redigir_thread, pauta)

    def _redigir_thread_v47_25(self, pauta):
        try:
            from tkinter import messagebox
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            from ururau.editorial.integridade_redacao_v47_25 import (
                criar_snapshot, validar_fonte_pertence, validar_materia_pertence,
                aplicar_assinatura, salvar_quarentena, texto_fonte,
            )
            pauta = criar_snapshot(pauta)
            uid = pauta.get('uid') or pauta.get('_uid') or _uid_para_pauta(pauta.get('link_origem',''), pauta.get('titulo_origem',''))
            pauta['uid'] = uid; pauta['_uid'] = uid
            wf = WorkflowPublicacao(self.db, self.client, self.modelo)
            if not wf.etapa_gate_antiduplicacao(uid, pauta, modo='redigir'):
                self.after(0, lambda: self._set_status('Pauta bloqueada pelo gate.'))
                self.after(0, self._carregar_pautas)
                return
            wf.etapa_coleta_texto(uid, pauta)
            try:
                ok_fonte, motivo_fonte = validar_fonte_pertence(pauta, texto_fonte(pauta))
                if not ok_fonte:
                    try: self._v105_hidratar_pauta(pauta, origem='redigir_integridade_v47_25', forcar=True, atualizar_ui=False)
                    except Exception: pass
                    ok_fonte, motivo_fonte = validar_fonte_pertence(pauta, texto_fonte(pauta))
                if not ok_fonte:
                    self.after(0, lambda mf=motivo_fonte: self._set_status('Redação bloqueada por integridade da fonte: ' + mf))
                    self.after(0, lambda mf=motivo_fonte: messagebox.showerror('Integridade bloqueada', 'A fonte carregada não pertence à pauta selecionada.\n\n' + mf))
                    return
            except Exception as e:
                print('[V47.25][INTEGRIDADE] falha ao validar fonte:', e)
            wf.etapa_imagem(uid, pauta)
            materia = wf.etapa_redacao(uid, pauta)
            if not materia:
                self.after(0, lambda: self._set_status('Falha na redação.'))
                return
            try:
                materia = wf.etapa_pacote_editorial(uid, materia)
            except Exception:
                pass
            try:
                ok_mat, motivo_mat = validar_materia_pertence(pauta, materia)
                if not ok_mat:
                    arq = salvar_quarentena('data', pauta, materia, motivo_mat)
                    self.after(0, lambda: self._set_status('Redação bloqueada: matéria gerada não pertence à pauta.'))
                    self.after(0, lambda mm=motivo_mat, arq=arq: messagebox.showerror('Integridade bloqueada', 'A IA gerou ou o sistema carregou conteúdo de outra pauta.\n\n' + mm + '\n\nNada foi salvo. Quarentena: ' + arq))
                    return
                aplicar_assinatura(pauta, materia)
            except Exception as e:
                self.after(0, lambda e=e: messagebox.showerror('Integridade', f'Falha na auditoria de integridade: {e}'))
                return
            try: wf.etapa_verificacao_risco(uid, pauta, materia)
            except Exception: pass
            wf.etapa_persistir_materia(uid, pauta, materia)
            self.after(0, lambda: self._set_status('Redação concluída com integridade pauta/fonte/matéria OK.'))
            self.after(0, lambda: messagebox.showinfo('Redação concluída', 'Matéria gerada com trava de integridade OK. Use Preview antes de publicar.'))
            self.after(0, self._carregar_pautas)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda msg=msg: self._set_status(f'Erro na redação: {msg}'))
            self.after(0, lambda msg=msg: messagebox.showerror('Erro na redação', msg))

    old_preview_inline = getattr(PainelUrurau, '_abrir_preview_inline', None)

    def _abrir_preview_inline_v47_25(self, pauta, md):
        from tkinter import messagebox
        from ururau.editorial.integridade_redacao_v47_25 import validar_materia_pertence
        try:
            ok, motivo = validar_materia_pertence(pauta, md)
            if not ok:
                messagebox.showerror('Preview bloqueado por integridade', 'A matéria salva não pertence à pauta selecionada.\n\n' + motivo + '\n\nUse Redigir novamente. O preview antigo foi bloqueado para evitar publicação errada.')
                try: self._set_status('Preview bloqueado: matéria não pertence à pauta selecionada.')
                except Exception: pass
                return
        except Exception as e:
            print('[V47.25][PREVIEW] aviso integridade:', e)
        if callable(old_preview_inline):
            return old_preview_inline(self, pauta, md)

    PainelUrurau._acao_redigir = _acao_redigir_v47_25
    PainelUrurau._redigir_thread = _redigir_thread_v47_25
    if callable(old_preview_inline):
        PainelUrurau._abrir_preview_inline = _abrir_preview_inline_v47_25
    print('[V47.25] Trava de integridade pauta/fonte/materia aplicada ao Redigir e Preview.')
