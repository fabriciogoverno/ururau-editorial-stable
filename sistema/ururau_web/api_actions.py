# -*- coding: utf-8 -*-
"""ururau_web.api_actions - Acoes editoriais por pauta (Redigir, Copydesk, etc.).

Cada acao roda em thread daemon. O frontend faz polling em
GET /api/pautas/{uid}/job para acompanhar.

REGRAS:
    * Reusa modulos existentes (WorkflowPublicacao, pipeline_copydesk).
    * Nao publica matéria automaticamente: handler_publicar exige confirm=true.
    * Nao reimplementa motor editorial.
"""
from __future__ import annotations

import json
import mimetypes
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from . import api as core


# Cache em memoria das revisoes do Copydesk pendentes de confirmacao do editor.
# Estrutura: {uid: {"materia": dict, "problemas": list, "criada_em": iso}}
# A revisao SO eh aplicada na pauta quando o editor confirma via /salvar-copydesk.
_revisoes_pendentes: dict[str, dict[str, Any]] = {}


# ────────────────────────────────────────────────────────────────────────────
# Helpers locais
# ────────────────────────────────────────────────────────────────────────────

def _carregar_pauta_completa(db, uid: str) -> dict | None:
    p = db.buscar_pauta(uid)
    if not p:
        return None
    try:
        if p.get("dados_json"):
            p = {**p, **(json.loads(p["dados_json"]) or {})}
    except Exception:
        pass
    if uid and not p.get("_uid"):
        p["_uid"] = uid
    return p


def _safe_image_local_path(rel_or_abs: str) -> Path | None:
    """Resolve um caminho local de imagem dentro de pastas seguras."""
    if not rel_or_abs:
        return None
    settings = core._import_settings()
    pasta = Path(getattr(settings, "PASTA_IMAGENS", "imagens"))
    candidatos = []
    p = Path(rel_or_abs)
    if p.is_absolute():
        candidatos.append(p)
    else:
        candidatos.extend([
            p,
            pasta / p.name,
            Path("sistema") / p,
            Path("sistema") / pasta / p.name,
        ])
    raizes_ok = [Path(pasta).resolve(), (Path("sistema") / pasta).resolve()]
    for cand in candidatos:
        try:
            full = cand.resolve()
            if not full.exists() or not full.is_file():
                continue
            if any(str(full).startswith(str(r)) for r in raizes_ok):
                return full
        except Exception:
            continue
    return None


# ────────────────────────────────────────────────────────────────────────────
# Materia (GET) e Job status
# ────────────────────────────────────────────────────────────────────────────

def handler_materia(db, uid: str):
    if not uid:
        return core._error("uid ausente", status=400)
    p = db.buscar_pauta(uid)
    if not p:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    try:
        if p.get("dados_json"):
            p = {**p, **(json.loads(p["dados_json"]) or {})}
    except Exception:
        pass
    md = core._parse_materia_pauta(p) or {}
    return core._json_response({
        "ok": True,
        "uid": uid,
        "materia": md,
        "pronta": bool(md.get("conteudo") or md.get("corpo_materia")),
    })


def handler_job_status(db, uid: str):
    if not uid:
        return core._error("uid ausente", status=400)
    with core._jobs_lock:
        slot = dict(core._jobs.get(uid, {}))
    return core._json_response({"ok": True, "uid": uid, "jobs": slot})


# ────────────────────────────────────────────────────────────────────────────
# Redigir (OpenAI / fallback local)
# ────────────────────────────────────────────────────────────────────────────

