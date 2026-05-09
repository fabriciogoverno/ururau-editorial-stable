# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox


def root_sistema() -> Path:
    return Path(__file__).resolve().parents[1]


def projeto_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ultimo_json(pasta: Path, padrao: str = "*.json") -> Path | None:
    if not pasta.exists():
        return None
    arquivos = sorted(pasta.glob(padrao), key=lambda p: p.stat().st_mtime, reverse=True)
    return arquivos[0] if arquivos else None


def ler_json(path: Path | None, default):
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def resumir_por_agente(classificados: list[dict]) -> dict[str, int]:
    resumo: dict[str, int] = {}
    for item in classificados or []:
        agente = (((item.get("classificacao") or {}).get("principal") or {}).get("agente") or "indefinido")
        resumo[agente] = resumo.get(agente, 0) + 1
    return dict(sorted(resumo.items(), key=lambda x: x[1], reverse=True))


class PainelAuditoriaIA(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ururau Auditor IA")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.relatorio_path: Path | None = None
        self.relatorio: dict = {}
        self.memoria: dict = {}
        self._montar_ui()
        self.carregar()

    def _montar_ui(self):
        topo = ttk.Frame(self, padding=10)
        topo.pack(fill="x")
        ttk.Label(topo, text="Ururau Auditor IA", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(topo, text="Atualizar", command=self.carregar).pack(side="right")

        self.lbl_status = ttk.Label(self, text="Carregando...", padding=(10, 0))
        self.lbl_status.pack(fill="x")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.txt_resumo = self._aba_texto("Resumo")
        self.txt_agentes = self._aba_texto("Agentes")
        self.txt_logs = self._aba_texto("Logs classificados")
        self.txt_compilacao = self._aba_texto("Compilação")
        self.txt_memoria = self._aba_texto("Memória")

    def _aba_texto(self, nome: str) -> tk.Text:
        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text=nome)
        txt = tk.Text(frame, wrap="word", font=("Consolas", 10))
        y = ttk.Scrollbar(frame, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=y.set)
        txt.pack(side="left", fill="both", expand=True)
        y.pack(side="right", fill="y")
        return txt

    def _set_text(self, txt: tk.Text, valor: str):
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        txt.insert("1.0", valor)
        txt.configure(state="disabled")

    def carregar(self):
        pasta_rel = root_sistema() / "relatorios_auditoria"
        self.relatorio_path = ultimo_json(pasta_rel, "auditoria_*.json")
        self.relatorio = ler_json(self.relatorio_path, {})
        memoria_path = root_sistema() / "ururau_ai_auditor" / "memoria" / "erros_conhecidos.json"
        self.memoria = ler_json(memoria_path, {})
        if not self.relatorio:
            self.lbl_status.configure(text="Nenhum relatório encontrado. Rode 30_AUDITORIA_TOTAL.bat primeiro.")
            return
        self._renderizar()

    def _renderizar(self):
        reg = self.relatorio.get("regressao", {})
        comp = reg.get("compilacao", {})
        logs = self.relatorio.get("logs", {}).get("achados", [])
        class_logs = self.relatorio.get("classificacao", {}).get("logs", [])
        class_comp = self.relatorio.get("classificacao", {}).get("compilacao", [])
        memoria_info = self.relatorio.get("memoria", {})

        self.lbl_status.configure(text=f"Relatório: {self.relatorio_path} | Python falhas: {len(comp.get('falhas', []))} | Logs: {len(logs)}")

        resumo = {
            "relatorio": str(self.relatorio_path),
            "python_total": comp.get("total"),
            "python_falhas": len(comp.get("falhas", [])),
            "logs_achados": len(logs),
            "logs_classificados": len(class_logs),
            "memoria": memoria_info,
        }
        self._set_text(self.txt_resumo, json.dumps(resumo, ensure_ascii=False, indent=2))

        agentes = {
            "logs_por_agente": resumir_por_agente(class_logs),
            "compilacao_por_agente": resumir_por_agente(class_comp),
            "agentes_registrados": self.relatorio.get("agentes", {}),
        }
        self._set_text(self.txt_agentes, json.dumps(agentes, ensure_ascii=False, indent=2))

        self._set_text(self.txt_logs, json.dumps(class_logs[-120:], ensure_ascii=False, indent=2))
        self._set_text(self.txt_compilacao, json.dumps(comp, ensure_ascii=False, indent=2))

        top_mem = sorted(self.memoria.items(), key=lambda kv: int((kv[1] or {}).get("ocorrencias", 0)), reverse=True)[:80]
        self._set_text(self.txt_memoria, json.dumps(dict(top_mem), ensure_ascii=False, indent=2))


def main():
    app = PainelAuditoriaIA()
    app.mainloop()


if __name__ == "__main__":
    main()
