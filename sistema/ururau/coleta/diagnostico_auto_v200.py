# -*- coding: utf-8 -*-
"""diagnostico_auto_v200 — diagnostico de fonte INTEGRADO ao sistema.

Spec do usuario (14/05/2026):
  "isso tem que estar integrado ao sistema, pra gente rodar o diagnostico
   de fonte de cada link, pra descobrir a forma de capta-los melhor e usar
   as ferramentas que temos pra nao ter mais problema com nenhum link."

Este modulo embrulha o diagnostico ja existente (diagnostico_fontes_v130 +
auto_perfil_fontes_v131) e oferece DOIS modos, conforme decidido:

  1. LOTE  -> diagnosticar_todas_as_fontes(): varre TODAS as fontes
              configuradas, roda o diagnostico completo de cada uma,
              gera/aplica perfil operacional e produz um relatorio
              consolidado. Disparado por botao na UI ou pela CLI
              sistema/diagnosticar_todas_fontes_v200.py.

  2. AUTO-CURA -> auto_curar_fonte_v200(): chamado DURANTE a coleta quando
              um feed devolve 0 itens ou falha. Roda o diagnostico daquele
              unico dominio, aplica um perfil fresco e tenta coletar pela
              cascata universal (rss -> rss xml -> wp api -> sitemap ->
              html). Cacheado por dominio para nao repetir na mesma sessao.

POLITICA "SO SINALIZAR" (decisao do usuario):
  Quando uma fonte falha em TODAS as estrategias, ela NAO e desativada nem
  despriorizada. Apenas e registrada em fontes_precisam_atencao_v200.json
  com o motivo, para revisao manual depois. Tudo continua como esta.

Tudo desativavel por ENV:
  URURAU_V200_AUTOCURA_COLETA=1        (auto-cura inline na coleta)
  URURAU_V200_DIAG_LOTE_JANELA_HORAS=24
  URURAU_V200_DIAG_LOTE_MAX_FONTES=0   (0 = sem limite)
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

# ─────────────────────── Localizacao de arquivos ─────────────────────────

def _sistema_dir() -> Path:
    """Pasta sistema/ — este arquivo esta em sistema/ururau/coleta/."""
    return Path(__file__).resolve().parents[2]


def _config_candidatos_fontes() -> list[Path]:
    base = _sistema_dir()
    return [
        base / "config" / "fontes_links.json",
        base / "config" / "fontes_rss.json",
        base / "fontes_rss.json",
        base / "configuracoes" / "fontes_rss.json",
    ]


def _relatorios_dir() -> Path:
    d = _sistema_dir() / "relatorios_diagnostico_fontes" / "lote_v200"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def _arquivo_precisam_atencao() -> Path:
    return _sistema_dir() / "fontes_precisam_atencao_v200.json"


# ─────────────────────── Helpers ─────────────────────────────────────────

def _env_bool(k: str, d: bool = True) -> bool:
    v = os.getenv(k)
    if v is None:
        return d
    return str(v).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _env_int(k: str, d: int) -> int:
    try:
        return int(os.getenv(k, str(d)) or d)
    except Exception:
        return d


def _dominio(url: str) -> str:
    try:
        host = urlparse(str(url or "").strip()).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return str(url or "").lower()


def _ler_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ─────────────────────── Enumeracao de fontes ────────────────────────────

def enumerar_fontes_configuradas() -> list[dict[str, str]]:
    """Le TODAS as fontes configuradas no sistema e devolve uma lista
    deduplicada por dominio: [{"url","nome","grupo"}].

    Prioriza config/fontes_links.json (Fonte unica V43, com items+metadados).
    Completa com os fontes_rss.json caso haja dominios nao cobertos.
    """
    vistos: set[str] = set()
    out: list[dict[str, str]] = []

    # 1) fontes_links.json — a fonte unica canonica
    flinks = _sistema_dir() / "config" / "fontes_links.json"
    dados = _ler_json(flinks)
    if isinstance(dados, dict):
        for item in dados.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            dom = _dominio(url)
            if not dom or dom in vistos:
                continue
            vistos.add(dom)
            out.append({
                "url": url,
                "nome": str(item.get("nome") or dom),
                "grupo": str(item.get("grupo") or "RSS"),
                "ativo": bool(item.get("ativo", True)),
            })

    # 2) demais fontes_rss.json — completa dominios faltantes
    for p in _config_candidatos_fontes():
        if p.name != "fontes_rss.json":
            continue
        dados = _ler_json(p)
        if isinstance(dados, dict):
            dados = dados.get("fontes", []) or list(dados.values())
        if not isinstance(dados, list):
            continue
        for item in dados:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            dom = _dominio(url)
            if not dom or dom in vistos:
                continue
            vistos.add(dom)
            out.append({
                "url": url,
                "nome": str(item.get("nome") or dom),
                "grupo": str(item.get("grupo") or item.get("tipo_coleta") or "RSS"),
                "ativo": bool(item.get("ativo", True)),
            })

    return out


# ─────────────────────── Diagnostico de UMA fonte ────────────────────────

def diagnosticar_e_aplicar_uma(url: str, nome: str = "", grupo: str = "",
                               *, janela_horas: int = 24,
                               log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Roda o diagnostico completo de UMA fonte e aplica o perfil operacional.

    Devolve um dict padronizado:
      {
        "url","nome","grupo","dominio",
        "ok": bool,                # diagnostico achou caminho funcional
        "aplicado": bool,          # perfil operacional salvo
        "estrategia": str,         # rss / sitemap / wp_api / html / -
        "status": str,             # funcional_com_pauta / tecnico / falhou
        "feeds": list[str],
        "motivo": str,
        "avisos": list[str],
      }
    """
    def _log(m: str) -> None:
        if log:
            try:
                log(m)
            except Exception:
                pass

    dom = _dominio(url)
    resultado: dict[str, Any] = {
        "url": url, "nome": nome or dom, "grupo": grupo or "RSS",
        "dominio": dom, "ok": False, "aplicado": False,
        "estrategia": "-", "status": "falhou", "feeds": [],
        "motivo": "", "avisos": [],
    }

    try:
        from ururau.coleta.diagnostico_fontes_v130 import diagnostico_completo
        from ururau.coleta.auto_perfil_fontes_v131 import (
            aplicar_diagnostico_operacional_v131,
        )
    except Exception as e:
        resultado["motivo"] = f"modulos_diagnostico_indisponiveis: {e}"
        return resultado

    try:
        results = diagnostico_completo(url, log_callback=log, janela_horas=janela_horas)
    except Exception as e:
        resultado["motivo"] = f"diagnostico_completo_falhou: {e}"
        return resultado

    # solucao sugerida pelo diagnostico
    solucao = results.get("solucao") or {}
    resultado["estrategia"] = str(solucao.get("estrategia_principal")
                                  or solucao.get("estrategia") or "-")
    resultado["feeds"] = list(solucao.get("feeds") or solucao.get("feeds_sugeridos") or [])

    try:
        info = aplicar_diagnostico_operacional_v131(
            results, nome_preferido=nome, grupo_preferido=grupo,
        )
    except Exception as e:
        resultado["motivo"] = f"aplicar_diagnostico_falhou: {e}"
        return resultado

    perfil = info.get("perfil") or {}
    teste = info.get("teste") or {}
    resultado["aplicado"] = bool(info.get("aplicado"))
    resultado["avisos"] = list(info.get("avisos") or [])
    if perfil.get("estrategia"):
        resultado["estrategia"] = str(perfil.get("estrategia"))
    if perfil.get("feeds"):
        resultado["feeds"] = list(perfil.get("feeds") or [])

    if teste.get("ok"):
        resultado["ok"] = True
        resultado["status"] = "funcional_com_pauta"
        resultado["motivo"] = f"teste gerou {teste.get('qtd', 0)} pauta(s)"
    elif teste.get("sucesso_tecnico") or info.get("aplicado"):
        resultado["ok"] = True
        resultado["status"] = "funcional_tecnico"
        resultado["motivo"] = "caminho coletavel comprovado, sem pauta na janela do teste"
    else:
        resultado["ok"] = False
        resultado["status"] = "falhou"
        resultado["motivo"] = "; ".join(resultado["avisos"]) or "nenhuma estrategia funcionou"

    _log(f"[DIAG_AUTO_V200] {dom}: {resultado['status']} "
         f"(estrategia={resultado['estrategia']}, aplicado={resultado['aplicado']})")
    return resultado


