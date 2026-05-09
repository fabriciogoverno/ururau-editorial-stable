# -*- coding: utf-8 -*-
from __future__ import annotations


def instalar_workflow_fonte_validada_v47_29(WorkflowPublicacao):
    """Instala gate de FonteValidada no WorkflowPublicacao.

    O patch é deliberadamente conservador: depois da coleta textual, a fonte
    precisa ser validada com UID/link/título antes da etapa de redação. Isso
    impede que resumo/RSS/snippet ou fonte contaminada chegue à IA.
    """
    if getattr(WorkflowPublicacao, "_v4729_fonte_validada_instalado", False):
        return WorkflowPublicacao

    old_coleta = getattr(WorkflowPublicacao, "etapa_coleta_texto", None)
    old_redacao = getattr(WorkflowPublicacao, "etapa_redacao", None)
    if not callable(old_coleta) or not callable(old_redacao):
        return WorkflowPublicacao

    def _texto_para_validar(pauta: dict) -> str:
        return (
            pauta.get("texto_fonte_validado")
            or pauta.get("cleaned_source_text")
            or pauta.get("texto_fonte")
            or pauta.get("dossie")
            or pauta.get("raw_source_text")
            or pauta.get("resumo_origem")
            or ""
        )

    def _bloquear(self, uid: str, pauta: dict, motivo: str) -> bool:
        try:
            pauta["status_validacao"] = "erro_extracao"
            pauta["status_publicacao_sugerido"] = "bloquear_total"
            pauta["fonte_validada_bloqueio_v47_29"] = motivo
            self._log(uid, "fonte_validada_v47_29", motivo, sucesso=False)
            self._set_status(uid, pauta, "bloqueada", "Fonte não validada: " + motivo)
        except Exception:
            pass
        return False

    def _validar_e_aplicar(self, uid: str, pauta: dict) -> bool:
        try:
            from ururau.coleta.fonte_validada import construir_fonte_validada, aplicar_fonte_validada_na_pauta
            from ururau.editorial.integridade_fonte_v47_26 import validar_fonte_estrita

            texto = _texto_para_validar(pauta)
            ok_estrita, motivo_estrita = validar_fonte_estrita(pauta, texto)
            if not ok_estrita:
                return _bloquear(self, uid, pauta, motivo_estrita)

            metodo = pauta.get("extraction_method", "") or ""
            score = int(pauta.get("source_sufficiency_score") or pauta.get("score_fonte") or 0)
            # Após validação estrita, o método passa a ter status de fonte validada,
            # mesmo que tenha vindo por fallback/rss, desde que o conteúdo pertença à pauta.
            fonte = construir_fonte_validada(
                pauta,
                texto,
                metodo=metodo,
                status="ok_integridade_v47_26",
                score=score,
            )
            if not fonte.validada:
                return _bloquear(self, uid, pauta, fonte.motivo)
            aplicar_fonte_validada_na_pauta(pauta, fonte)
            self._log(uid, "fonte_validada_v47_29", f"OK {fonte.chars_uteis} chars | metodo={fonte.metodo} | hash={fonte.hash_fonte}", sucesso=True)
            return True
        except Exception as e:
            return _bloquear(self, uid, pauta, "erro no gate FonteValidada: " + str(e))

    def etapa_coleta_texto_v47_29(self, uid: str, pauta: dict, modo: str = "panel"):
        ok = old_coleta(self, uid, pauta, modo)
        if not ok:
            return ok
        if not _validar_e_aplicar(self, uid, pauta):
            return False
        return True

    def etapa_redacao_v47_29(self, uid: str, pauta: dict):
        fv = pauta.get("fonte_validada_v47_29") or {}
        if not isinstance(fv, dict) or not fv.get("validada"):
            if not _validar_e_aplicar(self, uid, pauta):
                return None
        return old_redacao(self, uid, pauta)

    WorkflowPublicacao.etapa_coleta_texto = etapa_coleta_texto_v47_29
    WorkflowPublicacao.etapa_redacao = etapa_redacao_v47_29
    WorkflowPublicacao._v4729_fonte_validada_instalado = True
    return WorkflowPublicacao
