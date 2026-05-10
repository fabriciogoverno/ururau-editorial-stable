# -*- coding: utf-8 -*-
"""Executor persistente da Neural Engine.

O 49_INICIAR_NEURAL.bat anterior iniciava uma thread daemon e encerrava o Python
logo depois. Como thread daemon morre quando o processo principal termina, este
runner mantém o processo vivo e grava heartbeat para auditoria.
"""
from __future__ import annotations

import json
import signal
import time
from datetime import datetime
from pathlib import Path

from neural_service import get_neural

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "sistema" / "dados_ml" / "neural_runner_status.json"
LOG_PATH = ROOT / "sistema" / "dados_ml" / "neural_runner.log"
RUNNING = True


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _log(evento: str, detalhe: dict | None = None) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": _now(), "evento": evento, "detalhe": detalhe or {}}
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def _stop(signum=None, frame=None) -> None:  # noqa: ANN001
    global RUNNING
    RUNNING = False
    _log("stop_signal", {"signum": signum})


def main() -> int:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    neural = get_neural(ROOT)
    neural.start()
    _log("started", {"root": str(ROOT)})

    while RUNNING:
        try:
            status = neural.status()
            payload = {
                "ts": _now(),
                "root": str(ROOT),
                "running": bool(status.get("running")),
                "status": status,
            }
            _write_json(STATUS_PATH, payload)
            print(json.dumps(payload, ensure_ascii=False), flush=True)
        except Exception as exc:  # fail-safe: serviço não deve cair por erro de status
            _log("status_error", {"erro": repr(exc)})
        time.sleep(30)

    try:
        neural.stop()
    except Exception as exc:
        _log("stop_error", {"erro": repr(exc)})
    _log("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
