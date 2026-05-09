# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


IGNORAR_DIRTY = {
    "sistema/config/fontes_links.json",
    "sistema/config/layout_v43_premium.json",
    "sistema/config/status_fontes.json",
}


def projeto_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sistema_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path) -> dict:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
    }


def _path_from_status_line(linha: str) -> str:
    """Extrai caminho de `git status --short` preservando XY status.

    Exemplos:
    - ' M sistema/config/a.json' -> 'sistema/config/a.json'
    - 'M  sistema/x.py' -> 'sistema/x.py'
    - '?? sistema/log.txt' -> 'sistema/log.txt'
    - 'R  antigo -> novo' -> 'novo'
    """
    raw = linha.rstrip("\n")
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1]
    if len(raw) >= 3:
        return raw[3:].strip()
    return raw.strip()


def git_status(root: Path) -> dict:
    r = run(["git", "status", "--short"], root)
    linhas = [x.rstrip("\n") for x in (r["stdout"] or "").splitlines() if x.strip()]
    dirty_relevante = []
    dirty_ignorado = []
    for linha in linhas:
        path = _path_from_status_line(linha)
        if path in IGNORAR_DIRTY or path.startswith("sistema/relatorios_auditoria/") or path.startswith("sistema/ururau_ai_auditor/memoria/"):
            dirty_ignorado.append(linha)
        else:
            dirty_relevante.append(linha)
    return {
        "raw": linhas,
        "dirty_relevante": dirty_relevante,
        "dirty_ignorado": dirty_ignorado,
    }


def ultimo_json(pasta: Path, padrao: str) -> Path | None:
    if not pasta.exists():
        return None
    arquivos = sorted(pasta.glob(padrao), key=lambda p: p.stat().st_mtime, reverse=True)
    return arquivos[0] if arquivos else None


def ler_json(path: Path | None, default):
    if not path or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def avaliar() -> dict:
    root = projeto_root()
    rel_dir = sistema_root() / "relatorios_auditoria"
    auditoria_path = ultimo_json(rel_dir, "auditoria_*.json")
    sandbox_path = ultimo_json(rel_dir, "sandbox_*.json")
    auditoria = ler_json(auditoria_path, {})
    sandbox = ler_json(sandbox_path, {})
    comp = auditoria.get("regressao", {}).get("compilacao", {})
    baseline = (auditoria.get("logs", {}) or {}).get("baseline_status", {}) or {}
    status = git_status(root)

    contratos_ok = sandbox.get("validacoes", {}).get("testes_contrato", {}).get("returncode") == 0
    sandbox_ok = sandbox.get("validacoes", {}).get("auditoria_total", {}).get("returncode") == 0 and contratos_ok
    python_falhas = len(comp.get("falhas", []))
    logs_novos = len(baseline.get("novos") or [])

    bloqueios = []
    if python_falhas:
        bloqueios.append(f"python_falhas={python_falhas}")
    if logs_novos:
        bloqueios.append(f"logs_novos={logs_novos}")
    if not contratos_ok:
        bloqueios.append("testes_contrato_falharam")
    if not sandbox_ok:
        bloqueios.append("sandbox_falhou")
    if status["dirty_relevante"]:
        bloqueios.append("git_dirty_relevante")

    resultado = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "auditoria": str(auditoria_path) if auditoria_path else "",
        "sandbox": str(sandbox_path) if sandbox_path else "",
        "python_falhas": python_falhas,
        "logs_novos": logs_novos,
        "contratos_ok": contratos_ok,
        "sandbox_ok": sandbox_ok,
        "git_dirty_relevante": status["dirty_relevante"],
        "git_dirty_ignorado": status["dirty_ignorado"],
        "apto_promocao_main": not bloqueios,
        "bloqueios": bloqueios,
    }
    out = rel_dir / ("gate_promocao_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    out.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(out), "resultado": resultado}


def main() -> int:
    r = avaliar()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["resultado"].get("apto_promocao_main") else 1


if __name__ == "__main__":
    raise SystemExit(main())
