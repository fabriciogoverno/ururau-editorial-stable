"""
ururau/coleta/fail_closed_v84.py

Trava final de captura de pauta antes da fila/painel.

Objetivo v84:
- Uma pauta só pode entrar como CAPTADA se o robô já conseguiu ler texto útil da matéria.
- Título, snippet, RSS curto ou Google News não resolvido não entram na fila.
- O monitor continua usando o fail-closed v83 na execução; a v84 antecipa a trava na coleta do painel.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ururau.config.settings import StatusPauta


@dataclass
class ResultadoCapturaV84:
    ok: bool
    motivo: str
    codigo: str
    chars: int = 0
    metodo: str = ""
    status: str = ""
    resolved_url: str = ""
    res: dict[str, Any] | None = None


def _bool_env(nome: str, padrao: bool = False) -> bool:
    raw = str(os.getenv(nome, "1" if padrao else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _int_env(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _chars_uteis(res: dict[str, Any]) -> int:
    metadata = res.get("metadata") or {}
    try:
        return int(metadata.get("util_chars") or 0)
    except Exception:
        pass
    texto = str(res.get("cleaned_source_text") or res.get("dossie") or "")
    try:
        from ururau.coleta.limpeza_texto_v81 import texto_util_chars
        return int(texto_util_chars(texto))
    except Exception:
        return len(texto.strip())



def _metodo_tem_url_real_v104(metodo: str) -> bool:
    """Reconhece métodos que abriram URL pública real da matéria.

    Os métodos v86/v104 retornam nomes como requests:html_density,
    v104_requests:jsonld_articleBody, v104_wordpress_rest ou
    leitura_fonte_v104. Eles equivalem a url_scraping para o gate.
    """
    m = str(metodo or "").lower()
    bons = (
        "url_scraping", "requests:", "v86_requests:", "v104_requests:",
        "playwright", "v104_playwright", "v104_wordpress",
        "wordpress_rest", "leitura_fonte_v104", "leitura_fonte_v96",
        "v104_v86:requests:",
    )
    return any(x in m for x in bons)


def avaliar_resultado_captura_v84(res: dict[str, Any]) -> ResultadoCapturaV84:
    """Avalia a extração antes de permitir que a pauta entre na fila."""
    status = str(res.get("extraction_status") or "failed").strip().lower()
    metodo = str(res.get("extraction_method") or "failed").strip().lower()
    metadata = res.get("metadata") or {}
    chars = _chars_uteis(res)
    resolved = str(metadata.get("resolved_url") or "").strip()

    min_chars = _int_env("URURAU_V84_MIN_CHARS_CAPTURA", _int_env("URURAU_MIN_CHARS_TEXTO_FONTE", 500))
    permitir_rss = _bool_env("URURAU_V84_PERMITIR_RSS_ONLY_FILA", False)
    permitir_short = _bool_env("URURAU_V84_PERMITIR_SHORT_USABLE_FILA", False)
    bloquear_google = _bool_env("URURAU_BLOQUEAR_GOOGLE_NEWS_UNRESOLVED", True)

    if status == "failed":
        return ResultadoCapturaV84(False, "extração falhou", "extracao_failed", chars, metodo, status, resolved, res)
    if metodo in {"failed", "source_too_short_v81"}:
        return ResultadoCapturaV84(False, f"método inválido: {metodo}", "metodo_invalido", chars, metodo, status, resolved, res)
    if bloquear_google and metodo == "google_news_unresolved":
        return ResultadoCapturaV84(False, "Google News não resolvido para fonte real", "google_news_unresolved", chars, metodo, status, resolved, res)
    if metodo == "rss_only" and not permitir_rss:
        return ResultadoCapturaV84(False, "RSS/snippet não é texto de matéria", "rss_only_bloqueado", chars, metodo, status, resolved, res)
    if status == "short_usable" and not permitir_short:
        return ResultadoCapturaV84(False, "texto curto não entra na fila automática", "short_usable_bloqueado", chars, metodo, status, resolved, res)
    if chars < min_chars:
        return ResultadoCapturaV84(False, f"texto útil insuficiente: {chars}<{min_chars}", "texto_util_insuficiente", chars, metodo, status, resolved, res)
    return ResultadoCapturaV84(True, f"texto capturado antes da fila: {chars} caracteres", "ok", chars, metodo, status, resolved, res)


def preparar_pauta_para_fila_v84(pauta: dict[str, Any]) -> tuple[bool, dict[str, Any], ResultadoCapturaV84]:
    """Extrai a fonte e só libera a pauta para a fila se houver texto útil."""
    from ururau.coleta.scraping import extrair_dossie_completo

    # v86C: extrair_dossie_completo já chama o extrator multiestratégia v86
    # antes da avaliação fail-closed. Não bloquear antes dessa chamada.
    texto_existente = pauta.get("texto_fonte") or pauta.get("resumo_origem") or ""
    res = extrair_dossie_completo(
        url=pauta.get("link_origem", ""),
        texto_existente=texto_existente,
    )
    decisao = avaliar_resultado_captura_v84(res)

    pauta = dict(pauta)
    pauta["prevalidacao_fila_v84"] = {
        "ok": decisao.ok,
        "motivo": decisao.motivo,
        "codigo": decisao.codigo,
        "chars": decisao.chars,
        "metodo": decisao.metodo,
        "status": decisao.status,
        "resolved_url": decisao.resolved_url,
        "v86_antes_do_bloqueio": True,
        "v86_metodo": (res.get("metadata") or {}).get("v86_metodo", ""),
        "v86_tentativas": (res.get("metadata") or {}).get("v86_tentativas", []),
    }

    if decisao.resolved_url and decisao.resolved_url.startswith("http") and "news.google.com" not in decisao.resolved_url.lower():
        pauta["link_origem"] = decisao.resolved_url
        pauta["link_fonte_resolvido"] = decisao.resolved_url

    if decisao.ok:
        cleaned = str(res.get("cleaned_source_text") or res.get("dossie") or "")
        pauta["dossie"] = str(res.get("dossie") or cleaned)
        pauta["raw_source_text"] = str(res.get("raw_source_text") or "")
        pauta["cleaned_source_text"] = cleaned
        pauta["texto_fonte"] = cleaned[:5000]
        pauta["extraction_method"] = decisao.metodo
        pauta["extraction_status"] = decisao.status
        pauta["source_sufficiency_score"] = res.get("source_sufficiency_score", 0)
        pauta["fonte_texto_chars"] = decisao.chars
        pauta["status"] = 'captada'
        return True, pauta, decisao

    pauta["status"] = 'bloqueada'
    pauta["bloqueio_coleta_v84"] = True
    pauta["motivo_bloqueio_coleta_v84"] = decisao.motivo
    pauta["status_validacao"] = "erro_extracao"
    pauta["status_publicacao_sugerido"] = "bloquear_total"
    pauta["fonte_texto_chars"] = decisao.chars
    return False, pauta, decisao


def tem_texto_util_prevalidado_v84(pauta: dict[str, Any]) -> bool:
    """Usado em migração/filtro para reconhecer pautas realmente captadas."""
    for k in ("cleaned_source_text", "dossie", "texto_fonte", "raw_source_text"):
        txt = str(pauta.get(k) or "").strip()
        if len(txt) >= _int_env("URURAU_V84_MIN_CHARS_CAPTURA", 500):
            return True
    try:
        return int(pauta.get("fonte_texto_chars") or 0) >= _int_env("URURAU_V84_MIN_CHARS_CAPTURA", 500)
    except Exception:
        return False
