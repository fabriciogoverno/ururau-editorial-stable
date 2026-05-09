"""
ururau/ui/painel_v111_tab.py

Aba opcional para teste manual da coleta Google News integrada na v110 teste.
Pode ser importada pelo painel sem interferir no fluxo existente.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any


class AbaGoogleNewsV111(tk.Frame):
    """Painel simples para busca manual por termo livre ou grupo temático."""

    GRUPOS = [
        "campos_local",
        "norte_fluminense",
        "porto_do_acu",
        "rj_politica",
        "rj_policia",
        "governo_rj",
        "alerj",
        "deputados_rj",
        "pre_candidatos_governo_rj",
        "servico_brasil",
        "alto_trafego_brasil",
        "alertas_globais",
        "utilidade_publica_rj",
        "transparencia_e_investigacao",
    ]

    def __init__(self, master: Any, db: Any = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(master, *args, **kwargs)
        self.db = db
        self.resultados: list[dict] = []
        self._build()

    def _build(self) -> None:
        topo = tk.Frame(self)
        topo.pack(fill="x", padx=8, pady=8)

        tk.Label(topo, text="Google News v111/v110 teste").pack(side="left", padx=(0, 8))

        self.var_modo = tk.StringVar(value="termo_livre")
        ttk.Combobox(topo, textvariable=self.var_modo, values=["termo_livre", "grupo", "termos_config"], width=16, state="readonly").pack(side="left", padx=4)

        self.var_termo = tk.StringVar(value="Campos dos Goytacazes")
        tk.Entry(topo, textvariable=self.var_termo, width=32).pack(side="left", padx=4)

        self.var_grupo = tk.StringVar(value="campos_local")
        ttk.Combobox(topo, textvariable=self.var_grupo, values=self.GRUPOS, width=26, state="readonly").pack(side="left", padx=4)

        tk.Button(topo, text="Buscar", command=self._buscar).pack(side="left", padx=4)

        cols = ("score", "canal", "titulo", "fonte", "chars")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for col, titulo, largura in [
            ("score", "Score", 60),
            ("canal", "Canal", 100),
            ("titulo", "Título", 520),
            ("fonte", "Fonte", 160),
            ("chars", "Chars", 80),
        ]:
            self.tree.heading(col, text=titulo)
            self.tree.column(col, width=largura, stretch=(col == "titulo"))
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        botoes = tk.Frame(self)
        botoes.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(botoes, text="Adicionar selecionada à fila", command=self._adicionar_selecionada).pack(side="left")
        self.var_status = tk.StringVar(value="Pronto.")
        tk.Label(botoes, textvariable=self.var_status).pack(side="left", padx=12)

    def _buscar(self) -> None:
        self.var_status.set("Buscando...")
        threading.Thread(target=self._buscar_thread, daemon=True).start()

    def _buscar_thread(self) -> None:
        try:
            from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111_sync
            modo = self.var_modo.get()
            termo = self.var_termo.get().strip()
            grupo = self.var_grupo.get().strip()
            pautas = coletar_pautas_gnews_v111_sync(modo=modo, termo=termo, grupo=grupo)
            self.resultados = pautas
            self.after(0, self._render_resultados)
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Google News v111", str(exc), parent=self))

    def _render_resultados(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        for idx, p in enumerate(self.resultados):
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    p.get("score", ""),
                    p.get("canal_sugerido") or p.get("canal_forcado", ""),
                    p.get("titulo") or p.get("titulo_origem", ""),
                    p.get("dominio") or p.get("fonte_nome", ""),
                    p.get("chars_fonte", 0),
                ),
            )
        self.var_status.set(f"{len(self.resultados)} resultado(s).")

    def _adicionar_selecionada(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Google News v111", "Selecione uma pauta.", parent=self)
            return
        pauta = self.resultados[int(sel[0])]
        if not self.db or not hasattr(self.db, "salvar_pauta"):
            messagebox.showinfo(
                "Google News v111",
                "Pauta selecionada, mas esta instância do painel não expôs db.salvar_pauta().",
                parent=self,
            )
            return
        try:
            self.db.salvar_pauta(pauta)
            self.var_status.set("Pauta adicionada à fila.")
        except Exception as exc:
            messagebox.showerror("Google News v111", f"Falha ao salvar: {exc}", parent=self)