# ─────────────────────── Diagnostico em LOTE ─────────────────────────────

def _registrar_precisa_atencao(fontes_problema: list[dict[str, Any]]) -> str:
    """Politica 'so sinalizar': grava as fontes que falharam em TODAS as
    estrategias num JSON para revisao manual. NAO desativa nada.
    """
    p = _arquivo_precisam_atencao()
    payload = {
        "gerado_em": _dt.datetime.now().isoformat(timespec="seconds"),
        "politica": "so_sinalizar — nada foi desativado nem despriorizado",
        "total": len(fontes_problema),
        "fontes": fontes_problema,
    }
    try:
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    except Exception as e:
        return f"(falha ao gravar {p.name}: {e})"
    return str(p)


def diagnosticar_todas_as_fontes(log_callback: Callable[[str], None] | None = None,
                                 *, max_fontes: int | None = None,
                                 janela_horas: int | None = None) -> dict[str, Any]:
    """Varre TODAS as fontes configuradas, diagnostica e aplica perfil.

    Retorna um dict com o resumo consolidado e grava 2 arquivos:
      - relatorios_diagnostico_fontes/lote_v200/lote_v200_<ts>.{json,txt}
      - fontes_precisam_atencao_v200.json  (so as que falharam tudo)
    """
    def _log(m: str) -> None:
        if log_callback:
            try:
                log_callback(m)
            except Exception:
                pass

    if janela_horas is None:
        janela_horas = _env_int("URURAU_V200_DIAG_LOTE_JANELA_HORAS", 24)
    if max_fontes is None:
        mx = _env_int("URURAU_V200_DIAG_LOTE_MAX_FONTES", 0)
        max_fontes = mx if mx > 0 else None

    fontes = enumerar_fontes_configuradas()
    if max_fontes:
        fontes = fontes[:max_fontes]

    _log(f"[DIAG_LOTE_V200] Iniciando diagnostico de {len(fontes)} fonte(s)...")
    inicio = _dt.datetime.now()

    resultados: list[dict[str, Any]] = []
    ok_count = 0
    aplicado_count = 0
    problema: list[dict[str, Any]] = []

    for i, fonte in enumerate(fontes, 1):
        _log(f"[DIAG_LOTE_V200] ({i}/{len(fontes)}) {fonte['nome']} — {fonte['url']}")
        r = diagnosticar_e_aplicar_uma(
            fonte["url"], nome=fonte["nome"], grupo=fonte["grupo"],
            janela_horas=janela_horas, log=log_callback,
        )
        resultados.append(r)
        if r["ok"]:
            ok_count += 1
        if r["aplicado"]:
            aplicado_count += 1
        if not r["ok"]:
            problema.append({
                "url": r["url"], "nome": r["nome"], "grupo": r["grupo"],
                "dominio": r["dominio"], "motivo": r["motivo"],
            })

    duracao = (_dt.datetime.now() - inicio).total_seconds()
    ts = inicio.strftime("%Y%m%d_%H%M%S")

    # ── relatorio TXT consolidado ────────────────────────────────────────
    linhas: list[str] = []
    linhas.append("=" * 74)
    linhas.append("DIAGNOSTICO EM LOTE DE TODAS AS FONTES — URURAU v200")
    linhas.append("=" * 74)
    linhas.append(f"Gerado em: {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
    linhas.append(f"Duracao: {duracao:.0f}s")
    linhas.append(f"Total de fontes: {len(fontes)}")
    linhas.append(f"Funcionais: {ok_count}")
    linhas.append(f"Perfil aplicado: {aplicado_count}")
    linhas.append(f"Precisam de atencao: {len(problema)}")
    linhas.append("")
    linhas.append("DETALHE POR FONTE")
    linhas.append("-" * 74)
    for r in resultados:
        marca = "[OK]" if r["ok"] else "[!!]"
        linhas.append(
            f"  {marca} {r['nome']} ({r['dominio']}) | grupo={r['grupo']} | "
            f"estrategia={r['estrategia']} | status={r['status']} | "
            f"aplicado={'SIM' if r['aplicado'] else 'NAO'}"
        )
        if not r["ok"] and r["motivo"]:
            linhas.append(f"       motivo: {r['motivo'][:160]}")
    linhas.append("")
    if problema:
        linhas.append("FONTES QUE PRECISAM DE ATENCAO (politica: SO SINALIZAR)")
        linhas.append("-" * 74)
        linhas.append("  Nada foi desativado. Revise manualmente os links abaixo:")
        for f in problema:
            linhas.append(f"  - {f['nome']} ({f['dominio']}): {f['motivo'][:140]}")
    else:
        linhas.append("Nenhuma fonte ficou sem caminho de coleta. ")
    relatorio_txt = "\n".join(linhas)

    # ── persistencia ─────────────────────────────────────────────────────
    arq_json = _relatorios_dir() / f"lote_v200_{ts}.json"
    arq_txt = _relatorios_dir() / f"lote_v200_{ts}.txt"
    payload = {
        "gerado_em": inicio.isoformat(timespec="seconds"),
        "duracao_seg": round(duracao, 1),
        "total": len(fontes),
        "funcionais": ok_count,
        "aplicados": aplicado_count,
        "precisam_atencao": len(problema),
        "resultados": resultados,
    }
    try:
        arq_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        arq_txt.write_text(relatorio_txt, encoding="utf-8")
    except Exception as e:
        _log(f"[DIAG_LOTE_V200][AVISO] falha ao gravar relatorio: {e}")

    arq_atencao = _registrar_precisa_atencao(problema)

    _log(f"[DIAG_LOTE_V200] Concluido em {duracao:.0f}s. "
         f"{ok_count}/{len(fontes)} funcionais, {len(problema)} precisam de atencao.")

    return {
        "total": len(fontes),
        "funcionais": ok_count,
        "aplicados": aplicado_count,
        "precisam_atencao": len(problema),
        "resultados": resultados,
        "relatorio_txt": relatorio_txt,
        "arquivo_json": str(arq_json),
        "arquivo_txt": str(arq_txt),
        "arquivo_precisam_atencao": arq_atencao,
        "duracao_seg": round(duracao, 1),
    }


# ─────────────────────── AUTO-CURA inline na coleta ──────────────────────

# cache por dominio para nao re-diagnosticar na mesma sessao
_AUTOCURA_CACHE: dict[str, dict[str, Any]] = {}
_AUTOCURA_LOCK = threading.Lock()


def auto_curar_fonte_v200(url: str, nome: str = "", grupo: str = "",
                          *, log: Callable[[str], None] | None = None,
                          max_itens: int | None = None) -> dict[str, Any]:
    """Chamado DURANTE a coleta quando um feed devolve 0 itens ou falha.

    Roda o diagnostico daquele dominio, aplica perfil fresco e tenta coletar
    pela cascata universal. Devolve:
      {"ok": bool, "pautas": list[dict], "estrategia": str, "motivo": str}

    Cacheado por dominio: na mesma sessao, o segundo chamado para o mesmo
    dominio devolve o resultado anterior (evita travar a coleta).
    """
    def _log(m: str) -> None:
        if log:
            try:
                log(m)
            except Exception:
                pass

    if not _env_bool("URURAU_V200_AUTOCURA_COLETA", True):
        return {"ok": False, "pautas": [], "estrategia": "-",
                "motivo": "autocura_desativada_por_env"}

    dom = _dominio(url)
    with _AUTOCURA_LOCK:
        if dom in _AUTOCURA_CACHE:
            cached = _AUTOCURA_CACHE[dom]
            _log(f"[AUTOCURA_V200] {dom}: usando resultado em cache "
                 f"({len(cached.get('pautas') or [])} pautas)")
            return cached

    _log(f"[AUTOCURA_V200] {dom}: feed vazio/falho — rodando diagnostico inline...")
    saida: dict[str, Any] = {"ok": False, "pautas": [], "estrategia": "-", "motivo": ""}

    try:
        # 1) diagnostico + aplicacao do perfil
        diag = diagnosticar_e_aplicar_uma(url, nome=nome, grupo=grupo, log=log)
        saida["estrategia"] = diag.get("estrategia", "-")

        # 2) coleta pela cascata universal (mesmo motor do Diagnostico de Fonte)
        from ururau.coleta.auto_perfil_fontes_v131 import coletar_url_auto_v1325
        lote, stats, perfil = coletar_url_auto_v1325(
            url, nome=nome, grupo=grupo or "Regionais", max_itens=max_itens,
        )
        if lote:
            saida["ok"] = True
            saida["pautas"] = lote
            saida["estrategia"] = str(perfil.get("estrategia") or saida["estrategia"])
            saida["motivo"] = f"auto-cura coletou {len(lote)} pauta(s) via cascata"
            _log(f"[AUTOCURA_V200] {dom}: OK — {len(lote)} pauta(s) "
                 f"via {saida['estrategia']}")
        else:
            saida["motivo"] = (
                f"diagnostico={diag.get('status')}; cascata sem pautas "
                f"({stats.get('brutas', 0)} brutas)"
            )
            _log(f"[AUTOCURA_V200] {dom}: sem pautas — {saida['motivo']}")
    except Exception as e:
        saida["motivo"] = f"autocura_excecao: {e}"
        _log(f"[AUTOCURA_V200] {dom}: erro — {e}")

    with _AUTOCURA_LOCK:
        _AUTOCURA_CACHE[dom] = saida
    return saida


def limpar_cache_autocura() -> None:
    """Limpa o cache de auto-cura — chamar no inicio de cada coleta geral."""
    with _AUTOCURA_LOCK:
        _AUTOCURA_CACHE.clear()


__all__ = [
    "enumerar_fontes_configuradas",
    "diagnosticar_e_aplicar_uma",
    "diagnosticar_todas_as_fontes",
    "auto_curar_fonte_v200",
    "limpar_cache_autocura",
]
