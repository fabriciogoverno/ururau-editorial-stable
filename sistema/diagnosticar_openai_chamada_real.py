# -*- coding: utf-8 -*-
"""Teste controlado de chamada OpenAI.

spec_claudio_ia_real_gpt4mini_regras_editoriais §15.

Faz uma chamada minima com prompt nao-jornalistico para confirmar:
- ia_chamada=True
- modelo correto
- credencial valida
- modelo existente
- sem timeout

Nao usa texto real de materia. Nao publica nada. Nao vaza chave.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def main() -> dict:
    from ururau.ia import ia_service
    cfg = ia_service.carregar_config_ia()

    saida: dict = {
        "modelo_configurado": cfg["modelo"],
        "openai_key_presente": cfg["openai_key_presente"],
        "api_key_redacted": cfg["api_key_redacted"],
        "resultado": None,
        "ia_chamada": False,
        "request_id": None,
        "erro_tipo": None,
        "erro_msg": None,
    }

    if not cfg["openai_key_presente"]:
        saida["resultado"] = "OPENAI_API_KEY_AUSENTE"
        print(json.dumps(saida, ensure_ascii=False, indent=2))
        return saida

    # Prompt minimo, NAO-jornalistico, em JSON.
    res = ia_service.executar_ia_comando(
        "diagnostico_minimo",
        {"echo": "responda apenas {\"ok\": true}"},
    )
    saida["ia_chamada"] = res["ia_chamada"]
    saida["request_id"] = res["request_id"]
    saida["modelo_retornado"] = res["modelo"]
    saida["erro_tipo"] = res["erro_tipo"]
    saida["erro_msg"] = res["erro_msg"]
    saida["latencia_s"] = res.get("latencia_s")

    if res["ia_chamada"] and res["ok"]:
        saida["resultado"] = "IA_OK"
    elif res["erro_tipo"] == "credencial_ausente":
        saida["resultado"] = "OPENAI_API_KEY_AUSENTE"
    elif res["erro_tipo"] == "credencial_ausente_ou_invalida":
        saida["resultado"] = "OPENAI_AUTH_FALHOU"
    elif res["erro_tipo"] == "modelo_invalido":
        saida["resultado"] = "OPENAI_MODEL_INVALIDO"
    elif res["erro_tipo"] == "rede_ou_rate_limit":
        saida["resultado"] = "OPENAI_TIMEOUT_OU_REDE"
    elif res["erro_tipo"] == "sdk_ausente":
        saida["resultado"] = "OPENAI_SDK_ERRO"
    elif res["erro_tipo"] == "json_invalido":
        saida["resultado"] = "IA_RESPOSTA_NAO_JSON"
    else:
        saida["resultado"] = "OPENAI_ERRO_GENERICO"

    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return saida


if __name__ == "__main__":
    main()
