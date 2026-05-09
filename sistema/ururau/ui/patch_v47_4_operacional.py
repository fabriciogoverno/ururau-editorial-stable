"""Patch v47.4: F5 real, mensagens operacionais, fila cronológica e diagnóstico aplicado."""
from __future__ import annotations

def aplicar_patch_v47_4(g):
    PainelUrurau = g.get("PainelUrurau")
    if PainelUrurau is None:
        return
    old_build = getattr(PainelUrurau, "_construir_interface", None)
    def _acao_atualizar_geral_v47_4(self):
        try: self._set_status("Atualizando: configurações, fontes aplicadas, fila cronológica e diagnóstico...")
        except Exception: pass
        try:
            after_id = getattr(self, "_v1298_refresh_after_id", None)
            if after_id is not None: self.after_cancel(after_id)
            self._v1298_refresh_after_id = None; self._v1298_last_refresh = 0.0
        except Exception: pass
        for name in ("_recarregar_fontes_links_v1324", "_carregar_configuracoes", "_carregar_configuracoes_producao"):
            try:
                fn=getattr(self,name,None)
                if callable(fn): fn()
            except Exception as e: print(f"[v47.4][F5] aviso ao executar {name}: {e}")
        try:
            from ururau.coleta.leitura_fonte import limpar_cache_leitura
            limpar_cache_leitura()
        except Exception: pass
        try:
            from ururau.coleta import fonte_extractor_v104
            cache=getattr(fonte_extractor_v104,"_CACHE",None)
            if isinstance(cache,dict): cache.clear()
        except Exception: pass
        try: self._carregar_pautas(forcar=True)
        except Exception as e:
            try: self._set_status(f"Erro ao atualizar F5: {e}")
            except Exception: pass
            return
        try: self.after(800, lambda: self._set_status("Atualização concluída: fontes aplicadas recarregadas; fila cronológica; texto/imagem em segundo plano."))
        except Exception: pass
    def _publicacao_msg_manual(self, destino="rascunho"):
        if destino == "direto":
            return "Publicação ao vivo é manual e exige aprovação editorial: fonte completa, sem termo de IA, imagem/legenda, título, subtítulo, tags e risco jurídico checados."
        return "Salvar como rascunho é o modo seguro: a matéria fica no CMS para revisão humana antes de ir ao ar."
    PainelUrurau._acao_atualizar_geral_v47_4 = _acao_atualizar_geral_v47_4
    PainelUrurau._acao_atualizar_geral_v132 = _acao_atualizar_geral_v47_4
    PainelUrurau._publicacao_msg_manual_v47_4 = _publicacao_msg_manual
    if callable(old_build):
        def _build_wrap(self,*a,**kw):
            r=old_build(self,*a,**kw)
            try: self.bind("<F5>", lambda _e: self._acao_atualizar_geral_v47_4())
            except Exception: pass
            return r
        PainelUrurau._construir_interface = _build_wrap
