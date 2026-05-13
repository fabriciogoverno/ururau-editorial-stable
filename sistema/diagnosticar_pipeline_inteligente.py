# -*- coding: utf-8 -*-
"""Diagnostico do pipeline inteligente (bandit por dominio).

Uso:
    python sistema/diagnosticar_pipeline_inteligente.py            # relatorio geral
    python sistema/diagnosticar_pipeline_inteligente.py --url URL  # detalhes do dominio
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
    ap.add_argument("--url", default="")
    args = ap.parse_args()

    from ururau.coleta.pipeline_inteligente_v200 import (
        relatorio_global,
        estatisticas_por_dominio,
        ordem_recomendada_para_url,
    )
    if args.url:
        out = {
            "url": args.url,
            "estatisticas": estatisticas_por_dominio(args.url),
            "ordem_recomendada": ordem_recomendada_para_url(args.url),
        }
    else:
        out = relatorio_global()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