def handler_redigir(db, uid: str, body: dict):
    """Dispara redacao reusando WorkflowPublicacao (mesmo motor do desktop)."""
    if not uid:
        return core._error("uid ausente", status=400)
    pauta = _carregar_pauta_completa(db, uid)
    if not pauta:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    status_p = str(pauta.get("status") or "").lower()
    if status_p in {"publicada", "publicado"}:
        return core._error("pauta ja publicada nao pode ser redigida", status=409)
    forcar = bool(body.get("forcar"))
    if status_p in {
        "descartada", "descartado", "rejeitada", "rejeitado",
        "bloqueada", "bloqueado", "reprovada", "reprovado",
        "excluida", "excluido",
    } and not forcar:
        return core._error(
            f"pauta com status '{status_p}'; envie 'forcar=true' para reativar",
            status=409, status_pauta=status_p,
        )

    client, modelo = core._get_openai_client()
    if not client:
        return core._error(
            "OpenAI nao configurado (OPENAI_API_KEY ausente ou invalida)",
            status=503, modelo=modelo,
        )

    with core._jobs_lock:
        atual = core._jobs.get(uid, {}).get("ultimo_job", {})
        if atual.get("em_andamento") and atual.get("tipo") == "redigir":
            return core._json_response(
                {"ok": False, "motivo": "ja_rodando", "job": atual}, status=202,
            )

    core._job_inicio(uid, "redigir")

    def _trabalho():
        try:
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            uid_eff = (
                pauta.get("uid") or pauta.get("_uid")
                or _uid_para_pauta(pauta.get("link_origem", ""), pauta.get("titulo_origem", ""))
            )
            pauta["_uid"] = uid_eff
            wf = WorkflowPublicacao(db, client, modelo)
            if not wf.etapa_gate_antiduplicacao(uid_eff, pauta, modo="redigir"):
                core._job_fim(uid, "redigir", "bloqueado", "gate antiduplicacao bloqueou")
                return
            wf.etapa_coleta_texto(uid_eff, pauta)
            wf.etapa_imagem(uid_eff, pauta)
            materia = wf.etapa_redacao(uid_eff, pauta)
            if not materia:
                core._job_fim(uid, "redigir", "erro", "etapa_redacao nao retornou materia")
                return
            materia = wf.etapa_pacote_editorial(uid_eff, materia)
            wf.etapa_verificacao_risco(uid_eff, pauta, materia)
            wf.etapa_persistir_materia(uid_eff, pauta, materia)
            modo_ia = getattr(materia, "modo_geracao", "") or "sem_telemetria_ia"
            status_ia = getattr(materia, "ia_status", "") or "sem_telemetria_ia"
            ia_chamada = bool(modo_ia and modo_ia not in {"fallback_local", "sem_telemetria_ia", ""})
            if ia_chamada:
                core._job_fim(
                    uid, "redigir", "ok",
                    f"redacao concluida com IA ({modo_ia})",
                    detalhe={"modo_ia": modo_ia, "ia_status": status_ia},
                )
            else:
                core._job_fim(
                    uid, "redigir", "rascunho_local",
                    f"rascunho local sem IA (modo={modo_ia}); configure OPENAI_API_KEY/OPENAI_MODEL",
                    detalhe={"modo_ia": modo_ia, "ia_status": status_ia},
                )
        except Exception as exc:
            core._job_fim(uid, "redigir", "erro", f"{type(exc).__name__}: {exc}")

    threading.Thread(
        target=_trabalho, name=f"ururau_web_redigir_{uid}", daemon=True,
    ).start()
    return core._json_response(
        {"ok": True, "uid": uid, "job": core._jobs.get(uid, {}).get("ultimo_job", {})}
    )


# ────────────────────────────────────────────────────────────────────────────
# Copydesk (pipeline_copydesk)
# ────────────────────────────────────────────────────────────────────────────

