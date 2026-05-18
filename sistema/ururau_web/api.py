# -*- coding: utf-8 -*-
"""ururau_web.api - Dispatcher puro da API web local do Ururau.

Camada de roteamento sem dependencia de servidor. Recebe
(method, path, query, body, headers, db) e devolve (status, headers, body).

REGRAS QUE ESTA CAMADA PRESERVA
    * Nao publica matéria automaticamente. Publicacao exige `confirm=true`
      explicito no body e roda como acao humana iniciada pelo editor.
    * Nao reimplementa motor editorial. Reusa:
        - Database.query_fila_ativa, salvar_pauta, buscar_pauta,
          salvar_materia, marcar_descartada,
          feed_universal_source_health_summary, etc.
        - WorkflowPublicacao (etapa_redacao, etapa_imagem, etapa_pacote_editorial,
          etapa_persistir_materia, etapa_publicacao, etapa_gate_antiduplicacao).
        - pipeline_copydesk (ururau.editorial.copydesk).
        - feed_universal.api (discover_universal, collect_to_queue).
        - coletar_pautas_premium_v90 (source_hunter v90) para coleta tradicional.
    * Reusa funcoes v200 do painel desktop para ordenacao/filtragem da fila.
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


# ────────────────────────────────────────────────────────────────────────────
# Estado global compartilhado entre handlers.
# ────────────────────────────────────────────────────────────────────────────

_coleta_lock = threading.Lock()
_coleta_estado: dict[str, Any] = {
    "em_andamento": False,
    "iniciado_em": "",
    "finalizado_em": "",
    "inseridas": 0,
    "captadas_brutas": 0,
    "ultimo_erro": "",
    "ultimo_resumo": "",
}

_jobs_lock = threading.Lock()
# Mapa uid -> {ultimo_job: {tipo, em_andamento, iniciado_em, finalizado_em, status, mensagem}}
_jobs: dict[str, dict[str, Any]] = {}


# ────────────────────────────────────────────────────────────────────────────
# Auto-coleta (scheduler): roda na inicializacao e a cada N minutos.
# ────────────────────────────────────────────────────────────────────────────

_auto_lock = threading.Lock()
_auto_estado: dict[str, Any] = {
    "ativada": False,
    "intervalo_min": 30,
    "ultima_iso": "",      # quando rodou pela ultima vez
    "proxima_iso": "",     # quando rodara pela proxima vez
    "execucoes": 0,
    "ultimo_resumo": "",
    "ultimo_erro": "",
}
_auto_stop = threading.Event()
_auto_thread: Optional[threading.Thread] = None


def _auto_loop(db, intervalo_segundos: int, atraso_inicial: float = 8.0):
    """Loop background: dispara coleta imediatamente (apos atraso curto)
    e depois a cada `intervalo_segundos` segundos. Encerra quando
    `_auto_stop` for setado.
    """
    # Atraso inicial: deixa o servidor terminar o bind e o navegador abrir
    # antes da primeira coleta automatica nao bloquear nada visivel.
    if _auto_stop.wait(timeout=atraso_inicial):
        return
    while not _auto_stop.is_set():
        try:
            # Atualiza marcador "ultima_iso" antes mesmo de iniciar — ajuda na UI.
            agora = datetime.now()
            with _auto_lock:
                _auto_estado["ultima_iso"] = agora.isoformat(timespec="seconds")
                _auto_estado["proxima_iso"] = (
                    datetime.fromtimestamp(agora.timestamp() + intervalo_segundos)
                    .isoformat(timespec="seconds")
                )
                _auto_estado["execucoes"] = int(_auto_estado.get("execucoes", 0)) + 1
                _auto_estado["ultimo_erro"] = ""
            # Dispara coleta usando o mesmo handler do botao Coletar.
            # Body vazio → defaults (limite=500, janela=6).
            try:
                handler_coletar(db, {})
                with _auto_lock:
                    _auto_estado["ultimo_resumo"] = "coleta automatica disparada"
            except Exception as exc:
                with _auto_lock:
                    _auto_estado["ultimo_erro"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc_loop:
            # Loop nunca pode morrer; loga e segue.
            print(f"[ururau_web][auto-coleta][LOOP-ERR] {exc_loop}")
        # Aguarda o proximo ciclo (interruptivel via _auto_stop.set()).
        if _auto_stop.wait(timeout=intervalo_segundos):
            return


def iniciar_auto_coleta(db, intervalo_min: int = 30, atraso_inicial: float = 8.0) -> dict:
    """Inicia (uma vez) o scheduler de coleta automatica.

    Chamado pelo server.py logo apos make_server(). Idempotente: se ja
    estiver rodando, apenas atualiza o intervalo.

    EFEITO COLATERAL v1.14.3: grava o corte temporal em data/web_corte_captacao.txt
    para "agora - 5 minutos" ANTES de iniciar a primeira coleta automatica.
    Isso esconde pautas antigas do painel desktop ("Coleta 112" etc.) e deixa
    a fila web limpa, mostrando apenas o que a auto-coleta web for trazendo.
    """
    global _auto_thread
    intervalo_min = max(5, min(180, int(intervalo_min or 30)))
    intervalo_seg = intervalo_min * 60
    with _auto_lock:
        _auto_estado["intervalo_min"] = intervalo_min
        if _auto_estado["ativada"] and _auto_thread and _auto_thread.is_alive():
            # Ja esta rodando; nao cria thread nova.
            return dict(_auto_estado)
        _auto_estado["ativada"] = True
        _auto_estado["proxima_iso"] = (
            datetime.fromtimestamp(datetime.now().timestamp() + atraso_inicial)
            .isoformat(timespec="seconds")
        )
        _auto_stop.clear()

    # Aplica corte temporal: tudo coletado antes de "agora - 5 minutos" some
    # da fila visual (NAO apaga do banco). Garante que a fila inicia limpa
    # e popula com as novas coletas auto que vao acontecer.
    # BUG_FIX v1.14.5: se o SO esta em UTC, datetime.fromtimestamp() retorna
    # em UTC enquanto captada_em e gravado em BR. Comparacao de string falha
    # e TODAS as pautas novas ficam escondidas. Forcar tudo em BR sem offset.
    try:
        from datetime import timedelta as _td
        try:
            from zoneinfo import ZoneInfo
            agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
        except Exception:
            agora_br = datetime.now()
        # Subtrai 5 minutos diretamente do datetime aware e remove offset
        # para gerar string ISO "naive" em horario de Brasilia.
        corte_dt = agora_br - _td(seconds=300)
        corte_ts = corte_dt.replace(tzinfo=None).isoformat(timespec="seconds")
        destino = _CORTE_FILE
        if not destino.parent.exists():
            alt = Path("sistema") / _CORTE_FILE
            if alt.parent.exists():
                destino = alt
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(corte_ts, encoding="utf-8")
        print(f"[ururau_web][auto-coleta] corte temporal aplicado: pautas anteriores a {corte_ts} BR ocultas")
    except Exception as _e_corte:
        print(f"[ururau_web][auto-coleta] falha ao aplicar corte: {_e_corte}")

    _auto_thread = threading.Thread(
        target=_auto_loop,
        args=(db, intervalo_seg, atraso_inicial),
        name="ururau_web_auto_coleta",
        daemon=True,
    )
    _auto_thread.start()

    # V200_16: inicia o hidratador em background (extrai texto+imagem de
    # pautas TXT... sem usuario precisar clicar). Ciclo: 30s, batch 10,
    # janela 8h max + prioridade 4h.
    try:
        from ururau.coleta import hidratador_background_v200 as _hbg
        _hbg.iniciar(db)
        print("[ururau_web][HIDRATADOR_BG] worker iniciado em thread daemon")
    except Exception as _e_hbg:
        print(f"[ururau_web][HIDRATADOR_BG] falha ao iniciar: {_e_hbg}")

    return dict(_auto_estado)


def parar_auto_coleta() -> None:
    with _auto_lock:
        _auto_estado["ativada"] = False
    _auto_stop.set()


def handler_auto_status(db) -> tuple[int, dict, bytes]:
    with _auto_lock:
        snap = dict(_auto_estado)
    snap["agora_iso"] = datetime.now().isoformat(timespec="seconds")
    # Calcula segundos restantes (positivo se ainda nao chegou)
    try:
        if snap.get("proxima_iso"):
            prox = datetime.fromisoformat(snap["proxima_iso"])
            snap["segundos_para_proxima"] = max(0, int((prox - datetime.now()).total_seconds()))
        else:
            snap["segundos_para_proxima"] = None
    except Exception:
        snap["segundos_para_proxima"] = None
    return _json_response({"ok": True, "auto_coleta": snap})


def _job_set(uid: str, tipo: str, **fields):
    with _jobs_lock:
        slot = _jobs.setdefault(uid, {})
        slot["ultimo_job"] = {
            "tipo": tipo,
            "em_andamento": fields.get("em_andamento", False),
            "iniciado_em": fields.get("iniciado_em", ""),
            "finalizado_em": fields.get("finalizado_em", ""),
            "status": fields.get("status", "ok"),
            "mensagem": fields.get("mensagem", ""),
            "detalhe": fields.get("detalhe", {}),
        }


def _job_inicio(uid: str, tipo: str):
    _job_set(uid, tipo,
             em_andamento=True,
             iniciado_em=datetime.now().isoformat(timespec="seconds"),
             finalizado_em="",
             status="rodando",
             mensagem="")


def _job_fim(uid: str, tipo: str, status: str, mensagem: str = "", detalhe: dict | None = None):
    _job_set(uid, tipo,
             em_andamento=False,
             iniciado_em=_jobs.get(uid, {}).get("ultimo_job", {}).get("iniciado_em", ""),
             finalizado_em=datetime.now().isoformat(timespec="seconds"),
             status=status,
             mensagem=mensagem,
             detalhe=detalhe or {})


# ────────────────────────────────────────────────────────────────────────────
# Bootstrap de imports do projeto Ururau.
# ────────────────────────────────────────────────────────────────────────────

def _ensure_sys_path() -> None:
    here = Path(__file__).resolve()
    sistema_dir = here.parents[1]
    if str(sistema_dir) not in sys.path:
        sys.path.insert(0, str(sistema_dir))


_ensure_sys_path()


def _import_db():
    from ururau.core.database import Database, get_db  # noqa: WPS433
    return Database, get_db


def _import_feed_universal():
    from ururau.coleta.feed_universal.api import (  # noqa: WPS433
        collect_to_queue,
        discover_universal,
    )
    return discover_universal, collect_to_queue


def _import_settings():
    from ururau.config import settings  # noqa: WPS433
    return settings


def _import_painel_v200():
    """Funcoes puras v200 do painel para ordenacao da fila."""
    try:
        from ururau.ui.painel import (  # noqa: WPS433
            _filtrar_pendentes_antigas_fila_v200,
            _sort_key_fila_visual_v200,
        )
        return _sort_key_fila_visual_v200, _filtrar_pendentes_antigas_fila_v200
    except Exception:
        def _sort_min(p: dict) -> tuple:
            cap = str(p.get("captada_em") or p.get("atualizada_em") or "")
            txt = (p.get("cleaned_source_text") or p.get("texto_fonte") or "")
            pronto = 1 if len(str(txt).strip()) >= 550 else 0
            ordem = int(p.get("coleta_lote_ordem_v123") or 0)
            return (ordem, pronto, cap)

        def _filtra_min(itens: list[dict]) -> list[dict]:
            if not itens:
                return itens
            ordens = [int(p.get("coleta_lote_ordem_v123") or 0) for p in itens]
            ult = max(ordens) if ordens else 0
            if not ult:
                return itens
            return [
                p
                for p in itens
                if int(p.get("coleta_lote_ordem_v123") or 0) == ult
                or len(str(p.get("cleaned_source_text") or "").strip()) >= 550
            ]

        return _sort_min, _filtra_min


def _parse_materia_pauta(pauta: dict) -> dict | None:
    """Reusa _parse_materia do painel desktop."""
    try:
        from ururau.ui.painel import _parse_materia  # noqa: WPS433
        return _parse_materia(pauta)
    except Exception:
        m = pauta.get("materia") if isinstance(pauta, dict) else None
        if isinstance(m, dict):
            return m
        if isinstance(m, str):
            try:
                return json.loads(m)
            except Exception:
                return None
        return None


# Singleton de cliente OpenAI (criado sob demanda, igual ao painel).
_openai_client_lock = threading.Lock()
_openai_client: Any = None
_openai_modelo: str = ""


_openai_diag: dict[str, Any] = {
    "lib_instalada": None,
    "lib_versao": "",
    "key_origem": "",
    "key_presente": False,
    "ultimo_erro": "",
}


def _carregar_env_defensivo() -> dict[str, str]:
    """Carrega o .env de forma defensiva, devolvendo o mapa lido.

    Caminhos prioritarios (em ordem):
        1. sistema/credenciais/env_principal.env
        2. sistema/.env
        3. <project_root>/.env
    """
    aqui = Path(__file__).resolve()
    sistema = aqui.parents[1]
    root = aqui.parents[2] if len(aqui.parents) > 2 else sistema
    caminhos = [
        sistema / "credenciais" / "env_principal.env",
        sistema / ".env",
        root / ".env",
    ]
    lidos: dict[str, str] = {}
    try:
        from dotenv import dotenv_values, load_dotenv  # noqa: WPS433
    except Exception:
        # python-dotenv ausente: faz parse manual KEY=VAL.
        for p in caminhos:
            if not p.exists():
                continue
            try:
                for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and not os.environ.get(k):
                        os.environ[k] = v
                    lidos.setdefault(k, v)
            except Exception:
                continue
        return lidos
    for p in caminhos:
        if p.exists():
            try:
                load_dotenv(p, override=True)
                vals = dotenv_values(p) or {}
                for k, v in vals.items():
                    if v is not None:
                        lidos.setdefault(k, v)
            except Exception:
                continue
    return lidos


def _get_openai_client() -> tuple[Any, str]:
    """Cria o client OpenAI uma unica vez. Carga defensiva do .env."""
    global _openai_client, _openai_modelo
    with _openai_client_lock:
        if _openai_client is not None or _openai_modelo:
            return _openai_client, _openai_modelo
        # 1. Recarrega .env de forma defensiva (mesmo se settings.py ja rodou).
        lidos = _carregar_env_defensivo()
        # 2. Tenta o settings importado primeiro; depois variaveis de ambiente
        #    diretas; por ultimo o que lemos do arquivo.
        try:
            settings = _import_settings()
            api_key = (getattr(settings, "OPENAI_API_KEY", "") or "").strip()
            modelo = (getattr(settings, "MODELO_OPENAI", "") or "").strip()
        except Exception:
            api_key = ""
            modelo = ""
        if not api_key:
            api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if not modelo:
            modelo = (os.environ.get("OPENAI_MODEL") or "").strip()
        if not api_key:
            api_key = (lidos.get("OPENAI_API_KEY") or "").strip()
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
        if not modelo:
            modelo = (lidos.get("OPENAI_MODEL") or "gpt-4.1-mini").strip()
            os.environ.setdefault("OPENAI_MODEL", modelo)
        modelo = modelo or "gpt-4.1-mini"
        _openai_modelo = modelo
        _openai_diag["key_presente"] = bool(api_key)
        _openai_diag["key_origem"] = (
            "settings" if hasattr(settings if "settings" in dir() else object, "OPENAI_API_KEY")
            else ("env" if os.environ.get("OPENAI_API_KEY") else ("arquivo" if lidos.get("OPENAI_API_KEY") else "nenhuma"))
        )
        if not api_key:
            _openai_diag["lib_instalada"] = None
            return None, modelo
        # 3. Tenta importar a lib openai.
        try:
            import openai as _openai_pkg  # noqa: WPS433
            _openai_diag["lib_instalada"] = True
            _openai_diag["lib_versao"] = getattr(_openai_pkg, "__version__", "?")
            from openai import OpenAI  # noqa: WPS433
            _openai_client = OpenAI(api_key=api_key)
            _openai_diag["ultimo_erro"] = ""
        except ImportError as exc:
            _openai_diag["lib_instalada"] = False
            _openai_diag["ultimo_erro"] = f"biblioteca 'openai' nao instalada ({exc})"
            print(f"[ururau_web][IA] {_openai_diag['ultimo_erro']}")
            _openai_client = None
        except Exception as exc:
            _openai_diag["ultimo_erro"] = f"{type(exc).__name__}: {exc}"
            print(f"[ururau_web][IA] OpenAI nao criado: {exc}")
            _openai_client = None
        return _openai_client, modelo


def handler_diag(db) -> tuple[int, dict, bytes]:
    """Diagnostico do servidor: o que esta carregado, o que falta."""
    settings = None
    try:
        settings = _import_settings()
    except Exception:
        pass
    # Forca carga do client (para popular _openai_diag).
    client, modelo = _get_openai_client()
    api_key = ""
    try:
        api_key = (getattr(settings, "OPENAI_API_KEY", "") or
                   os.environ.get("OPENAI_API_KEY", "") or "")
    except Exception:
        pass
    mask = ""
    if api_key:
        mask = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 14 else "[curta]"
    login = ""
    senha_presente = False
    assinatura = ""
    try:
        login = getattr(settings, "LOGIN", "") if settings else os.environ.get("URURAU_LOGIN", "")
        senha_presente = bool(getattr(settings, "SENHA", "") if settings else os.environ.get("URURAU_SENHA", ""))
        assinatura = getattr(settings, "ASSINATURA_FIXA", "") if settings else ""
    except Exception:
        pass
    libs = {}
    for nome in ["openai", "feedparser", "dotenv", "playwright", "PIL"]:
        try:
            __import__(nome)
            libs[nome] = "instalado"
        except Exception as exc:
            libs[nome] = f"ausente ({type(exc).__name__})"
    aqui = Path(__file__).resolve()
    return _json_response({
        "ok": True,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "ia": {
            "modelo": modelo,
            "client_criado": bool(client),
            "lib_instalada": _openai_diag.get("lib_instalada"),
            "lib_versao": _openai_diag.get("lib_versao", ""),
            "key_origem": _openai_diag.get("key_origem", "nenhuma"),
            "key_mascarada": mask or "(ausente)",
            "ultimo_erro": _openai_diag.get("ultimo_erro", ""),
        },
        "cms": {
            "login": login or "(ausente)",
            "senha_presente": senha_presente,
            "assinatura": assinatura or "(ausente)",
        },
        "arquivo_db": getattr(settings, "ARQUIVO_DB", "") if settings else "",
        "bibliotecas": libs,
        "caminhos": {
            "api.py": str(aqui),
            "sistema": str(aqui.parents[1]),
            "cwd": os.getcwd(),
        },
    })


# ────────────────────────────────────────────────────────────────────────────
# Helpers de resposta HTTP.
# ────────────────────────────────────────────────────────────────────────────

def _json_response(payload: Any, status: int = 200) -> tuple[int, dict, bytes]:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
    }
    return status, headers, body


def _binary_response(body: bytes, content_type: str, status: int = 200, cache: str = "public, max-age=3600") -> tuple[int, dict, bytes]:
    headers = {"Content-Type": content_type, "Cache-Control": cache}
    return status, headers, body


def _redirect(url: str, status: int = 302) -> tuple[int, dict, bytes]:
    headers = {"Location": url, "Cache-Control": "no-store"}
    return status, headers, b""


def _error(msg: str, status: int = 400, **extra) -> tuple[int, dict, bytes]:
    payload = {"erro": msg, "status": status, **extra}
    return _json_response(payload, status=status)


def _parse_json_body(body_bytes: bytes) -> dict:
    if not body_bytes:
        return {}
    try:
        data = json.loads(body_bytes.decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _query_dict(query: str) -> dict[str, str]:
    if not query:
        return {}
    from urllib.parse import parse_qs

    parsed = parse_qs(query, keep_blank_values=True)
    return {k: (v[-1] if v else "") for k, v in parsed.items()}


# ────────────────────────────────────────────────────────────────────────────
# Visualizacao das pautas (rotulos curtos + miniaturas).
# ────────────────────────────────────────────────────────────────────────────

def _status_visual_v200(p: dict) -> dict[str, str]:
    texto = str(p.get("cleaned_source_text") or p.get("texto_fonte") or "").strip()
    chars = len(texto)
    fonte_status = str(p.get("fonte_status") or p.get("status_fonte_v105") or "").lower()
    status_pauta = str(p.get("status") or "").lower()

    if status_pauta in {"publicada", "publicado"}:
        rotulo = "PUBLICADA"
    elif status_pauta in {"bloqueada", "bloqueado", "descartada", "descartado",
                          "rejeitada", "rejeitado", "reprovada", "reprovado"}:
        rotulo = "BLOQUEADO"
    elif "duplic" in status_pauta:
        rotulo = "DUPLICADO"
    # V200_14: separa visualmente pautas redigidas/revisadas das brutas TXT OK
    elif status_pauta in {"revisada"}:
        rotulo = "REVISADA"
    # V200_57: separa em_redacao de redigida. Antes ambos eram REDIGIDA,
    # o que enganava o usuario quando o job de redacao travava sem salvar.
    # em_redacao = job em andamento ou travado (rotulo "RASCUNHO").
    # redigida/pronta = materia gerada com sucesso ("REDIGIDA").
    elif status_pauta in {"em_redacao", "em_redação"}:
        rotulo = "RASCUNHO"
    elif status_pauta in {"redigida", "pronta"}:
        rotulo = "REDIGIDA"
    elif chars >= 550:
        rotulo = "TXT OK"
    elif "429" in fonte_status or "429" in status_pauta:
        rotulo = "TXT 429"
    elif chars > 0:
        rotulo = "TXT CURTO"
    else:
        rotulo = "TXT..."

    return {"rotulo": rotulo, "fonte_status": fonte_status, "chars": str(chars)}


def _data_visual(p: dict) -> str:
    raw = str(p.get("data_pub_fonte") or p.get("data_fonte") or "").strip()
    if raw:
        return raw
    cap = str(p.get("captada_em") or p.get("atualizada_em") or "").strip()
    if not cap:
        return ""
    cap_br = cap.replace("T", " ").replace("Z", "")
    try:
        dt = datetime.fromisoformat(cap_br[:19])
        cap_br = dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        pass
    return f"Captada: {cap_br}"


def _detectar_imagem_url(p: dict) -> str:
    """Procura URL de imagem em varios campos comuns das pautas captadas."""
    for k in ("imagem_url", "imagem_principal", "imagem_capa", "og_image",
             "fonte_imagem_url", "image_url", "imagem", "thumbnail"):
        v = p.get(k)
        if v and isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _texto_tem_boilerplate_lista(texto: str) -> bool:
    """V200_44: detecta se o texto tem o padrao caracteristico de "lista de
    outras noticias" vazando para o corpo (caso da Prefeitura de Campos).

    Heuristica: se acha pelo menos 3 linhas batendo em qualquer um destes
    padroes, considera contaminado:
      - "- DD/MM/AAAA HH:MM:SS Titulo"
      - "DDMM HHhMM Titulo" (compacto sem espaco)
      - "NTitulo" (numero colado, ex: "2Cartao")
    """
    if not texto or len(texto) < 100:
        return False
    import re as _re
    pad_a = _re.compile(r"^\s*-?\s*\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s+\S")
    pad_b = _re.compile(r"^\s*\d{4}\s+\d{1,2}h\d{2}\S")
    pad_c = _re.compile(r"^\s*\d{1,2}[A-ZÁ-Úa-zá-ú][a-zá-ú]{3,}")
    cnt = 0
    for l in texto.split("\n"):
        l = (l or "").strip()
        if not l:
            continue
        if pad_a.match(l) or pad_b.match(l) or pad_c.match(l):
            cnt += 1
            if cnt >= 3:
                return True
    return False


def _limpar_boilerplate_listas(texto: str, link: str = "") -> str:
    """V200_44: pos-processamento conservador - corta texto a partir da
    primeira linha de lista lateral, se identificar 3+ ocorrencias.

    Versao mais agressiva (threshold baixo de 80 chars) para nao deixar lixo
    quando o corpo real nao esta no texto. Se sobra menos que 80 chars (so
    titulo), retorna texto vazio para sinalizar que precisa rehidratar.
    """
    if not texto or len(texto) < 100:
        return texto
    import re as _re
    linhas = texto.split("\n")
    pad_a = _re.compile(r"^\s*-?\s*\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s+\S")
    pad_b = _re.compile(r"^\s*\d{4}\s+\d{1,2}h\d{2}\S")
    pad_c = _re.compile(r"^\s*\d{1,2}[A-ZÁ-Úa-zá-ú][a-zá-ú]{3,}")
    def _eh(l):
        l = (l or "").strip()
        return bool(l and (pad_a.match(l) or pad_b.match(l) or pad_c.match(l)))
    # Acha primeira janela de 3 linhas-lista
    idx_corte = -1
    for i in range(len(linhas) - 2):
        if _eh(linhas[i]) and _eh(linhas[i+1]) and _eh(linhas[i+2]):
            idx_corte = i
            # Volta backwards por linhas em branco
            while idx_corte > 0 and not linhas[idx_corte - 1].strip():
                idx_corte -= 1
            break
    if idx_corte <= 0:
        return texto
    texto_limpo = "\n".join(linhas[:idx_corte]).rstrip()
    # Se sobrou pouco (so titulo+subtitulo), retorna vazio - sinaliza que
    # precisa rehidratar via pipeline_v90 com isolamento V200_43.
    if len(texto_limpo) < 80:
        return ""
    return texto_limpo


def _link_pauta_para_hidratacao(p: dict) -> str:
    """Retorna o melhor URL real disponivel para hidratar texto da fonte."""
    for k in (
        "link_origem_resolvido",
        "url_final",
        "canonical_url",
        "link_origem",
        "url_original",
        "link",
        "url",
        "fonte_url",
        "origem_url",
    ):
        v = p.get(k)
        if isinstance(v, str):
            url = v.strip()
            if url.startswith(("http://", "https://")):
                return url
    return ""


def _classificar_url_hidratacao(url: str) -> tuple[str, str]:
    """Classifica dominio/tipo para reusar os adaptadores do pipeline v90."""
    try:
        dominio = urlparse(url).netloc.lower()
    except Exception:
        return "", "generic"
    if not dominio:
        return "", "generic"
    if "g1.globo" in dominio or dominio.endswith("globo.com"):
        tipo = "globo"
    elif "folha.uol.com.br" in dominio or dominio.endswith("uol.com.br"):
        tipo = "uol"
    elif "agenciabrasil.ebc.com.br" in dominio:
        tipo = "agenciabrasil"
    elif dominio.endswith((".jus.br", ".gov.br", ".mp.br")) or "alerj" in dominio:
        tipo = "oficial"
    else:
        tipo = "generic"
    return dominio, tipo


def _pauta_view(p: dict) -> dict:
    st = _status_visual_v200(p)
    uid = p.get("uid") or p.get("_uid") or ""
    imagem_url = _detectar_imagem_url(p)
    imagem_local = p.get("imagem_caminho") or ""
    # Sempre temos thumb: a propria pauta tem URL/arquivo OU o endpoint cai
    # para favicon do dominio da fonte, garantindo identidade visual no card.
    imagem_thumb = f"/api/pautas/{uid}/imagem" if uid else ""
    md = _parse_materia_pauta(p) if isinstance(p, dict) else None
    materia_pronta = bool(md and (md.get("conteudo") or md.get("corpo_materia")))
    return {
        "uid": uid,
        "titulo": p.get("titulo_origem") or p.get("titulo") or "",
        "fonte": p.get("fonte_nome") or p.get("fonte") or "",
        "link": p.get("link_origem") or p.get("url") or "",
        "data": _data_visual(p),
        "captada_em": p.get("captada_em") or "",
        "atualizada_em": p.get("atualizada_em") or "",
        "data_pub_fonte": p.get("data_pub_fonte") or p.get("data_fonte") or "",
        "metodo": (
            p.get("metodo_feed_universal")
            or p.get("extraction_method")
            or p.get("origem_captacao")
            or p.get("origem")
            or ""
        ),
        "status_pauta": p.get("status") or "",
        "score": int(p.get("score_editorial") or 0),
        "score_risco": int(p.get("score_risco") or 0),
        "coleta_lote": (
            p.get("coleta_lote_label_v123")
            or p.get("coleta_lote")
            or ""
        ),
        "txt_chars": int(st["chars"]),
        "txt_rotulo": st["rotulo"],
        "fonte_status": st["fonte_status"],
        "imagem_url": imagem_url,
        "imagem_local": imagem_local,
        "imagem_thumb": imagem_thumb,
        "imagem_status": p.get("imagem_status") or "",
        "materia_pronta": materia_pronta,
        "resumo": p.get("resumo_origem") or "",
        "canal": p.get("canal_forcado") or p.get("canal") or "",
        "urgente": bool(p.get("urgente")),
        "termos_prioridade": list(
            p.get("_v129_termos_positivos")
            or p.get("_v129_termos_prioridade")
            or []
        )[:6],
    }


# ────────────────────────────────────────────────────────────────────────────
# Handlers.
# ────────────────────────────────────────────────────────────────────────────

def handler_health(db) -> tuple[int, dict, bytes]:
    settings = _import_settings()
    arquivo_db = getattr(settings, "ARQUIVO_DB", "ururau.db")
    _client, _modelo = _get_openai_client()
    return _json_response(
        {
            "ok": True,
            "servico": "ururau_web",
            "versao": "1.15.13",
            "arquivo_db": arquivo_db,
            "db_existe": Path(arquivo_db).exists() or (Path("sistema") / arquivo_db).exists(),
            "ts": datetime.now().isoformat(timespec="seconds"),
            "publicacao_automatica": False,
            "ia_configurada": bool(_client),
            "ia_modelo": _modelo,
        }
    )


_CORTE_FILE = Path("data") / "web_corte_captacao.txt"
_PROMPT_COPYDESK_FILE = Path("data") / "web_prompt_copydesk_padrao.txt"


def _ler_prompt_copydesk_padrao() -> str:
    """Le o prompt SEO padrao do Copydesk."""
    for p in (_PROMPT_COPYDESK_FILE, Path("sistema") / _PROMPT_COPYDESK_FILE):
        try:
            if p.exists():
                return p.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""


def _gravar_prompt_copydesk_padrao(conteudo: str) -> Path:
    """Persiste o prompt SEO padrao do Copydesk em data/."""
    base = _PROMPT_COPYDESK_FILE
    if not base.parent.exists():
        alt = Path("sistema") / _PROMPT_COPYDESK_FILE
        if alt.parent.exists():
            base = alt
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_text(conteudo or "", encoding="utf-8")
    return base


def handler_get_prompt_copydesk(db) -> tuple[int, dict, bytes]:
    return _json_response({
        "ok": True,
        "prompt": _ler_prompt_copydesk_padrao(),
    })


def handler_post_prompt_copydesk(db, body: dict) -> tuple[int, dict, bytes]:
    conteudo = str((body or {}).get("prompt") or "").strip()
    try:
        gravado = _gravar_prompt_copydesk_padrao(conteudo)
    except Exception as exc:
        return _error(f"falha ao salvar: {exc}", status=500)
    return _json_response({"ok": True, "arquivo": str(gravado), "tamanho": len(conteudo)})


def _ler_corte(db=None) -> str:
    """Le o timestamp ISO do corte (vazio se nao houver)."""
    if db is not None and getattr(db, "caminho", None):
        try:
            db_path = Path(db.caminho).resolve()
            cwd = Path.cwd().resolve()
            try:
                db_no_projeto = db_path.is_relative_to(cwd)
            except AttributeError:
                db_no_projeto = str(db_path).startswith(str(cwd))
            local = db_path.parent / _CORTE_FILE.name
            if local.exists():
                v = local.read_text(encoding="utf-8").strip()
                if v:
                    return v
            if not db_no_projeto:
                return ""
        except Exception:
            pass
    for p in (_CORTE_FILE, Path("sistema") / _CORTE_FILE):
        try:
            if p.exists():
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except Exception:
            pass
    return ""


def handler_listar_pautas(db, qs: dict[str, str]) -> tuple[int, dict, bytes]:
    try:
        limite = max(1, min(int(qs.get("limite") or 500), 1000))
    except Exception:
        limite = 500
    incluir_baixo = qs.get("incluir_baixo_score", "1").strip() not in {"0", "false", "nao", "não"}

    fila_raw = db.query_fila_ativa(
        incluir_baixo_score=incluir_baixo,
        limite=max(limite, 1000) if _ler_corte(db) else limite,  # pega mais quando ha corte para nao deixar fila vazia
    )

    # Filtro de corte: oculta tudo antes do timestamp salvo em data/web_corte_captacao.txt
    corte = _ler_corte(db)
    fila_corte = list(fila_raw)
    if corte:
        antes_corte = len(fila_corte)
        c = corte[:19]
        def _capt_iso(p):
            return str(p.get("captada_em") or p.get("atualizada_em") or "")[:19]
        fila_corte = [p for p in fila_corte if _capt_iso(p) >= c]
        # mantem itens em redacao/revisada/pronta independente do corte (work in progress)
        for p in fila_raw:
            st = str(p.get("status") or "").lower()
            if st in {"em_redacao", "revisada", "pronta"} and p not in fila_corte:
                fila_corte.append(p)

    # V200_17: filtro de janela de PUBLICACAO DA FONTE (8h max).
    # Considera a hora em que a materia foi publicada no site original,
    # NAO a hora da coleta. Antes uma materia de 15/05 captada em 17/05
    # ficava no topo porque captada_em era recente.
    try:
        from datetime import timedelta as _td
        try:
            from zoneinfo import ZoneInfo as _ZI
            _agora_br = datetime.now(_ZI("America/Sao_Paulo")).replace(tzinfo=None)
        except Exception:
            _agora_br = datetime.now()
        _JANELA_MAX_H = int(os.environ.get("URURAU_FILA_JANELA_MAX_H", "8"))
        _limite_dt = _agora_br - _td(hours=_JANELA_MAX_H)
        def _pub_dt(p):
            """Data de publicacao real da fonte, com fallback para captada_em."""
            for k in ("data_pub_fonte", "data_fonte", "published_iso",
                      "published", "pub_date", "pubDate", "datePublished",
                      "data_publicacao"):
                v = p.get(k)
                if isinstance(v, str) and v.strip() and not v.lower().startswith("captada:"):
                    try:
                        s = v.replace("T", " ")[:19].replace(" ", "T")
                        return datetime.fromisoformat(s)
                    except Exception:
                        # tenta dd/mm/aaaa
                        import re as _re
                        m = _re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", v.strip())
                        if m:
                            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                            h = int(m.group(4) or 0); mi = int(m.group(5) or 0)
                            try:
                                return datetime(y, mo, d, h, mi)
                            except Exception:
                                pass
            # fallback: captada_em
            cap = str(p.get("captada_em") or p.get("atualizada_em") or "")[:19]
            try:
                return datetime.fromisoformat(cap) if cap else _agora_br
            except Exception:
                return _agora_br
        # V200_24: tolerancia para datas zeradas (Google News retorna pubDate
        # "17/05/2026 00:00" - meia-noite do dia, hora real desconhecida).
        # Regra ampliada:
        #   - Se a data de publicacao >= limite (8h atras), passa
        #   - OU se captada nas ultimas 8h (independente de pub_dt), passa
        #   - OU se status e em_redacao/revisada/pronta/publicada, passa
        # Isso garante que toda materia COLETADA RECENTEMENTE entre na fila,
        # mesmo que a fonte tenha pubDate impreciso.
        def _captada_recente(p):
            cap_iso = str(p.get("captada_em") or p.get("atualizada_em") or "")[:19]
            if not cap_iso:
                return False
            try:
                return datetime.fromisoformat(cap_iso) >= _limite_dt
            except Exception:
                return False
        fila_corte = [
            p for p in fila_corte
            if _pub_dt(p) >= _limite_dt
            or _captada_recente(p)
            or str(p.get("status") or "").lower() in {
                "em_redacao", "revisada", "pronta", "publicada", "publicado",
            }
        ]
    except Exception as _e_jan:
        print(f"[ururau_web] V200_17 filtro janela publicacao falhou: {_e_jan}")

    # ── v1.14.3 WEB: NAO usa o filtro V200 do desktop (filtrar_pendentes)
    # porque ele prioriza a "ultima coleta" baseado no contador legado
    # coleta_seq_v123 (que chegou em 112) e oculta as coletas novas do
    # web (que reiniciam em 01 a cada dia). Resultado visivel: a tela
    # ficava travada em "Coleta 112" e novas pautas nunca apareciam.
    # Solucao: ordenar puramente por captada_em DESC (cronologico real).
    fila_filtrada = list(fila_corte)
    # V200_16: ordenacao da fila
    #   1) Materias ja processadas (PUBLICADA, REVISADA, REDIGIDA, TXT OK) vem no topo
    #   2) Dentro de cada grupo, mais recentes primeiro (captada_em DESC)
    #   3) TXT... e TXT CURTO vao para o final
    def _grupo_prioridade(p):
        texto = str(p.get("cleaned_source_text") or p.get("texto_fonte") or "").strip()
        status_pauta = str(p.get("status") or "").lower()
        if status_pauta in {"publicada", "publicado"}:
            return 0  # ja publicada -> topo
        if status_pauta == "revisada":
            return 1  # revisada
        if status_pauta in {"redigida", "em_redacao", "em_redação", "pronta"}:
            return 2  # redigida
        if len(texto) >= 550:
            return 3  # TXT OK
        return 9  # TXT.../TXT CURTO/etc -> fundo
    def _data_pub_key(p):
        """V200_17: ordena por data de publicacao REAL da fonte, nao por
        captada_em. Garante que materias mais recentes da fonte fiquem
        no topo, e nao materias antigas captadas hoje."""
        for k in ("data_pub_fonte", "data_fonte", "published_iso",
                  "published", "pub_date", "pubDate", "datePublished"):
            v = p.get(k)
            if isinstance(v, str) and v.strip() and not v.lower().startswith("captada:"):
                try:
                    return datetime.fromisoformat(
                        v.replace("T", " ")[:19].replace(" ", "T")
                    ).isoformat()
                except Exception:
                    pass
        # fallback: captada_em
        return str(p.get("captada_em") or p.get("atualizada_em") or "")[:19]
    try:
        # Sort estavel: primeiro por data de publicacao desc, depois por grupo
        fila_filtrada.sort(key=_data_pub_key, reverse=True)
        fila_filtrada.sort(key=_grupo_prioridade)
    except Exception:
        pass

    itens = [_pauta_view(p) for p in fila_filtrada[:limite]]
    return _json_response(
        {
            "ok": True,
            "total": len(itens),
            "limite": limite,
            "incluir_baixo_score": incluir_baixo,
            "corte_captacao": corte,
            "pautas": itens,
        }
    )


def handler_zerar_fila(db, body: dict) -> tuple[int, dict, bytes]:
    """Grava timestamp do corte. Pautas anteriores ficam ocultas (não apagadas)."""
    if not bool(body.get("confirm")):
        return _error("requer 'confirm=true' para zerar (decisao humana)", status=409)
    try:
        from zoneinfo import ZoneInfo
        agora = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")
    except Exception:
        agora = datetime.now().isoformat(timespec="seconds")
    # Tenta gravar no diretorio data/ relativo ao cwd; se nao existir, em sistema/data/
    destino = _CORTE_FILE
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        destino = Path("sistema") / _CORTE_FILE
        destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        destino.write_text(agora, encoding="utf-8")
    except Exception as exc:
        return _error(f"falha gravar corte: {exc}", status=500)
    return _json_response({"ok": True, "corte": agora, "arquivo": str(destino),
                            "info": "Pautas antigas continuam no banco; somente ocultas da fila web."})


def handler_restaurar_fila(db, body: dict) -> tuple[int, dict, bytes]:
    """Apaga o arquivo de corte: volta a mostrar todas as pautas."""
    for p in (_CORTE_FILE, Path("sistema") / _CORTE_FILE):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    return _json_response({"ok": True, "corte": "", "info": "Fila restaurada: mostra todas as pautas novamente."})


# ────────────────────────────────────────────────────────────────────────────
# Termos editoriais (prioridade/destaque) — reusa termos_captacao_premium_v88
# ────────────────────────────────────────────────────────────────────────────

def _path_termos() -> Path:
    """Localiza o arquivo termos_captacao_premium_v88.json (varios caminhos)."""
    for cam in (
        Path("termos_captacao_premium_v88.json"),
        Path("configuracoes/termos_captacao_premium_v88.json"),
        Path("sistema/termos_captacao_premium_v88.json"),
        Path("sistema/configuracoes/termos_captacao_premium_v88.json"),
    ):
        if cam.exists():
            return cam
    return Path("termos_captacao_premium_v88.json")


def handler_termos_get(db) -> tuple[int, dict, bytes]:
    p = _path_termos()
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            data = {"versao": "v88_terms_premium", "grupos": {}}
    except Exception as exc:
        return _error(f"falha ler termos: {exc}", status=500)
    return _json_response({"ok": True, "arquivo": str(p.resolve()),
                            "versao": data.get("versao", ""),
                            "grupos": data.get("grupos", {})})


def handler_termos_post(db, body: dict) -> tuple[int, dict, bytes]:
    if not isinstance(body, dict) or "grupos" not in body:
        return _error("body deve conter 'grupos' (dict de listas)", status=400)
    grupos = body["grupos"]
    if not isinstance(grupos, dict):
        return _error("'grupos' deve ser um dict", status=400)
    # Sanitiza: cada valor deve ser lista de strings.
    limpos: dict[str, list[str]] = {}
    for k, v in grupos.items():
        k = str(k or "").strip()
        if not k:
            continue
        if isinstance(v, str):
            v = [s.strip() for s in v.split(",")]
        if not isinstance(v, list):
            continue
        limpos[k] = [str(t).strip() for t in v if str(t).strip()]
    p = _path_termos()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"versao": body.get("versao") or "v88_terms_premium", "grupos": limpos}
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        return _error(f"falha gravar termos: {exc}", status=500)
    total = sum(len(v) for v in limpos.values())
    return _json_response({"ok": True, "arquivo": str(p.resolve()),
                            "grupos": len(limpos), "total_termos": total})


# ────────────────────────────────────────────────────────────────────────────
# Fontes RSS editáveis pela UI
# ────────────────────────────────────────────────────────────────────────────

def _path_fontes_rss() -> Path:
    for cam in (
        Path("config/fontes_rss.json"),
        Path("configuracoes/fontes_rss.json"),
        Path("fontes_rss.json"),
        Path("sistema/config/fontes_rss.json"),
    ):
        if cam.exists():
            return cam
    return Path("config/fontes_rss.json")


def handler_fontes_get(db) -> tuple[int, dict, bytes]:
    p = _path_fontes_rss()
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            data = []
    except Exception as exc:
        return _error(f"falha ler fontes: {exc}", status=500)
    if not isinstance(data, list):
        data = []
    return _json_response({"ok": True, "arquivo": str(p.resolve()), "fontes": data})


def handler_fontes_post(db, body: dict) -> tuple[int, dict, bytes]:
    if not isinstance(body, dict) or "fontes" not in body:
        return _error("body deve conter 'fontes' (lista de objetos)", status=400)
    fontes = body["fontes"]
    if not isinstance(fontes, list):
        return _error("'fontes' deve ser lista", status=400)
    limpas = []
    for i, f in enumerate(fontes):
        if not isinstance(f, dict):
            continue
        url = str(f.get("url") or "").strip()
        nome = str(f.get("nome") or "").strip()
        if not url or not nome:
            continue
        # V200_35: preserva campos extras (links, _obs, _origem) para
        # fontes oficiais/especiais que entraram na UI via merge.
        item = {
            "url": url,
            "nome": nome,
            "canal_forcado": str(f.get("canal_forcado") or "").strip(),
            "ativo": bool(f.get("ativo", True)),
            "tipo_coleta": str(f.get("tipo_coleta") or "rss"),
            "max_por_link": int(f.get("max_por_link") or 5),
            "ordem": int(f.get("ordem") or (i + 1)),
        }
        links_extra = f.get("links")
        if isinstance(links_extra, list) and links_extra:
            item["links"] = [str(x).strip() for x in links_extra if str(x).strip()]
        if f.get("_obs"):
            item["_obs"] = str(f.get("_obs")).strip()
        if f.get("_origem"):
            item["_origem"] = str(f.get("_origem")).strip()
        limpas.append(item)
    p = _path_fontes_rss()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(limpas, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        return _error(f"falha gravar fontes: {exc}", status=500)
    return _json_response({"ok": True, "arquivo": str(p.resolve()),
                            "total": len(limpas), "ativas": sum(1 for x in limpas if x.get("ativo"))})


def _normalizar_dominio(url_ou_dominio: str) -> tuple[str, str]:
    """De 'folha1.com.br', 'https://folha1.com.br/', 'www.folha1.com.br',
    extrai (dominio_limpo, url_base_https). Ex.:
       ('folha1.com.br', 'https://folha1.com.br')
       ('www.folha1.com.br', 'https://www.folha1.com.br')
    """
    s = (url_ou_dominio or "").strip().lower()
    if not s:
        return "", ""
    # Remove protocolo (ja em lowercase)
    if s.startswith("http://"):
        s = s[7:]
    elif s.startswith("https://"):
        s = s[8:]
    elif s.startswith("//"):
        s = s[2:]
    # Remove path/query/fragment
    s = s.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
    # Remove porta
    s = s.split(":", 1)[0].strip()
    if not s:
        return "", ""
    base = f"https://{s}"
    return s, base


def _validar_feed_rss(url: str, timeout: float = 6.0) -> tuple[bool, str, int]:
    """Verifica se uma URL retorna um feed RSS/Atom valido.
    Retorna (ok, motivo, n_items).
    """
    import urllib.request
    import re as _re
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Ururau-RSS-Discover/1.0)",
            "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status >= 400:
                return (False, f"HTTP {resp.status}", 0)
            raw = resp.read(200_000)
        # Detecta encoding
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.decode("latin-1", errors="replace")
        snippet = html[:5000].lower()
        # Confere se tem cara de RSS/Atom
        if not any(tag in snippet for tag in ("<rss", "<feed", "<channel>", "<atom:feed")):
            return (False, "nao parece RSS/Atom", 0)
        # Conta items
        n_items = len(_re.findall(r"<item[\s>]|<entry[\s>]", html, _re.IGNORECASE))
        if n_items == 0:
            return (False, "feed sem <item>/<entry>", 0)
        return (True, f"{n_items} items", n_items)
    except Exception as exc:
        msg = str(exc)[:100]
        return (False, f"erro: {type(exc).__name__}: {msg}", 0)


def _descobrir_feed_rss(url_input: str) -> dict:
    """Tenta descobrir o feed RSS de um site testando endpoints comuns.
    Estrategia em 3 fases:
      1) Tenta sufixos comuns no dominio raiz (cobre 95% dos WordPress)
      2) Parseia HTML procurando <link rel="alternate" type="application/rss+xml">
      3) Fallback: gera URL do Google News com site:<dominio>
    Retorna dict: {dominio, feed_url, fonte_descoberta, valida, motivo, items}
    """
    dominio, base = _normalizar_dominio(url_input)
    if not dominio:
        return {"dominio": "", "feed_url": "", "fonte_descoberta": "erro",
                "valida": False, "motivo": "URL invalida", "items": 0}

    # Fase 1: tenta sufixos comuns (em ordem de probabilidade)
    sufixos = [
        "/feed/",          # WordPress padrao
        "/feed",           # WordPress sem barra
        "/rss",            # Drupal, sites genericos
        "/rss.xml",        # Padrao classico
        "/feed.xml",       # Some custom
        "/atom.xml",       # Atom feed
        "/?feed=rss2",     # WordPress alternativo
        "/feed/rss/",      # Variante
        "/feeds/posts/default",  # Blogger
    ]
    for sufixo in sufixos:
        candidato = base + sufixo
        ok, motivo, n_items = _validar_feed_rss(candidato, timeout=5.0)
        if ok:
            return {
                "dominio": dominio,
                "feed_url": candidato,
                "fonte_descoberta": "sufixo_padrao",
                "valida": True,
                "motivo": motivo,
                "items": n_items,
            }

    # Fase 2: baixa a home e procura por <link rel="alternate" type="application/rss+xml">
    try:
        import urllib.request
        import re as _re
        from urllib.parse import urljoin
        req = urllib.request.Request(base, headers={
            "User-Agent": "Mozilla/5.0 (Ururau-RSS-Discover/1.0)",
        })
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            raw = resp.read(200_000)
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.decode("latin-1", errors="replace")
        # Procura link de feed no <head>
        pat = r'<link[^>]+(?:type=["\'](?:application/rss\+xml|application/atom\+xml)["\']|rel=["\']alternate["\'])[^>]+href=["\']([^"\']+)["\']'
        for m in _re.finditer(pat, html, _re.IGNORECASE):
            href = m.group(1).strip()
            if not href:
                continue
            full = urljoin(base + "/", href)
            ok, motivo, n_items = _validar_feed_rss(full, timeout=5.0)
            if ok:
                return {
                    "dominio": dominio,
                    "feed_url": full,
                    "fonte_descoberta": "html_link_alternate",
                    "valida": True,
                    "motivo": motivo,
                    "items": n_items,
                }
    except Exception:
        pass

    # Fase 3: fallback Google News
    from urllib.parse import quote_plus
    gnews = f"https://news.google.com/rss/search?q={quote_plus('site:' + dominio + ' when:24h')}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    ok, motivo, n_items = _validar_feed_rss(gnews, timeout=8.0)
    if ok:
        return {
            "dominio": dominio,
            "feed_url": gnews,
            "fonte_descoberta": "google_news_fallback",
            "valida": True,
            "motivo": motivo,
            "items": n_items,
        }

    return {
        "dominio": dominio,
        "feed_url": "",
        "fonte_descoberta": "nenhuma",
        "valida": False,
        "motivo": "nenhuma estrategia retornou feed valido",
        "items": 0,
    }


def handler_fontes_auto_discover(db, body: dict) -> tuple[int, dict, bytes]:
    """Recebe lista de URLs/dominios, tenta descobrir o feed de cada um,
    e (se solicitado) adiciona ao fontes_rss.json automaticamente.

    Body: {
        "urls": ["folha1.com.br", "https://campos24horas.com.br", ...],
        "adicionar": true,   // se true, salva os feeds validos no arquivo
    }
    Resposta: {
        ok: true,
        resultados: [{dominio, nome_sugerido, feed_url, valida, motivo, items, ...}],
        adicionadas: N,
        ja_existiam: M,
        invalidas: K,
    }
    """
    if not isinstance(body, dict):
        return _error("body invalido", status=400)
    urls = body.get("urls") or []
    if isinstance(urls, str):
        # Aceita string com URLs separadas por quebra de linha ou vírgula
        urls = [u.strip() for u in urls.replace(",", "\n").splitlines() if u.strip()]
    if not isinstance(urls, list) or not urls:
        return _error("informe 'urls' como lista ou string com URLs", status=400)
    adicionar = bool(body.get("adicionar", True))

    # Le fontes existentes para evitar duplicatas
    p = _path_fontes_rss()
    try:
        fontes_existentes = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except Exception:
        fontes_existentes = []
    if not isinstance(fontes_existentes, list):
        fontes_existentes = []
    urls_existentes_norm = {
        str(f.get("url", "")).rstrip("/").lower() for f in fontes_existentes
    }
    dominios_existentes = set()
    for f in fontes_existentes:
        try:
            from urllib.parse import urlparse
            host = urlparse(f.get("url", "")).netloc.lower().replace("www.", "")
            if host:
                dominios_existentes.add(host)
        except Exception:
            pass
    max_ordem = max((int(f.get("ordem") or 0) for f in fontes_existentes), default=0)

    resultados = []
    novas_para_adicionar = []
    for raw_url in urls:
        raw_url = str(raw_url).strip()
        if not raw_url:
            continue
        # v1.15.7: auto-deteccao inteligente. Testa em ordem rapido->lento:
        #   1. RSS direto (/feed/, /rss, etc)
        #   2. Jina Home (SPAs e sites com anti-bot)
        #   3. Google News fallback (sempre tem algo)
        try:
            from ururau.coleta.auto_detect_fonte import detectar_melhor_metodo
            r_detect = detectar_melhor_metodo(raw_url)
        except Exception as _e_det:
            # se auto-detect quebrar, cai no metodo antigo
            r_detect = None
        if r_detect:
            from urllib.parse import urlparse as _up
            dom = _up(r_detect["url_recomendada"]).netloc.lower()
            dom_sem_www = dom.replace("www.", "")
            nome_sugerido = r_detect.get("nome_sugerido") or (
                dom_sem_www.split(".")[0].replace("-", " ").title()
            )
            descoberta = {
                "dominio": dom,
                "feed_url": r_detect["url_recomendada"],
                "fonte_descoberta": r_detect["metodo_detalhe"],
                "valida": r_detect["ok"],
                "motivo": r_detect["metodo_detalhe"],
                "items": r_detect["qtd_amostra"],
                "tipo_coleta": r_detect["tipo_coleta"],
                "nome_sugerido": nome_sugerido,
                "url_input": raw_url,
            }
        else:
            descoberta = _descobrir_feed_rss(raw_url)
            dom_sem_www = descoberta["dominio"].replace("www.", "")
            descoberta["nome_sugerido"] = dom_sem_www.split(".")[0].replace("-", " ").title()
            descoberta["url_input"] = raw_url
            descoberta["tipo_coleta"] = "rss"

        # Verifica duplicata por dominio OU pela url exata
        ja_existe = (
            dom_sem_www in dominios_existentes
            or descoberta["feed_url"].rstrip("/").lower() in urls_existentes_norm
        )
        descoberta["ja_existia"] = ja_existe

        if descoberta["valida"] and adicionar and not ja_existe:
            max_ordem += 1
            novas_para_adicionar.append({
                "url": descoberta["feed_url"],
                "nome": descoberta["nome_sugerido"],
                "canal_forcado": "",
                "ativo": True,
                "tipo_coleta": descoberta.get("tipo_coleta", "rss"),
                "max_por_link": 8 if descoberta.get("tipo_coleta") == "jina_home" else 5,
                "ordem": max_ordem,
                "_descoberta": descoberta["fonte_descoberta"],
            })
            descoberta["adicionada"] = True
        else:
            descoberta["adicionada"] = False
        resultados.append(descoberta)

    # Persiste se houve novas
    if novas_para_adicionar:
        fontes_existentes.extend(novas_para_adicionar)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(
                json.dumps(fontes_existentes, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            return _error(f"falha gravar fontes: {exc}", status=500)

    return _json_response({
        "ok": True,
        "arquivo": str(p.resolve()),
        "resultados": resultados,
        "adicionadas": len(novas_para_adicionar),
        "ja_existiam": sum(1 for r in resultados if r["ja_existia"]),
        "invalidas": sum(1 for r in resultados if not r["valida"]),
        "total_fontes_apos": len(fontes_existentes),
    })


def handler_detalhe_pauta(db, uid: str) -> tuple[int, dict, bytes]:
    if not uid:
        return _error("uid ausente", status=400)
    pauta = db.buscar_pauta(uid)
    if not pauta:
        return _error("pauta nao encontrada", status=404, uid=uid)
    extra = {}
    try:
        if pauta.get("dados_json"):
            extra = json.loads(pauta["dados_json"]) or {}
    except Exception:
        extra = {}
    merged = {**pauta, **(extra if isinstance(extra, dict) else {})}

    # V200_44: invalida cleaned_source_text contaminado com boilerplate de lista
    # lateral (caso Prefeitura de Campos). Forca re-extracao na hidratacao
    # on-demand abaixo, que usa pipeline_v90 com isolamento V200_43.
    try:
        _texto_existente = str(merged.get("cleaned_source_text") or "")
        if _texto_existente and _texto_tem_boilerplate_lista(_texto_existente):
            print(f"[ururau_web][V200_44] uid={uid} texto contaminado com lista lateral detectado - invalidando para rehidratar")
            merged["cleaned_source_text"] = ""
            merged["texto_fonte"] = ""
            for _k_invalida in ("fonte_status", "status_fonte_v105", "fonte_chars_v105",
                                "texto_fonte_chars", "hidratacao_on_demand",
                                "hidratado_em", "_hidratador_bg_tentado_em"):
                merged.pop(_k_invalida, None)
    except Exception as _e_inv:
        print(f"[ururau_web][V200_44] deteccao falhou uid={uid}: {_e_inv}")

    view = _pauta_view(merged)
    # v1.15.5: HIDRATACAO ON-DEMAND.
    # Se nao ha texto hidratado completo (cleaned_source_text/texto_fonte) e
    # existe um link, tenta extrair AGORA usando trafilatura. Resolve o caso
    # de pautas que entraram pela coleta RSS principal sem passar por
    # source_hunter (Giro RJ, Band, Folha 1, etc.).
    _texto_hidratado = (merged.get("cleaned_source_text") or "").strip()
    _texto_legacy = (merged.get("texto_fonte") or "").strip()
    _metodo_hidratacao = ""
    # v1.15.10: Limiar 1500 chars. Resumos de RSS WordPress costumam ter
    # 600-1500 chars com entidades HTML e marcadores "The post X appeared".
    # So texto >= 1500 (cinco-seis paragrafos reais) eh considerado completo.
    # Caso contrario, dispara escada trafilatura -> Jina e marca on-demand
    # para nao repetir nas proximas requisicoes.
    # V200_28: voltou para 1500 - o hidratador BG ja garante que materias
    # com texto >= 1500 chars sao hidratacoes reais (nao resumo). Manter
    # em 3000 fazia toda materia 1500-3000 disparar hidratacao on-demand a
    # cada click, demorando 5-30s. Agora so dispara se texto < 1500 chars.
    _TEXTO_MIN_UTIL = 1500
    _maior_texto = max(len(_texto_hidratado), len(_texto_legacy))
    _metodo_anterior = merged.get("hidratacao_on_demand", "")
    _link_pauta = _link_pauta_para_hidratacao(merged)
    # So considera hidratado se a tecnica foi GOOGLEBOT e veio texto util
    # (Googlebot e a tecnica mais robusta para paywall poroso brasileiro)
    # V200_7: tambem aceita source_hunter:* (bypass Burlesco, adapters globo/uol,
    # generic, etc) com texto >= 1000 chars - evita lag ao clicar em pauta
    # ja resgatada pelo bypass.
    _metodo_eh_burlesco = (
        isinstance(_metodo_anterior, str)
        and _metodo_anterior.startswith(("source_hunter", "bypass_"))
    )
    _ja_hidratado_ok = (
        (_metodo_anterior == "googlebot" and _maior_texto >= 1000)
        or (_metodo_eh_burlesco and _maior_texto >= 1000)
    )
    _precisa_hidratar = (
        not _ja_hidratado_ok
        and _maior_texto < _TEXTO_MIN_UTIL
        and _link_pauta
        and _link_pauta.startswith(("http://", "https://"))
    )
    # DEBUG v1.15.13 - loga sempre pra descobrir por que nao dispara
    print("[DEBUG_HIDRAT] uid=" + str(uid) + " precisa=" + str(_precisa_hidratar) + " ja_ok=" + str(_ja_hidratado_ok) + " texto_max=" + str(_maior_texto) + " metodo_ant=" + str(_metodo_anterior) + " link=" + str(_link_pauta)[:80])
    if _precisa_hidratar:
        print("[ururau_web][HIDRATACAO_ON_DEMAND] disparando uid=" + str(uid) + " texto_atual=" + str(_maior_texto) + "chars link=" + _link_pauta[:80])
        # v1.15.6: ESCADA DE HIDRATACAO ON-DEMAND
        # 1) resolver Google News/canonical para URL real
        # 2) pipeline v90 completo (adaptadores, JSON, WP REST, densidade, Jina)
        # 3) leitura_fonte v104/v136
        # 4) trafilatura -> Googlebot -> Jina como fallback local
        _link_original = _link_pauta
        _tentativas_resolucao = []

        # ESCADA 0: resolve Google News/AMP/redirecionamentos antes de extrair.
        try:
            from ururau.coleta.link_resolver_v90 import resolver_url_final_v90
            _res = resolver_url_final_v90(
                _link_pauta,
                merged.get("titulo_origem") or merged.get("titulo") or "",
                merged.get("fonte_nome") or merged.get("fonte") or "",
            )
            _tentativas_resolucao = _res.get("tentativas") or []
            _url_resolvida = str(_res.get("url_final") or "").strip()
            if _res.get("ok") and _url_resolvida.startswith(("http://", "https://")):
                if _url_resolvida != _link_pauta:
                    print("[ururau_web][HIDRATACAO_ON_DEMAND][resolver] uid=" + str(uid) + " " + _link_pauta[:60] + " -> " + _url_resolvida[:90])
                _link_pauta = _url_resolvida
                merged["url_final"] = _url_resolvida
                merged["link_origem_resolvido"] = _url_resolvida
                view["link"] = _url_resolvida
            elif _res.get("status"):
                merged["motivo_extracao"] = str(_res.get("status"))
        except Exception as _e_res:
            print("[ururau_web][HIDRATACAO_ON_DEMAND] resolver falhou uid=" + str(uid) + ": " + str(_e_res))

        # ESCADA 1: pipeline premium v90 ja concentra adaptadores, fallbacks e Jina.
        # V200_48: se pipeline_v90 ACEITA via adapter especializado (oficial/article,
        # globo/article-article, uol/article, bypass_burlesco_rule), CONFIA no
        # resultado mesmo abaixo de TEXTO_MIN_UTIL=1500. Esses adapters ja tem
        # critério_aceite_v90 validando paragrafos uteis. Senao, as escadas
        # seguintes (leitura_fonte, googlebot, trafilatura) podem SOBRESCREVER
        # texto limpo do adapter com lixo de pagina inteira (caso campos.rj.gov.br).
        _pipeline_v90_aceito_por_adapter = False
        if not _texto_hidratado or len(_texto_hidratado) < _TEXTO_MIN_UTIL:
            try:
                from ururau.coleta.extract_pipeline_v90 import extrair_materia_v90
                _dominio, _tipo_site = _classificar_url_hidratacao(_link_pauta)
                _pipe = extrair_materia_v90(
                    _link_pauta,
                    dominio=_dominio,
                    tipo_site=_tipo_site,
                    contexto={"uid": uid, "origem": "web_on_demand"},
                )
                _pipe_texto = str(_pipe.get("texto") or "").strip()
                if _pipe.get("tentativas"):
                    merged["tentativas"] = _pipe.get("tentativas")
                if _pipe.get("motivo"):
                    merged["motivo_extracao"] = _pipe.get("motivo")
                _pipe_url_final = str(_pipe.get("url_final") or "").strip()
                if _pipe_url_final.startswith(("http://", "https://")):
                    _link_pauta = _pipe_url_final
                    merged["url_final"] = _pipe_url_final
                    view["link"] = _pipe_url_final
                if _pipe.get("aceita") and len(_pipe_texto) >= 700:
                    _texto_hidratado = _pipe_texto
                    _pipe_metodo = str(_pipe.get("metodo") or "")
                    _metodo_hidratacao = "pipeline_v90:" + _pipe_metodo
                    # V200_48: marca confianca quando adapter especializado entregou
                    _adapters_confiaveis = (
                        "oficial/", "globo/", "uol/", "folha/", "agenciabrasil/",
                        "wordpress/", "bypass_",
                    )
                    if any(_pipe_metodo.startswith(p) for p in _adapters_confiaveis):
                        _pipeline_v90_aceito_por_adapter = True
                    print("[ururau_web][HIDRATACAO_ON_DEMAND][pipeline_v90] uid=" + str(uid) + " chars=" + str(len(_texto_hidratado)) + " metodo=" + _pipe_metodo + " confiavel=" + str(_pipeline_v90_aceito_por_adapter))
            except Exception as _e_pipe:
                print("[ururau_web][HIDRATACAO_ON_DEMAND] pipeline_v90 falhou uid=" + str(uid) + ": " + str(_e_pipe))

        # V200_48: se adapter especializado deu sucesso, NAO disparar escadas
        # seguintes mesmo se texto < TEXTO_MIN_UTIL. As outras escadas podem
        # contaminar com texto de pagina inteira.
        if _pipeline_v90_aceito_por_adapter:
            print("[ururau_web][HIDRATACAO_ON_DEMAND] V200_48 - adapter especializado entregou texto limpo, pulando escadas 2-5")

        # ESCADA 2: leitura_fonte reaproveita heuristicas historicas do painel.
        # V200_48: pula se pipeline_v90 ja entregou texto limpo via adapter.
        if not _pipeline_v90_aceito_por_adapter and (not _texto_hidratado or len(_texto_hidratado) < _TEXTO_MIN_UTIL):
            try:
                from ururau.coleta.leitura_fonte import ler_fonte_pauta
                _pauta_lf = {**merged}
                _pauta_lf["link_origem"] = _link_pauta
                _pauta_lf["url_final"] = _link_pauta
                _pauta_lf["cleaned_source_text"] = ""
                _pauta_lf["texto_fonte"] = ""
                _lf = ler_fonte_pauta(_pauta_lf, forcar_refresh=True)
                _lf_texto = str(getattr(_lf, "texto_limpo", "") or "").strip()
                if getattr(_lf, "sucesso", False) and len(_lf_texto) >= 700:
                    _texto_hidratado = _lf_texto
                    _metodo_hidratacao = "leitura_fonte"
                    if getattr(_lf, "url", ""):
                        _link_pauta = getattr(_lf, "url")
                        merged["url_final"] = _link_pauta
                        view["link"] = _link_pauta
                    print("[ururau_web][HIDRATACAO_ON_DEMAND][leitura_fonte] uid=" + str(uid) + " chars=" + str(len(_texto_hidratado)))
            except Exception as _e_lf:
                print("[ururau_web][HIDRATACAO_ON_DEMAND] leitura_fonte falhou uid=" + str(uid) + ": " + str(_e_lf))

        # ESCADA 3: trafilatura
        # V200_48: pula se pipeline_v90 ja entregou texto limpo via adapter especializado.
        if not _pipeline_v90_aceito_por_adapter and (not _texto_hidratado or len(_texto_hidratado) < _TEXTO_MIN_UTIL):
            try:
                import trafilatura as _traf
                _downloaded = _traf.fetch_url(_link_pauta)
                if _downloaded:
                    _result = _traf.extract(
                        _downloaded, url=_link_pauta,
                        include_comments=False, include_tables=False,
                        favor_recall=True, with_metadata=False,
                        output_format="txt", target_language="pt",
                    )
                    # v1.15.9: aceita >=500 chars (era 200). Texto curto cai pra Jina.
                    if _result and len(_result.strip()) >= _TEXTO_MIN_UTIL:
                        _texto_hidratado = _result.strip()
                        _metodo_hidratacao = "trafilatura"
                        print(f"[ururau_web][HIDRATACAO_ON_DEMAND][trafilatura] uid={uid} chars={len(_texto_hidratado)}")
            except ImportError:
                pass
            except Exception as _e_traf:
                print(f"[ururau_web][HIDRATACAO_ON_DEMAND] trafilatura falhou uid={uid}: {_e_traf}")

        # ESCADA 4: Googlebot (tecnica Burlesco - libera paywall poroso
        # de Estadao, Globo, Veja, Exame, Crusoe etc)
        # V200_48: pula se pipeline_v90 ja entregou texto limpo via adapter.
        if not _pipeline_v90_aceito_por_adapter and (not _texto_hidratado or len(_texto_hidratado) < _TEXTO_MIN_UTIL):
            try:
                from ururau.coleta.googlebot_extractor import extrair_via_googlebot
                _gb = extrair_via_googlebot(_link_pauta, timeout=15, min_chars=_TEXTO_MIN_UTIL)
                if _gb.get("ok") and _gb.get("texto"):
                    _texto_hidratado = _gb["texto"].strip()
                    _metodo_hidratacao = "googlebot"
                    print("[ururau_web][HIDRATACAO_ON_DEMAND][googlebot] uid=" + str(uid) + " chars=" + str(len(_texto_hidratado)))
            except Exception as _e_gb:
                print("[ururau_web][HIDRATACAO_ON_DEMAND] googlebot excecao uid=" + str(uid) + ": " + str(_e_gb))

        # ESCADA 5: Jina Reader (ultimo recurso para SPAs e bloqueios)
        # V200_48: pula se pipeline_v90 ja entregou texto limpo via adapter.
        if not _pipeline_v90_aceito_por_adapter and (not _texto_hidratado or len(_texto_hidratado) < _TEXTO_MIN_UTIL):
            try:
                from ururau.coleta.jina_extractor import extrair_via_jina
                _jina = extrair_via_jina(_link_pauta, timeout=20, min_chars=300)
                if _jina.get("ok") and _jina.get("texto"):
                    _texto_hidratado = _jina["texto"].strip()
                    _metodo_hidratacao = "jina"
                    print(f"[ururau_web][HIDRATACAO_ON_DEMAND][jina] uid={uid} chars={len(_texto_hidratado)} elapsed={_jina.get('elapsed_s', 0):.1f}s")
                else:
                    print(f"[ururau_web][HIDRATACAO_ON_DEMAND][jina] uid={uid} falhou: {_jina.get('motivo', '?')}")
            except Exception as _e_jina:
                print(f"[ururau_web][HIDRATACAO_ON_DEMAND] jina excecao uid={uid}: {_e_jina}")

        # Persiste no banco se conseguiu hidratar (qualquer metodo)
        if _texto_hidratado and _metodo_hidratacao:
            try:
                _payload = {**(extra if isinstance(extra, dict) else {})}
                _payload["cleaned_source_text"] = _texto_hidratado
                _payload["hidratacao_on_demand"] = _metodo_hidratacao
                _payload["url_final"] = _link_pauta
                _payload["link_origem_resolvido"] = _link_pauta
                if _link_original != _link_pauta:
                    _payload["link_origem_original"] = _link_original
                if _tentativas_resolucao:
                    _payload["tentativas_resolucao_link"] = _tentativas_resolucao[-8:]
                if merged.get("tentativas"):
                    _payload["tentativas"] = merged.get("tentativas")
                if merged.get("motivo_extracao"):
                    _payload["motivo_extracao"] = merged.get("motivo_extracao")
                from datetime import datetime as _dt
                _payload["hidratado_em"] = _dt.now().isoformat(timespec="seconds")
                db.atualizar_pauta(uid, {"dados_json": json.dumps(_payload, ensure_ascii=False)})
                # V200_15: sinaliza pro front recarregar a fila para o badge
                # 'TXT OK' aparecer imediatamente (sem esperar auto-refresh).
                view["_hidratado_agora"] = True
                view["txt_chars"] = len(_texto_hidratado)
                view["txt_rotulo"] = "TXT OK"
                view["fonte_status"] = "ok"
                print(f"[ururau_web][HIDRATACAO_ON_DEMAND] uid={uid} persistido com {len(_texto_hidratado)} chars (txt_rotulo=TXT OK)")
            except Exception as _e_persist:
                print(f"[ururau_web][HIDRATACAO_ON_DEMAND] persist falhou: {_e_persist}")

    # Fallback cascateado para texto_fonte:
    # 1) cleaned_source_text (resultado da hidratacao bem sucedida ou on-demand)
    # 2) texto_fonte (legacy/desktop)
    # 3) resumo_origem (texto do RSS - SEMPRE existe quando veio de feed)
    # 4) descricao/resumo (variantes que algumas fontes salvam)
    _texto_final = (
        _texto_hidratado
        or _texto_legacy
        or (merged.get("resumo_origem") or "").strip()
        or (merged.get("descricao") or "").strip()
        or (merged.get("resumo") or "").strip()
        or (merged.get("summary") or "").strip()
    )

    # V200_44: pos-processamento - limpa boilerplate de listas em sites
    # municipais quando o texto ja vem sujo do banco. Funciona retroativa-
    # mente para pautas captadas antes do fix do extrator.
    try:
        _texto_final = _limpar_boilerplate_listas(_texto_final, _link_pauta)
    except Exception as _e_clean:
        print(f"[ururau_web][POS_LIMPEZA] falhou uid={uid}: {_e_clean}")

    view["texto_fonte"] = _texto_final
    # Sinaliza para a UI quando o texto veio do RSS resumo (nao da hidratacao
    # completa). Considera tambem o resultado da hidratacao on-demand v1.15.5.
    if _texto_final and (_texto_hidratado or _texto_legacy):
        view["texto_fonte_origem"] = "hidratado"
    elif _texto_final:
        view["texto_fonte_origem"] = "rss_resumo"
    else:
        view["texto_fonte_origem"] = "vazio"
    # v1.15.4: propaga motivo REAL de falha de hidratacao para a UI.
    # Categoriza para que o front exiba mensagem especifica (sem esconder).
    _motivo_extracao = (merged.get("motivo_extracao")
                        or merged.get("ultimo_erro_extracao")
                        or merged.get("status_extracao") or "")
    _motivo_extracao = str(_motivo_extracao)
    view["motivo_falha_extracao"] = ""
    view["tipo_falha_extracao"] = ""
    if not _texto_final or view["texto_fonte_origem"] in ("vazio", "rss_resumo"):
        # Detecta tipo de falha a partir das tentativas/motivo salvos no dados_json
        _falhas_str = json.dumps(merged.get("tentativas") or []) + " " + _motivo_extracao
        _f = _falhas_str.upper()
        if "MATERIA_REMOVIDA" in _f or "404_MASCARADO" in _f or "MASCARADO" in _f:
            view["tipo_falha_extracao"] = "materia_removida"
            view["motivo_falha_extracao"] = "Link do RSS aponta para uma materia que ja nao existe no servidor (404 mascarado)."
        elif "BLOQUEIO_ANTI_BOT_403" in _f or "HTTP_BLOCK_403" in _f or "403" in _f:
            view["tipo_falha_extracao"] = "bloqueio_anti_bot"
            view["motivo_falha_extracao"] = "Site bloqueia bots (HTTP 403). Sem proxy/IP rotativo o conteudo nao pode ser baixado."
        elif "ACESSO_NEGADO_401" in _f:
            view["tipo_falha_extracao"] = "exige_login"
            view["motivo_falha_extracao"] = "Site exige login para ler esta materia."
        elif "PAYWALL" in _f or "CAPTCHA" in _f or "ASSINANTE" in _f:
            view["tipo_falha_extracao"] = "paywall"
            view["motivo_falha_extracao"] = "Materia atras de paywall/assinatura."
        elif "TIMEOUT" in _f:
            view["tipo_falha_extracao"] = "timeout"
            view["motivo_falha_extracao"] = "Site demorou demais para responder (timeout)."
        elif "NAO ATENDE CRITERIOS" in _f or "NÃO ATENDE CRITÉRIOS" in _f or "PARAGRAFOS_UTEIS" in _f or "URL_NAO_MATERIA" in _f:
            view["tipo_falha_extracao"] = "fonte_insuficiente"
            view["motivo_falha_extracao"] = "URL resolvida, mas o conteudo util nao parece uma materia completa."
        elif view["texto_fonte_origem"] == "rss_resumo":
            view["tipo_falha_extracao"] = "spa_js_rendered"
            view["motivo_falha_extracao"] = "Site renderiza conteudo via JavaScript apos carregar a pagina (SPA). Sem browser headless nao da pra extrair o texto completo - so o resumo do RSS."
        elif view["texto_fonte_origem"] == "vazio":
            view["tipo_falha_extracao"] = "indisponivel"
            view["motivo_falha_extracao"] = "Conteudo da materia indisponivel: nao veio no RSS e a hidratacao falhou."
    md = _parse_materia_pauta(merged) or {}
    view["materia"] = md
    return _json_response({"ok": True, "pauta": view})


def handler_materia(db, uid: str) -> tuple[int, dict, bytes]:
    if not uid:
        return _error("uid ausente", status=400)
    p = db.buscar_pauta(uid)
    if not p:
        return _error("pauta nao encontrada", status=404, uid=uid)
    try:
        if p.get("dados_json"):
            p = {**p, **(json.loads(p["dados_json"]) or {})}
    except Exception:
        pass
    md = _parse_materia_pauta(p) or {}
    return _json_response({"ok": True, "uid": uid, "materia": md, "pronta": bool(md.get("conteudo") or md.get("corpo_materia"))})


# ── Coleta tradicional ───────────────────────────────────────────────────────

def handler_coletar(db, body: dict) -> tuple[int, dict, bytes]:
    with _coleta_lock:
        if _coleta_estado["em_andamento"]:
            return _json_response(
                {"ok": False, "motivo": "coleta_em_andamento", "estado": dict(_coleta_estado)},
                status=202,
            )
        _coleta_estado.update({
            "em_andamento": True,
            "iniciado_em": datetime.now().isoformat(timespec="seconds"),
            "finalizado_em": "",
            "inseridas": 0,
            "captadas_brutas": 0,
            "novas": 0,
            "duplicadas": 0,
            "duracao_seg": 0,
            "ultimo_erro": "",
            "ultimo_resumo": "",
            "ultimo_lote": "",
        })

    # Limite POR COLETA (não global do dia). Cap defensivo: 1000 máximo.
    limite_pedido = int(body.get("limite") or 500)
    limite = max(20, min(1000, limite_pedido))
    # Janela operacional: 6h (entre 4 e 8h conforme decisao editorial).
    # Cobre matérias publicadas no turno atual sem poluir a fila com antigas.
    # V200_16: janela default = 8h max (com prioridade nas ultimas 4h
    # via ordenacao no front). Limita a captura para nao trazer materias
    # velhas que poluem a fila editorial.
    janela_pedida = int(body.get("janela") or 8)
    janela = max(1, min(8, janela_pedida))

    def _trabalho():
        import time as _t
        t_inicio = _t.time()
        # Snapshot de uids existentes para distinguir novas vs duplicadas.
        uids_antes: set[str] = set()
        try:
            conn = db._conectar()
            try:
                for r in conn.execute("SELECT uid FROM pautas").fetchall():
                    uids_antes.add(str(r[0]))
            finally:
                conn.close()
        except Exception as _e_snap:
            print(f"[ururau_web][COLETA] snapshot falhou: {_e_snap}")

        # Aumenta a janela do RSS para o que foi pedido na coleta web
        # (URURAU_V100_JANELA_PUBLICACAO_HORAS limita o filtro do rss.py).
        os.environ["URURAU_V100_JANELA_PUBLICACAO_HORAS"] = str(janela)
        os.environ["URURAU_V99_JANELA_PUBLICACAO_HORAS"] = str(janela)
        os.environ["URURAU_JANELA_PUBLICACAO_HORAS"] = str(janela)
        os.environ["URURAU_V131_JANELA_HORAS"] = str(janela)

        # Helper para carregar fontes RSS configuradas (igual ao desktop).
        def _carregar_fontes_rss():
            from pathlib import Path as _P
            import json as _json
            for cam in [_P("config/fontes_rss.json"),
                        _P("configuracoes/fontes_rss.json"),
                        _P("fontes_rss.json"),
                        _P("sistema/config/fontes_rss.json"),
                        _P("sistema/configuracoes/fontes_rss.json"),
                        _P("sistema/fontes_rss.json")]:
                if cam.exists():
                    try:
                        return _json.loads(cam.read_text(encoding="utf-8"))
                    except Exception:
                        continue
            return []

        try:
            # Patch defensivo: source_hunter_v90.coletar_pautas_premium_v90 tem
            # bug pre-existente (usa nome 'janela_horas' em vez do parametro
            # 'janela').
            import ururau.coleta.source_hunter_v90 as _sh
            _sh.janela_horas = janela
            from ururau.coleta.source_hunter_v90 import coletar_pautas_premium_v90  # noqa
            from ururau.coleta.rss import coletar_rss as _coletar_rss_direto  # noqa
            # ── v140: cada coleta gera um lote visual novo, mas o numero
            # do lote REINICIA EM 01 a cada dia (timezone Brasilia). Arquivo
            # data/coleta_seq_diario_v140.txt guarda "YYYY-MM-DD|N" e quando
            # o dia muda o contador zera. Independente do arquivo legacy
            # coleta_seq_v123.txt do painel desktop (que continua acumulando).
            import time as _time
            try:
                from zoneinfo import ZoneInfo
                _agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
            except Exception:
                _agora_br = datetime.now()
            hora_lote = _agora_br.strftime("%H:%M")
            data_hoje = _agora_br.strftime("%Y-%m-%d")
            seq_path = Path("data") / "coleta_seq_diario_v140.txt"
            if not seq_path.parent.exists():
                seq_path.parent.mkdir(parents=True, exist_ok=True)
            # Le "YYYY-MM-DD|N"; se data mudou, zera contador.
            seq_atual = 1
            try:
                if seq_path.exists():
                    raw = seq_path.read_text(encoding="utf-8", errors="ignore").strip()
                    if "|" in raw:
                        data_salva, n_salvo = raw.split("|", 1)
                        if data_salva == data_hoje:
                            seq_atual = int(n_salvo.strip() or "0") + 1
                        # Se data_salva != hoje, mantem seq_atual = 1
            except Exception:
                seq_atual = 1
            try:
                seq_path.write_text(f"{data_hoje}|{seq_atual}", encoding="utf-8")
            except Exception as _e_seq:
                print(f"[ururau_web] aviso: falha ao gravar coleta_seq_diario: {_e_seq}")
            # Formato visual: "Coleta 01 - 16:30" (zero-padded ate 99).
            num_fmt = f"{seq_atual:02d}" if seq_atual < 100 else str(seq_atual)
            lote_label = f"Coleta {num_fmt} - {hora_lote}"
            lote_id = f"coleta_{data_hoje}_{seq_atual}_{int(_time.time())}"
            print(f"[ururau_web][COLETA] iniciado lote: {lote_label} (dia {data_hoje})")

            # V200_25: Estrategia em 2 fases SALVANDO progressivamente.
            # Fase 1: coletar_rss + SALVAR imediatamente (~5s para 243 pautas)
            # Fase 2: source_hunter + SALVAR (lento, ~2.5min)
            # Antes: ambas terminavam, depois salvavam tudo. Fila vazia 2.5min.
            pautas: list[dict] = []
            rss_pautas: list[dict] = []
            premium_pautas: list[dict] = []
            try:
                fontes_rss = _carregar_fontes_rss()
                print(f"[ururau_web][COLETA] coletar_rss: {len(fontes_rss)} fontes configuradas")
                rss_pautas = _coletar_rss_direto(fontes_rss, incluir_oficiais=True) or []
                pautas.extend(rss_pautas)
                print(f"[ururau_web][COLETA] coletar_rss retornou {len(rss_pautas)} pautas")
            except Exception as _e_rss:
                print(f"[ururau_web][COLETA] coletar_rss falhou: {_e_rss}")
            # source_hunter movido para DEPOIS da Fase 1 de save (V200_25)

            with _coleta_lock:
                _coleta_estado["captadas_brutas"] = len(pautas)
            inseridas = 0
            # Timestamp ISO em America/Sao_Paulo (naive, sem offset) para
            # comparacao consistente com o corte temporal (que tambem e naive BR).
            # BUG_FIX v1.14.5: antes gerava ISO com offset "-03:00" e o corte
            # vinha em UTC, causando string compare falso e fila vazia.
            try:
                from zoneinfo import ZoneInfo as _ZI
                agora_iso = datetime.now(_ZI("America/Sao_Paulo")).replace(tzinfo=None).isoformat(timespec="seconds")
            except Exception:
                agora_iso = datetime.now().isoformat(timespec="seconds")
            # Carrega lista plana de termos editoriais (do arquivo premium_v88)
            # para fazer match em cada pauta. Pautas que casarem ganham
            # _v129_termos_positivos (mesma chave que o painel desktop usa).
            termos_lista: list[str] = []
            try:
                _tpath = _path_termos()
                if _tpath.exists():
                    # V200_24: era "_t = json.loads(...)" que SOBRESCREVIA o
                    # modulo time importado como _t no inicio de _trabalho.
                    # Resultado: ao chegar em "int(_t.time() - t_inicio)" no
                    # fim da coleta, _t era dict e gerava AttributeError.
                    # Renomeado para _termos_json (nao colide com nada).
                    _termos_json = json.loads(_tpath.read_text(encoding="utf-8"))
                    for _grp_lst in (_termos_json.get("grupos", {}) or {}).values():
                        for _t_item in (_grp_lst or []):
                            _t_clean = str(_t_item or "").strip()
                            # Ignora termos com 'site:' (são auxiliares de busca, nao
                            # destacam pautas).
                            if _t_clean and not _t_clean.lower().startswith("site:"):
                                termos_lista.append(_t_clean)
            except Exception as _e_tl:
                print(f"[ururau_web][COLETA] termos: {_e_tl}")

            def _match_termos(p):
                hay = " ".join([
                    str(p.get("titulo_origem") or ""),
                    str(p.get("resumo_origem") or ""),
                    str(p.get("cleaned_source_text") or "")[:5000],
                ]).lower()
                if not hay.strip():
                    return []
                achados = []
                for t in termos_lista:
                    tl = t.lower()
                    # Match simples por substring; bordas vagas para evitar
                    # falso positivo dentro de palavras longas demais.
                    if len(tl) <= 2:
                        continue
                    if tl in hay:
                        achados.append(t)
                # Remove duplicatas preservando ordem; cap 6.
                seen = set(); out = []
                for t in achados:
                    if t not in seen:
                        out.append(t); seen.add(t)
                    if len(out) >= 6:
                        break
                return out

            erros_salvar = 0
            normalizadas_burlesco = 0
            # V200_12 + V200_25: chunks de 25 + 2 fases (RSS antes, SH depois)
            CHUNK_SIZE = 25
            _chunk_buffer = []
            _chunk_idx = 0
            def _flush_chunk():
                nonlocal inseridas, erros_salvar, _chunk_idx
                if not _chunk_buffer:
                    return
                _chunk_idx += 1
                try:
                    if hasattr(db, "salvar_pautas_batch"):
                        r = db.salvar_pautas_batch(_chunk_buffer)
                        inseridas += int(r.get("inseridas") or 0)
                        erros_salvar += int(r.get("erros") or 0)
                        print(f"[ururau_web][COLETA] chunk {_chunk_idx}: +{r.get('inseridas',0)} ({inseridas} total)")
                    else:
                        # fallback: salva uma a uma
                        for _p in _chunk_buffer:
                            try:
                                db.salvar_pauta(_p)
                                inseridas += 1
                            except Exception:
                                erros_salvar += 1
                except Exception as _e:
                    print(f"[ururau_web][COLETA] chunk {_chunk_idx} FALHOU: {_e}")
                    erros_salvar += len(_chunk_buffer)
                _chunk_buffer.clear()
            def _processar_e_salvar(lista_pautas, rotulo_fase):
                """V200_25: processa uma lista de pautas em chunks e salva."""
                nonlocal normalizadas_burlesco, erros_salvar
                if not lista_pautas:
                    return
                print(f"[ururau_web][COLETA][{rotulo_fase}] salvando {len(lista_pautas)} pautas em chunks de {CHUNK_SIZE}...")
                for pauta in lista_pautas:
                    try:
                            # Marca o lote v123 (igual ao desktop) antes de salvar.
                        pauta["coleta_lote_id_v123"] = lote_id
                        pauta["coleta_lote_ordem_v123"] = seq_atual
                        pauta["coleta_lote_hora_v123"] = hora_lote
                        pauta["coleta_lote_label_v123"] = lote_label
                        # IMPORTANTE: força captada_em/atualizada_em ao momento atual.
                        pauta["captada_em"] = agora_iso
                        pauta["atualizada_em"] = agora_iso
                        pauta["data_pub_fonte"] = pauta.get("data_pub_fonte") or pauta.get("data_fonte") or ""
                        # ── V200_7: NORMALIZACAO DE CHAVES (Source Hunter / Burlesco) ──
                        # O source_hunter_v90 (que rescata via bypass_burlesco_rule)
                        # retorna pautas com chaves "titulo", "url_original", "fonte",
                        # "texto_fonte" — diferente do contrato canonico do banco
                        # (titulo_origem, link_origem, fonte_nome, cleaned_source_text).
                        # Sem normalizar:
                        #  - link_origem fica vazio na coluna -> query_fila_ativa filtra
                        #    (WHERE link_origem <> '') e a pauta SUMIA da fila;
                        #  - cleaned_source_text fica vazio -> TXT OK nao aparece e a
                        #    hidratacao on-demand re-extrai (lag ao clicar);
                        #  - 'TEXTO DA FONTE' demora a aparecer na 2a coluna porque
                        #    o front considera texto incompleto e dispara escada.
                        _eh_source_hunter = bool(
                            pauta.get("metodo_extracao")
                            or pauta.get("metodo_coleta")
                            or pauta.get("dominio")
                            or pauta.get("url_original")
                        ) and not pauta.get("titulo_origem")
                        if not pauta.get("titulo_origem") and pauta.get("titulo"):
                            pauta["titulo_origem"] = pauta["titulo"]
                        if not pauta.get("link_origem"):
                            for k in ("url_final", "url_original", "url", "link"):
                                v = pauta.get(k)
                                if isinstance(v, str) and v.startswith(("http://", "https://")):
                                    pauta["link_origem"] = v
                                    break
                        if not pauta.get("fonte_nome") and pauta.get("fonte"):
                            pauta["fonte_nome"] = pauta["fonte"]
                        if not pauta.get("resumo_origem") and pauta.get("resumo"):
                            pauta["resumo_origem"] = pauta["resumo"]
                        # V200_8: imagem do pipeline_v90 -> imagem_url canonico
                        # (handler_imagem_pauta e _detectar_imagem_url procuram
                        # "imagem_url"/"imagem_capa" antes de cair em og:image)
                        if not pauta.get("imagem_url"):
                            for _k_img in ("imagem", "og_image", "image_url",
                                           "imagem_principal", "thumbnail"):
                                _v_img = pauta.get(_k_img)
                                if isinstance(_v_img, str) and _v_img.startswith(("http://", "https://")):
                                    pauta["imagem_url"] = _v_img
                                    break
                        # V200_8: limpa titulo lixo do Google News RSS (caso
                        # "| Folha de Londrina - Folha de Londrina"). Heuristica:
                        # comeca com | ou -, ou e curto demais sem letras uteis.
                        _tit_atual = str(pauta.get("titulo_origem") or "").strip()
                        _tit_limpo = _tit_atual.lstrip("|- \t").rstrip("|- \t")
                        _eh_titulo_lixo = (
                            not _tit_atual
                            or _tit_atual.startswith(("|", "-"))
                            or len(_tit_limpo) < 15
                        )
                        if _eh_titulo_lixo:
                            _alt = (
                                str(pauta.get("resumo_origem") or "").strip()
                                or str(pauta.get("resumo") or "").strip()
                                or str(pauta.get("descricao") or "").strip()
                            )
                            if _alt:
                                _alt = _alt.split("\n")[0].split(". ")[0].strip()[:200]
                                pauta["titulo_origem"] = _alt
                        # texto_fonte do source_hunter -> cleaned_source_text canonico
                        _texto_sh = (
                            pauta.get("texto_fonte")
                            or pauta.get("texto")
                            or ""
                        )
                        if (
                            not (pauta.get("cleaned_source_text") or "").strip()
                            and isinstance(_texto_sh, str)
                            and _texto_sh.strip()
                        ):
                            pauta["cleaned_source_text"] = _texto_sh
                            # Marca que ja veio hidratada para o handler de detalhe
                            # NAO disparar hidratacao on-demand de novo (lag ao clicar).
                            pauta["fonte_status"] = pauta.get("fonte_status") or "ok"
                            if _eh_source_hunter:
                                pauta["hidratacao_on_demand"] = (
                                    pauta.get("hidratacao_on_demand")
                                    or "source_hunter:" + str(pauta.get("metodo_extracao") or "")
                                )
                                normalizadas_burlesco += 1
                        # Match de termos editoriais para destacar prioridade na fila.
                        termos_encontrados = _match_termos(pauta)
                        if termos_encontrados:
                            pauta["_v129_termos_positivos"] = termos_encontrados
                            pauta["_v129_termos_prioridade"] = termos_encontrados
                        _chunk_buffer.append(pauta)
                        if len(_chunk_buffer) >= CHUNK_SIZE:
                            _flush_chunk()
                    except Exception as e:
                        erros_salvar += 1
                        print(f"[ururau_web] falha ao preparar pauta: {e}")
                # ultimo chunk parcial da fase
                _flush_chunk()
                print(f"[ururau_web][COLETA][{rotulo_fase}] fase concluida (total acumulado: {inseridas})")

            # V200_25: FASE 1 - salva RSS imediatamente (~5s)
            _processar_e_salvar(rss_pautas, "RSS")
            with _coleta_lock:
                _coleta_estado["captadas_brutas"] = len(rss_pautas)

            # V200_25: FASE 2 - agora roda source_hunter (lento) e salva
            try:
                premium_pautas = coletar_pautas_premium_v90(limite=limite, janela=janela) or []
                pautas.extend(premium_pautas)
                print(f"[ururau_web][COLETA] source_hunter retornou {len(premium_pautas)} pautas")
            except Exception as _e_sh:
                print(f"[ururau_web][COLETA] source_hunter falhou: {_e_sh}")
            _processar_e_salvar(premium_pautas, "SOURCE_HUNTER")
            with _coleta_lock:
                _coleta_estado["captadas_brutas"] = len(rss_pautas) + len(premium_pautas)
            if normalizadas_burlesco:
                print(f"[ururau_web][COLETA][V200_7] normalizadas {normalizadas_burlesco} pautas do source_hunter "
                      f"(chaves canonicas + cleaned_source_text preenchido)")
            print(f"[ururau_web][COLETA] save loop concluido: {inseridas}/{len(pautas)} salvas ({erros_salvar} erros)")
            # (a marcação dos termos foi feita em pauta antes do salvar — ver loop acima)
            # Conta novas vs duplicadas comparando uids depois da coleta.
            uids_depois: set[str] = set()
            try:
                conn = db._conectar()
                try:
                    for r in conn.execute("SELECT uid FROM pautas").fetchall():
                        uids_depois.add(str(r[0]))
                finally:
                    conn.close()
            except Exception:
                pass
            novas = len(uids_depois - uids_antes)
            duplicadas = max(0, inseridas - novas)
            duracao = int(_t.time() - t_inicio)
            with _coleta_lock:
                _coleta_estado["inseridas"] = inseridas
                _coleta_estado["novas"] = novas
                _coleta_estado["duplicadas"] = duplicadas
                _coleta_estado["duracao_seg"] = duracao
                _coleta_estado["ultimo_lote"] = lote_label
                _coleta_estado["ultimo_resumo"] = (
                    f"{lote_label} concluida em {duracao}s: "
                    f"{novas} nova(s), {duplicadas} já existente(s), "
                    f"{len(pautas)} captada(s) brutas (janela {janela}h)"
                )
                if novas == 0 and len(pautas) == 0:
                    _coleta_estado["ultimo_resumo"] = (
                        f"{lote_label}: nenhuma pauta nova nesta janela de {janela}h. "
                        f"Tente Manual ou amplie a janela em Coletar > avançado."
                    )
                print(f"[ururau_web][COLETA] >>> RESUMO: {_coleta_estado['ultimo_resumo']}")
        except Exception as e:
            # V200_6: imprime traceback completo no console para diagnosticar
            # erros como "AttributeError: 'dict' object has no attribute 'time'"
            # que de outro modo so aparecem como string no status bar do front.
            import traceback as _tb
            _tb_str = _tb.format_exc()
            print(f"[ururau_web][COLETA][ERRO] {type(e).__name__}: {e}")
            print(f"[ururau_web][COLETA][TRACEBACK]\n{_tb_str}", flush=True)
            with _coleta_lock:
                _coleta_estado["ultimo_erro"] = f"{type(e).__name__}: {e}"
        finally:
            with _coleta_lock:
                _coleta_estado["em_andamento"] = False
                _coleta_estado["finalizado_em"] = datetime.now().isoformat(timespec="seconds")

    threading.Thread(target=_trabalho, name="ururau_web_coleta", daemon=True).start()
    return _json_response({"ok": True, "estado": dict(_coleta_estado)})


def handler_coletar_status(db) -> tuple[int, dict, bytes]:
    with _coleta_lock:
        return _json_response({"ok": True, "estado": dict(_coleta_estado)})


# ── Feed Universal ───────────────────────────────────────────────────────────

def handler_feed_universal_discover(db, body: dict) -> tuple[int, dict, bytes]:
    url = (body.get("url") or "").strip()
    if not url:
        return _error("url ausente", status=400)
    mode = (body.get("mode") or "auto").strip().lower()
    try:
        limit = max(1, min(int(body.get("limit") or 30), 100))
    except Exception:
        limit = 30
    discover_universal, _ = _import_feed_universal()
    try:
        out = discover_universal(url, mode=mode, limit=limit)
    except Exception as e:
        return _error(f"falha discover: {type(e).__name__}: {e}", status=500)
    return _json_response({"ok": True, "resultado": out})


def handler_feed_universal_collect(db, body: dict) -> tuple[int, dict, bytes]:
    url = (body.get("url") or "").strip()
    if not url:
        return _error("url ausente", status=400)
    try:
        limit = max(1, min(int(body.get("limit") or 20), 50))
    except Exception:
        limit = 20
    try:
        last_hours = max(0, int(body.get("last_hours") or 24))
    except Exception:
        last_hours = 24
    _, collect_to_queue = _import_feed_universal()
    try:
        out = collect_to_queue(url, limit=limit, last_hours=last_hours, db=db)
    except Exception as e:
        return _error(f"falha collect: {type(e).__name__}: {e}", status=500)
    out["sem_publicacao"] = True
    return _json_response({"ok": True, "resultado": out})


def handler_source_health(db) -> tuple[int, dict, bytes]:
    try:
        rows = db.feed_universal_source_health_summary(limite=200)
    except Exception as e:
        return _error(f"falha source_health: {type(e).__name__}: {e}", status=500)
    return _json_response({"ok": True, "total": len(rows), "dominios": rows})


# ────────────────────────────────────────────────────────────────────────────
# Logs / config
# ────────────────────────────────────────────────────────────────────────────

def handler_logs_recentes(db, qs: dict[str, str]) -> tuple[int, dict, bytes]:
    settings = _import_settings()
    pasta = Path(getattr(settings, "PASTA_LOGS", "logs"))
    try:
        n = max(10, min(int(qs.get("n") or 200), 2000))
    except Exception:
        n = 200
    if not pasta.exists():
        alt = Path("sistema") / "logs"
        if alt.exists():
            pasta = alt
    arquivos: list[dict] = []
    if pasta.exists():
        for p in sorted(pasta.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
                linhas = txt.splitlines()[-n:]
                arquivos.append({"nome": p.name, "linhas": linhas})
            except Exception as e:
                arquivos.append({"nome": p.name, "erro": str(e), "linhas": []})
    return _json_response({"ok": True, "n": n, "pasta": str(pasta), "arquivos": arquivos})


_runtime_config: dict[str, Any] = {"limite_visual": 240, "janela_padrao_horas": 24}


def handler_get_config(db) -> tuple[int, dict, bytes]:
    settings = _import_settings()
    _client, _modelo = _get_openai_client()
    return _json_response({
        "ok": True,
        "host": "127.0.0.1",
        "port": 8787,
        "arquivo_db": getattr(settings, "ARQUIVO_DB", "ururau.db"),
        "runtime": dict(_runtime_config),
        "publicacao_automatica": False,
        "cors_origens_permitidas": ["http://127.0.0.1:8787", "http://localhost:8787"],
        "ia_configurada": bool(_client),
        "ia_modelo": _modelo,
    })


def handler_post_config(db, body: dict) -> tuple[int, dict, bytes]:
    if not isinstance(body, dict):
        return _error("body invalido", status=400)
    novo = dict(_runtime_config)
    if "limite_visual" in body:
        try:
            novo["limite_visual"] = max(20, min(int(body["limite_visual"]), 1000))
        except Exception:
            return _error("limite_visual invalido", status=400)
    if "janela_padrao_horas" in body:
        try:
            novo["janela_padrao_horas"] = max(1, min(int(body["janela_padrao_horas"]), 168))
        except Exception:
            return _error("janela_padrao_horas invalido", status=400)
    _runtime_config.update(novo)
    return _json_response({"ok": True, "runtime": dict(_runtime_config)})


# ────────────────────────────────────────────────────────────────────────────
# Stats / Historico
# ────────────────────────────────────────────────────────────────────────────

def handler_stats(db) -> tuple[int, dict, bytes]:
    """Contagens agregadas: total + hoje (timezone America/Sao_Paulo)."""
    # Início do dia em America/Sao_Paulo (zera quando vira o dia).
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Sao_Paulo")
    except Exception:
        tz = None
    agora = datetime.now(tz) if tz else datetime.now()
    inicio_hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    # Para comparar com captada_em que vem em ISO (com ou sem tz), uso
    # somente os 19 primeiros chars (yyyy-mm-ddTHH:MM:SS).
    hoje_iso = inicio_hoje.strftime("%Y-%m-%dT%H:%M:%S")
    hoje_data = inicio_hoje.strftime("%Y-%m-%d")
    out = {
        "ok": True,
        "ts": agora.isoformat(timespec="seconds"),
        "data_hoje": hoje_data,
        "totais": {"pautas": 0, "publicacoes": 0},
        "hoje": {
            "captadas": 0,
            "publicadas": 0,
            "descartadas": 0,
            "redigidas": 0,
            "por_status": {},
            "por_fonte": [],
        },
        "por_status": {},
        "por_fonte": [],
        "por_canal": [],
        "por_lote": [],
    }
    try:
        conn = db._conectar()
        try:
            total = conn.execute("SELECT COUNT(*) FROM pautas").fetchone()[0]
            out["totais"]["pautas"] = int(total or 0)
            try:
                pub = conn.execute("SELECT COUNT(*) FROM publicacoes").fetchone()[0]
                out["totais"]["publicacoes"] = int(pub or 0)
            except Exception:
                pass
            for r in conn.execute(
                "SELECT COALESCE(NULLIF(LOWER(status), ''), 'sem_status') AS s, COUNT(*) "
                "FROM pautas GROUP BY s ORDER BY 2 DESC"
            ).fetchall():
                out["por_status"][r[0]] = int(r[1])
            for r in conn.execute(
                "SELECT COALESCE(NULLIF(fonte_nome, ''), 'sem_fonte') AS f, COUNT(*) "
                "FROM pautas GROUP BY f ORDER BY 2 DESC LIMIT 25"
            ).fetchall():
                out["por_fonte"].append({"fonte": r[0], "qtd": int(r[1])})
            for r in conn.execute(
                "SELECT COALESCE(NULLIF(canal, ''), 'sem_canal') AS c, COUNT(*) "
                "FROM pautas GROUP BY c ORDER BY 2 DESC LIMIT 25"
            ).fetchall():
                out["por_canal"].append({"canal": r[0], "qtd": int(r[1])})

            # ── HOJE ─────────────────────────────────────────────────────
            # captadas hoje: substr(captada_em,1,19) >= hoje_iso OU
            # substr(captada_em,1,10) = data_hoje.
            row = conn.execute(
                "SELECT COUNT(*) FROM pautas WHERE substr(captada_em,1,10)=?",
                (hoje_data,),
            ).fetchone()
            out["hoje"]["captadas"] = int(row[0] or 0)
            # publicadas hoje: status=publicada e atualizada_em do dia.
            row = conn.execute(
                "SELECT COUNT(*) FROM pautas WHERE LOWER(status) IN ('publicada','publicado') "
                "AND substr(atualizada_em,1,10)=?",
                (hoje_data,),
            ).fetchone()
            out["hoje"]["publicadas"] = int(row[0] or 0)
            row = conn.execute(
                "SELECT COUNT(*) FROM pautas WHERE LOWER(status) IN ('descartada','descartado','rejeitada','rejeitado','bloqueada','bloqueado','excluida','excluido') "
                "AND substr(atualizada_em,1,10)=?",
                (hoje_data,),
            ).fetchone()
            out["hoje"]["descartadas"] = int(row[0] or 0)
            row = conn.execute(
                "SELECT COUNT(*) FROM pautas WHERE LOWER(status) IN ('revisada','pronta','em_redacao') "
                "AND substr(atualizada_em,1,10)=?",
                (hoje_data,),
            ).fetchone()
            out["hoje"]["redigidas"] = int(row[0] or 0)
            # Por status hoje (com base em captada_em).
            for r in conn.execute(
                "SELECT COALESCE(NULLIF(LOWER(status), ''), 'sem_status') AS s, COUNT(*) "
                "FROM pautas WHERE substr(captada_em,1,10)=? GROUP BY s ORDER BY 2 DESC",
                (hoje_data,),
            ).fetchall():
                out["hoje"]["por_status"][r[0]] = int(r[1])
            for r in conn.execute(
                "SELECT COALESCE(NULLIF(fonte_nome, ''), 'sem_fonte') AS f, COUNT(*) "
                "FROM pautas WHERE substr(captada_em,1,10)=? GROUP BY f ORDER BY 2 DESC LIMIT 15",
                (hoje_data,),
            ).fetchall():
                out["hoje"]["por_fonte"].append({"fonte": r[0], "qtd": int(r[1])})
        finally:
            conn.close()
    except Exception as exc:
        return _error(f"falha stats: {type(exc).__name__}: {exc}", status=500)

    # Por lote (precisa olhar dados_json — lote esta la, nao em coluna).
    try:
        from collections import Counter
        lotes = Counter()
        for p in db.query_fila_ativa(limite=400):
            lab = (p.get("coleta_lote_label_v123") or p.get("coleta_lote")
                   or "Sem lote")
            lotes[lab] += 1
        out["por_lote"] = [
            {"lote": lab, "qtd": n} for lab, n in lotes.most_common(20)
        ]
    except Exception:
        pass
    return _json_response(out)


def handler_historico(db, qs: dict[str, str]) -> tuple[int, dict, bytes]:
    """Pautas com status finais (publicada/descartada/rejeitada/bloqueada)."""
    try:
        limite = max(1, min(int(qs.get("limite") or 100), 500))
    except Exception:
        limite = 100
    filtro = (qs.get("status") or "").strip().lower()
    pautas: list[dict] = []
    try:
        conn = db._conectar()
        try:
            if filtro:
                sql = (
                    "SELECT uid, titulo_origem, link_origem, fonte_nome, status, "
                    "       canal, score_editorial, atualizada_em, captada_em "
                    "FROM pautas WHERE LOWER(status)=? "
                    "ORDER BY datetime(COALESCE(NULLIF(atualizada_em,''), NULLIF(captada_em,''))) DESC "
                    "LIMIT ?"
                )
                rows = conn.execute(sql, (filtro, limite)).fetchall()
            else:
                sql = (
                    "SELECT uid, titulo_origem, link_origem, fonte_nome, status, "
                    "       canal, score_editorial, atualizada_em, captada_em "
                    "FROM pautas WHERE LOWER(status) IN "
                    "      ('publicada','publicado','descartada','descartado',"
                    "       'rejeitada','rejeitado','bloqueada','bloqueado',"
                    "       'reprovada','reprovado') "
                    "ORDER BY datetime(COALESCE(NULLIF(atualizada_em,''), NULLIF(captada_em,''))) DESC "
                    "LIMIT ?"
                )
                rows = conn.execute(sql, (limite,)).fetchall()
            for r in rows:
                pautas.append(dict(r))
        finally:
            conn.close()
    except Exception as exc:
        return _error(f"falha historico: {exc}", status=500)
    return _json_response({"ok": True, "total": len(pautas), "pautas": pautas})


def handler_aprovar_baixo_score(db, uid: str, body: dict) -> tuple[int, dict, bytes]:
    if not uid:
        return _error("uid ausente", status=400)
    try:
        db.atualizar_status_pauta(uid, "captada")
    except Exception as exc:
        return _error(f"falha aprovar: {exc}", status=500)
    return _json_response({"ok": True, "uid": uid, "status": "captada", "novo_status": "captada"})


def handler_adicionar_manual(db, body: dict) -> tuple[int, dict, bytes]:
    if not isinstance(body, dict):
        return _error("body invalido", status=400)
    titulo = str(body.get("titulo") or "").strip()
    link = str(body.get("link") or body.get("url") or "").strip()
    fonte = str(body.get("fonte") or body.get("fonte_nome") or "").strip()
    if not titulo or not link:
        return _error("titulo e link sao obrigatorios", status=400)
    if not fonte:
        try:
            fonte = urlparse(link).netloc.lower().removeprefix("www.") or "Manual"
        except Exception:
            fonte = "Manual"
    try:
        from zoneinfo import ZoneInfo as _ZI
        agora_iso = datetime.now(_ZI("America/Sao_Paulo")).replace(tzinfo=None).isoformat(timespec="seconds")
    except Exception:
        agora_iso = datetime.now().isoformat(timespec="seconds")
    pauta = {
        "titulo_origem": titulo,
        "link_origem": link,
        "fonte_nome": fonte,
        "resumo_origem": str(body.get("resumo") or "")[:500],
        "status": "captada",
        "captada_em": agora_iso,
        "atualizada_em": agora_iso,
        "coleta_lote_label_v123": "Pauta manual (web)",
    }
    try:
        uid = db.salvar_pauta(pauta)
    except Exception as exc:
        return _error(f"falha salvar manual: {exc}", status=500)
    return _json_response({"ok": True, "uid": uid, "fonte": fonte, "link": link})


def dispatch(*, method, path, query, body, headers=None, db=None):
    from . import api_actions as acoes
    method = (method or "GET").upper()
    path = path or "/"

    if path == "/api/health" and method == "GET":
        return handler_health(db)
    if path == "/api/diag" and method == "GET":
        return handler_diag(db)
    if path == "/api/config" and method == "GET":
        return handler_get_config(db)
    if path == "/api/config" and method == "POST":
        return handler_post_config(db, _parse_json_body(body))

    if path == "/api/pautas" and method == "GET":
        return handler_listar_pautas(db, _query_dict(query))
    if path.startswith("/api/pautas/") and path.endswith("/imagem") and method == "GET":
        uid = path[len("/api/pautas/"):-len("/imagem")]
        return acoes.handler_imagem_pauta(db, uid)
    if path.startswith("/api/pautas/") and path.endswith("/buscar-imagem") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/buscar-imagem")]
        return acoes.handler_buscar_imagem(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/job") and method == "GET":
        uid = path[len("/api/pautas/"):-len("/job")]
        return acoes.handler_job_status(db, uid)
    # V200_34: prioriza essa pauta no proximo ciclo do hidratador BG
    if path.startswith("/api/pautas/") and path.endswith("/priorizar-hidratacao") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/priorizar-hidratacao")]
        try:
            from ururau.coleta.hidratador_background_v200 import marcar_prioridade
            marcar_prioridade(uid)
            return _json_response({"ok": True, "uid": uid})
        except Exception as _e:
            return _json_response({"ok": False, "erro": str(_e)})
    if path.startswith("/api/pautas/") and path.endswith("/materia/salvar") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/materia/salvar")]
        return acoes.handler_salvar_materia(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/materia") and method == "GET":
        uid = path[len("/api/pautas/"):-len("/materia")]
        return acoes.handler_materia(db, uid)
    if path.startswith("/api/pautas/") and path.endswith("/redigir") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/redigir")]
        return acoes.handler_redigir(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/copydesk/salvar") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/copydesk/salvar")]
        return acoes.handler_salvar_copydesk(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/copydesk/descartar") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/copydesk/descartar")]
        return acoes.handler_descartar_copydesk(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/copydesk") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/copydesk")]
        return acoes.handler_copydesk(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/revisao") and method == "GET":
        uid = path[len("/api/pautas/"):-len("/revisao")]
        return acoes.handler_revisao_pendente(db, uid)
    if path.startswith("/api/pautas/") and path.endswith("/descartar") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/descartar")]
        return acoes.handler_descartar(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/reativar") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/reativar")]
        return acoes.handler_reativar(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/publicar") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/publicar")]
        return acoes.handler_publicar(db, uid, _parse_json_body(body))
    if path.startswith("/api/pautas/") and path.endswith("/aprovar") and method == "POST":
        uid = path[len("/api/pautas/"):-len("/aprovar")]
        return handler_aprovar_baixo_score(db, uid, _parse_json_body(body))
    if path == "/api/pautas/manual" and method == "POST":
        return handler_adicionar_manual(db, _parse_json_body(body))
    if path.startswith("/api/pautas/") and method == "GET":
        uid = path[len("/api/pautas/"):]
        return handler_detalhe_pauta(db, uid)

    if path == "/api/coletar" and method == "POST":
        return handler_coletar(db, _parse_json_body(body))
    if path == "/api/coletar/status" and method == "GET":
        return handler_coletar_status(db)
    if path == "/api/auto-coleta/status" and method == "GET":
        return handler_auto_status(db)
    if path == "/api/stats" and method == "GET":
        return handler_stats(db)
    if path == "/api/source-health" and method == "GET":
        return handler_source_health(db)
    if path == "/api/historico" and method == "GET":
        return handler_historico(db, _query_dict(query))
    if path == "/api/logs" and method == "GET":
        return handler_logs_recentes(db, _query_dict(query))
    if path == "/api/feed-universal/discover" and method == "POST":
        return handler_feed_universal_discover(db, _parse_json_body(body))
    if path == "/api/feed-universal/collect" and method == "POST":
        return handler_feed_universal_collect(db, _parse_json_body(body))
    if path == "/api/prompt/copydesk" and method == "GET":
        return handler_get_prompt_copydesk(db)
    if path == "/api/prompt/copydesk" and method == "POST":
        return handler_post_prompt_copydesk(db, _parse_json_body(body))

    if path == "/api/admin/zerar-fila" and method == "POST":
        return handler_zerar_fila(db, _parse_json_body(body))
    if path == "/api/admin/restaurar-fila" and method == "POST":
        return handler_restaurar_fila(db, _parse_json_body(body))
    if path == "/api/admin/termos" and method == "GET":
        return handler_termos_get(db)
    if path == "/api/admin/termos" and method == "POST":
        return handler_termos_post(db, _parse_json_body(body))
    if path == "/api/admin/fontes-rss" and method == "GET":
        return handler_fontes_get(db)
    if path == "/api/admin/fontes-rss" and method == "POST":
        return handler_fontes_post(db, _parse_json_body(body))
    if path == "/api/admin/fontes-rss/auto-discover" and method == "POST":
        return handler_fontes_auto_discover(db, _parse_json_body(body))

    return _error("rota nao encontrada", status=404, path=path, method=method)
