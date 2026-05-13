# -*- coding: utf-8 -*-
"""Diagnostico de boilerplate em fontes captadas.

spec_auditoria_global_linha_editorial_ururau §16.

Uso:
    python sistema/diagnosticar_boilerplate_fonte.py --input "caminho/texto.txt"
    python sistema/diagnosticar_boilerplate_fonte.py --texto "..."
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
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--input")
    grp.add_argument("--texto")
    args = ap.parse_args()

    if args.input:
        try:
            texto = Path(args.input).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(json.dumps({"ok": False, "erro": str(e)}))
            return 1
    else:
        texto = args.texto or ""

    from ururau.editorial.validador_boilerplate import (
        limpar_boilerplate_fonte,
        detectar_boilerplate,
        fonte_tem_boilerplate_critico,
    )
    limp = limpar_boilerplate_fonte(texto)
    out = {
        "chars_antes": limp["chars_antes"],
        "chars_depois": limp["chars_depois"],
        "padroes_detectados": detectar_boilerplate(texto),
        "boilerplate_critico": fonte_tem_boilerplate_critico(texto),
        "remocoes_amostra": limp["removidos"][:8],
        "texto_limpo_amostra": (limp["texto_limpo"] or "")[:400],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
