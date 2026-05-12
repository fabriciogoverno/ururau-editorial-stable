# -*- coding: utf-8 -*-
"""Diagnostico das credenciais OpenAI/CMS, sem expor chave.

spec_claudio_ia_real_gpt4mini_regras_editoriais §14.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CHAVES = (
    "OPENAI_API_KEY", "OPENAI_MODEL", "MODELO_OPENAI",
    "URURAU_LOGIN", "URURAU_SENHA", "URURAU_ASSINATURA",
    "SITE_LOGIN_URL", "SITE_NOVA_URL",
)

CAMINHOS_ENV = (
    ".env", "sistema/.env", "credenciais/.env",
    "sistema/credenciais/.env", "sistema/credenciais/env_principal.env",
)


def _redigir(v: str) -> str:
    if not v:
        return ""
    if len(v) <= 10:
        return "***"
    return f"{v[:4]}...{v[-4:]}"


def _ler_env_file(p: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        if not p.exists() or not p.is_file():
            return out
        for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def main() -> dict:
    root = Path(__file__).resolve().parent
    res: dict[str, dict] = {}

    # Ambiente atual
    res["ambiente_processo"] = {
        k: {
            "presente": bool(os.getenv(k)),
            "valor_redigido": _redigir(os.getenv(k, "")),
        } for k in CHAVES
    }

    # Arquivos .env
    for rel in CAMINHOS_ENV:
        p = (root / rel) if not rel.startswith("sistema/") else (root.parent / rel)
        # tentar tambem a partir do projeto raiz (sistema/ esta dentro)
        alt = (root.parent / rel)
        p_real = p if p.exists() else alt
        if p_real.exists():
            envs = _ler_env_file(p_real)
            res[f"env_file::{rel}"] = {
                "encontrado": True,
                "path": str(p_real),
                "valores": {
                    k: {
                        "presente": k in envs,
                        "valor_redigido": _redigir(envs.get(k, "")),
                    } for k in CHAVES
                },
            }
        else:
            res[f"env_file::{rel}"] = {"encontrado": False}

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return res


if __name__ == "__main__":
    main()
