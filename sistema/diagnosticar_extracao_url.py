# -*- coding: utf-8 -*-
"""Diagnostico de extracao por URL.

spec_scrapling_artigo_unico_sem_mistura §6.

Uso:
    python sistema/diagnosticar_extracao_url.py --url "https://..."
    python sistema/diagnosticar_extracao_url.py --url "..." --titulo "..."

Modo offline (texto ja extraido):
    python sistema/diagnosticar_extracao_url.py --texto-arq "fonte.txt" \
        --url "..." --titulo "..." --canonical "..."
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _extrair_via_pipeline(url: str) -> dict:
    """Tenta usar o pipeline do projeto. Em modo offline retorna placeholder."""
    try:
        from ururau.coleta.leitura_fonte import ler_fonte_pauta
        res = ler_fonte_pauta({"link_origem": url}, forcar_refresh=False)
        return {
            "estrategias_testadas": [getattr(res, "estrategia", "") or "v134"],
            "estrategia_vencedora": getattr(res, "estrategia", "") or "v134",
            "url_final": getattr(res, "url", "") or url,
            "texto": (getattr(res, "texto_limpo", "") or "").strip(),
            "sucesso": bool(getattr(res, "sucesso", False)),
            "erro": getattr(res, "erro", "") or "",
        }
    except Exception as e:
        return {
            "estrategias_testadas": [],
            "estrategia_vencedora": "",
            "url_final": url,
            "texto": "",
            "sucesso": False,
            "erro": f"pipeline_indisponivel:{e}",
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--titulo", default="")
    ap.add_argument("--canonical", default="")
    ap.add_argument("--og", default="")
    ap.add_argument("--texto-arq", default="",
                    help="Modo offline: caminho de arquivo .txt com texto ja extraido")
    args = ap.parse_args()

    if args.texto_arq:
        try:
            texto = Path(args.texto_arq).read_text(encoding="utf-8", errors="ignore")
            estrategia = "arquivo_local"
            url_final = args.url
        except Exception as e:
            print(json.dumps({"ok": False, "erro": str(e)}, ensure_ascii=False))
            return 1
    else:
        pipe = _extrair_via_pipeline(args.url)
        texto = pipe["texto"]
        estrategia = pipe["estrategia_vencedora"] or pipe["erro"]
        url_final = pipe["url_final"]

    from ururau.coleta.extrator_artigo_unico import validar_extracao_artigo_unico
    val = validar_extracao_artigo_unico(
        texto,
        titulo_pauta=args.titulo,
        url_pauta=args.url,
        canonical_url=args.canonical or url_final,
        og_url=args.og or url_final,
        estrategia=estrategia,
    )

    out = {
        "url_original": args.url,
        "url_final": url_final,
        "canonical_url": args.canonical,
        "og_url": args.og,
        "titulo_pauta": args.titulo,
        "estrategias_testadas": [estrategia] if estrategia else [],
        "estrategia_vencedora": estrategia,
        "texto_limpo_chars": val["chars"],
        "assuntos_detectados": val["titulos_relacionados"],
        "boilerplate_detectado": val["boilerplate"],
        "multiassunto_detectado": val["multiassunto"],
        "aprovado_para_redigir": val["ok"],
        "motivo": val["motivo"],
        "status": val["status"],
        "score_coerencia": val["score_coerencia"],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if val["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