def handler_copydesk(db, uid: str, body: dict):
    if not uid:
        return core._error("uid ausente", status=400)
    pauta = _carregar_pauta_completa(db, uid)
    if not pauta:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    md = core._parse_materia_pauta(pauta)
    if not md or not (md.get("conteudo") or md.get("corpo_materia")):
        return core._error("materia ainda nao foi gerada; use Redigir primeiro", status=409)
    client, modelo = core._get_openai_client()
    if not client:
        return core._error("OpenAI nao configurado", status=503, modelo=modelo)
    # Default: aplicar=False (modo preview). O editor confirma com Salvar.
    aplicar = bool(body.get("aplicar", False))
    orientacao = str(body.get("orientacao") or "").strip()

    core._job_inicio(uid, "copydesk")

    def _trabalho():
        try:
            from ururau.editorial.copydesk import pipeline_copydesk
            canal = pauta.get("canal_forcado") or pauta.get("canal", "Brasil e Mundo")
            mapa = md.get("mapa_evidencias")
            md_in = dict(md)
            # Injeta orientacao do editor para entrar no prompt do GPT.
            if orientacao:
                md_in["_orientacao_editor_web"] = orientacao
            md_rev, problemas = pipeline_copydesk(md_in, canal, mapa, client, modelo)
            problemas = list(problemas or [])
            if aplicar:
                # Aplicacao direta (mantida por compatibilidade).
                md_rev.setdefault("status", "rascunho")
                db.salvar_materia(uid, md_rev)
                pauta["materia"] = md_rev
                pauta["status"] = "revisada"
                db.salvar_pauta(pauta)
                _revisoes_pendentes.pop(uid, None)
                core._job_fim(
                    uid, "copydesk", "ok",
                    f"aplicado · {len(problemas)} problema(s) residual(is)",
                    detalhe={"aplicado": True, "pendente": False, "problemas": problemas[:50]},
                )
            else:
                # Preview: guarda revisao em memoria para confirmacao posterior.
                _revisoes_pendentes[uid] = {
                    "materia": md_rev,
                    "problemas": problemas,
                    "criada_em": datetime.now().isoformat(timespec="seconds"),
                    "orientacao": orientacao[:1000],
                }
                core._job_fim(
                    uid, "copydesk", "ok",
                    f"revisao pronta · {len(problemas)} aviso(s) · use Salvar para aplicar",
                    detalhe={
                        "aplicado": False,
                        "pendente": True,
                        "problemas": problemas[:50],
                    },
                )
        except Exception as exc:
            core._job_fim(uid, "copydesk", "erro", f"{type(exc).__name__}: {exc}")

    threading.Thread(
        target=_trabalho, name=f"ururau_web_copydesk_{uid}", daemon=True,
    ).start()
    return core._json_response(
        {"ok": True, "uid": uid, "job": core._jobs.get(uid, {}).get("ultimo_job", {})}
    )


def handler_revisao_pendente(db, uid: str):
    """Retorna a revisao do Copydesk pendente para esta pauta (se houver)."""
    if not uid:
        return core._error("uid ausente", status=400)
    slot = _revisoes_pendentes.get(uid)
    if not slot:
        return core._json_response({"ok": True, "uid": uid, "pendente": False})
    md = slot["materia"]
    return core._json_response({
        "ok": True,
        "uid": uid,
        "pendente": True,
        "criada_em": slot.get("criada_em"),
        "orientacao": slot.get("orientacao", ""),
        "problemas": list(slot.get("problemas") or [])[:50],
        "revisao": {
            "titulo_seo": md.get("titulo_seo") or md.get("titulo") or "",
            "titulo_capa": md.get("titulo_capa", ""),
            "subtitulo_curto": md.get("subtitulo_curto") or md.get("subtitulo") or "",
            "legenda_curta": md.get("legenda_curta") or md.get("legenda") or "",
            "retranca": md.get("retranca", ""),
            "tags": md.get("tags", ""),
            "meta_description": md.get("meta_description", ""),
            "slug": md.get("slug", ""),
            "alt_imagem": md.get("alt_imagem") or md.get("alt") or "",
            "corpo_materia": (md.get("corpo_materia") or md.get("conteudo") or md.get("texto_final") or ""),
            "copydesk_ia_status": md.get("copydesk_ia_status", ""),
            "copydesk_ia_modelo": md.get("copydesk_ia_modelo", ""),
        },
    })


