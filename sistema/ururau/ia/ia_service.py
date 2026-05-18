# -*- coding: utf-8 -*-
"""ia_service — servico oficial e auditavel de IA do Ururau Editorial.

spec_claudio_ia_real_gpt4mini_regras_editoriais §9: centraliza
acesso a OpenAI e padroniza retorno para Redigir/Copydesk.

Regras inegociaveis:

1. Modelo padrao: gpt-4.1-mini (overridavel por OPENAI_MODEL ou MODELO_OPENAI).
2. Se OPENAI_API_KEY estiver ausente, ia_chamada=False e erro_tipo='credencial_ausente'.
3. Se a API falhar, ia_chamada=False e erro_tipo classificado.
4. Toda chamada gera linha JSONL em sistema/logs/ia_execucao.log SEM chave.
5. Fallback local NAO marca ia_chamada=True. fallback_sem_ia=True bloqueia publicacao.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

MODELO_PADRAO = "gpt-4.1-mini"
ENDPOINT_PADRAO = "chat.completions"


def _agora_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _redigir_chave(chave: str) -> str:
    """Versao redigida da chave para log (nunca completa)."""
    if not chave:
        return ""
    if len(chave) <= 10:
        return "***"
    return f"{chave[:4]}...{chave[-4:]}"


def _logs_dir() -> Path:
    base = Path(__file__).resolve().parents[2] / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _registrar_log(payload: dict) -> None:
    try:
        fp = _logs_dir() / "ia_execucao.log"
        # nunca persistir chave completa
        sanitizado = dict(payload)
        if "api_key" in sanitizado:
            sanitizado["api_key"] = _redigir_chave(sanitizado.get("api_key") or "")
        with fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(sanitizado, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def carregar_config_ia() -> dict:
    """Le configuracao de IA do ambiente / settings do projeto.

    Retorno:
        {
          "modelo": str,                # gpt-4.1-mini default
          "endpoint": str,              # chat.completions
          "openai_key_presente": bool,
          "api_key_redacted": str,      # so para diagnostico
          "max_tokens": int,
          "temperature": float,
        }
    """
    chave = os.getenv("OPENAI_API_KEY", "").strip()
    modelo = (os.getenv("OPENAI_MODEL", "").strip()
              or os.getenv("MODELO_OPENAI", "").strip()
              or MODELO_PADRAO)
    endpoint = os.getenv("OPENAI_ENDPOINT", "").strip() or ENDPOINT_PADRAO
    try:
        max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2400"))
    except Exception:
        max_tokens = 2400
    try:
        temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.4"))
    except Exception:
        temperature = 0.4
    return {
        "modelo": modelo,
        "endpoint": endpoint,
        "openai_key_presente": bool(chave),
        "api_key_redacted": _redigir_chave(chave),
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


def diagnosticar_ia() -> dict:
    """Diagnostico nao destrutivo: nao chama OpenAI."""
    cfg = carregar_config_ia()
    return {
        "openai_key_presente": cfg["openai_key_presente"],
        "modelo_configurado": cfg["modelo"],
        "endpoint_usado": cfg["endpoint"],
        "modelo_e_padrao_ururau": cfg["modelo"].lower().startswith("gpt-4.1")
                                  or cfg["modelo"].lower().startswith("gpt-4o"),
        "api_key_redacted": cfg["api_key_redacted"],
    }


def _resposta_base(acao: str, cfg: dict) -> dict:
    return {
        "ok": False,
        "ia_chamada": False,
        "modelo": cfg["modelo"],
        "endpoint": cfg["endpoint"],
        "request_id": None,
        "response_id": None,
        "prompt_chars": 0,
        "resposta_chars": 0,
        "erro_tipo": None,
        "erro_msg": None,
        "conteudo": None,
        "fallback_sem_ia": False,
        "publicar_bloqueado": True,
        "acao": acao,
    }


def _erro_classificado(exc: Exception) -> tuple[str, str]:
    msg = str(exc)
    low = msg.lower()
    if any(k in low for k in ("api key", "apikey", "401", "credencial", "credential", "token", "unauthorized")):
        return "credencial_ausente_ou_invalida", msg
    if any(k in low for k in ("model", "modelo", "404", "not found", "no such model")):
        return "modelo_invalido", msg
    if any(k in low for k in ("connection", "timeout", "network", "dns", "ssl", "tls", "503", "502", "rate", "429")):
        return "rede_ou_rate_limit", msg
    return "erro_ia_generico", msg


def _build_prompt_sistema(regras_extras: list[str] | None = None,
                          pauta: dict | None = None,
                          fonte_texto: str = "",
                          editoria: str | None = None) -> str:
    """V200_55 (Fase 2): unifica o prompt mestre numa unica fonte de verdade.

    Ordem de prioridade:
      1. linha_editorial_ururau.build_prompt_redigir(pauta, fonte, editoria)
         - caminho canonico, usa SYSTEM_PROMPT_EDITORIAL_URURAU completo
      2. editorial_policy.get_editorial_system_prompt()
         - reexporta o SYSTEM_PROMPT_EDITORIAL_URURAU do agente canonico
         - acopla matriz JSON via montar_bloco_prompt_editorial()
      3. Prompt legado minimo (compatibilidade)

    Loga qual versao foi usada para rastreabilidade.
    """
    # ESCADA 1: linha editorial ururau (caminho preferido)
    try:
        from ururau.editorial.linha_editorial_ururau import build_prompt_redigir
        base = build_prompt_redigir(pauta or {}, fonte_texto or "", editoria)
        if base and len(base) > 500:  # sanidade: deve ser substancial
            if regras_extras:
                base += "\n\nRegras adicionais:\n- " + "\n- ".join(regras_extras)
            try:
                print(f"[IA][V200_55] prompt_sistema=linha_editorial_ururau ({len(base)} chars)")
            except Exception:
                pass
            return base
    except Exception as _e_lin:
        try:
            print(f"[IA][V200_55] linha_editorial_ururau indisponivel: {_e_lin}")
        except Exception:
            pass

    # ESCADA 2: editorial_policy + matriz JSON acoplada
    try:
        from ururau.editorial.editorial_policy import get_editorial_system_prompt
        sys_prompt = get_editorial_system_prompt() or ""
        if sys_prompt and len(sys_prompt) > 500:
            # Anexa o bloco da matriz central com limites e termos proibidos
            try:
                from ururau.editorial.regras_editoriais import montar_bloco_prompt_editorial
                bloco_matriz = montar_bloco_prompt_editorial()
                if bloco_matriz:
                    sys_prompt = sys_prompt.rstrip() + "\n\n" + bloco_matriz
            except Exception:
                pass
            if regras_extras:
                sys_prompt += "\n\nRegras adicionais:\n- " + "\n- ".join(regras_extras)
            try:
                print(f"[IA][V200_55] prompt_sistema=editorial_policy ({len(sys_prompt)} chars)")
            except Exception:
                pass
            return sys_prompt
    except Exception as _e_ep:
        try:
            print(f"[IA][V200_55] editorial_policy indisponivel: {_e_ep}")
        except Exception:
            pass

    # ESCADA 3: fallback legado minimo (compat com versoes antigas)
    base = (
        "Voce e o redator-chefe do portal jornalistico Ururau. "
        "Receba o texto integral da fonte e produza materia em portugues do Brasil. "
        "Saida obrigatoria: JSON valido com as chaves "
        "titulo_seo, subtitulo_curto, titulo_capa, legenda_curta, retranca, "
        "tags, fonte, credito_foto, corpo_materia. Nao adicione campos extras. "
        "Sem texto fora do JSON. Sem cercas markdown.\n"
        "Regras editoriais:\n"
        "- Nao inventar fato, cargo, valor, data, orgao, acusacao ou declaracao.\n"
        "- Nao transformar investigacao/suspeita/apuracao em condenacao.\n"
        "- Quando a informacao nao for confirmada, usar formula cautelosa "
        "  ('segundo a fonte', 'a apuracao aponta', 'a suspeita e', etc).\n"
        "- Documento/mensagem nao verificado: 'supostas mensagens atribuidas a...', "
        "  'a autenticidade nao foi confirmada'.\n"
        "- titulo_seo ate 89 caracteres. titulo_capa ate 60. "
        "  retranca 1-3 palavras. tags separadas por virgula sem hashtag.\n"
        "- corpo_materia: minimo 4 paragrafos quando ha informacao suficiente; "
        "  cada paragrafo ate 650 caracteres; sem travessao no corpo.\n"
        "- Para fonte longa, use corpo proporcional: 5+ paragrafos acima de 1.400 chars, "
        "6+ acima de 2.600 chars e 7+ acima de 4.200 chars, sem encher com frases vazias.\n"
        "- Abertura direta com o fato principal. Hierarquia jornalistica. "
        "  Sem tom de release, sem linguagem infantil.\n"
        "- Reorganizar os fatos, nao parafrasear linha a linha.\n"
        "- Nao cite no corpo o veiculo de origem que apurou/publicou a materia. "
        "Use o campo fonte/link para credito e atribua no texto a autoridade, documento, empresa, defesa ou orgao citado na fonte.\n"
        "- Nao repetir formula fixa entre materias. A estrutura deve nascer dos fatos concretos da fonte.\n"
        "- Termos proibidos serao bloqueados em pos-processamento; evite-os.\n"
    )
    if regras_extras:
        base += "\nRegras adicionais:\n- " + "\n- ".join(regras_extras)
    try:
        print(f"[IA][V200_55] prompt_sistema=fallback_legado ({len(base)} chars) - matriz central indisponivel")
    except Exception:
        pass
    return base


def _build_prompt_user_redigir(texto_fonte: str, pauta: dict | None) -> str:
    titulo = (pauta or {}).get("titulo_origem") or ""
    fonte = (pauta or {}).get("fonte_nome") or ""
    link = (pauta or {}).get("link_origem") or ""
    return (
        f"PAUTA: {titulo}\nFONTE: {fonte}\nLINK: {link}\n\n"
        f"TEXTO INTEGRAL DA FONTE (use somente o que esta aqui):\n{texto_fonte}\n\n"
        "Tarefa: redija a materia completa em JSON valido."
    )


def _build_prompt_user_copydesk(materia: dict, fonte_texto: str = "") -> str:
    bruto = json.dumps(materia, ensure_ascii=False, default=str)[:12000]
    extra = ""
    if fonte_texto:
        extra = "\n\nFONTE INTEGRAL (validada):\n" + str(fonte_texto)[:12000]
    return (
        "Voce esta no Copydesk. Refine a materia abaixo aplicando as regras "
        "editoriais do Ururau. Retorne JSON com os mesmos campos. "
        "Nao invente. Nao mude o sentido. Remova termos proibidos.\n\n"
        f"{bruto}{extra}"
    )


def _call_openai(prompt_sistema: str, prompt_user: str, cfg: dict) -> dict:
    """Chama OpenAI usando o SDK >= 1.x. Retorna dict com ia_chamada e demais."""
    out = _resposta_base("openai_call", cfg)
    if not cfg["openai_key_presente"]:
        out["erro_tipo"] = "credencial_ausente"
        out["erro_msg"] = "OPENAI_API_KEY ausente no ambiente."
        return out
    try:
        from openai import OpenAI
    except Exception as e:
        out["erro_tipo"] = "sdk_ausente"
        out["erro_msg"] = f"SDK openai indisponivel: {e}"
        return out
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        t0 = time.time()
        resp = client.chat.completions.create(
            model=cfg["modelo"],
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_user},
            ],
            temperature=cfg.get("temperature", 0.4),
            max_tokens=cfg.get("max_tokens", 2400),
            response_format={"type": "json_object"},
        )
        dt = time.time() - t0
        out["ia_chamada"] = True
        out["request_id"] = getattr(resp, "id", None)
        out["response_id"] = getattr(resp, "id", None)
        out["modelo"] = getattr(resp, "model", cfg["modelo"]) or cfg["modelo"]
        try:
            texto = resp.choices[0].message.content
        except Exception:
            texto = ""
        out["resposta_chars"] = len(texto or "")
        out["prompt_chars"] = len(prompt_sistema) + len(prompt_user)
        out["latencia_s"] = round(dt, 3)
        try:
            out["conteudo"] = json.loads(texto)
        except Exception as je:
            out["erro_tipo"] = "json_invalido"
            out["erro_msg"] = f"Resposta nao e JSON valido: {je}"
            out["conteudo"] = {"_texto_bruto": texto}
            return out
        out["ok"] = True
        out["publicar_bloqueado"] = False
        return out
    except Exception as e:
        tipo, msg = _erro_classificado(e)
        out["erro_tipo"] = tipo
        out["erro_msg"] = msg
        return out


def executar_ia_redigir(pauta: dict, texto_fonte: str,
                        regras_extras: list[str] | None = None) -> dict:
    """Chama IA real para redigir. Retorno padronizado.

    Pos-IA, valida o pacote contra a fonte (factual + SEO + termos proibidos).
    Se reprovar, tenta UMA regeneracao com prompt corretivo. Em ambos os casos,
    o resultado tras res['auditoria_copydesk'] com o relatorio.
    """
    cfg = carregar_config_ia()
    # spec_auditoria_global §12: limpar boilerplate ANTES da IA, sem perder o
    # texto original (mantemos cache para auditoria pos).
    texto_fonte_original = texto_fonte
    try:
        from ururau.editorial.validador_boilerplate import (
            limpar_boilerplate_fonte, fonte_tem_boilerplate_critico,
        )
        if fonte_tem_boilerplate_critico(texto_fonte or ""):
            # bloqueio explicito antes da IA
            base = _resposta_base("redigir", cfg)
            base["erro_tipo"] = "FONTE_COM_BOILERPLATE_CRITICO"
            base["erro_msg"] = "Fonte e majoritariamente boilerplate (login/newsletter/publicidade). Recoletar."
            base["publicar_bloqueado"] = True
            return base
        _limp = limpar_boilerplate_fonte(texto_fonte or "")
        texto_fonte = _limp["texto_limpo"] or (texto_fonte or "")
    except Exception:
        pass
    # detecta editoria para regras especificas no prompt
    try:
        from ururau.editorial.regras_editoriais_ururau import categorizar_editoria
        editoria = categorizar_editoria(
            titulo=(pauta or {}).get("titulo_origem") or "",
            fonte_texto=texto_fonte or "",
            link=(pauta or {}).get("link_origem") or "",
        )
    except Exception:
        editoria = "geral"
    prompt_sistema = _build_prompt_sistema(regras_extras, pauta=pauta,
                                            fonte_texto=texto_fonte,
                                            editoria=editoria)
    prompt_user = _build_prompt_user_redigir(texto_fonte or "", pauta)
    res = _call_openai(prompt_sistema, prompt_user, cfg)
    res["acao"] = "redigir"
    res["editoria"] = editoria

    # Pos-processamento OBRIGATORIO: conserta defeitos tipicos do GPT
    # (dedup de frases, aspas tipograficas, pontuacao, titulo SEO truncado).
    # Roda ANTES da auditoria editorial — o validador deve ver o pacote ja
    # corrigido.
    if res.get("ok") and isinstance(res.get("conteudo"), dict):
        try:
            from ururau.editorial.pos_processador_redacao import (
                aplicar_metricas_seo_google,
            )
            pp = aplicar_metricas_seo_google(
                {
                    **res["conteudo"],
                    "_veiculo_origem_para_remover": (pauta or {}).get("fonte_nome") or "",
                    "link_da_fonte": (pauta or {}).get("link_origem") or "",
                },
                fonte_texto=texto_fonte or "",
                palavra_chave="",
            )
            res["conteudo"] = pp["pacote"]
            res["pos_processador"] = {
                "correcoes": pp["correcoes"],
                "diagnostico": pp["diagnostico"],
            }
        except Exception as _e_pp:
            res["pos_processador"] = {"erro": str(_e_pp)}

    # Auditoria pos-IA + regeneracao opcional.
    if res.get("ok") and isinstance(res.get("conteudo"), dict):
        try:
            from ururau.editorial.validador_copydesk import (
                auditar_copydesk, validar_tudo_antes_de_salvar,
            )
            from ururau.editorial.linha_editorial_ururau import (
                build_prompt_regeneracao,
            )
            # Pipeline completo (factual + seo + termos + boilerplate na materia)
            pipeline = validar_tudo_antes_de_salvar(res["conteudo"], texto_fonte or "")
            aud = auditar_copydesk(res["conteudo"], texto_fonte or "")
            aud["pipeline"] = pipeline
            aud["copydesk_ok"] = aud["copydesk_ok"] and pipeline["ok"]
            res["auditoria_copydesk"] = aud
            if not aud["copydesk_ok"]:
                # Tenta regenerar UMA vez.
                user_regen = build_prompt_regeneracao(
                    res["conteudo"], aud["problemas"], texto_fonte or ""
                )
                res2 = _call_openai(prompt_sistema, user_regen, cfg)
                if res2.get("ok") and isinstance(res2.get("conteudo"), dict):
                    aud2 = auditar_copydesk(res2["conteudo"], texto_fonte or "")
                    res2["auditoria_copydesk"] = aud2
                    res2["editoria"] = editoria
                    res2["acao"] = "redigir"
                    # Se 2a tentativa passou, troca; senao mantem a primeira mas
                    # marca publicar_bloqueado=True.
                    if aud2["copydesk_ok"]:
                        res = res2
                    else:
                        res["publicar_bloqueado"] = True
                        res["erro_tipo"] = res.get("erro_tipo") or "VALIDACAO_EDITORIAL_REPROVADA"
                        res["erro_msg"] = (res.get("erro_msg") or "") + " | regen falhou: " + ";".join(aud2["problemas"][:4])
                else:
                    res["publicar_bloqueado"] = True
                    res["erro_tipo"] = res.get("erro_tipo") or "VALIDACAO_EDITORIAL_REPROVADA"
                    res["erro_msg"] = (res.get("erro_msg") or "") + " | regen falhou na chamada"
        except Exception as _e_aud:
            res["auditoria_copydesk"] = {"copydesk_ok": False,
                                          "problemas": [f"validador_falhou:{_e_aud}"],
                                          "motivo_bloqueio": "validador_indisponivel"}
    _registrar_log({
        "timestamp": _agora_iso(),
        "acao": "redigir",
        "pauta_uid": (pauta or {}).get("uid") or (pauta or {}).get("_uid") or "",
        "modelo": res["modelo"],
        "endpoint": res["endpoint"],
        "ia_chamada": res["ia_chamada"],
        "fallback_sem_ia": res["fallback_sem_ia"],
        "fonte_chars": len(texto_fonte or ""),
        "prompt_chars": res["prompt_chars"],
        "resposta_chars": res["resposta_chars"],
        "request_id": res["request_id"],
        "status": "ok" if res["ok"] else "erro",
        "erro_tipo": res["erro_tipo"],
    })
    return res


def executar_ia_copydesk(materia: dict,
                         regras_extras: list[str] | None = None,
                         fonte_texto: str = "") -> dict:
    """Copydesk usa prompt mais rigoroso e nao inventa."""
    cfg = carregar_config_ia()
    try:
        from ururau.editorial.linha_editorial_ururau import (
            build_prompt_copydesk, build_prompt_user_copydesk,
        )
        from ururau.editorial.regras_editoriais_ururau import categorizar_editoria
        from ururau.editorial.validador_copydesk import auditar_copydesk
        # pre-auditoria para incluir lista de problemas no prompt
        pre = auditar_copydesk(materia or {}, fonte_texto or "")
        editoria = categorizar_editoria(
            titulo=(materia or {}).get("titulo_seo") or "",
            fonte_texto=fonte_texto or "",
        )
        prompt_sistema = build_prompt_copydesk(materia or {}, fonte_texto or "",
                                                editoria=editoria,
                                                problemas=pre["problemas"])
        prompt_user = build_prompt_user_copydesk(materia or {}, fonte_texto or "")
    except Exception:
        prompt_sistema = _build_prompt_sistema(regras_extras)
        prompt_user = _build_prompt_user_copydesk(materia or {})
        pre = None
    res = _call_openai(prompt_sistema, prompt_user, cfg)
    res["acao"] = "copydesk"
    if pre is not None:
        res["auditoria_copydesk_pre"] = pre
    # auditoria pos-resposta
    try:
        if res.get("ok") and isinstance(res.get("conteudo"), dict):
            from ururau.editorial.validador_copydesk import auditar_copydesk
            res["auditoria_copydesk"] = auditar_copydesk(
                res["conteudo"], fonte_texto or "",
            )
            if not res["auditoria_copydesk"]["copydesk_ok"]:
                res["publicar_bloqueado"] = True
    except Exception:
        pass
    _registrar_log({
        "timestamp": _agora_iso(),
        "acao": "copydesk",
        "pauta_uid": (materia or {}).get("pauta_uid") or "",
        "modelo": res["modelo"],
        "endpoint": res["endpoint"],
        "ia_chamada": res["ia_chamada"],
        "fallback_sem_ia": res["fallback_sem_ia"],
        "prompt_chars": res["prompt_chars"],
        "resposta_chars": res["resposta_chars"],
        "request_id": res["request_id"],
        "status": "ok" if res["ok"] else "erro",
        "erro_tipo": res["erro_tipo"],
    })
    return res


def executar_ia_comando(tipo: str, payload: dict,
                        regras_extras: list[str] | None = None) -> dict:
    cfg = carregar_config_ia()
    prompt_sistema = _build_prompt_sistema(regras_extras)
    user = json.dumps(payload or {}, ensure_ascii=False, default=str)[:14000]
    prompt_user = f"Comando: {tipo}\n\nPayload:\n{user}"
    res = _call_openai(prompt_sistema, prompt_user, cfg)
    res["acao"] = tipo
    _registrar_log({
        "timestamp": _agora_iso(),
        "acao": tipo,
        "modelo": res["modelo"],
        "endpoint": res["endpoint"],
        "ia_chamada": res["ia_chamada"],
        "prompt_chars": res["prompt_chars"],
        "resposta_chars": res["resposta_chars"],
        "request_id": res["request_id"],
        "status": "ok" if res["ok"] else "erro",
        "erro_tipo": res["erro_tipo"],
    })
    return res


__all__ = [
    "MODELO_PADRAO",
    "ENDPOINT_PADRAO",
    "carregar_config_ia",
    "diagnosticar_ia",
    "executar_ia_redigir",
    "executar_ia_copydesk",
    "executar_ia_comando",
]
