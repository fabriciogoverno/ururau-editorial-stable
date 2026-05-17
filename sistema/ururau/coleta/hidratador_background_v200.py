# -*- coding: utf-8 -*-
"""Hidratador em background — V200_16.

Roda em thread daemon no servidor web. A cada N segundos:
  1. Busca pautas com TXT... (sem cleaned_source_text) na fila ativa
  2. Limita por janela temporal: prioriza últimas 4h, máximo 8h
  3. Para cada uma, roda o mesmo pipeline da hidratação on-demand
     (extract_pipeline_v90 + Jina + leitura_fonte como fallback)
  4. Persiste no banco (atualizar_pauta com dados_json novo)

Resultado: o usuário NÃO precisa clicar em cada pauta. À medida que o
worker processa, as pautas vão virando TXT OK na fila sozinhas.

Configuração por env (com defaults):
  URURAU_HIDRATADOR_INTERVALO_SEG=30      ciclo entre rodadas
  URURAU_HIDRATADOR_BATCH=10              pautas por rodada
  URURAU_HIDRATADOR_TIMEOUT_PAUTA=15      timeout por pauta (segundos)
  URURAU_HIDRATADOR_JANELA_MAX_H=8        janela máxima (horas)
  URURAU_HIDRATADOR_JANELA_PRIORIDADE_H=4 janela de prioridade (horas)
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)
PREFIX = "[HIDRATADOR_BG]"

# Configurável via env
INTERVALO_SEG = int(os.environ.get("URURAU_HIDRATADOR_INTERVALO_SEG", "30"))
BATCH = int(os.environ.get("URURAU_HIDRATADOR_BATCH", "10"))
TIMEOUT_PAUTA = int(os.environ.get("URURAU_HIDRATADOR_TIMEOUT_PAUTA", "15"))
JANELA_MAX_H = int(os.environ.get("URURAU_HIDRATADOR_JANELA_MAX_H", "8"))
JANELA_PRIORIDADE_H = int(
    os.environ.get("URURAU_HIDRATADOR_JANELA_PRIORIDADE_H", "4")
)
TEXTO_MIN_CHARS = 550

_stop_event = threading.Event()
_worker_thread: Optional[threading.Thread] = None
_estado = {
    "rodando": False,
    "ciclos": 0,
    "pautas_hidratadas": 0,
    "pautas_falhas": 0,
    "ultimo_ciclo_em": "",
    "ultima_pauta_uid": "",
    "ultimo_erro": "",
}
_estado_lock = threading.Lock()


def _texto_chars(p: dict[str, Any]) -> int:
    t = str(p.get("cleaned_source_text") or p.get("texto_fonte") or "").strip()
    return len(t)


def _imagem_ok(p: dict[str, Any]) -> bool:
    for k in ("imagem_url", "imagem", "og_image", "image_url", "imagem_capa"):
        v = p.get(k)
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            return True
    return False


def _link_pauta(p: dict[str, Any]) -> str:
    for k in ("link_origem_resolvido", "url_final", "canonical_url",
              "link_origem", "url_original", "link", "url"):
        v = p.get(k)
        if isinstance(v, str) and v.strip().startswith(("http://", "https://")):
            return v.strip()
    return ""


def _selecionar_candidatas(db) -> list[dict[str, Any]]:
    """Retorna pautas TXT... dentro da janela de 8h, priorizando 4h."""
    try:
        pautas = db.query_fila_ativa(incluir_baixo_score=False, limite=200)
    except Exception as e:
        logger.warning("%s query_fila_ativa falhou: %s", PREFIX, e)
        return []
    agora = datetime.now()
    janela_max = agora - timedelta(hours=JANELA_MAX_H)
    janela_prio = agora - timedelta(hours=JANELA_PRIORIDADE_H)
    candidatas: list[tuple[int, dict]] = []
    for p in pautas:
        # Já tem texto suficiente? pula
        if _texto_chars(p) >= TEXTO_MIN_CHARS and _imagem_ok(p):
            continue
        # Tem link real?
        if not _link_pauta(p):
            continue
        # Já tentou hidratar e falhou recentemente? pula por 1h
        ult_tentativa = p.get("_hidratador_bg_tentado_em") or ""
        if ult_tentativa:
            try:
                dt = datetime.fromisoformat(ult_tentativa[:19])
                if (agora - dt) < timedelta(hours=1):
                    continue
            except Exception:
                pass
        # Janela temporal
        cap_iso = str(p.get("captada_em") or p.get("atualizada_em") or "")[:19]
        try:
            cap_dt = datetime.fromisoformat(cap_iso) if cap_iso else agora
        except Exception:
            cap_dt = agora
        if cap_dt < janela_max:
            continue
        prio = 0 if cap_dt >= janela_prio else 1  # 0 = mais prioritário
        candidatas.append((prio, p))
    # Ordena: prioridade asc, captada_em desc
    candidatas.sort(key=lambda x: (
        x[0],
        -(_iso_to_ts(x[1].get("captada_em") or x[1].get("atualizada_em") or "")),
    ))
    return [p for _, p in candidatas[:BATCH]]


def _iso_to_ts(s: str) -> float:
    try:
        return datetime.fromisoformat(str(s)[:19]).timestamp()
    except Exception:
        return 0.0


def _hidratar_pauta(p: dict[str, Any]) -> dict[str, Any]:
    """Extrai texto + imagem da pauta usando o mesmo pipeline da on-demand.

    Retorna dict: {ok: bool, texto, imagem_url, metodo, motivo}
    """
    url = _link_pauta(p)
    if not url:
        return {"ok": False, "motivo": "sem_url"}

    titulo = str(p.get("titulo_origem") or p.get("titulo") or "")

    # ESCADA 1: pipeline_v90 (adapters + trafilatura + Jina interno)
    try:
        from ururau.coleta.extract_pipeline_v90 import extrair_materia_v90
        from urllib.parse import urlparse
        dominio = urlparse(url).netloc.lower()
        tipo_site = "globo" if "globo.com" in dominio else (
            "uol" if "uol.com.br" in dominio else "generic"
        )
        r = extrair_materia_v90(
            url, dominio=dominio, tipo_site=tipo_site,
            contexto={"uid": p.get("uid"), "origem": "hidratador_bg"},
        )
        texto = (r.get("texto") or "").strip()
        if r.get("aceita") and len(texto) >= TEXTO_MIN_CHARS:
            imagem = (
                str(r.get("imagem") or "").strip()
                or str(r.get("og_image") or "").strip()
            )
            return {
                "ok": True,
                "texto": texto,
                "imagem_url": imagem,
                "metodo": "pipeline_v90:" + str(r.get("metodo") or ""),
                "motivo": "ok",
            }
    except Exception as e:
        logger.debug("%s pipeline_v90 falhou uid=%s: %s",
                     PREFIX, p.get("uid"), e)

    # ESCADA 2: Jina Reader (renderiza JS, ótimo para SPA)
    try:
        from ururau.coleta.jina_extractor import extrair_via_jina
        r = extrair_via_jina(url, timeout=TIMEOUT_PAUTA, min_chars=TEXTO_MIN_CHARS)
        if r.get("ok"):
            texto = (r.get("texto") or "").strip()
            if len(texto) >= TEXTO_MIN_CHARS:
                return {
                    "ok": True, "texto": texto,
                    "imagem_url": "",
                    "metodo": "jina_bg",
                    "motivo": r.get("motivo") or "ok",
                }
    except Exception as e:
        logger.debug("%s jina falhou uid=%s: %s", PREFIX, p.get("uid"), e)

    return {"ok": False, "motivo": "todos_metodos_falharam"}


def _persistir(db, p: dict[str, Any], resultado: dict[str, Any]) -> None:
    """Atualiza dados_json da pauta com texto+imagem+metadados."""
    uid = str(p.get("uid") or p.get("_uid") or "")
    if not uid:
        return
    # Reconstrói o payload completo do dados_json com os novos campos
    extra = dict(p)
    extra.pop("uid", None)
    extra.pop("_uid", None)

    if resultado.get("ok"):
        extra["cleaned_source_text"] = resultado["texto"]
        extra["fonte_status"] = "ok"
        extra["status_fonte_v105"] = "ok"
        extra["fonte_chars_v105"] = len(resultado["texto"])
        extra["texto_fonte_chars"] = len(resultado["texto"])
        extra["hidratacao_on_demand"] = resultado.get("metodo") or "hidratador_bg"
        extra["hidratado_em"] = datetime.now().isoformat(timespec="seconds")
        extra["_hidratador_bg_tentado_em"] = extra["hidratado_em"]
        if resultado.get("imagem_url"):
            extra["imagem_url"] = resultado["imagem_url"]
    else:
        # Marca tentativa pra não martelar a mesma pauta em loop
        extra["_hidratador_bg_tentado_em"] = datetime.now().isoformat(
            timespec="seconds"
        )
        extra["_hidratador_bg_motivo"] = resultado.get("motivo") or "falhou"

    try:
        db.atualizar_pauta(uid, {
            "dados_json": json.dumps(extra, ensure_ascii=False, default=str),
        })
    except Exception as e:
        logger.warning("%s persist falhou uid=%s: %s", PREFIX, uid, e)


def _ciclo(db) -> dict[str, int]:
    """Roda um ciclo de hidratação e retorna stats."""
    candidatas = _selecionar_candidatas(db)
    if not candidatas:
        return {"candidatas": 0, "hidratadas": 0, "falhas": 0}

    hidratadas = 0
    falhas = 0
    for p in candidatas:
        if _stop_event.is_set():
            break
        uid = str(p.get("uid") or "")
        try:
            r = _hidratar_pauta(p)
            _persistir(db, p, r)
            if r.get("ok"):
                hidratadas += 1
                logger.info(
                    "%s OK uid=%s chars=%d metodo=%s",
                    PREFIX, uid[:12], len(r.get("texto") or ""),
                    r.get("metodo") or "",
                )
            else:
                falhas += 1
                logger.debug(
                    "%s FALHA uid=%s motivo=%s",
                    PREFIX, uid[:12], r.get("motivo") or "",
                )
            with _estado_lock:
                _estado["ultima_pauta_uid"] = uid
                if r.get("ok"):
                    _estado["pautas_hidratadas"] += 1
                else:
                    _estado["pautas_falhas"] += 1
        except Exception as e:
            falhas += 1
            with _estado_lock:
                _estado["ultimo_erro"] = f"{type(e).__name__}: {str(e)[:100]}"
            logger.warning("%s erro uid=%s: %s", PREFIX, uid[:12], e)
    return {"candidatas": len(candidatas), "hidratadas": hidratadas, "falhas": falhas}


def _loop(db) -> None:
    logger.info(
        "%s worker iniciado: intervalo=%ds batch=%d janela_max=%dh prio=%dh",
        PREFIX, INTERVALO_SEG, BATCH, JANELA_MAX_H, JANELA_PRIORIDADE_H,
    )
    with _estado_lock:
        _estado["rodando"] = True
    # Pequeno warmup pra deixar o server subir tranquilo
    if _stop_event.wait(timeout=10.0):
        return
    while not _stop_event.is_set():
        try:
            stats = _ciclo(db)
            with _estado_lock:
                _estado["ciclos"] += 1
                _estado["ultimo_ciclo_em"] = datetime.now().isoformat(
                    timespec="seconds"
                )
            if stats["candidatas"] > 0:
                print(
                    f"[ururau_web][HIDRATADOR_BG] ciclo: "
                    f"{stats['hidratadas']} hidratadas, {stats['falhas']} falhas "
                    f"de {stats['candidatas']} candidatas",
                    flush=True,
                )
        except Exception as e:
            with _estado_lock:
                _estado["ultimo_erro"] = f"{type(e).__name__}: {str(e)[:100]}"
            logger.warning("%s ciclo falhou: %s", PREFIX, e)
        # Aguarda o intervalo (mas pode acordar antes se receber stop)
        if _stop_event.wait(timeout=INTERVALO_SEG):
            break
    with _estado_lock:
        _estado["rodando"] = False
    logger.info("%s worker parado", PREFIX)


def iniciar(db) -> bool:
    """Inicia o worker em thread daemon. Idempotente."""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return False
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_loop, args=(db,),
        name="ururau_hidratador_bg", daemon=True,
    )
    _worker_thread.start()
    return True


def parar() -> None:
    _stop_event.set()


def status() -> dict[str, Any]:
    with _estado_lock:
        return dict(_estado)


__all__ = ["iniciar", "parar", "status"]
