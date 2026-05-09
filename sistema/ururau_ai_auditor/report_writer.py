# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime


def salvar_relatorio(dados: dict, root: str = ".") -> str:
    raiz = Path(root).resolve()
    pasta = raiz / "sistema" / "relatorios_auditoria"
    pasta.mkdir(parents=True, exist_ok=True)
    nome = "auditoria_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    caminho = pasta / nome
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(caminho)
