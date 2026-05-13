# -*- coding: utf-8 -*-
"""Diagnostico CLI de conversao WebP.

Uso:
    python sistema/diagnosticar_webp.py --input "caminho/imagem.jpg"
    python sistema/diagnosticar_webp.py --input "caminho/img.png" --max-kb 80
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
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--max-kb", type=int, default=80)
    p.add_argument("--width", type=int, default=900)
    p.add_argument("--height", type=int, default=675)
    p.add_argument("--no-canvas", action="store_true")
    args = p.parse_args()

    from ururau.imaging.webp_converter import converter_para_webp_ururau

    out_dir = args.output_dir or Path(args.input).parent
    res = converter_para_webp_ururau(
        args.input,
        output_dir=out_dir,
        max_bytes=args.max_kb * 1024,
        target_width=args.width,
        target_height=args.height,
        allow_canvas=not args.no_canvas,
    )
    breve = {
        "ok": res.get("ok"),
        "output_path": res.get("output_path"),
        "size_kb": round((res.get("size_bytes") or 0) / 1024.0, 2),
        "quality": res.get("quality"),
        "width": res.get("width"),
        "height": res.get("height"),
        "method": res.get("method"),
        "erro_tipo": res.get("erro_tipo"),
        "erro": res.get("erro"),
    }
    print(json.dumps(breve, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
