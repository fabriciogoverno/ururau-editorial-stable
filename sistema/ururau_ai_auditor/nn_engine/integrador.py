# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ururau_ai_auditor.scanner_codigo import escanear
from ururau_ai_auditor.nn_engine.patch_generator import PatchGenerator
from ururau_ai_auditor.nn_engine.sandbox_ml import SandboxML
from ururau_ai_auditor.nn_engine.rollback_guard import RollbackGuard
from ururau_ai_auditor.nn_engine.long_term_memory import LongTermMemory

class NeuralRepairPipeline:
    def __init__(self, root=None):
        if root is None:
            root = BASE_DIR
        self.root = Path(root)
        self.generator = PatchGenerator()
        self.sandbox = SandboxML(root)
        self.guard = RollbackGuard(root)
        self.memory = LongTermMemory(root)

    def run(self):
        print("=" * 60)
        print("NEURAL REPAIR PIPELINE — FASE 2")
        print("=" * 60)
        print("[1/5] Escaneando codigo...")
        resultados = escanear(str(self.root / "sistema"))
        sintaxe = []
        for r in resultados:
            for erro in r.get("erros", []):
                if "SyntaxError" in erro:
                    sintaxe.append({"arquivo": str(self.root / "sistema" / r["caminho"]), "caminho_rel": r["caminho"], "mensagem": erro, "linhas": r["linhas"]})
        if not sintaxe:
            print("[OK] Nenhum SyntaxError encontrado.")
            return {"acao": "NADA_A_FAZER"}
        print("[OK] " + str(len(sintaxe)) + " SyntaxError(s) detectado(s).")
        erro = sintaxe[0]
        problema = erro["caminho_rel"] + ": " + erro["mensagem"]
        print("[2/5] Buscando memoria para: " + problema[:80] + "...")
        similares = self.memory.buscar(problema, top_k=1)
        if similares and similares[0]["similaridade"] > 0.85:
            print("[OK] Solucao similar encontrada. Reutilizando...")
            patch = {"original": "", "patched": similares[0]["solucao"], "explicacao": "Reutilizado da memoria", "fonte": "memory"}
        else:
            print("[3/5] Gerando patch novo...")
            patch = self.generator.generate_for_syntax_error(erro["arquivo"], erro["mensagem"], "")
        if not patch:
            print("[ERRO] Nao foi possivel gerar patch.")
            return {"acao": "FALHA_GERACAO"}
        print("[4/5] Validando em sandbox...")
        laudo = self.sandbox.validar_patch(erro["arquivo"], patch)
        if not laudo["aprovado"]:
            print("[REJEITADO] " + laudo.get("motivo_rejeicao", "Sem motivo"))
            return {"acao": "REJEITADO_SANDBOX", "laudo": laudo}
        print("[OK] Sandbox aprovou.")
        safe_name = erro["caminho_rel"].replace("/", "_").replace("\\", "_").replace(":", "_")
        patch_id = "patch_" + safe_name + "_" + str(int(time.time()))
        print("[5/5] Aplicando patch (" + patch_id + ")...")
        resultado = self.guard.aplicar_patch(erro["arquivo"], patch, patch_id)
        self.memory.adicionar(problema, patch["patched"], "aplicado", erro["arquivo"], patch_id)
        print("[OK] Patch aplicado. Aguarde 24h para fechamento.")
        return {"acao": "APLICADO", "patch_id": patch_id, "laudo": laudo}

def main() -> int:
    pipe = NeuralRepairPipeline(BASE_DIR)
    r = pipe.run()
    print("=" * 60)
    print("RESULTADO: " + r["acao"])
    print("=" * 60)
    return 0 if r["acao"] in ("NADA_A_FAZER", "APLICADO") else 1

if __name__ == "__main__":
    raise SystemExit(main())
