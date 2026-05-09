# diagnostico_fontes_tab_v130.py
# Aba interna Config > Diagnóstico de Fonte, sem alterar o visual geral do painel.

from __future__ import annotations

import json
import threading
import time
from pathlib import Path


def aplicar_patch_v130(g: dict) -> None:
    tk = g.get("tk")
    ttk = g.get("ttk")
    messagebox = g.get("messagebox")
    filedialog = g.get("filedialog")
    scrolledtext = g.get("scrolledtext")
    COR_PAINEL = g.get("COR_PAINEL", "#1a1a2e")
    COR_TEXTO = g.get("COR_TEXTO", "#e2e8f0")
    COR_CINZA = g.get("COR_CINZA", "#64748b")
    COR_AZUL = g.get("COR_AZUL", "#0ea5e9")
    COR_VERDE = g.get("COR_VERDE", "#22c55e")
    COR_AMARELO = g.get("COR_AMARELO", "#eab308")
    COR_VERMELHO = g.get("COR_VERMELHO", "#ef4444")
    FONTE_NORMAL = g.get("FONTE_NORMAL", ("Helvetica", 10))
    FONTE_PEQUENA = g.get("FONTE_PEQUENA", ("Helvetica", 9))

    if not tk or not ttk:
        return

    def _criar_aba_diagnostico_fontes_v130(self, nb):
        f = tk.Frame(nb, bg=COR_PAINEL)
        nb.add(f, text="Diagnóstico de Fonte")
        tk.Label(
            f,
            text="Diagnóstico de fonte: cole domínio ou URL. O sistema faz diagnóstico completo, escolhe a melhor estratégia, testa, aplica com backup e informa se a fonte passará a ser usada na próxima coleta.",
            bg=COR_PAINEL,
            fg=COR_TEXTO,
            font=FONTE_NORMAL,
            wraplength=950,
            justify="left",
        ).pack(padx=8, pady=(8, 4), anchor="w")

        row = tk.Frame(f, bg=COR_PAINEL)
        row.pack(fill="x", padx=8, pady=4)
        tk.Label(row, text="URL/domínio:", bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_PEQUENA).pack(side="left")
        self._v130_diag_url = tk.StringVar(value="")
        tk.Entry(row, textvariable=self._v130_diag_url, bg="#16213e", fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat", font=("Courier New", 9)).pack(side="left", fill="x", expand=True, padx=6)
        tk.Label(row, text="Nome opcional:", bg=COR_PAINEL, fg=COR_TEXTO, font=FONTE_PEQUENA).pack(side="left", padx=(8, 0))
        self._v130_diag_nome = tk.StringVar(value="")
        tk.Entry(row, textvariable=self._v130_diag_nome, bg="#16213e", fg=COR_TEXTO, insertbackground=COR_TEXTO, relief="flat", font=("Courier New", 9), width=22).pack(side="left", padx=6)

        bf = tk.Frame(f, bg=COR_PAINEL)
        bf.pack(fill="x", padx=8, pady=4)
        tk.Button(bf, text="Diagnosticar, aplicar e testar", command=lambda: _diagnosticar_aplicar(self), bg=COR_VERDE, fg="white", relief="flat", padx=10, pady=3, cursor="hand2", font=(FONTE_PEQUENA[0], FONTE_PEQUENA[1], "bold") if isinstance(FONTE_PEQUENA, tuple) else FONTE_PEQUENA).pack(side="left", padx=(0, 6))
        tk.Button(bf, text="Exportar TXT", command=lambda: _exportar_diag(self), bg=COR_AMARELO, fg="#111827", relief="flat", padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left", padx=(0, 6))
        tk.Button(bf, text="Limpar", command=lambda: _limpar_diag(self), bg=COR_VERMELHO, fg="white", relief="flat", padx=8, pady=2, cursor="hand2", font=FONTE_PEQUENA).pack(side="left")

        self._v130_diag_status = tk.StringVar(value="Pronto.")
        tk.Label(f, textvariable=self._v130_diag_status, bg=COR_PAINEL, fg=COR_CINZA, font=FONTE_PEQUENA, anchor="w").pack(fill="x", padx=8, pady=(2, 4))
        self._txt_diag_fonte_v130 = scrolledtext.ScrolledText(f, bg="#16213e", fg=COR_TEXTO, insertbackground=COR_TEXTO, font=("Courier New", 9), wrap="word", relief="flat", padx=8, pady=8)
        self._txt_diag_fonte_v130.pack(fill="both", expand=True, padx=8, pady=8)
        self._v130_diag_result = None

    def _set_text(self, texto: str):
        box = getattr(self, "_txt_diag_fonte_v130", None)
        if not box:
            return
        box.config(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", texto or "")
        box.see("1.0")
        box.config(state="normal")

    def _append_text(self, texto: str):
        box = getattr(self, "_txt_diag_fonte_v130", None)
        if not box:
            return
        box.config(state="normal")
        box.insert("end", (texto or "") + "\n")
        box.see("end")
        box.config(state="normal")

    def _recarregar_fontes_links_v1324(self):
        """Atualiza a aba visual Fontes / Links após aplicar uma fonte.

        Antes o perfil era salvo em perfis_fontes_v131.json e, em alguns casos,
        também em regionais/RSS, mas a tela ficava antiga até reiniciar ou apertar F5.
        Isso dava a impressão de que o link não tinha sido aplicado.
        """
        def _limpa(w):
            try:
                w.delete("1.0", "end")
            except Exception:
                pass

        # RSS
        try:
            if hasattr(self, "_txt_rss"):
                from ururau.ui.painel import _carregar_fontes_rss
                fontes = _carregar_fontes_rss()
                _limpa(self._txt_rss)
                self._txt_rss.insert("1.0", "\n".join(f.get("url", "") for f in fontes if f.get("url")))
        except Exception as e:
            print(f"[v132.4][DIAG] não recarregou RSS visual: {e}")

        # XML/Sitemap
        try:
            if hasattr(self, "_txt_xml"):
                p_xml = Path("fontes_xml_sitemap_vfinal.txt")
                if not p_xml.exists():
                    p_xml = Path(__file__).resolve().parents[2] / "fontes_xml_sitemap_vfinal.txt"
                _limpa(self._txt_xml)
                if p_xml.exists():
                    self._txt_xml.insert("1.0", p_xml.read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            print(f"[v132.4][DIAG] não recarregou XML visual: {e}")

        # Especiais
        try:
            if hasattr(self, "_txt_especiais_v129"):
                from ururau.ui.painel import _carregar_fontes_especiais_v129_texto
                _limpa(self._txt_especiais_v129)
                self._txt_especiais_v129.insert("1.0", _carregar_fontes_especiais_v129_texto())
        except Exception as e:
            print(f"[v132.4][DIAG] não recarregou Especiais visual: {e}")

        # Regionais
        try:
            if hasattr(self, "_txt_regionais_v1305"):
                from ururau.ui.painel import _carregar_regionais_v1305_texto
                _limpa(self._txt_regionais_v1305)
                self._txt_regionais_v1305.insert("1.0", _carregar_regionais_v1305_texto())
        except Exception as e:
            print(f"[v132.4][DIAG] não recarregou Regionais visual: {e}")

        # Recarrega cache operacional do painel, se a Config estiver embutida nele.
        try:
            owner = getattr(self, "_owner", None) or getattr(self, "master", None)
            if owner and hasattr(owner, "_acao_atualizar_geral_v132"):
                owner.after(200, owner._acao_atualizar_geral_v132)
        except Exception:
            pass

    def _rodar_diag(self, completo: bool = True):
        url = (getattr(self, "_v130_diag_url").get() if hasattr(self, "_v130_diag_url") else "").strip()
        if not url:
            messagebox.showwarning("Diagnóstico de Fonte", "Informe uma URL ou domínio.")
            return
        _set_text(self, "Iniciando diagnóstico...\n")
        self._v130_diag_status.set("Rodando diagnóstico. Aguarde...")

        def worker():
            try:
                from ururau.coleta.diagnostico_fontes_v130 import diagnostico_completo, diagnostico_rapido, format_report
                logs = []
                def log(msg):
                    logs.append(str(msg))
                    try:
                        self.after(0, lambda m=str(msg): _append_text(self, m))
                    except Exception:
                        pass
                res = diagnostico_completo(url, log_callback=log) if completo else diagnostico_rapido(url, log_callback=log)
                rel = format_report(res)
                self._v130_diag_result = res
                try:
                    self.after(0, lambda: _set_text(self, rel))
                    self.after(0, lambda: self._v130_diag_status.set("Diagnóstico concluído. Revise a sugestão antes de aplicar."))
                except Exception:
                    pass
            except Exception as e:
                try:
                    self.after(0, lambda: self._v130_diag_status.set("Erro no diagnóstico."))
                    self.after(0, lambda: _append_text(self, f"ERRO: {e}"))
                except Exception:
                    pass
        threading.Thread(target=worker, daemon=True).start()

    def _diagnosticar_aplicar(self):
        """Fluxo único v132: diagnóstico completo -> aplicação -> teste -> relatório visual.

        Corrige o bug da v132 em que o botão verde chamava uma função inexistente.
        Esta função não depende do usuário clicar antes em diagnóstico rápido/completo.
        """
        url = (getattr(self, "_v130_diag_url").get() if hasattr(self, "_v130_diag_url") else "").strip()
        if not url:
            messagebox.showwarning("Diagnóstico de Fonte", "Informe uma URL ou domínio.")
            return
        nome_pref = (getattr(self, "_v130_diag_nome").get() if hasattr(self, "_v130_diag_nome") else "").strip()
        _set_text(self, "INICIANDO DIAGNÓSTICO COMPLETO + APLICAÇÃO + TESTE\n" + "=" * 70 + f"\nURL/domínio: {url}\n\n")
        try:
            self._v130_diag_status.set("Diagnosticando, aplicando e testando. Aguarde...")
        except Exception:
            pass

        def ui_set(texto: str):
            try:
                self.after(0, lambda t=texto: _set_text(self, t))
            except Exception:
                _set_text(self, texto)

        def ui_append(texto: str):
            try:
                self.after(0, lambda t=texto: _append_text(self, t))
            except Exception:
                _append_text(self, texto)

        def ui_status(texto: str):
            try:
                self.after(0, lambda t=texto: self._v130_diag_status.set(t))
            except Exception:
                try:
                    self._v130_diag_status.set(texto)
                except Exception:
                    pass

        def worker():
            try:
                import traceback
                from ururau.coleta.diagnostico_fontes_v130 import diagnostico_completo, format_report, salvar_relatorio
                from ururau.coleta.aplicador_diagnostico_v130 import (
                    aplicar_sugestao_diagnostico_v130,
                    formatar_relatorio_aplicacao_v130,
                    resumo_resultado_aplicacao_v131,
                    salvar_relatorio_aplicacao_v131,
                )

                def log(msg):
                    ui_append(str(msg))

                ui_append("[1/4] Rodando diagnóstico completo...")
                res = diagnostico_completo(url, log_callback=log)
                self._v130_diag_result = res
                rel_diag = format_report(res)

                ui_append("\n[2/4] Diagnóstico concluído. Gerando perfil operacional e aplicando com backup...")
                info = aplicar_sugestao_diagnostico_v130(res, nome_preferido=nome_pref)
                rel_aplicacao = formatar_relatorio_aplicacao_v130(info)
                resumo_final = resumo_resultado_aplicacao_v131(info)

                ui_append("\n[3/4] Salvando relatórios TXT/JSON...")
                try:
                    paths_diag = salvar_relatorio(res)
                except Exception as e:
                    paths_diag = {"erro": str(e)}
                try:
                    paths_app = salvar_relatorio_aplicacao_v131(info, rel_aplicacao)
                except Exception as e:
                    paths_app = {"erro": str(e)}

                aplicado = bool((info.get("v131") or {}).get("aplicado"))
                teste = ((info.get("v131") or {}).get("teste") or {})
                qtd = teste.get("qtd", 0)
                status = "APLICADO E FUNCIONAL" if aplicado else "NÃO APLICADO"

                texto = []
                texto.append("RESULTADO DO DIAGNOSTICAR, APLICAR E TESTAR v132.1")
                texto.append("=" * 70)
                texto.append(resumo_final.strip())
                texto.append("")
                texto.append(f"STATUS FINAL: {status}")
                texto.append(f"Pautas geradas no teste: {qtd}")
                texto.append(f"Será usada na próxima coleta geral: {'SIM' if aplicado else 'NÃO'}")
                texto.append("")
                texto.append("ARQUIVOS GERADOS")
                texto.append("-" * 70)
                if paths_diag.get("txt"):
                    texto.append(f"Diagnóstico TXT: {paths_diag.get('txt')}")
                if paths_diag.get("json"):
                    texto.append(f"Diagnóstico JSON: {paths_diag.get('json')}")
                if paths_diag.get("erro"):
                    texto.append(f"Diagnóstico: erro ao salvar relatório: {paths_diag.get('erro')}")
                if paths_app.get("txt"):
                    texto.append(f"Aplicação TXT: {paths_app.get('txt')}")
                if paths_app.get("json"):
                    texto.append(f"Aplicação JSON: {paths_app.get('json')}")
                if paths_app.get("erro"):
                    texto.append(f"Aplicação: erro ao salvar relatório: {paths_app.get('erro')}")
                texto.append("")
                texto.append("RELATÓRIO TÉCNICO DA APLICAÇÃO")
                texto.append("=" * 70)
                texto.append(rel_aplicacao.strip())
                texto.append("")
                texto.append("RELATÓRIO TÉCNICO DO DIAGNÓSTICO")
                texto.append("=" * 70)
                texto.append(rel_diag.strip())

                final_text = "\n".join(texto)
                ui_set(final_text)
                ui_status(f"{status} | pautas no teste: {qtd}")
                if aplicado:
                    try:
                        self.after(0, lambda: _recarregar_fontes_links_v1324(self))
                    except Exception:
                        pass

                def show_final():
                    msg = resumo_final
                    if len(msg) > 1800:
                        msg = msg[:1800] + "\n...\nRelatório completo exibido na tela e salvo em arquivo."
                    if aplicado:
                        messagebox.showinfo("Aplicado e testado", msg)
                    else:
                        messagebox.showwarning("Não aplicado", msg)
                try:
                    self.after(0, show_final)
                except Exception:
                    pass

            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                ui_status("Erro ao diagnosticar/aplicar/testar.")
                ui_set("ERRO NO DIAGNOSTICAR, APLICAR E TESTAR\n" + "=" * 70 + f"\n{e}\n\n{tb}")
                try:
                    self.after(0, lambda err=str(e): messagebox.showerror("Erro ao diagnosticar/aplicar/testar", err))
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _aplicar_sugestao(self):
        res = getattr(self, "_v130_diag_result", None)
        if not res:
            messagebox.showwarning("Diagnóstico de Fonte", "Rode o diagnóstico antes de aplicar.")
            return
        sol = res.get("solucao") or {}
        cfg = sol.get("config_sugerido") or {}
        resumo = [
            f"Fonte: {getattr(self, '_v130_diag_nome').get().strip() or res.get('name')}",
            f"Estratégia: {sol.get('estrategia_principal')}",
            "",
            "Feeds sugeridos:",
        ]
        resumo += [f"- {u}" for u in (sol.get("feeds") or [])[:8]] or ["- nenhum"]
        if sol.get("sitemaps"):
            resumo += ["", "Sitemaps:"] + [f"- {u}" for u in sol.get("sitemaps")[:8]]
        resumo += ["", "A aplicação é operacional: faz backup, gera perfil técnico, testa imediatamente e só salva como AutoFonte v131.3 se produzir pauta real."]
        ok = messagebox.askyesno("Aplicar sugestão v130", "\n".join(resumo) + "\n\nAplicar agora?")
        if not ok:
            return
        try:
            from ururau.coleta.aplicador_diagnostico_v130 import (
                aplicar_sugestao_diagnostico_v130,
                formatar_relatorio_aplicacao_v130,
                resumo_resultado_aplicacao_v131,
                salvar_relatorio_aplicacao_v131,
            )
            info = aplicar_sugestao_diagnostico_v130(res, nome_preferido=getattr(self, "_v130_diag_nome").get().strip())
            rel = formatar_relatorio_aplicacao_v130(info)
            resumo_final = resumo_resultado_aplicacao_v131(info)
            paths = salvar_relatorio_aplicacao_v131(info, rel)

            # Mostra o resultado final no topo da área de texto. Isso evita o erro anterior:
            # o usuário precisava procurar no fim de um relatório longo para saber se aplicou.
            resultado_visual = resumo_final + "\n\n" + rel
            if paths.get("txt") or paths.get("json"):
                resultado_visual += "\n\nRELATÓRIO SALVO\n" + "-" * 70
                if paths.get("txt"):
                    resultado_visual += f"\nTXT: {paths.get('txt')}"
                if paths.get("json"):
                    resultado_visual += f"\nJSON: {paths.get('json')}"
            _set_text(self, resultado_visual)

            aplicado = bool((info.get("v131") or {}).get("aplicado"))
            teste = ((info.get("v131") or {}).get("teste") or {})
            qtd = teste.get("qtd", 0)
            status = "APLICADO E FUNCIONAL" if aplicado else "NÃO APLICADO"
            self._v130_diag_status.set(f"{status} | pautas no teste: {qtd} | veja o relatório exibido na tela.")
            if aplicado:
                try:
                    _recarregar_fontes_links_v1324(self)
                except Exception:
                    pass

            # Atualiza campos visíveis da configuração, se existirem.
            try:
                if hasattr(self, "_txt_rss"):
                    from ururau.ui.painel import _carregar_fontes_rss
                    fontes = _carregar_fontes_rss()
                    self._txt_rss.delete("1.0", "end")
                    self._txt_rss.insert("1.0", "\n".join(f.get("url", "") for f in fontes))
            except Exception:
                pass
            try:
                if hasattr(self, "_txt_xml"):
                    p = Path("fontes_xml_sitemap_vfinal.txt")
                    if p.exists():
                        self._txt_xml.delete("1.0", "end")
                        self._txt_xml.insert("1.0", p.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass

            msg = resumo_final
            if len(msg) > 1800:
                msg = msg[:1800] + "\n...\nRelatório completo exibido na tela e salvo em arquivo."
            if aplicado:
                messagebox.showinfo("Aplicado e testado", msg)
            else:
                messagebox.showwarning("Não aplicado", msg)
        except Exception as e:
            self._v130_diag_status.set("Erro ao aplicar/testar perfil.")
            messagebox.showerror("Erro ao aplicar", str(e))

    def _exportar_diag(self):
        res = getattr(self, "_v130_diag_result", None)
        if not res:
            messagebox.showwarning("Diagnóstico de Fonte", "Não há diagnóstico para exportar.")
            return
        try:
            from ururau.coleta.diagnostico_fontes_v130 import salvar_relatorio
            paths = salvar_relatorio(res)
            messagebox.showinfo("Exportado", f"TXT: {paths.get('txt')}\nJSON técnico: {paths.get('json')}")
            self._v130_diag_status.set(f"Relatórios exportados em {Path(paths.get('txt', '')).parent}")
        except Exception as e:
            messagebox.showerror("Erro ao exportar", str(e))

    def _limpar_diag(self):
        self._v130_diag_result = None
        self._v130_diag_status.set("Pronto.")
        _set_text(self, "")

    # Anexa método e envolve _build das duas janelas de configuração.
    for cls_name in ("_ConfigWidget", "JanelaConfiguracoes"):
        cls = g.get(cls_name)
        if not cls or getattr(cls, "_v130_diag_patch_aplicado", False):
            continue
        setattr(cls, "_criar_aba_diagnostico_fontes_v130", _criar_aba_diagnostico_fontes_v130)
        old_build = getattr(cls, "_build")

        def make_build(old):
            def _build_v130(self, *a, **kw):
                old(self, *a, **kw)
                try:
                    nb = getattr(self, "_nb", None)
                    if nb and not getattr(self, "_v130_diag_tab_criada", False):
                        self._criar_aba_diagnostico_fontes_v130(nb)
                        self._v130_diag_tab_criada = True
                except Exception as e:
                    print(f"[v130][DIAGNOSTICO_FONTE] aba não criada: {e}")
            return _build_v130

        setattr(cls, "_build", make_build(old_build))
        setattr(cls, "_v130_diag_patch_aplicado", True)

