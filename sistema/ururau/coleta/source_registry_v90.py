"""
source_registry_v90.py
Compatibilidade v90/v91 para registro de fontes.

Este arquivo sobrescreve o registry simplificado do pacote técnico v90 para
usar o loader v91, aceitar JSON com "sources" ou "fontes" e resolver caminhos
do projeto real.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

from ururau.coleta.source_config_loader_v91 import (
    carregar_config_fontes_v91,
    listar_fontes_ativas_v91,
    salvar_config_fontes_v91,
    normalizar_fonte_v91,
)


def safe_get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else default


def carregar_config_fontes(path="config/source_domains_config_v90.json") -> dict:
    return carregar_config_fontes_v91(path)


def salvar_config_fontes(config: dict, path="config/source_domains_config_v90.json") -> None:
    salvar_config_fontes_v91(config, path)


def listar_fontes_ativas(path="config/source_domains_config_v90.json") -> list[dict]:
    return listar_fontes_ativas_v91(path)


def adicionar_fonte(fonte: dict, path="config/source_domains_config_v90.json") -> dict:
    cfg = carregar_config_fontes(path)
    fontes = cfg.get("sources") or cfg.get("fontes") or []
    f = normalizar_fonte_v91(fonte)
    fontes = [x for x in fontes if (x.get("domain") or x.get("dominio")) != (f.get("domain") or f.get("dominio"))]
    fontes.append(f)
    cfg["sources"] = fontes
    cfg["fontes"] = fontes
    cfg["ultima_atualizacao"] = datetime.now(timezone.utc).isoformat()
    salvar_config_fontes(cfg, path)
    return f


def remover_fonte(dominio: str, path="config/source_domains_config_v90.json") -> bool:
    cfg = carregar_config_fontes(path)
    fontes = cfg.get("sources") or cfg.get("fontes") or []
    novo = [f for f in fontes if (f.get("domain") or f.get("dominio")) != dominio]
    mudou = len(novo) != len(fontes)
    cfg["sources"] = novo
    cfg["fontes"] = novo
    salvar_config_fontes(cfg, path)
    return mudou
