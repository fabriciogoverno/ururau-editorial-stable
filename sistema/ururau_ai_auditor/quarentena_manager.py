import json
from pathlib import Path
from datetime import datetime, UTC

BASE_DIR = Path(__file__).resolve().parent
QUARENTENA_DIR = BASE_DIR / "quarentena_fontes"

ARQ_BLOQUEADOS = QUARENTENA_DIR / "dominios_bloqueados.json"
ARQ_REINCIDENCIA = QUARENTENA_DIR / "reincidencia.json"
ARQ_CONFIG = QUARENTENA_DIR / "config_quarentena.json"


def _load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_json(path, payload):
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def obter_config():
    return _load_json(ARQ_CONFIG, {})


def obter_bloqueados():
    data = _load_json(
        ARQ_BLOQUEADOS,
        {"bloqueados": [], "ultima_atualizacao": None}
    )
    return set(data.get("bloqueados", []))


def dominio_esta_bloqueado(dominio):
    return dominio in obter_bloqueados()


def registrar_falha(dominio):
    data = _load_json(
        ARQ_REINCIDENCIA,
        {"dominios": {}, "ultima_atualizacao": None}
    )

    dominios = data.setdefault("dominios", {})

    atual = dominios.get(dominio, 0)
    atual += 1

    dominios[dominio] = atual
    data["ultima_atualizacao"] = datetime.now(UTC).isoformat()

    _save_json(ARQ_REINCIDENCIA, data)

    config = obter_config()
    limite = config.get("limite_reincidencia", 3)

    if atual >= limite:
        bloquear_dominio(dominio)

    return atual


def bloquear_dominio(dominio):
    data = _load_json(
        ARQ_BLOQUEADOS,
        {"bloqueados": [], "ultima_atualizacao": None}
    )

    bloqueados = set(data.get("bloqueados", []))
    bloqueados.add(dominio)

    data["bloqueados"] = sorted(list(bloqueados))
    data["ultima_atualizacao"] = datetime.now(UTC).isoformat()

    _save_json(ARQ_BLOQUEADOS, data)


if __name__ == "__main__":
    teste = "dominio-teste.com"

    for _ in range(3):
        registrar_falha(teste)

    print("bloqueado:", dominio_esta_bloqueado(teste))