def handler_salvar_copydesk(db, uid: str, body: dict):
    """Aplica a revisao pendente do Copydesk sobre a materia gerada."""
    if not uid:
        return core._error("uid ausente", status=400)
    slot = _revisoes_pendentes.get(uid)
    if not slot:
        return core._error("nenhuma revisao pendente — rode o Copydesk primeiro", status=404, uid=uid)
    pauta = _carregar_pauta_completa(db, uid)
    if not pauta:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    md_rev = dict(slot["materia"])
    md_rev.setdefault("status", "rascunho")
    md_rev["copydesk_aplicado_em"] = datetime.now().isoformat(timespec="seconds")
    try:
        db.salvar_materia(uid, md_rev)
        pauta["materia"] = md_rev
        pauta["status"] = "revisada"
        db.salvar_pauta(pauta)
        _revisoes_pendentes.pop(uid, None)
    except Exception as exc:
        return core._error(f"falha ao salvar: {exc}", status=500, uid=uid)
    return core._json_response({
        "ok": True,
        "uid": uid,
        "aplicado_em": md_rev["copydesk_aplicado_em"],
        "problemas": list(slot.get("problemas") or [])[:50],
    })


def handler_descartar_copydesk(db, uid: str, body: dict):
    """Descarta a revisao do Copydesk pendente sem alterar a materia atual."""
    if not uid:
        return core._error("uid ausente", status=400)
    existia = uid in _revisoes_pendentes
    _revisoes_pendentes.pop(uid, None)
    return core._json_response({"ok": True, "uid": uid, "descartada": existia})


# ────────────────────────────────────────────────────────────────────────────
# Buscar imagem
# ────────────────────────────────────────────────────────────────────────────

def handler_buscar_imagem(db, uid: str, body: dict):
    if not uid:
        return core._error("uid ausente", status=400)
    pauta = _carregar_pauta_completa(db, uid)
    if not pauta:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    client, modelo = core._get_openai_client()

    core._job_inicio(uid, "buscar_imagem")

    def _trabalho():
        try:
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            uid_eff = (
                pauta.get("uid") or pauta.get("_uid")
                or _uid_para_pauta(pauta.get("link_origem", ""), pauta.get("titulo_origem", ""))
            )
            pauta["_uid"] = uid_eff
            wf = WorkflowPublicacao(db, client, modelo)
            res = wf.etapa_imagem(uid_eff, pauta)
            if res and getattr(res, "caminho_imagem", ""):
                pauta["imagem_caminho"] = res.caminho_imagem
                pauta["imagem_estrategia"] = getattr(res, "estrategia_imagem", "")
                db.salvar_pauta(pauta)
                core._job_fim(
                    uid, "buscar_imagem", "ok",
                    f"imagem obtida ({getattr(res, 'estrategia_imagem', '?')})",
                    detalhe={"caminho_imagem": res.caminho_imagem},
                )
            else:
                core._job_fim(uid, "buscar_imagem", "vazio", "nenhuma imagem encontrada")
        except Exception as exc:
            core._job_fim(uid, "buscar_imagem", "erro", f"{type(exc).__name__}: {exc}")

    threading.Thread(
        target=_trabalho, name=f"ururau_web_imagem_{uid}", daemon=True,
    ).start()
    return core._json_response(
        {"ok": True, "uid": uid, "job": core._jobs.get(uid, {}).get("ultimo_job", {})}
    )


# ────────────────────────────────────────────────────────────────────────────
# Descartar / Reativar
# ────────────────────────────────────────────────────────────────────────────

def handler_descartar(db, uid: str, body: dict):
    if not uid:
        return core._error("uid ausente", status=400)
    pauta = _carregar_pauta_completa(db, uid)
    if not pauta:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    motivo = (body.get("motivo") or "").strip() or "Descartada via web local"
    try:
        db.marcar_descartada(uid, motivo, pauta=pauta)
    except Exception as exc:
        return core._error(f"falha ao descartar: {type(exc).__name__}: {exc}", status=500)
    return core._json_response(
        {"ok": True, "uid": uid, "motivo": motivo, "novo_status": "rejeitada"}
    )


