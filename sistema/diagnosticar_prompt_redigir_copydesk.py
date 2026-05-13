# -*- coding: utf-8 -*-
"""Diagnostico do prompt efetivo de Redigir/Copydesk.

spec_auditoria_global_linha_editorial_ururau §16.

Mostra o prompt-sistema completo que o ia_service vai mandar para OpenAI,
para inspecao manual. Confirma uso da linha editorial canonica.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=("redigir", "copydesk"), default="redigir")
    ap.add_argument("--titulo", default="Pauta de teste para diagnostico")
    ap.add_argument("--fonte", default="Texto da fonte para teste de diagnostico.")
    args = ap.parse_args()

    from ururau.editorial.linha_editorial_ururau import (
        build_prompt_redigir, build_prompt_copydesk,
    )

    if args.modo == "redigir":
        prompt = build_prompt_redigir({"titulo_origem": args.titulo}, args.fonte)
    else:
        prompt = build_prompt_copydesk(
            {"titulo_seo": args.titulo, "corpo_materia": "x"},
            args.fonte,
        )
    relatorio = {
        "modo": args.modo,
        "tem_anti_alucinacao": "ANTI-ALUCINACAO" in prompt,
        "tem_termos_proibidos": "TERMOS PROIBIDOS" in prompt,
        "tem_schema_json": "titulo_seo" in prompt and "corpo_materia" in prompt,
        "tem_cronologia": "CRONOLOGIA" in prompt,
        "len_chars": len(prompt),
        "prompt_amostra_inicio": prompt[:600],
        "prompt_amostra_fim": prompt[-400:],
    }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
