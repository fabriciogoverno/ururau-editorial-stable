"""
Patch v132 - organização de configuração, atualização útil, preview -> copydesk e ajustes de fluxo.

Este patch evita mexer profundamente no motor de coleta. Ele reorganiza a UI por composição,
reaproveitando os métodos de leitura/salvamento já existentes para reduzir risco de regressão.
"""
from __future__ import annotations

import os
import json
from pathlib import Path


def aplicar_patch_v132(g: dict) -> None:
    tk = g.get("tk")
    ttk = g.get("ttk")
    messagebox = g.get("messagebox")
    if not tk or not ttk:
        return

    COR_PAINEL = g.get("COR_PAINEL", "#1a1a2e")
    COR_FUNDO = g.get("COR_FUNDO", "#0f0f1a")
    COR_TEXTO = g.get("COR_TEXTO", "#e2e8f0")
    COR_CINZA = g.get("COR_CINZA", "#64748b")
    COR_VERDE = g.get("COR_VERDE", "#22c55e")
    COR_DESTAQUE = g.get("COR_DESTAQUE", "#7c3aed")
    COR_AMARELO = g.get("COR_AMARELO", "#eab308")
    FONTE_NORMAL = g.get("FONTE_NORMAL", ("Helvetica", 10))
    FONTE_PEQUENA = g.get("FONTE_PEQUENA", ("Helvetica", 9))

    _ConfigWidget = g.get("_ConfigWidget")
    JanelaConfiguracoes = g.get("JanelaConfiguracoes")
    PainelUrurau = g.get("PainelUrurau")

    def _criar_aba_fontes_links_v132(self, nb):
        outer = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(outer, text="Fontes / Links")
        tk.Label(
            outer,
            text="Fontes e links de coleta. RSS, XML/Sitemap, Especiais e Regionais ficam juntos aqui, separados por subtítulos.",
            bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_NORMAL,
            wraplength=900, justify="left",
        ).pack(fill="x", padx=8, pady=(8, 4), anchor="w")
        sub = ttk.Notebook(outer)
        sub.pack(fill="both", expand=True, padx=8, pady=8)
        self._fontes_links_nb_v132 = sub
        self._criar_aba_rss(sub)
        self._criar_aba_xml_sitemap(sub)
        self._criar_aba_fontes_especiais_v129(sub)
        if hasattr(self, "_criar_aba_regionais_v1305"):
            self._criar_aba_regionais_v1305(sub)

    def _build_config_widget_v132(self):
        tb = tk.Frame(self, bg=COR_PAINEL, height=44)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="⚙ Configurações", bg=COR_PAINEL, fg=COR_DESTAQUE,
                 font=("Helvetica", 12, "bold")).pack(side="left", padx=10)
        tk.Button(tb, text="Salvar e Aplicar", command=self._salvar,
                  bg=COR_VERDE, fg="white", relief="flat",
                  padx=10, pady=3, cursor="hand2",
                  font=("Helvetica", 9, "bold")).pack(side="right", padx=6, pady=6)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=4)
        self._nb = nb
        self._criar_aba_fontes_links_v132(nb)
        self._criar_aba_termos(nb)
        self._criar_aba_params(nb)
        self._criar_aba_creds(nb)
        self._criar_aba_diagnostico_v127(nb)
        if hasattr(self, "_criar_aba_diagnostico_fontes_v130"):
            self._criar_aba_diagnostico_fontes_v130(nb)

    def _build_janela_config_v132(self):
        tb = tk.Frame(self, bg=COR_PAINEL, height=48)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="Configurações", bg=COR_PAINEL, fg=COR_DESTAQUE,
                 font=("Helvetica", 13, "bold")).pack(side="left", padx=12)
        tk.Button(tb, text="Salvar e Aplicar", command=self._salvar,
                  bg=COR_VERDE, fg="white", relief="flat",
                  padx=12, pady=4, cursor="hand2",
                  font=("Helvetica", 10, "bold")).pack(side="right", padx=8, pady=8)
        tk.Button(tb, text="Fechar sem salvar", command=self.destroy,
                  bg=COR_CINZA, fg="white", relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  font=("Helvetica", 10, "bold")).pack(side="right", padx=4, pady=8)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._nb = nb
        self._criar_aba_fontes_links_v132(nb)
        self._criar_aba_termos(nb)
        self._criar_aba_params(nb)
        self._criar_aba_creds(nb)
        if hasattr(self, "_criar_aba_diagnostico_v127"):
            self._criar_aba_diagnostico_v127(nb)
        if hasattr(self, "_criar_aba_diagnostico_fontes_v130"):
            self._criar_aba_diagnostico_fontes_v130(nb)
        if hasattr(self, "_criar_aba_producao"):
            self._criar_aba_producao(nb)
        if hasattr(self, "_criar_aba_estilo"):
            self._criar_aba_estilo(nb)
        tk.Label(self,
                 text="Salvar e Aplicar recarrega configurações, limpa caches operacionais e atualiza a fila sem reiniciar.",
                 bg=COR_FUNDO, fg=COR_AMARELO, font=FONTE_PEQUENA,
                 wraplength=900).pack(pady=4, padx=8)

    def _wrap_salvar(cls):
        old = getattr(cls, "_salvar", None)
        if not old or getattr(cls, "_v132_salvar_wrap", False):
            return
        def _salvar_v132(self, *a, **kw):
            ret = old(self, *a, **kw)
            try:
                owner = getattr(self, "_owner", None) or getattr(self, "master", None)
                if owner and hasattr(owner, "_acao_atualizar_geral_v132"):
                    owner.after(100, owner._acao_atualizar_geral_v132)
            except Exception as e:
                print(f"[v132][CONFIG] pós-salvar não recarregou: {e}")
            return ret
        setattr(cls, "_salvar", _salvar_v132)
        setattr(cls, "_v132_salvar_wrap", True)

    if _ConfigWidget:
        setattr(_ConfigWidget, "_criar_aba_fontes_links_v132", _criar_aba_fontes_links_v132)
        setattr(_ConfigWidget, "_build", _build_config_widget_v132)
        _wrap_salvar(_ConfigWidget)
    if JanelaConfiguracoes:
        setattr(JanelaConfiguracoes, "_criar_aba_fontes_links_v132", _criar_aba_fontes_links_v132)
        setattr(JanelaConfiguracoes, "_build", _build_janela_config_v132)
        _wrap_salvar(JanelaConfiguracoes)

    if PainelUrurau:
        def _acao_atualizar_geral_v132(self):
            """F5 útil: recarrega configurações, invalida caches leves e redesenha a fila."""
            try:
                self._set_status("Atualizando: recarregando configurações, limpando caches leves e recarregando fila...")
            except Exception:
                pass
            try:
                # settings.py
                from ururau.config import settings as _s
                if hasattr(_s, "recarregar"):
                    _s.recarregar()
            except Exception as e:
                print(f"[v132][F5] settings não recarregou: {e}")
            try:
                # caches visuais/seleção e cache de prioridades locais
                if hasattr(self, "_fila"):
                    try: self._fila.limpar_selecao()
                    except Exception: pass
                for attr in ("_uids_cache", "_cards_cache", "_prioridade_cache", "_cache_status_filtro"):
                    obj = getattr(self, attr, None)
                    if hasattr(obj, "clear"):
                        obj.clear()
            except Exception:
                pass
            try:
                # Recarrega a aba Config visível, se existir, sem destruir a UI.
                cfg = getattr(self, "_config_widget", None)
                if cfg and hasattr(cfg, "_carregar_valores"):
                    # Evita duplicar texto se o widget já estava preenchido.
                    for nm in ("_txt_rss", "_txt_xml", "_txt_especiais_v129", "_txt_regionais_v1305", "_txt_termos"):
                        w = getattr(cfg, nm, None)
                        if w:
                            try: w.delete("1.0", "end")
                            except Exception: pass
                    cfg._carregar_valores()
            except Exception as e:
                print(f"[v132][F5] config UI não recarregou: {e}")
            try:
                self._carregar_pautas()
            except Exception as e:
                print(f"[v132][F5] fila não recarregou: {e}")
            try:
                self._set_status("Atualização concluída. Novas fontes/termos já valem para a próxima coleta.")
            except Exception:
                pass

        setattr(PainelUrurau, "_acao_atualizar_geral_v132", _acao_atualizar_geral_v132)

        # Patches leves de inicialização: F5 aponta para a atualização útil e console inicia oculto.
        old_construir_interface = getattr(PainelUrurau, "_construir_interface", None)
        if old_construir_interface and not getattr(PainelUrurau, "_v132_interface_wrap", False):
            def _construir_interface_v132(self, *a, **kw):
                ret = old_construir_interface(self, *a, **kw)
                try:
                    self.bind("<F5>", lambda _=None: self._acao_atualizar_geral_v132())
                except Exception:
                    pass
                # v132: console interno existe, mas não abre por padrão. O usuário abre pelo botão Console.
                try:
                    if getattr(self, "_console_visible", False):
                        self._toggle_console()
                except Exception:
                    pass
                return ret
            setattr(PainelUrurau, "_construir_interface", _construir_interface_v132)
            setattr(PainelUrurau, "_v132_interface_wrap", True)

        # Patches no preview: botão CopyDesk que salva o texto do preview e usa também a fonte original.
        def _preview_copydesk_v132(self):
            try:
                if not getattr(self, "_prev_pauta", None):
                    messagebox.showwarning("CopyDesk", "Abra uma matéria no Preview primeiro.")
                    return
                m = dict(getattr(self, "_prev_md", {}) or {})
                for k, v in getattr(self, "_prev_mvars", {}).items():
                    m[k] = v.get().strip()
                if hasattr(self, "_prev_txt"):
                    m["conteudo"] = self._prev_txt.get("1.0", "end-1c").strip()
                    m["corpo_materia"] = m["conteudo"]
                p = self._prev_pauta
                # Injeta a fonte original no pacote, para o CopyDesk comparar fonte + texto gerado.
                fonte = (
                    p.get("cleaned_source_text") or p.get("leitura_fonte_texto") or p.get("texto_fonte") or
                    p.get("dossie") or p.get("_fonte_aba_texto") or ""
                )
                if fonte:
                    for k in ("cleaned_source_text", "texto_fonte", "dossie", "_fonte_aba_texto"):
                        m[k] = fonte
                self._prev_md = m
                self._ao_salvar_preview(p, m)
                self._pauta_sel = p
                self.after(150, self._acao_copydesk)
            except Exception as e:
                messagebox.showerror("CopyDesk", f"Falha ao enviar preview ao CopyDesk: {e}")
        setattr(PainelUrurau, "_preview_copydesk_v132", _preview_copydesk_v132)

        # Botão Imagem: quando mantido por versões antigas, deixa claro que a busca externa não é automática.
        old_buscar_img = getattr(PainelUrurau, "_acao_buscar_imagem", None)
        def _acao_buscar_imagem_v132(self):
            messagebox.showinfo(
                "Imagem",
                "A busca automática aberta por internet foi desativada nesta versão para evitar uso de imagem com direito autoral sem validação.\n\n"
                "Use o Preview para conferir a imagem da fonte ou escolha manualmente uma imagem licenciada/autorizada."
            )
        if old_buscar_img:
            setattr(PainelUrurau, "_acao_buscar_imagem", _acao_buscar_imagem_v132)

    print("[v132] Organização, F5 útil, preview→CopyDesk e ajustes de fluxo aplicados.")
