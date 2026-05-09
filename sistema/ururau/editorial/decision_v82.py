"""
ururau/editorial/decision_v82.py

Decisão operacional v82 para o monitor 24h:
- aprovado para direta -> publicar direto no CMS;
- não aprovado para direta, mas editorialmente aproveitável -> salvar como RASCUNHO no painel do Ururau;
- erro fatal -> não enviar ao CMS, salvar localmente com motivo.

Rascunho aqui significa cadastro real no CMS com a opção:
"Não publicar a notícia agora. Salvar como rascunho!" marcada.
"""
from __future__ import annotations

import os
from typing import Any


AVISO_RASCUNHO_URURAU = (
    "AVISO: Esta matéria não foi aprovada para publicação direta. "
    "Foi enviada ao CMS do Ururau como rascunho para revisão humana."
)


def _get(obj: Any, key: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return dict(obj)
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass
    try:
        return dict(vars(obj))
    except Exception:
        return {}


def _bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(str(os.getenv(name, str(default))).strip())
    except Exception:
        return default


def _score(materia: dict, auditoria: dict) -> int:
    for fonte in (auditoria, materia):
        for key in ("score", "score_qualidade", "score_editorial"):
            try:
                val = fonte.get(key)
                if val not in (None, ""):
                    return int(float(val))
            except Exception:
                pass
    return 0


def _text_len(materia: dict) -> int:
    corpo = (
        materia.get("conteudo")
        or materia.get("corpo_materia")
        or materia.get("texto")
        or ""
    )
    return len(str(corpo).strip())


def _has_fatal(materia: dict, auditoria: dict, contexto: dict) -> list[str]:
    motivos: list[str] = []

    titulo = str(materia.get("titulo") or materia.get("titulo_seo") or "").strip()
    corpo_len = _text_len(materia)
    link = str(materia.get("link_origem") or materia.get("linkfonte") or contexto.get("link_origem") or "").strip()
    fonte = str(materia.get("fonte_nome") or materia.get("nome_da_fonte") or contexto.get("fonte_nome") or "").strip()

    if not titulo:
        motivos.append("título vazio")
    if corpo_len < 120:
        motivos.append(f"texto final insuficiente ({corpo_len} caracteres)")
    if not link:
        motivos.append("link de origem ausente")
    if not fonte:
        motivos.append("fonte de origem ausente")

    status = str(materia.get("status_validacao") or "").lower().strip()
    if status in {"erro_configuracao", "erro_extracao"}:
        motivos.append(f"status_validacao fatal: {status}")

    erros = materia.get("erros_validacao") or []
    for erro in erros:
        if isinstance(erro, dict):
            categoria = str(erro.get("categoria") or "").upper()
            if categoria in {"CONFIG_ERROR", "EXTRACTION_ERROR"}:
                motivos.append(f"erro fatal de pipeline: {categoria}")

    if bool(materia.get("_bloqueio_coleta_v83") or contexto.get("_bloqueio_coleta_v83")):
        motivos.append("coleta_texto fail-closed v83: texto da matéria não foi capturado")

    extraction_status = str(materia.get("extraction_status") or contexto.get("extraction_status") or "").lower()
    extraction_method = str(materia.get("extraction_method") or contexto.get("extraction_method") or "").lower()
    if extraction_status == "failed":
        motivos.append("extração da fonte falhou")
    if extraction_method in {"failed", "google_news_unresolved", "rss_only", "source_too_short_v81"}:
        motivos.append(f"método de extração não aceito para publicação: {extraction_method}")

    source_chars = contexto.get("chars_fonte") or contexto.get("texto_fonte_chars") or contexto.get("source_chars")
    min_chars = _int_env("URURAU_MIN_CHARS_FONTE_MONITOR", 350)
    try:
        if source_chars is not None and int(source_chars) < min_chars:
            motivos.append(f"fonte útil insuficiente ({source_chars} caracteres)")
    except Exception:
        pass

    # A auditoria factual continua tendo veto para erro grave.
    contradicoes = auditoria.get("contradicoes") or []
    if contradicoes:
        motivos.append("contradição factual grave: " + "; ".join(map(str, contradicoes[:2])))

    claims = auditoria.get("claims_sem_evidencia") or []
    # Na v82, claims sem evidência continuam fatais quando a própria auditoria marcou status reprovado/bloqueado.
    if claims and str(auditoria.get("status") or "").lower() in {"reprovado", "bloqueado", "bloquear"}:
        motivos.append("dado central sem evidência: " + "; ".join(map(str, claims[:2])))

    risco = materia.get("score_risco_validacao") or materia.get("score_risco") or contexto.get("score_risco") or 0
    try:
        if int(risco) >= int(os.getenv("LIMIAR_RISCO_MAXIMO", "70")):
            motivos.append(f"risco editorial grave ({risco}/100)")
    except Exception:
        pass

    return motivos


def decidir_destino_publicacao_v82(materia: Any, auditoria: dict | None = None, contexto: dict | None = None) -> dict:
    """
    Decide o destino operacional da matéria.

    Retorna:
    {
        "destino": "publicar_direto" | "salvar_rascunho" | "bloquear_total",
        "pode_enviar_cms": bool,
        "rascunho": bool,
        "motivos": list[str],
        "aviso": str | None
    }
    """
    m = _as_dict(materia)
    aud = auditoria if isinstance(auditoria, dict) else (m.get("auditoria_factual_v81") or {})
    if not isinstance(aud, dict):
        aud = {}
    ctx = contexto or {}

    fatal = _has_fatal(m, aud, ctx)
    if fatal:
        return {
            "destino": "bloquear_total",
            "pode_enviar_cms": False,
            "rascunho": True,
            "motivos": fatal,
            "aviso": None,
        }

    publicar_direto_env = _bool_env("URURAU_PUBLICAR_DIRETO", False) or _bool_env("URURAU_CMS_PUBLICACAO_DIRETA", False)
    if contexto is not None and "permitir_publicacao_direta" in ctx:
        publicar_direto_env = publicar_direto_env and bool(ctx.get("permitir_publicacao_direta"))
    rascunho_se_nao_aprovar = _bool_env("URURAU_MONITOR_RASCUNHO_SE_NAO_APROVAR", True)

    termos_ia_motivos: list[str] = []
    try:
        from ururau.editorial.regras_editoriais import validar_termos_ia_em_artigo
        check_ia = validar_termos_ia_em_artigo(m, modo=str(ctx.get("modo_cms") or "monitor"))
        if not check_ia.get("passou", True):
            achados = check_ia.get("achados", []) or []
            termos_ia_motivos = [
                "termo de IA proibido: " + "; ".join(
                    f"{a.get('campo')}={a.get('termo')}" for a in achados[:5]
                )
            ]
            publicar_direto_env = False
    except Exception as e:
        # No monitor, falha na blocklist não pode liberar publicação direta.
        termos_ia_motivos = [f"falha ao validar blocklist de IA: {e}"]
        publicar_direto_env = False

    status = str(m.get("status_validacao") or "").lower().strip()
    auditoria_bloqueada = bool(m.get("auditoria_bloqueada", True))
    aud_status = str(aud.get("status") or "").lower().strip()
    aud_pode_publicar = bool(aud.get("pode_publicar", False))
    score = _score(m, aud)
    min_direta = _int_env("URURAU_SCORE_MINIMO_DIRETA", 90)

    aprovado_para_direta = (
        publicar_direto_env
        and status == "aprovado"
        and not auditoria_bloqueada
        and (not aud_status or aud_status == "aprovado")
        and (aud_pode_publicar or score >= min_direta)
        and score >= min_direta
    )

    if aprovado_para_direta:
        return {
            "destino": "publicar_direto",
            "pode_enviar_cms": True,
            "rascunho": False,
            "motivos": ["aprovada para publicação direta"],
            "aviso": None,
        }

    score_min_rascunho = _int_env("URURAU_SCORE_MINIMO_RASCUNHO", 35)
    if rascunho_se_nao_aprovar and score >= score_min_rascunho:
        motivos = []
        if not publicar_direto_env:
            if ctx.get("permitir_publicacao_direta") is False:
                motivos.append("publicação direta bloqueada pelo modo do monitor")
            else:
                motivos.append("publicação direta desligada no .env")
        motivos.extend(termos_ia_motivos)
        if status != "aprovado":
            motivos.append(f"status_validacao={status or 'ausente'}")
        if auditoria_bloqueada:
            motivos.append("auditoria exige revisão humana")
        if score < min_direta:
            motivos.append(f"score {score} abaixo do mínimo de direta {min_direta}")
        if aud_status and aud_status != "aprovado":
            motivos.append(f"auditoria_factual_status={aud_status}")

        return {
            "destino": "salvar_rascunho",
            "pode_enviar_cms": True,
            "rascunho": True,
            "motivos": motivos or ["não aprovada para direta"],
            "aviso": AVISO_RASCUNHO_URURAU,
        }

    return {
        "destino": "bloquear_total",
        "pode_enviar_cms": False,
        "rascunho": True,
        "motivos": [f"score {score} abaixo do mínimo de rascunho {score_min_rascunho}"],
        "aviso": None,
    }


def aplicar_aviso_rascunho_v82(materia: Any, aviso: str | None = None) -> Any:
    """Registra aviso interno sem inserir texto no corpo público da matéria."""
    aviso = aviso or AVISO_RASCUNHO_URURAU
    if isinstance(materia, dict):
        materia["aviso_rascunho_cms"] = aviso
        materia["status_pipeline"] = "rascunho_cms"
        materia["status_publicacao_sugerido"] = "salvar_rascunho"
        materia["revisao_humana_necessaria"] = True
        return materia

    for key, value in {
        "aviso_rascunho_cms": aviso,
        "status_pipeline": "rascunho_cms",
        "status_publicacao_sugerido": "salvar_rascunho",
        "revisao_humana_necessaria": True,
    }.items():
        try:
            setattr(materia, key, value)
        except Exception:
            pass

    try:
        hist = getattr(materia, "historico_correcoes", None)
        if isinstance(hist, list):
            hist.append({"tipo": "v82_rascunho_cms", "mensagem": aviso})
    except Exception:
        pass

    return materia
