# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def memoria_dir(root: str = ".") -> Path:
    raiz = Path(root).resolve()
    pasta = raiz / "sistema" / "ururau_ai_auditor" / "memoria"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def registrar_evento(tipo: str, dados: dict, root: str = ".") -> str:
    pasta = memoria_dir(root)
    path = pasta / "eventos.jsonl"
    item = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tipo": tipo,
        "dados": dados,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return str(path)


def atualizar_erros_conhecidos(achados: list[dict], root: str = ".") -> str:
    pasta = memoria_dir(root)
    path = pasta / "erros_conhecidos.json"
    atual = _read_json(path, {})
    for item in achados:
        chave = str(item.get("texto") or item.get("erro") or item.get("arquivo") or "")[:180]
        if not chave:
            continue
        rec = atual.setdefault(chave, {"ocorrencias": 0, "primeiro": time.strftime("%Y-%m-%d %H:%M:%S")})
        rec["ocorrencias"] = int(rec.get("ocorrencias", 0)) + 1
        rec["ultimo"] = time.strftime("%Y-%m-%d %H:%M:%S")
        rec["ultimo_item"] = item
    _write_json(path, atual)
    return str(path)


def salvar_snapshot_auditoria(dados: dict, root: str = ".") -> dict:
    pasta = memoria_dir(root)
    logs = dados.get("classificacao", {}).get("logs", [])
    compilacao = dados.get("classificacao", {}).get("compilacao", [])
    erros_path = atualizar_erros_conhecidos(logs + compilacao, root)
    registrar_evento("auditoria", {
        "python_total": dados.get("regressao", {}).get("compilacao", {}).get("total"),
        "python_falhas": len(dados.get("regressao", {}).get("compilacao", {}).get("falhas", [])),
        "logs_achados": len(dados.get("logs", {}).get("achados", [])),
        "erros_conhecidos": erros_path,
    }, root)
    return {"erros_conhecidos": erros_path, "eventos": str(pasta / "eventos.jsonl")}
