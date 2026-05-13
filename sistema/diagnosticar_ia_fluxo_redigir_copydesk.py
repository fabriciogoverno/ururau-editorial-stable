# -*- coding: utf-8 -*-
"""Diagnostico nao destrutivo do fluxo Redigir/Copydesk.

spec_claudio_ia_real_gpt4mini_regras_editoriais §8.

Uso:
    cd sistema
    python diagnosticar_ia_fluxo_redigir_copydesk.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> dict:
    from ururau.ia import ia_service
    cfg = ia_service.diagnosticar_ia()

    painel_path = ROOT / "ururau" / "ui" / "painel.py"
    patch_v4726 = ROOT / "ururau" / "ui" / "patch_v47_26_fonte_antes_ia.py"
    motor_gpt = ROOT / "ururau" / "editorial" / "motor_gpt_spec_v2.py"

    def _texto(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    painel = _texto(painel_path)
    p4726 = _texto(patch_v4726)
    motor = _texto(motor_gpt)

    redigir_chama_ia = bool(re.search(r"etapa_redacao|executar_ia_redigir|openai", painel))
    copydesk_chama_ia = bool(re.search(r"copydesk|executar_ia_copydesk|openai", painel, re.I))
    fallback_redigir_existe = bool(re.search(r"fallback_local|sem_telemetria_ia|fallback_sem_ia", painel + p4726))
    fallback_pode_fingir = bool(
        re.search(r"Redacao concluida com IA", painel) is None
        and re.search(r"fallback_local.*Redacao concluida", painel + p4726, re.I)
    )
    mensagem_concluida_sem_ia = bool(
        re.search(r"Mat.ria gerada com fonte validada antes da IA", painel + p4726)
    )

    out = {
        "openai_key_presente": cfg["openai_key_presente"],
        "modelo_configurado": cfg["modelo_configurado"],
        "endpoint_usado": cfg["endpoint_usado"],
        "modelo_e_padrao_ururau": cfg["modelo_e_padrao_ururau"],
        "redigir_chama_ia": redigir_chama_ia,
        "copydesk_chama_ia": copydesk_chama_ia,
        "fallback_redigir_existe": fallback_redigir_existe,
        "fallback_redigir_pode_fingir_ia": fallback_pode_fingir,
        "mensagem_redacao_concluida_sem_ia": mensagem_concluida_sem_ia,
        "motor_gpt_spec_v2_presente": motor_gpt.exists() and bool(motor.strip()),
        "ia_service_modulo_presente": True,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    main()