def handler_reativar(db, uid: str, body: dict):
    if not uid:
        return core._error("uid ausente", status=400)
    pauta = _carregar_pauta_completa(db, uid)
    if not pauta:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    novo_status = str(body.get("status") or "captada")
    try:
        info = db.reativar_pauta_para_redacao(uid, motivo="reativacao_web", novo_status=novo_status)
    except Exception as exc:
        return core._error(f"falha ao reativar: {type(exc).__name__}: {exc}", status=500)
    return core._json_response({"ok": True, "uid": uid, "info": info})


# ────────────────────────────────────────────────────────────────────────────
# Publicar (CMS) — NUNCA automatico, exige confirm=true
# ────────────────────────────────────────────────────────────────────────────

def handler_publicar(db, uid: str, body: dict):
    if not uid:
        return core._error("uid ausente", status=400)
    if not bool(body.get("confirm")):
        return core._error(
            "publicacao bloqueada: requer 'confirm=true' (decisao humana)", status=409,
        )
    pauta = _carregar_pauta_completa(db, uid)
    if not pauta:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    if db.pauta_ja_publicada(pauta.get("link_origem", ""), uid):
        return core._error("pauta ja foi publicada", status=409)
    md = core._parse_materia_pauta(pauta)
    if not md or not (md.get("conteudo") or md.get("corpo_materia")):
        return core._error(
            "materia ainda nao foi gerada; use Redigir antes de Publicar", status=409,
        )

    settings = core._import_settings()
    _login = getattr(settings, "LOGIN", "") or ""
    _senha = getattr(settings, "SENHA", "") or ""
    if not (_login and _senha):
        print(f"[ururau_web][PUBLICAR][V200_20] FALHA credenciais CMS: login={'OK' if _login else 'VAZIO'} senha={'OK' if _senha else 'VAZIO'}", flush=True)
        return core._error(
            "credenciais do CMS ausentes (URURAU_LOGIN/URURAU_SENHA no .env)",
            status=503,
        )

    # V200_21: pre-check de imagem ANTES de chamar workflow.
    # O workflow tem preflight_publicacao_v47_23 que bloqueia sem imagem
    # mas a mensagem ficava so no print do PowerShell. Aqui retornamos
    # 409 com mensagem clara que o front mostra na UI.
    _tem_imagem = False
    for _k_img in ("imagem_caminho", "imagem_local", "imagem_url",
                   "imagem", "og_image", "image_url"):
        _v_img = pauta.get(_k_img)
        if isinstance(_v_img, str) and _v_img.strip():
            _tem_imagem = True
            break
    if not _tem_imagem:
        print(f"[ururau_web][PUBLICAR][V200_21] BLOQUEADO uid={uid}: pauta sem imagem", flush=True)
        return core._error(
            "Pauta sem imagem. Anexe uma foto (botao 'Buscar imagem' ou cole "
            "URL/arquivo) antes de publicar.",
            status=409, uid=uid, motivo="sem_imagem",
        )

    print(f"[ururau_web][PUBLICAR][V200_20] iniciando uid={uid} rascunho={body.get('rascunho', True)} login={_login[:3]}***", flush=True)

    rascunho = bool(body.get("rascunho", True))
    client, modelo = core._get_openai_client()

    core._job_inicio(uid, "publicar")

    def _trabalho():
        try:
            from ururau.publisher.workflow import WorkflowPublicacao, _uid_para_pauta
            from ururau.core.models import Materia, ImagemDados
            uid_eff = (
                pauta.get("uid") or pauta.get("_uid")
                or _uid_para_pauta(pauta.get("link_origem", ""), pauta.get("titulo_origem", ""))
            )
            pauta["_uid"] = uid_eff
            wf = WorkflowPublicacao(db, client, modelo)
            if not wf.etapa_gate_antiduplicacao(uid_eff, pauta, modo="publicar"):
                core._job_fim(uid, "publicar", "bloqueado", "antiduplicacao")
                return
            canal_p = pauta.get("canal_forcado") or pauta.get("canal", "Brasil e Mundo")
            md_full = dict(md)
            md_full.setdefault("link_origem", pauta.get("link_origem", ""))
            md_full.setdefault("fonte_nome", pauta.get("fonte_nome", ""))
            md_full.setdefault("canal", canal_p)
            try:
                materia = Materia.from_dict(md_full)
                if not getattr(materia, "link_origem", ""):
                    materia.link_origem = md_full["link_origem"]
                if not getattr(materia, "fonte_nome", ""):
                    materia.fonte_nome = md_full["fonte_nome"]
                if not getattr(materia, "canal", ""):
                    materia.canal = md_full["canal"]
            except Exception:
                materia = Materia(
                    titulo=md_full.get("titulo", ""),
                    titulo_capa=md_full.get("titulo_capa", ""),
                    subtitulo=md_full.get("subtitulo", ""),
                    legenda=md_full.get("legenda", ""),
                    retranca=md_full.get("retranca", ""),
                    conteudo=md_full.get("conteudo", ""),
                    slug=md_full.get("slug", ""),
                    tags=md_full.get("tags", ""),
                    meta_description=md_full.get("meta_description", ""),
                    canal=canal_p,
                    score_risco=pauta.get("score_risco", 0) or 0,
                    resumo_curto=md_full.get("resumo_curto", ""),
                    chamada_social=md_full.get("chamada_social", ""),
                    link_origem=md_full["link_origem"],
                    fonte_nome=md_full["fonte_nome"],
                )
            try:
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                materia.approved_by = "editor_web_local"
                materia.approved_at = agora
                materia.manual_approval_reason = (
                    "Editor confirmou publicacao via Ururau Web local."
                )
                materia.status_validacao = "aprovado"
                materia.auditoria_bloqueada = False
                materia.status_publicacao_sugerido = (
                    "publicar_direto" if not rascunho else "salvar_rascunho"
                )
                materia.status_pipeline = materia.status_publicacao_sugerido
                setattr(materia, "forcar_publicacao_manual", True)
                setattr(materia, "aprovacao_manual_editor", True)
            except Exception:
                pass
            imagem = None
            if pauta.get("imagem_caminho"):
                try:
                    imagem = ImagemDados(
                        caminho_imagem=pauta.get("imagem_caminho", ""),
                        url_imagem=pauta.get("imagem_url", ""),
                        credito_foto=pauta.get("imagem_credito", ""),
                        estrategia_imagem=pauta.get("imagem_estrategia", ""),
                    )
                except Exception:
                    imagem = None
            sucesso = wf.etapa_publicacao(uid_eff, pauta, materia, imagem, rascunho=rascunho)
            if sucesso:
                rotulo = "rascunho salvo no CMS" if rascunho else "publicado ao vivo"
                print(f"[ururau_web][PUBLICAR][V200_20] OK uid={uid} {rotulo}", flush=True)
                core._job_fim(uid, "publicar", "ok", rotulo, detalhe={"rascunho": rascunho})
            else:
                r = getattr(wf, "ultimo_resultado_cms", None) or {}
                # V200_21: fallback - se ultimo_resultado_cms ficou vazio,
                # tenta achar a mensagem em outros atributos do workflow.
                msg = (
                    r.get("mensagem") or r.get("erro")
                    or getattr(wf, "ultimo_motivo_bloqueio", "")
                    or getattr(wf, "ultimo_motivo", "")
                    or getattr(wf, "_ultimo_motivo_preflight", "")
                    or "CMS nao confirmou (sem mensagem detalhada - veja log do PowerShell)"
                )
                # Heuristica: se ainda generica, checa imagem
                if msg.startswith("CMS nao confirmou") and not any(
                    pauta.get(k) for k in ("imagem_caminho", "imagem_url", "imagem")
                ):
                    msg = "Bloqueado: pauta sem imagem valida."
                print(f"[ururau_web][PUBLICAR][V200_20] FALHOU uid={uid} msg={msg} detalhe={r}", flush=True)
                core._job_fim(
                    uid, "publicar", "erro", msg,
                    detalhe=r if isinstance(r, dict) else {},
                )
        except Exception as exc:
            import traceback as _tb
            _tb_str = _tb.format_exc()
            print(f"[ururau_web][PUBLICAR][V200_20] EXCECAO uid={uid} {type(exc).__name__}: {exc}", flush=True)
            print(f"[ururau_web][PUBLICAR][V200_20] traceback:\n{_tb_str}", flush=True)
            core._job_fim(uid, "publicar", "erro", f"{type(exc).__name__}: {exc}")

    threading.Thread(
        target=_trabalho, name=f"ururau_web_publicar_{uid}", daemon=True,
    ).start()
    return core._json_response({
        "ok": True, "uid": uid, "rascunho": rascunho,
        "job": core._jobs.get(uid, {}).get("ultimo_job", {}),
    })


