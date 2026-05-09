"""
ururau/publisher/monitor_v111_patch.py

Adaptador da v110 teste para conectar a coleta Google News v111 ao monitor 24h
sem quebrar o fluxo legado. O monitor importa este módulo no começo do ciclo e
recebe uma lista de pautas já normalizadas para scoring/workflow.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List


def _env_bool(key: str, default: bool = False) -> bool:
    val = str(os.environ.get(key, "1" if default else "0")).strip().lower()
    return val in {"1", "true", "sim", "yes", "s", "on"}


def _env_int(key: str, default: int) -> int:
    try:
        return int(str(os.environ.get(key, str(default))).strip())
    except Exception:
        return default


def _log(logger: Any, nivel: str, msg: str, *args: Any) -> None:
    if logger is not None and hasattr(logger, nivel):
        try:
            getattr(logger, nivel)(msg, *args)
            return
        except Exception:
            pass
    try:
        texto = msg % args if args else msg
    except Exception:
        texto = msg
    print(texto)


def _hidratar_pauta_se_preciso(pauta: Dict[str, Any], logger: Any = None) -> Dict[str, Any]:
    """Completa texto/foto da pauta usando a cascata v111 quando a flag permite."""
    if not _env_bool("URURAU_V111_USAR_EXTRACAO_COMPLETA", True):
        return pauta

    min_chars = _env_int("URURAU_V111_GNEWS_MIN_CHARS_FONTE", 1200)
    texto_atual = str(
        pauta.get("cleaned_source_text")
        or pauta.get("texto_fonte")
        or pauta.get("dossie")
        or ""
    )
    if len(texto_atual.strip()) >= min_chars:
        return pauta

    url = str(pauta.get("url") or pauta.get("link_origem") or "").strip()
    if not url:
        return pauta

    try:
        from ururau.coleta.gnews_v111_integrado import extrair_fonte_v111_sync
        res = extrair_fonte_v111_sync(url)
    except Exception as exc:
        _log(logger, "warning", "[V111][FONTE] Falha na hidratação: %s", exc)
        pauta["status"] = "hidratacao"
        pauta["extraction_status"] = "erro_hidratacao_v111"
        return pauta

    texto = str(res.get("texto") or "").strip()
    chars = int(res.get("chars") or len(texto))
    pauta["metodo_extracao"] = res.get("metodo") or pauta.get("metodo_extracao") or "gnews_v111"
    pauta["chars_fonte"] = chars
    pauta["fonte_chars_v111"] = chars
    pauta["status_fonte_v111"] = "ok" if res.get("suficiente") else "curto"
    pauta["extraction_status"] = "ok" if res.get("suficiente") else "short_text"
    pauta["status"] = "pendente" if res.get("suficiente") else "hidratacao"

    if texto:
        pauta["texto_fonte"] = texto
        pauta["cleaned_source_text"] = texto
        pauta["raw_source_text"] = texto
        pauta["original_source_text"] = texto
        pauta["dossie"] = texto[:14000]
        pauta["_fonte_aba_texto"] = texto
        pauta["fonte_aba_texto"] = texto
        pauta["leitura_fonte_texto"] = texto

    if res.get("autor") and not pauta.get("autor"):
        pauta["autor"] = res.get("autor")
    if res.get("data") and not pauta.get("data_publicacao"):
        pauta["data_publicacao"] = res.get("data")
    imagens = res.get("imagens") or []
    if imagens and not pauta.get("imagens"):
        pauta["imagens"] = imagens
    if imagens and not pauta.get("imagem"):
        pauta["imagem"] = imagens[0]
    if pauta.get("imagem") and not pauta.get("imagem_url"):
        pauta["imagem_url"] = pauta.get("imagem")
        pauta.setdefault("imagem_status", "url_pendente")
        pauta.setdefault("imagem_credito", "Reprodução")

    return pauta


def coletar_gnews_para_monitor_v111(logger: Any = None) -> List[Dict[str, Any]]:
    """
    Coleta pautas v111 para o ciclo do monitor.

    Regra operacional:
    - Se URURAU_V111_USAR_CICLO_COMBINADO=1, usa v111.1
      (termos prioritários + grupos temáticos + dedup + hidratação).
    - Caso contrário, usa v111 base (somente termos_config).

    Respeita:
    - URURAU_V111_GNEWS_INTEGRADO=1
    - URURAU_V111_SCORE_MINIMO_PAUTA
    - URURAU_V111_USAR_EXTRACAO_COMPLETA
    """
    if not _env_bool("URURAU_V111_GNEWS_INTEGRADO", False):
        return []

    score_min = _env_int("URURAU_V111_SCORE_MINIMO_PAUTA", 65)

    if _env_bool("URURAU_V111_USAR_CICLO_COMBINADO", False):
        try:
            from ururau.coleta.gnews_v111_integrado import rodar_async_v111
            from ururau.publisher.monitor_v111_ciclo_combinado import coletar_ciclo_combinado_v111
            pautas = rodar_async_v111(coletar_ciclo_combinado_v111())
            _log(logger, "info", "[V111.1][GNEWS] Ciclo combinado retornou %s pauta(s)", len(pautas or []))
            return list(pautas or [])
        except Exception as exc:
            _log(logger, "warning", "[V111.1][GNEWS] Ciclo combinado falhou; tentando v111 base: %s", exc)

    try:
        from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111_sync
    except Exception as exc:
        _log(logger, "warning", "[V111][GNEWS] Import falhou: %s", exc)
        return []

    janela = _env_int("URURAU_V111_GNEWS_JANELA_HORAS", 4)
    max_resultados = _env_int("URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO", 3)

    try:
        pautas = coletar_pautas_gnews_v111_sync(
            modo="termos_config",
            janela=janela,
            max_resultados=max_resultados,
        )
    except Exception as exc:
        _log(logger, "warning", "[V111][GNEWS] Falha na coleta integrada: %s", exc)
        return []

    saida: list[dict] = []
    descartadas = 0
    for pauta in pautas:
        score = int(pauta.get("score") or pauta.get("score_editorial") or 0)
        if score < score_min:
            descartadas += 1
            continue

        pauta = _hidratar_pauta_se_preciso(dict(pauta), logger=logger)
        # Mantém baixa hidratação na fila apenas se o score for alto; o workflow
        # ainda aplica fail-closed antes de redigir/publicar.
        saida.append(pauta)

    _log(
        logger,
        "info",
        "[V111][GNEWS] Monitor recebeu %s pauta(s); %s abaixo do score mínimo %s",
        len(saida),
        descartadas,
        score_min,
    )
    return saida

def coletar_gnews_legado_v110(logger: Any = None, termos_legado: List[str] | None = None) -> List[Dict[str, Any]]:
    """Fallback explícito para a ponte v110 quando a flag legada estiver ligada."""
    if not _env_bool("URURAU_V110_MONITOR_GNEWS_LEGADO", False):
        return []
    try:
        from ururau.coleta.kimi_bridge_v110 import coletar_google_news_kimi_v110
        termos = termos_legado or [
            "Rio de Janeiro",
            "Campos dos Goytacazes",
            "Norte Fluminense",
            "Porto do Açu",
            "ALERJ",
            "governo RJ",
        ]
        pautas = coletar_google_news_kimi_v110(termos)
        _log(logger, "info", "[KIMI v110] fallback coletou %s pauta(s)", len(pautas))
        return list(pautas or [])
    except Exception as exc:
        _log(logger, "warning", "[KIMI v110] fallback falhou: %s", exc)
        return []


def injetar_gnews_v111_no_raw(raw: List[Dict[str, Any]], logger: Any = None, termos_legado: List[str] | None = None) -> int:
    """
    Adiciona pautas Google News ao raw do monitor.

    Regra:
    - Se URURAU_V111_GNEWS_INTEGRADO=1, usa v111.
    - Senão, se URURAU_V110_MONITOR_GNEWS_LEGADO=1, usa v110.
    - Senão, não injeta nada.
    """
    total_antes = len(raw)
    usou_algum = False

    if _env_bool("URURAU_V111_GNEWS_INTEGRADO", False):
        usou_algum = True
        lote = coletar_gnews_para_monitor_v111(logger=logger)
        raw.extend(lote)
        _log(logger, "info", "[V111][GNEWS] %s pauta(s) adicionadas ao raw do monitor", len(lote))

        # V47.7: capacidade aditiva. Se o integrado não trouxe nada, o legado
        # pode complementar sem substituir RSS, AutoFontes ou Source Hunter.
        if not lote and _env_bool("URURAU_V110_MONITOR_GNEWS_LEGADO", False):
            lote_legado = coletar_gnews_legado_v110(logger=logger, termos_legado=termos_legado)
            raw.extend(lote_legado)
            _log(logger, "info", "[KIMI v110] fallback após v111 vazio adicionou %s pauta(s)", len(lote_legado))
    elif _env_bool("URURAU_V110_MONITOR_GNEWS_LEGADO", False):
        usou_algum = True
        lote = coletar_gnews_legado_v110(logger=logger, termos_legado=termos_legado)
        raw.extend(lote)
        _log(logger, "info", "[KIMI v110] %s pauta(s) adicionadas ao raw do monitor", len(lote))

    if not usou_algum:
        _log(logger, "info", "[V111][GNEWS] Google News integrado desligado neste ciclo")
    return len(raw) - total_antes


# PATCH_V47_20_GNEWS_HARD_OFF
try:
    import os as _os_v4720_g
    if _os_v4720_g.environ.get('URURAU_GNEWS_DESLIGADO_NO_MONITOR') == '1':
        def injetar_gnews_v111_no_raw(raw, logger=None, termos_legado=None):
            try:
                logger.info('[V47.20][GNEWS] desligado no monitor; ciclo segue com RSS/AutoFontes/fila')
            except Exception:
                pass
            return 0
        def coletar_gnews_para_monitor_v111(logger=None):
            return []
        def coletar_gnews_legado_v110(logger=None, termos_legado=None):
            return []
except Exception:
    pass
