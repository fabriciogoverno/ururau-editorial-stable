# -*- coding: utf-8 -*-
from __future__ import annotations

def aplicar_patch_v47_26(ns):
    PainelUrurau = ns.get('PainelUrurau')
    if PainelUrurau is None:
        print('[V47.26] PainelUrurau não encontrado')
        return
    def _redigir_thread_v47_26(self, pauta):
        try:
            from tkinter import messagebox
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            from ururau.editorial.integridade_redacao_v47_25 import criar_snapshot, validar_materia_pertence, aplicar_assinatura, salvar_quarentena
            from ururau.editorial.integridade_fonte_v47_26 import validar_fonte_estrita, forcar_reextracao_estrita, quarentena_fonte, texto_fonte
            pauta = criar_snapshot(pauta)
            uid = pauta.get('uid') or pauta.get('_uid') or _uid_para_pauta(pauta.get('link_origem',''), pauta.get('titulo_origem',''))
            pauta['uid'] = uid; pauta['_uid'] = uid
            wf = WorkflowPublicacao(self.db, self.client, self.modelo)
            if not wf.etapa_gate_antiduplicacao(uid, pauta, modo='redigir'):
                self.after(0, lambda: self._set_status('Pauta bloqueada pelo gate.'))
                self.after(0, self._carregar_pautas)
                return
            wf.etapa_coleta_texto(uid, pauta)
            ok_fonte, motivo_fonte = validar_fonte_estrita(pauta, texto_fonte(pauta))
            if not ok_fonte:
                for k in ['texto_fonte','cleaned_source_text','raw_source_text','rss_context_text']:
                    pauta[k] = ''
                try:
                    self.db.salvar_evento(uid, 'integridade_fonte_v47_26', 'Fonte inconsistente antes da IA: ' + motivo_fonte)
                except Exception:
                    pass
                ok_re, motivo_re = forcar_reextracao_estrita(pauta)
                ok_fonte, motivo_fonte = validar_fonte_estrita(pauta, texto_fonte(pauta))
                if not (ok_re and ok_fonte):
                    arq = quarentena_fonte('data', pauta, motivo_re + ' | ' + motivo_fonte)
                    self.after(0, lambda: self._set_status('Redação bloqueada: fonte não pertence à pauta selecionada.'))
                    self.after(0, lambda: messagebox.showerror('Fonte bloqueada por integridade', 'A fonte carregada não pertence à pauta selecionada e a reextração não corrigiu.\n\nNada foi enviado à IA.\n\nQuarentena: ' + arq))
                    return
            wf.etapa_imagem(uid, pauta)
            materia = wf.etapa_redacao(uid, pauta)
            if not materia:
                self.after(0, lambda: self._set_status('Falha na redação.'))
                return
            try:
                materia = wf.etapa_pacote_editorial(uid, materia)
            except Exception:
                pass
            ok_mat, motivo_mat = validar_materia_pertence(pauta, materia)
            if not ok_mat:
                arq = salvar_quarentena('data', pauta, materia, motivo_mat)
                self.after(0, lambda: self._set_status('Redação bloqueada: matéria gerada não pertence à pauta.'))
                self.after(0, lambda: messagebox.showerror('Integridade bloqueada', 'A IA gerou ou o sistema carregou conteúdo de outra pauta.\n\n' + motivo_mat + '\n\nNada foi salvo. Quarentena: ' + arq))
                return
            aplicar_assinatura(pauta, materia)
            try:
                wf.etapa_verificacao_risco(uid, pauta, materia)
            except Exception:
                pass
            wf.etapa_persistir_materia(uid, pauta, materia)
            self.after(0, lambda: self._set_status('Redação concluída com fonte validada antes da IA.'))
            self.after(0, lambda: messagebox.showinfo('Redação concluída', 'Matéria gerada com fonte validada antes da IA. Use Preview antes de publicar.'))
            self.after(0, self._carregar_pautas)
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: self._set_status('Erro na redação: ' + msg))
            self.after(0, lambda: messagebox.showerror('Erro na redação', msg))
    PainelUrurau._redigir_thread = _redigir_thread_v47_26
    print('[V47.26] Redigir agora valida/reextrai a fonte ANTES de chamar a IA.')