# ────────────────────────────────────────────────────────────────────────────
# Imagem (miniatura/thumb)
# ────────────────────────────────────────────────────────────────────────────

# Cache em memória para og:image extraído por uid (evita refetch).
_og_image_cache: dict[str, str] = {}
_og_image_lock = threading.Lock()


def _extrair_og_image(url_pagina: str) -> str:
    """Faz GET rápido na página da matéria e procura og:image / twitter:image.

    Cobre fontes (Poder360, CNN, Manchete Rio, Giro RJ, Folha) que não trazem
    a imagem no RSS — a imagem fica na página HTML em <meta property="og:image">.
    """
    if not url_pagina or not url_pagina.startswith(("http://", "https://")):
        return ""
    try:
        import urllib.request
        import re as _re
        from urllib.parse import urljoin
        req = urllib.request.Request(
            url_pagina,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "pt-BR,pt;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            # Lê só o <head> (primeiros 200KB) — suficiente para meta tags.
            raw = resp.read(200_000)
        # Detecta encoding rapidamente.
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.decode("latin-1", errors="replace")
        # Procura nas variantes mais comuns.
        candidatos = []
        for pat in (
            r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
            r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
            r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
        ):
            m = _re.search(pat, html, _re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                if cand:
                    candidatos.append(cand)
        if not candidatos:
            return ""
        og = candidatos[0]
        if og.startswith("//"):
            og = "https:" + og
        elif og.startswith("/"):
            og = urljoin(url_pagina, og)
        elif not og.startswith(("http://", "https://")):
            og = urljoin(url_pagina, og)
        return og
    except Exception:
        return ""


def handler_imagem_pauta(db, uid: str):
    """Resolve a thumbnail para a pauta em 4 niveis de fallback."""
    if not uid:
        return core._error("uid ausente", status=400)
    p = _carregar_pauta_completa(db, uid)
    if not p:
        return core._error("pauta nao encontrada", status=404, uid=uid)
    # 1) Arquivo local seguro
    local = p.get("imagem_caminho") or p.get("imagem_local") or ""
    if local:
        full = _safe_image_local_path(local)
        if full and full.exists():
            mime = mimetypes.guess_type(str(full))[0] or "image/jpeg"
            try:
                with open(full, "rb") as f:
                    data = f.read()
                return core._binary_response(data, mime, cache="public, max-age=86400")
            except Exception:
                pass
    # 2) URL remota direta do RSS
    remoto = p.get("imagem_url") or p.get("imagem_capa") or p.get("media_url") or ""
    if remoto and remoto.startswith(("http://", "https://")):
        return core._redirect(remoto, status=302)
    # 3) og:image extraido on-demand
    link = p.get("link_origem") or p.get("url") or ""
    if link:
        with _og_image_lock:
            og = _og_image_cache.get(uid, None)
        if og is None:
            og = _extrair_og_image(link)
            with _og_image_lock:
                _og_image_cache[uid] = og
            if og:
                try:
                    p["imagem_url"] = og
                    db.salvar_pauta(p)
                except Exception as _e_persist:
                    print(f"[ururau_web][og:image] falha persist: {_e_persist}")
        if og:
            return core._redirect(og, status=302)
    # 4) Favicon do dominio
    if link:
        try:
            from urllib.parse import urlparse
            host = urlparse(link).netloc
            if host:
                return core._redirect(
                    f"https://www.google.com/s2/favicons?domain={host}&sz=128",
                    status=302,
                )
        except Exception:
            pass
    return core._error("imagem nao disponivel", status=404)



def handler_salvar_materia(db, uid: str, body: dict):
    """V200_11: Salva edicoes feitas pelo usuario na aba Materia Gerada.

    Aceita campos: titulo, subtitulo, legenda, conteudo, canal, tags,
    meta_description. Atualiza a materia salva no banco e, se canal/titulo
    mudaram, propaga para o nivel da pauta tambem (canal_forcado,
    titulo_origem). NAO publica - so persiste a edicao.
    """
    if not uid:
        return core._error("uid ausente", status=400)
    if not isinstance(body, dict):
        body = {}
    pauta = _carregar_pauta_completa(db, uid)
    if not pauta:
        return core._error("pauta nao encontrada", status=404, uid=uid)

    md_atual = pauta.get("materia") or {}
    if not isinstance(md_atual, dict):
        md_atual = {}

    campos_materia = (
        "titulo", "subtitulo", "legenda", "conteudo", "corpo_materia",
        "tags", "meta_description", "canal", "categoria",
    )
    mudou = False
    for k in campos_materia:
        if k in body:
            v = body.get(k)
            if v is None:
                continue
            v = str(v) if not isinstance(v, str) else v
            if md_atual.get(k) != v:
                md_atual[k] = v
                mudou = True

    # alias: conteudo <-> corpo_materia (compat com renderers)
    if "conteudo" in md_atual and "corpo_materia" not in md_atual:
        md_atual["corpo_materia"] = md_atual["conteudo"]
    if "corpo_materia" in md_atual and "conteudo" not in md_atual:
        md_atual["conteudo"] = md_atual["corpo_materia"]

    md_atual["editado_em"] = datetime.now().isoformat(timespec="seconds")
    md_atual.setdefault("status", "rascunho")

    try:
        db.salvar_materia(uid, md_atual)
    except Exception as exc:
        return core._error(f"falha ao salvar materia: {exc}", status=500, uid=uid)

    # Propaga titulo/canal para a pauta (usados no card da fila e CMS)
    pauta_mudou = False
    novo_titulo = body.get("titulo")
    if isinstance(novo_titulo, str) and novo_titulo.strip():
        if pauta.get("titulo_origem") != novo_titulo:
            pauta["titulo_origem"] = novo_titulo
            pauta_mudou = True
    novo_canal = body.get("canal") or body.get("categoria")
    if isinstance(novo_canal, str) and novo_canal.strip():
        if pauta.get("canal_forcado") != novo_canal:
            pauta["canal_forcado"] = novo_canal
            pauta["canal"] = novo_canal
            pauta_mudou = True

    pauta["materia"] = md_atual
    if mudou or pauta_mudou:
        try:
            db.salvar_pauta(pauta)
        except Exception as exc:
            return core._error(f"falha ao salvar pauta: {exc}", status=500, uid=uid)

    return core._json_response({
        "ok": True,
        "uid": uid,
        "editado_em": md_atual["editado_em"],
        "campos_alterados": [k for k in campos_materia if k in body],
        "materia": md_atual,
    })


__all__ = [
    "handler_materia",
    "handler_job_status",
    "handler_redigir",
    "handler_copydesk",
    "handler_revisao_pendente",
    "handler_salvar_copydesk",
    "handler_descartar_copydesk",
    "handler_buscar_imagem",
    "handler_descartar",
    "handler_reativar",
    "handler_publicar",
    "handler_imagem_pauta",
    "handler_salvar_materia",
]
