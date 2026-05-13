# -*- coding: utf-8 -*-
"""Diagnostico de bypass de paywall.

Uso:
    python sistema/diagnosticar_bypass_paywall.py --url URL [--titulo X]

Tenta cada estrategia em sequencia e reporta qual conseguiu extrair texto.
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
    ap.add_argument("--url", required=True)
    ap.add_argument("--titulo", default="")
    args = ap.parse_args()

    from ururau.coleta.bypass_paywall_v200 import (
        tentar_bypass_paywall, BYPASS_DISPONIVEL,
    )
    if not BYPASS_DISPONIVEL:
        print(json.dumps({"ok": False, "erro": "requests nao instalado"}))
        return 1
    r = tentar_bypass_paywall(args.url, args.titulo)
    # Resumo sem o texto inteiro
    resumo = {
        "ok": r["ok"],
        "estrategia_vencedora": r["estrategia"],
        "url_final": r["url_final"],
        "chars_extraidos": len(r["texto"]),
        "amostra": (r["texto"] or "")[:300],
        "tentativas": r["tentativas"],
    }
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
