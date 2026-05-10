# -*- coding: utf-8 -*-
"""Ururau Autopilot: correções autônomas persistentes.

Aplica apenas correções determinísticas encontradas e validadas:
- arquiva sobras de deploy que quebram auditoria;
- corrige 46_STATUS_NN.bat quando estiver no formato quebrado;
- roda auditoria, testes de contrato e reparo neural;
- usa diagnóstico/aplicador de fontes v130/v131 para persistir fonte corrigida quando houver solução.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SISTEMA = ROOT / "sistema"
LOG_DIR = SISTEMA / "dados_autopilot"
STATUS = LOG_DIR / "autopilot_status.json"
LOG = LOG_DIR / "autopilot.log"
PATCHES = LOG_DIR / "patches_aplicados.jsonl"
INTERVALO = int(os.getenv("URURAU_AUTOPILOT_INTERVAL", "300"))


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def garantir_dirs() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def salvar_json(path: Path, data: dict[str, Any]) -> None:
    garantir_dirs()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def registrar(evento: str, dados: dict[str, Any] | None = None) -> None:
    garantir_dirs()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": agora(), "evento": evento, "dados": dados or {}}, ensure_ascii=False, default=str) + "\n")


def registrar_patch(nome: str, dados: dict[str, Any]) -> None:
    garantir_dirs()
    with PATCHES.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": agora(), "patch": nome, "dados": dados}, ensure_ascii=False, default=str) + "\n")


def rodar(cmd: list[str], timeout: int = 180) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, encoding="utf-8", errors="replace")
        return {"exit": p.returncode, "out": p.stdout or ""}
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        return {"exit": 124, "out": out + "\n[TIMEOUT]"}
    except Exception as exc:
        return {"exit": 1, "out": repr(exc)}


def arquivar_sobras_deploy() -> dict[str, Any]:
    rx = [re.compile(r"^fix_.*\.(py|ps1)$", re.I), re.compile(r"^deploy_.*\.ps1$", re.I)]
    destino = ROOT / "_arquivados_deploy"
    destino.mkdir(exist_ok=True)
    movidos: list[str] = []
    for p in ROOT.iterdir():
        if p.is_file() and any(r.match(p.name) for r in rx):
            alvo = destino / f"{p.name}.txt"
            shutil.move(str(p), str(alvo))
            movidos.append(f"{p.name} -> {alvo.name}")
    if movidos:
        registrar_patch("arquivar_sobras_deploy", {"movidos": movidos})
    return {"acao": "arquivar_sobras_deploy", "aplicou": bool(movidos), "movidos": movidos}


def corrigir_bat_status_nn() -> dict[str, Any]:
    path = ROOT / "46_STATUS_NN.bat"
    atual = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    if "python -c \"" not in atual and "ururau_status_nn.py" in atual:
        return {"acao": "corrigir_bat_status_nn", "aplicou": False, "detalhe": "já corrigido"}
    novo = r'''@echo off
chcp 65001 >nul
echo ==========================================
echo  URURAU — STATUS NEURAL ENGINE
echo ==========================================
cd /d "%~dp0"
set "TMP_PY=%TEMP%\ururau_status_nn.py"
(
echo from pathlib import Path
echo import json, sys
echo root = Path.cwd()
echo sistema = root / "sistema"
echo sys.path.insert(0, str(sistema))
echo print("Raiz:", root)
echo print("Sistema:", sistema)
echo for p in [root / "modelos_ml", sistema / "modelos_ml"]:
echo     print("Modelos em", p, ":", [x.name for x in p.glob("*")] if p.exists() else "Nenhum")
echo for p in [root / "dados_ml", sistema / "dados_ml"]:
echo     print("Dados em", p, ":", [x.name for x in p.glob("*")] if p.exists() else "Nenhum")
echo db = sistema / "data" / "ururau.db"
echo print("Banco:", db, "OK" if db.exists() else "NAO ENCONTRADO")
echo try:
echo     from neural_hooks import nn_status
echo     print("Neural status:", json.dumps(nn_status(), ensure_ascii=False, indent=2))
echo except Exception as e:
echo     print("Neural status: ERRO:", repr(e))
) > "%TMP_PY%"
python "%TMP_PY%"
if %errorlevel% neq 0 (
    echo [ERRO] Status neural falhou.
    pause
    exit /b 1
)
echo [OK] Status neural consultado.
pause
'''
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak_autopilot"))
    path.write_text(novo, encoding="utf-8")
    registrar_patch("corrigir_bat_status_nn", {"arquivo": str(path)})
    return {"acao": "corrigir_bat_status_nn", "aplicou": True, "arquivo": str(path)}


def auditoria() -> dict[str, Any]:
    r = rodar(["cmd", "/c", "30_AUDITORIA_TOTAL.bat"], timeout=240)
    ok = r["exit"] == 0 and '"python_falhas": 0' in r["out"]
    return {"acao": "auditoria", "ok": ok, "exit": r["exit"], "tail": r["out"][-3000:]}


def testes_contrato() -> dict[str, Any]:
    r = rodar(["cmd", "/c", "31_TESTES_CONTRATO.bat"], timeout=240)
    ok = r["exit"] == 0 and "OK" in r["out"] and "FAILED" not in r["out"]
    return {"acao": "testes_contrato", "ok": ok, "exit": r["exit"], "tail": r["out"][-3000:]}


def reparo_neural() -> dict[str, Any]:
    r = rodar(["cmd", "/c", "47_REPARO_NEURAL.bat"], timeout=300)
    return {"acao": "reparo_neural", "ok": r["exit"] == 0, "exit": r["exit"], "tail": r["out"][-3000:]}


def urls_problematicas(limit: int = 3) -> list[str]:
    urls: list[str] = []
    roots = [SISTEMA / "logs", SISTEMA / "relatorios_auditoria", SISTEMA / "dados_autopilot"]
    rx_url = re.compile(r"https?://[^\s\]\)\"']+", re.I)
    marcas = ("FAIL", "NoneType", "IncompleteRead", "0 entradas", "fallback legado")
    for root in roots:
        if not root.exists():
            continue
        arquivos = sorted([p for p in root.rglob("*") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)[:40]
        for p in arquivos:
            txt = p.read_text(encoding="utf-8", errors="ignore")[-25000:]
            if not any(m in txt for m in marcas):
                continue
            for m in rx_url.finditer(txt):
                u = m.group(0).rstrip(".,;:")
                if u not in urls:
                    urls.append(u)
                    if len(urls) >= limit:
                        return urls
    return urls


def diagnosticar_e_aplicar_fonte(url: str) -> dict[str, Any]:
    sys.path.insert(0, str(SISTEMA))
    from ururau.coleta.diagnostico_fontes_v130 import diagnostico_completo
    from ururau.coleta.aplicador_diagnostico_v130 import aplicar_sugestao_diagnostico_v130, salvar_relatorio_aplicacao_v131, formatar_relatorio_aplicacao_v130

    diag = diagnostico_completo(url, janela_horas=24)
    info = aplicar_sugestao_diagnostico_v130(diag)
    rel = formatar_relatorio_aplicacao_v130(info)
    salvo = salvar_relatorio_aplicacao_v131(info, rel)
    aplicado = bool((info.get("v131") or {}).get("aplicado") or info.get("rss") or info.get("xml"))
    if aplicado:
        registrar_patch("diagnosticar_e_aplicar_fonte", {"url": url, "salvo": salvo})
    return {"acao": "diagnosticar_e_aplicar_fonte", "url": url, "aplicou": aplicado, "salvo": salvo, "resumo": {"dominio": info.get("dominio"), "estrategia": info.get("estrategia"), "avisos": info.get("avisos")}}


def ciclo(aplicar_fontes: bool = True) -> dict[str, Any]:
    resultado: dict[str, Any] = {"ts": agora(), "acoes": []}
    for fn in (arquivar_sobras_deploy, corrigir_bat_status_nn):
        try:
            resultado["acoes"].append(fn())
        except Exception as exc:
            resultado["acoes"].append({"acao": fn.__name__, "ok": False, "erro": repr(exc)})

    a1 = auditoria()
    resultado["acoes"].append(a1)
    if not a1.get("ok"):
        resultado["acoes"].append(reparo_neural())
        resultado["acoes"].append(auditoria())

    resultado["acoes"].append(testes_contrato())

    if aplicar_fontes:
        cand = urls_problematicas()
        resultado["fontes_candidatas"] = cand
        for u in cand:
            try:
                resultado["acoes"].append(diagnosticar_e_aplicar_fonte(u))
            except Exception as exc:
                resultado["acoes"].append({"acao": "diagnosticar_e_aplicar_fonte", "url": u, "ok": False, "erro": repr(exc)})
    salvar_json(STATUS, resultado)
    return resultado


def main() -> int:
    once = "--once" in sys.argv
    no_sources = "--no-sources" in sys.argv
    interval = INTERVALO
    for arg in sys.argv:
        if arg.startswith("--interval="):
            interval = max(60, int(arg.split("=", 1)[1]))
    registrar("start", {"once": once, "interval": interval, "fontes": not no_sources})
    while True:
        res = ciclo(aplicar_fontes=not no_sources)
        print(json.dumps(res, ensure_ascii=False, default=str), flush=True)
        registrar("cycle_done", {"acoes": len(res.get("acoes", []))})
        if once:
            break
        time.sleep(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
