# -*- coding: utf-8 -*-
"""diagnosticar_todas_fontes_v200 — CLI do diagnostico de fonte em LOTE.

Roda o diagnostico completo de TODAS as fontes configuradas no sistema,
gera/aplica o perfil operacional de cada uma e produz um relatorio
consolidado. As fontes que falharem em todas as estrategias sao apenas
SINALIZADAS (politica do usuario: nada e desativado).

Uso:
    python sistema/diagnosticar_todas_fontes_v200.py
    python sistema/diagnosticar_todas_fontes_v200.py --max 10
    python sistema/diagnosticar_todas_fontes_v200.py --janela 12
    python sistema/diagnosticar_todas_fontes_v200.py --json
    python sistema/diagnosticar_todas_fontes_v200.py --listar

Saidas:
    sistema/relatorios_diagnostico_fontes/lote_v200/lote_v200_<ts>.txt
    sistema/relatorios_diagnostico_fontes/lote_v200/lote_v200_<ts>.json
    sistema/fontes_precisam_atencao_v200.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# garante que 'ururau' seja importavel rodando de qualquer lugar
_SISTEMA = Path(__file__).resolve().parent
if str(_SISTEMA) not in sys.path:
    sys.path.insert(0, str(_SISTEMA))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Diagnostico de fonte em lote — Ururau v200",
    )
    ap.add_argument("--max", type=int, default=0,
                    help="limita o numero de fontes (0 = todas)")
    ap.add_argument("--janela", type=int, default=24,
                    help="janela de horas para considerar pauta valida")
    ap.add_argument("--json", action="store_true",
                    help="imprime o resumo final em JSON")
    ap.add_argument("--listar", action="store_true",
                    help="apenas lista as fontes configuradas e sai")
    args = ap.parse_args()

    try:
        from ururau.coleta.diagnostico_auto_v200 import (
            enumerar_fontes_configuradas,
            diagnosticar_todas_as_fontes,
        )
    except Exception as e:
        print(f"ERRO: nao consegui importar o modulo de diagnostico: {e}")
        return 2

    if args.listar:
        fontes = enumerar_fontes_configuradas()
        print(f"{len(fontes)} fonte(s) configurada(s):\n")
        for i, f in enumerate(fontes, 1):
            ativo = "ativa" if f.get("ativo", True) else "INATIVA"
            print(f"  {i:>3}. [{f['grupo']:<12}] {f['nome']} — {f['url']} ({ativo})")
        return 0

    def log(msg: str) -> None:
        print(msg, flush=True)

    resumo = diagnosticar_todas_as_fontes(
        log_callback=log,
        max_fontes=(args.max if args.max > 0 else None),
        janela_horas=args.janela,
    )

    if args.json:
        # remove o texto longo do json do stdout
        resumo_compacto = {k: v for k, v in resumo.items() if k != "relatorio_txt"}
        print(json.dumps(resumo_compacto, ensure_ascii=False, indent=2))
    else:
        print("\n" + resumo["relatorio_txt"])
        print(f"\nRelatorio salvo em: {resumo['arquivo_txt']}")
        print(f"JSON salvo em:      {resumo['arquivo_json']}")
        if resumo["precisam_atencao"]:
            print(f"Fontes p/ atencao:  {resumo['arquivo_precisam_atencao']}")

    # sucesso mesmo com fontes problematicas — politica "so sinalizar"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
