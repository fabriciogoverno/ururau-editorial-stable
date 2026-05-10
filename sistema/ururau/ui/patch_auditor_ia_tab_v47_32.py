# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk


def _sistema_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if parent.name == "sistema":
            return parent
    return Path.cwd()


def _ultimo_json(pasta: Path, padrao: str) -> Path | None:
    if not pasta.exists():
        return None
    arquivos = sorted(pasta.glob(padrao), key=lambda x: x.stat().st_mtime, reverse=True)
    return arquivos[0] if arquivos else None


def _ler_json(path: Path | None, default):
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def _resumo_auditor(auto_status: str = "") -> str:
    s = _sistema_root()
    rel = _ultimo_json(s / "relatorios_auditoria", "auditoria_*.json")
    status = _ultimo_json(s / "relatorios_auditoria", "status_agentes_*.json")
    auditoria = _ler_json(rel, {})
    st = _ler_json(status, {})
    comp = auditoria.get("regressao", {}).get("compilacao", {})
    logs = auditoria.get("logs", {})
    baseline = logs.get("baseline_status", {}) or {}
    agente = (st.get("status", {}) or {}).get("agente_prioritario") or "fonte"
    linhas = [
        "AUDITOR IA — STATUS OPERACIONAL",
        "",
        f"Autoauditoria: {auto_status or 'ativa'}",
        f"Relatorio: {rel.name if rel else 'nenhum'}",
        f"Python: {comp.get('total', '--')} arquivo(s) | falhas: {len(comp.get('falhas', []))}",
        f"Logs: {len(logs.get('achados', []))} achado(s) | novos: {len(baseline.get('novos') or [])} | conhecidos: {baseline.get('total_conhecidos', 0)}",
        f"Agente prioritario: {agente}",
        "",
        "Gates ativos:",
        "- FonteValidada antes da IA",
        "- Bloqueio 403/429",
        "- Bloqueio de fonte curta",
        "- Preview anti-contaminacao",
        "- CMS sem imagem bloqueado",
        "- Sandbox Auditor",
        "- Baseline de logs para separar erro velho de erro novo",
        "",
        "Este painel roda auditoria automaticamente em segundo plano.",
    ]
    return "\n".join(linhas)


def aplicar_patch_auditor_ia_tab_v47_32(ns: dict):
    PainelUrurau = ns.get("PainelUrurau")
    if PainelUrurau is None:
        print("[V47.33] PainelUrurau nao encontrado; aba Auditor IA nao aplicada")
        return
    if getattr(PainelUrurau, "_v4732_auditor_tab", False):
        return

    old_construir_detalhe = getattr(PainelUrurau, "_construir_detalhe", None)
    if not callable(old_construir_detalhe):
        print("[V47.33] _construir_detalhe nao encontrado")
        return

    def _rodar_cmd_async(self, cmd: list[str], callback=None):
        def worker():
            try:
                p = subprocess.run(cmd, cwd=str(_sistema_root()), text=True, capture_output=True, timeout=600)
                saida = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
            except Exception as e:
                saida = str(e)
            if callback:
                try:
                    self.after(0, lambda: callback(saida))
                except Exception:
                    pass
        threading.Thread(target=worker, daemon=True).start()

    def _criar_aba_auditor(self):
        nb = getattr(self, "_notebook", None)
        if nb is None:
            return
        try:
            for i in range(nb.index("end")):
                if nb.tab(i, "text") == "🧠 Auditor IA":
                    return
        except Exception:
            pass

        frame = tk.Frame(nb, bg="#0f0f1a")
        nb.add(frame, text="🧠 Auditor IA")

        top = tk.Frame(frame, bg="#11112a", height=42)
        top.pack(fill="x")
        top.pack_propagate(False)

        tk.Label(top, text="Auditor IA — Integridade Operacional", bg="#11112a", fg="#e2e8f0", font=("Segoe UI", 11, "bold")).pack(side="left", padx=10)

        txt = tk.Text(frame, bg="#101827", fg="#dbeafe", insertbackground="#dbeafe", font=("Consolas", 10), wrap="word")
        txt.pack(fill="both", expand=True, padx=8, pady=8)

        auto_var = tk.BooleanVar(value=True)
        status_var = tk.StringVar(value="Auto ON")

        def set_text(valor: str):
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("1.0", valor)
            txt.configure(state="disabled")

        def atualizar():
            set_text(_resumo_auditor(status_var.get()))

        def _pos_auditoria(_saida: str = ""):
            status_var.set("Auto ON | ultimo ciclo " + datetime.now().strftime("%H:%M:%S"))
            atualizar()

        def rodar_auditoria():
            status_var.set("rodando auditoria...")
            set_text(_resumo_auditor(status_var.get()))
            _rodar_cmd_async(self, [sys.executable, "-m", "ururau_ai_auditor.run_auditoria"], _pos_auditoria)

        def rodar_pipeline():
            status_var.set("pipeline rapido rodando...")
            set_text(_resumo_auditor(status_var.get()))
            _rodar_cmd_async(self, [sys.executable, "-m", "ururau_ai_auditor.run_auditoria"], lambda s: set_text(s[-8000:] + "\n\n" + _resumo_auditor("pipeline rapido concluido")))

        def toggle_auto():
            status_var.set("Auto ON" if auto_var.get() else "Auto OFF")
            atualizar()

        def auto_loop():
            try:
                if auto_var.get():
                    rodar_auditoria()
            finally:
                try:
                    self.after(120000, auto_loop)
                except Exception:
                    pass

        tk.Checkbutton(top, text="Auto", variable=auto_var, command=toggle_auto, bg="#11112a", fg="#e2e8f0", selectcolor="#1e293b", activebackground="#11112a", activeforeground="#e2e8f0").pack(side="right", padx=5, pady=7)
        tk.Button(top, text="Atualizar", command=atualizar, bg="#334155", fg="white", relief="flat", padx=10).pack(side="right", padx=5, pady=7)
        tk.Button(top, text="Rodar auditoria", command=rodar_auditoria, bg="#2563eb", fg="white", relief="flat", padx=10).pack(side="right", padx=5, pady=7)
        tk.Button(top, text="Pipeline rápido", command=rodar_pipeline, bg="#7c3aed", fg="white", relief="flat", padx=10).pack(side="right", padx=5, pady=7)

        atualizar()
        self.after(5000, auto_loop)

    def _construir_detalhe_v47_32(self, frame):
        old_construir_detalhe(self, frame)
        try:
            _criar_aba_auditor(self)
            print("[V47.33] Aba Auditor IA integrada ao painel principal com autoauditoria")
        except Exception as e:
            print(f"[V47.33] falha ao criar aba Auditor IA: {e}")

    PainelUrurau._construir_detalhe = _construir_detalhe_v47_32
    PainelUrurau._v4732_auditor_tab = True
    print("[V47.33] Patch de aba Auditor IA auto instalado")
