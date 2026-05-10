# -*- coding: utf-8 -*-
"""
Integrador Fase 2: Liga scanner_codigo.py -> patch_generator -> sandbox -> rollback_guard -> long_term_memory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ururau_ai_auditor.scanner_codigo import ScannerCodigo
from ururau_ai_auditor.nn_engine.patch_generator import PatchGenerator
from ururau_ai_auditor.nn_engine.sandbox_ml import SandboxML
from ururau_ai_auditor.nn_engine.rollback_guard import RollbackGuard
from ururau_ai_auditor.nn_engine.long_term_memory import LongTermMemory


class NeuralRepairPipeline:
    """Pipeline completo: detecta -> gera -> valida -> aplica -> monitora."""

    def __init__(self, root: Union[str, Path] = "."):
        self.root = Path(root)
        self.scanner = ScannerCodigo()
        self.generator = PatchGenerator()
        self.sandbox = SandboxML(root)
        self.guard = RollbackGuard(root)
        self.memory = LongTermMemory(root)

    def run(self) -> Dict:
        """Executa ciclo completo de reparo neural."""
        print("=" * 60)
        print("NEURAL REPAIR PIPELINE — FASE 2")
        print("=" * 60)

        # 1. Scan
        print("[1/5] Escaneando codigo...")
        erros = self.scanner.escanear_diretorio(self.root / "sistema")
        sintaxe = [e for e in erros if e.get("tipo") == "SyntaxError"]
        if not sintaxe:
            print("[OK] Nenhum SyntaxError encontrado.")
            return {"acao": "NADA_A_FAZER"}

        print(f"[OK] {len(sintaxe)} SyntaxError(s) detectado(s).")

        # 2. Busca memória
        erro = sintaxe[0]
        problema = f"{erro['arquivo']}: {erro['mensagem']}"
        print(f"[2/5] Buscando memoria para: {problema[:80]}...")
        similares = self.memory.buscar(problema, top_k=1)
        if similares and similares[0]["similaridade"] > 0.85:
            print(f"[OK] Solucao similar encontrada (sim={similares[0]['similaridade']}). Reutilizando...")
            patch = {"original": "", "patched": similares[0]["solucao"], "explicacao": "Reutilizado da memoria", "fonte": "memory"}
        else:
            print("[3/5] Gerando patch novo...")
            patch = self.generator.generate_for_syntax_error(
                erro["arquivo"], erro["mensagem"], erro.get("linha", "")
            )

        if not patch:
            print("[ERRO] Nao foi possivel gerar patch.")
            return {"acao": "FALHA_GERACAO"}

        # 3. Sandbox
        print("[4/5] Validando em sandbox...")
        laudo = self.sandbox.validar_patch(erro["arquivo"], patch)
        if not laudo["aprovado"]:
            print(f"[REJEITADO] {laudo.get('motivo_rejeicao', 'Sem motivo')}")
            return {"acao": "REJEITADO_SANDBOX", "laudo": laudo}

        print("[OK] Sandbox aprovou.")

        # 4. Aplica + Guarda
        patch_id = f"patch_{erro['arquivo'].replace('/','_').replace('\','_')}_{int(__import__('time').time())}"
        print(f"[5/5] Aplicando patch ({patch_id})...")
        resultado = self.guard.aplicar_patch(erro["arquivo"], patch, patch_id)

        # 5. Memória
        self.memory.adicionar(problema, patch["patched"], "aplicado", erro["arquivo"], patch_id)

        print("[OK] Patch aplicado. Aguarde 24h para fechamento.")
        return {"acao": "APLICADO", "patch_id": patch_id, "laudo": laudo}


def main() -> int:
    pipe = NeuralRepairPipeline(BASE_DIR)
    r = pipe.run()
    print("=" * 60)
    print(f"RESULTADO: {r['acao']}")
    print("=" * 60)
    return 0 if r["acao"] in ("NADA_A_FAZER", "APLICADO") else 1


if __name__ == "__main__":
    raise SystemExit(main())
