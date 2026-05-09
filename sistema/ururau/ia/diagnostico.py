"""
ururau.ia.diagnostico — telemetria explícita da IA editorial.

Objetivo:
- Registrar se o GPT realmente foi chamado.
- Diferenciar saída OpenAI de fallback local.
- Persistir erro/motivo sem expor chave de API.
- Alimentar painel, logs e dados_json da matéria.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TZ_BR = ZoneInfo("America/Sao_Paulo")


def agora_br_iso() -> str:
    return datetime.now(TZ_BR).isoformat(timespec="seconds")


def mask_secret(value: str, keep_start: int = 7, keep_end: int = 4) -> str:
    """Mascara segredos para logs. Nunca grave a chave completa."""
    value = str(value or "").strip()
    if not value:
        return ""
    if len(value) <= keep_start + keep_end:
        return value[:2] + "..."
    return value[:keep_start] + "..." + value[-keep_end:]


def _logs_dir() -> Path:
    base = Path(os.getenv("PASTA_LOGS", "logs"))
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base


def registrar_evento_ia(
    etapa: str,
    status: str,
    modelo: str = "",
    provider: str = "openai",
    mensagem: str = "",
    uid: str = "",
    detalhes: dict | None = None,
    sucesso: bool | None = None,
) -> dict:
    """Grava evento em JSONL + log legível e devolve o próprio evento."""
    detalhes = dict(detalhes or {})
    evento = {
        "ts": agora_br_iso(),
        "uid": str(uid or ""),
        "etapa": str(etapa or ""),
        "provider": str(provider or ""),
        "modelo": str(modelo or ""),
        "status": str(status or ""),
        "sucesso": bool(sucesso) if sucesso is not None else str(status or "").lower() in {"ok", "openai_ok", "gpt_ok"},
        "mensagem": str(mensagem or "")[:1000],
        "detalhes": detalhes,
    }
    try:
        d = _logs_dir()
        with (d / "ia_diagnostico.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(evento, ensure_ascii=False) + "\n")
        linha = (
            f"[{evento['ts']}] [{evento['etapa']}] provider={evento['provider']} "
            f"modelo={evento['modelo']} status={evento['status']} sucesso={evento['sucesso']} "
            f"uid={evento['uid']} msg={evento['mensagem']}"
        )
        with (d / "ia_diagnostico.log").open("a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass
    return evento


def classificar_erro_openai(exc: Exception) -> tuple[str, str]:
    """Classifica erro em código estável, sem depender de classes específicas da lib."""
    msg = str(exc or "")
    low = msg.lower()
    if "401" in low or "invalid_api_key" in low or "incorrect api key" in low or "authentication" in low:
        return "openai_invalid_api_key", "Chave OpenAI inválida ou sem permissão."
    if "429" in low or "rate_limit" in low or "insufficient_quota" in low or "quota" in low:
        return "openai_quota_or_rate_limit", "Cota/limite da OpenAI atingido."
    if "timeout" in low or "timed out" in low:
        return "openai_timeout", "Timeout na chamada à OpenAI."
    if "model" in low and ("not found" in low or "does not exist" in low or "invalid" in low):
        return "openai_model_error", "Modelo configurado indisponível ou inválido."
    if "json" in low or "expecting value" in low or "decode" in low:
        return "openai_json_invalid", "A OpenAI respondeu, mas o JSON veio inválido."
    return "openai_call_failed", msg[:280] or "Falha na chamada à OpenAI."


def trace_openai_ok(etapa: str, modelo: str, uid: str = "", detalhe: dict | None = None) -> dict:
    evento = registrar_evento_ia(etapa, "openai_ok", modelo=modelo, provider="openai", uid=uid, mensagem="GPT respondeu com sucesso.", detalhes=detalhe or {}, sucesso=True)
    return {
        "ok": True,
        "provider": "openai",
        "modelo": modelo,
        "status": "openai_ok",
        "etapa": etapa,
        "timestamp": evento["ts"],
        "erro_codigo": "",
        "erro_mensagem": "",
    }


def trace_openai_erro(etapa: str, modelo: str, exc: Exception | str, uid: str = "", detalhe: dict | None = None) -> dict:
    if isinstance(exc, Exception):
        codigo, mensagem = classificar_erro_openai(exc)
        bruto = str(exc)
    else:
        codigo, mensagem, bruto = "openai_error", str(exc), str(exc)
    evento = registrar_evento_ia(etapa, codigo, modelo=modelo, provider="openai", uid=uid, mensagem=mensagem, detalhes={**(detalhe or {}), "erro_bruto": bruto[:700]}, sucesso=False)
    return {
        "ok": False,
        "provider": "openai",
        "modelo": modelo,
        "status": codigo,
        "etapa": etapa,
        "timestamp": evento["ts"],
        "erro_codigo": codigo,
        "erro_mensagem": mensagem,
    }


def trace_fallback(etapa: str, modelo: str = "", motivo: str = "", uid: str = "", origem: str = "fallback_local") -> dict:
    evento = registrar_evento_ia(etapa, "fallback_local", modelo=modelo, provider="local", uid=uid, mensagem=motivo or "Fallback local usado.", detalhes={"origem": origem}, sucesso=False)
    return {
        "ok": False,
        "provider": "local",
        "modelo": modelo,
        "status": "fallback_local",
        "etapa": etapa,
        "timestamp": evento["ts"],
        "erro_codigo": "fallback_local",
        "erro_mensagem": motivo or "Fallback local usado.",
    }


def aplicar_trace_em_dados(
    dados: dict,
    trace: dict | None,
    fallback_motivo: str = "",
    original_trace: dict | None = None,
) -> dict:
    """Anexa metadados de IA em dict de matéria/pacote editorial.

    v46.8: os campos de diagnóstico são autoritativos e não usam ``setdefault``.
    Isso evita que uma camada legada/GPT devolva ``ia_ou_engine`` ou status vazio e
    mascare o caminho real de geração. Quando a OpenAI falha e o texto final vem
    de fallback local, ``modo_geracao`` fica ``fallback_sem_ia`` e ``ia_status``
    preserva o erro raiz da OpenAI quando houver.
    """
    dados = dict(dados or {})
    trace = dict(trace or {})
    original_trace = dict(original_trace or dados.get("ia_erro_original_openai") or {})

    final_provider = trace.get("provider") or "local"
    final_ok = bool(trace.get("ok"))
    final_modelo = trace.get("modelo") or original_trace.get("modelo") or dados.get("ia_modelo") or ""
    original_status = original_trace.get("status") or ""

    modo = "openai_gpt4mini" if final_ok and final_provider == "openai" else "fallback_sem_ia"
    status = trace.get("status") or "indefinido"
    if modo == "fallback_sem_ia" and original_status and str(original_trace.get("provider") or "") == "openai":
        status = original_status

    motivo = (
        fallback_motivo
        or (original_trace.get("erro_mensagem") if original_trace else "")
        or trace.get("erro_mensagem")
        or ""
    )
    erros = []
    if original_trace and not original_trace.get("ok"):
        erros.append(original_trace)
    if trace and not trace.get("ok") and trace not in erros:
        erros.append(trace)

    dados["modo_geracao"] = modo
    dados["ia_provider"] = final_provider
    dados["ia_modelo"] = final_modelo
    dados["ia_status"] = status
    dados["ia_etapa"] = trace.get("etapa") or original_trace.get("etapa") or ""
    dados["ia_chamada_ok"] = bool(final_ok and final_provider == "openai")
    dados["ia_fallback_motivo"] = motivo
    dados["ia_erros"] = [] if dados["ia_chamada_ok"] else erros
    dados["ia_trace"] = trace
    dados["_ia_trace"] = trace
    dados["ia_texto_final_origem"] = "openai" if dados["ia_chamada_ok"] else "fallback_local"
    if original_trace:
        dados["ia_erro_original_openai"] = original_trace
        dados["ia_openai_status"] = original_trace.get("status") or status
        dados["ia_openai_chamada_ok"] = bool(original_trace.get("ok"))
    else:
        dados.setdefault("ia_openai_status", status if final_provider == "openai" else "")
        dados.setdefault("ia_openai_chamada_ok", bool(final_ok and final_provider == "openai"))
    return dados


def aplicar_trace_em_materia(
    materia: Any,
    trace: dict | None,
    fallback_motivo: str = "",
    original_trace: dict | None = None,
) -> Any:
    """Propaga metadados de IA para Materia/dict e generated_article_json."""
    if materia is None:
        return materia
    trace = dict(trace or {})
    original_trace = dict(original_trace or {})
    final_provider = trace.get("provider") or "local"
    final_ok = bool(trace.get("ok"))
    modo = "openai_gpt4mini" if final_ok and final_provider == "openai" else "fallback_sem_ia"
    status = trace.get("status") or "indefinido"
    if modo == "fallback_sem_ia" and original_trace.get("status") and str(original_trace.get("provider") or "") == "openai":
        status = original_trace.get("status")
    motivo = fallback_motivo or original_trace.get("erro_mensagem") or trace.get("erro_mensagem") or ""
    erros = []
    if original_trace and not original_trace.get("ok"):
        erros.append(original_trace)
    if trace and not trace.get("ok") and trace not in erros:
        erros.append(trace)
    values = {
        "modo_geracao": modo,
        "ia_provider": final_provider,
        "ia_modelo": trace.get("modelo") or original_trace.get("modelo") or "",
        "ia_status": status,
        "ia_etapa": trace.get("etapa") or original_trace.get("etapa") or "",
        "ia_chamada_ok": bool(final_ok and final_provider == "openai"),
        "ia_fallback_motivo": motivo,
        "ia_erros": [] if (final_ok and final_provider == "openai") else erros,
        "ia_texto_final_origem": "openai" if (final_ok and final_provider == "openai") else "fallback_local",
        "ia_openai_status": original_trace.get("status") or (status if final_provider == "openai" else ""),
        "ia_openai_chamada_ok": bool(original_trace.get("ok") or (final_ok and final_provider == "openai")),
    }
    try:
        for k, v in values.items():
            if isinstance(materia, dict):
                materia[k] = v
            else:
                setattr(materia, k, v)
    except Exception:
        pass
    try:
        if isinstance(materia, dict):
            gj = dict(materia.get("generated_article_json", {}) or {})
        else:
            gj = dict(getattr(materia, "generated_article_json", {}) or {})
        gj.update(values)
        gj["ia_trace"] = trace
        gj["_ia_trace"] = trace
        if original_trace:
            gj["ia_erro_original_openai"] = original_trace
        if isinstance(materia, dict):
            materia["generated_article_json"] = gj
        else:
            setattr(materia, "generated_article_json", gj)
    except Exception:
        pass
    try:
        hist = materia.get("historico_correcoes", []) if isinstance(materia, dict) else getattr(materia, "historico_correcoes", [])
        hist = list(hist or [])
        hist.append({"etapa": "ia_diagnostico", **values, "trace": trace, "original_trace": original_trace})
        if isinstance(materia, dict):
            materia["historico_correcoes"] = hist
        else:
            setattr(materia, "historico_correcoes", hist)
    except Exception:
        pass
    return materia
