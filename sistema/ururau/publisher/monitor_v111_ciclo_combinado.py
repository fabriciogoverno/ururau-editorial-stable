"""
v111.2 Plus — Ciclo Combinado de Coleta Google News + Source Hunter
Consolida termos prioritários, grupos temáticos, RSS público e descoberta de homepages/categorias.

Uso no monitor.py:
    if os.environ.get("URURAU_V111_GNEWS_INTEGRADO") == "1":
        if os.environ.get("URURAU_V111_USAR_CICLO_COMBINADO") == "1":
            from ururau.publisher.monitor_v111_ciclo_combinado import coletar_ciclo_combinado_v111
            pautas_gnews = await coletar_ciclo_combinado_v111()
        else:
            # v111 base (apenas termos)
            from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111
            pautas_gnews = await coletar_pautas_gnews_v111(modo="termos_config")

Dependências: google_news_scraper (já instalado), aiohttp, beautifulsoup4
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ururau.coleta.gnews_v111_integrado import (
    coletar_pautas_gnews_v111,
    extrair_fonte_v111,
)

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------

GRUPOS_PADRAO: List[str] = [
    "campos_local",
    "norte_fluminense",
    "porto_do_acu",
    "rj_politica",
    "rj_policia",
    "governo_rj",
    "alerj",
    "deputados_rj",
    "pre_candidatos_governo_rj",
    "transparencia_e_investigacao",
    "utilidade_publica_rj",
    "servico_brasil",
    "alto_trafego_brasil",
    "alertas_globais",
]

GRUPOS_BONUS: set = {
    "alerj",
    "governo_rj",
    "transparencia_e_investigacao",
    "porto_do_acu",
    "rj_politica",
}

_MAX_CONCORRENCIA_GNEWS = 3


# ---------------------------------------------------------------------------
# UTILITÁRIOS INTERNOS
# ---------------------------------------------------------------------------

def _env_int(key: str, default: int) -> int:
    """Lê variável de ambiente como int."""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    val = str(os.environ.get(key, "1" if default else "0")).strip().lower()
    return val in {"1", "true", "sim", "yes", "s", "on"}


def _normalizar_url_para_chave(url: str) -> str:
    """Extrai chave de deduplicação: domínio + path, sem www, sem query."""
    if not url:
        return ""
    try:
        p = urlparse(url)
        netloc = p.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = p.path.rstrip("/").lower()
        return f"{netloc}{path}"
    except Exception:
        return url.lower().strip()


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_agora() -> str:
    return _agora_utc().isoformat()


# ---------------------------------------------------------------------------
# COLETA COMBINADA
# ---------------------------------------------------------------------------

async def coletar_ciclo_combinado_v111(
    max_por_grupo: Optional[int] = None,
    max_total: Optional[int] = None,
    janela_horas: Optional[int] = None,
    grupos_ativos: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Coleta combinada: termos prioritários + grupos temáticos.

    Retorna pautas únicas, filtradas, ordenadas por score decrescente.
    """
    # Defaults do .env
    max_por_grupo = max_por_grupo or _env_int("URURAU_V111_MAX_POR_GRUPO", 3)
    max_total = max_total or _env_int("URURAU_V111_MAX_TOTAL_PAUTAS", 30)
    janela_horas = janela_horas or _env_int("URURAU_V111_GNEWS_JANELA_HORAS", 4)

    # Grupos ativos (string CSV do .env ou lista padrão)
    if grupos_ativos is None:
        env_grupos = os.environ.get("URURAU_V111_GRUPOS_ATIVOS", "")
        if env_grupos:
            grupos_ativos = [g.strip() for g in env_grupos.split(",") if g.strip()]
        else:
            grupos_ativos = GRUPOS_PADRAO[:8]  # 8 principais por padrão

    print(f"[V111.1][INIT] Ciclo combinado iniciado (termos + {len(grupos_ativos)} grupos)")

    # --- [1] COLETA POR TERMOS ---
    print("[V111.1][TERMOS] Coletando termos prioritarios...")
    pautas_termos: List[Dict[str, Any]] = []
    try:
        pautas_termos = await coletar_pautas_gnews_v111(modo="termos_config")
        print(f"[V111.1][TERMOS] {len(pautas_termos)} pautas de termos")
    except Exception as e:
        print(f"[V111.1][TERMOS][ERRO] {e}")

    # --- [2] COLETA POR GRUPOS (limitado concorrência) ---
    pautas_grupos: List[Dict[str, Any]] = []
    semaphore = asyncio.Semaphore(_MAX_CONCORRENCIA_GNEWS)

    async def _buscar_grupo(grupo: str) -> List[Dict[str, Any]]:
        async with semaphore:
            try:
                pts = await coletar_pautas_gnews_v111(
                    modo="grupo",
                    grupo=grupo,
                    max_resultados=max_por_grupo,
                    janela=janela_horas,
                )
                # Marca grupo na pauta para scoring
                for p in pts:
                    p["grupo_tematico"] = grupo
                print(f"[V111.1][GRUPO][{grupo}] {len(pts)} pautas")
                return pts
            except Exception as e:
                print(f"[V111.1][GRUPO][{grupo}][ERRO] {e}")
                return []

    tasks = [_buscar_grupo(g) for g in grupos_ativos]
    resultados_grupos = await asyncio.gather(*tasks)

    for pts in resultados_grupos:
        pautas_grupos.extend(pts)

    print(f"[V111.1][COMBINADO] {len(pautas_termos)} termos + {len(pautas_grupos)} grupos = {len(pautas_termos) + len(pautas_grupos)} brutas")

    # --- [2b] SOURCE HUNTER PLUS v111.2 ---
    # Aprendizado aplicado de newspaper/newspaper4k/meridian:
    # RSS descoberto, homepage/categorias publicas, heuristica de URL,
    # cooldown por dominio e hidratacao pela cascata ArticleExtractor.
    pautas_source_plus: List[Dict[str, Any]] = []
    if _env_bool("URURAU_PLUS_SOURCE_HUNTER", False):
        try:
            from ururau.coleta.source_discovery_plus_v112 import coletar_source_hunter_plus_v112
            pautas_source_plus = await coletar_source_hunter_plus_v112(
                max_total=_env_int("URURAU_PLUS_MAX_TOTAL", 20),
                hidratar=_env_bool("URURAU_PLUS_HIDRATAR_FONTES", True),
            )
            for p in pautas_source_plus:
                p["grupo_tematico"] = p.get("grupo_tematico") or "source_hunter_plus"
            print(f"[V111.2][SOURCE_PLUS] {len(pautas_source_plus)} pautas de fontes publicas/RSS/homepages")
        except Exception as e:
            print(f"[V111.2][SOURCE_PLUS][ERRO] {e}")

    # --- [3] COMBINAÇÃO ---
    todas = pautas_termos + pautas_grupos + pautas_source_plus
    print(f"[V111.2][TOTAL] {len(todas)} pautas brutas apos Google News + Source Plus")

    # --- [3b] RECÁLCULO DE SCORE COMBINADO ---
    for p in todas:
        p["score"] = recalcular_score_combinado(p)

    # --- [4] DEDUPLICAÇÃO (mantém maior score) ---
    unicas = _deduplicar_mantendo_maior_score(todas)
    print(f"[V111.1][DEDUP] {len(todas)} → {len(unicas)} unicas ({len(todas) - len(unicas)} removidas)")

    # --- [5] FILTRO TEMPORAL ---
    dentro_janela = _filtrar_janela_temporal(unicas, janela_horas)
    print(f"[V111.1][FILTRO] {len(unicas)} → {len(dentro_janela)} dentro da janela ({janela_horas}h)")

    # --- [6] SCORE MÍNIMO ---
    min_score = _env_int("URURAU_V111_SCORE_MINIMO_PAUTA", 65)
    acima_minimo = [p for p in dentro_janela if p.get("score", 0) >= min_score]
    print(f"[V111.1][SCORE] {len(dentro_janela)} → {len(acima_minimo)} acima do minimo ({min_score})")

    # --- [7] ORDENAÇÃO ---
    ordenadas = sorted(
        acima_minimo,
        key=lambda p: (p.get("score", 0), p.get("data_publicacao", "")),
        reverse=True,
    )

    # --- [8] LIMITE TOTAL ---
    if len(ordenadas) > max_total:
        ordenadas = ordenadas[:max_total]
        print(f"[V111.1][LIMITE] Cortado para {max_total} pautas (max_total)")

    # --- [9] HIDRATAÇÃO (se ativada) ---
    if os.environ.get("URURAU_V111_HIDRATAR_SEM_TEXTO") == "1":
        ordenadas = await _hidratar_pautas(ordenadas)

    # --- [10] ADICIONA METADADOS DE COLETA ---
    for p in ordenadas:
        p.setdefault("coletado_em", _iso_agora())
        p.setdefault("fonte_tipo", "google_news")
        p.setdefault("fonte_nome", "Google News v111.1")
        p.setdefault("fonte_id", "gnews_v111_1")
        # Campos legados (compatibilidade)
        _garantir_campos_legados(p)

    print(f"[V111.1][FILA] {len(ordenadas)} pautas prontas para o pipeline")
    return ordenadas



# ---------------------------------------------------------------------------
# SCORE PUBLICO / COMPATIBILIDADE COM A SPEC
# ---------------------------------------------------------------------------

def recalcular_score_combinado(pauta: Dict[str, Any]) -> int:
    """
    Recalcula score editorial do ciclo combinado sem depender de rede.

    Mantém compatibilidade com o score vindo do GoogleNewsIntegrado, mas
    adiciona sinais úteis do ciclo combinado: grupo temático prioritário,
    texto suficiente, recência, autor, imagem e canal.
    """
    score = 50

    grupo = str(pauta.get("grupo_tematico") or pauta.get("grupo") or "").strip()
    termo = str(pauta.get("termo_busca") or "").lower()
    chars = int(pauta.get("chars_fonte") or len(str(pauta.get("texto_fonte") or "")))
    canal = str(pauta.get("canal_sugerido") or pauta.get("canal_forcado") or "").strip()

    # Termos/assuntos prioritários conhecidos no radar editorial.
    termos_prioritarios = (
        "anvisa",
        "fgts",
        "eduardo paes",
        "douglas ruas",
        "alerj",
        "campos",
        "norte fluminense",
        "porto do açu",
        "porto do acu",
        "polícia",
        "policia",
        "governo rj",
    )
    if any(t in termo for t in termos_prioritarios):
        score += 15

    if grupo in GRUPOS_BONUS:
        score += 5

    if chars > 2000:
        score += 10
    elif chars > 1200:
        score += 5

    data = pauta.get("data_publicacao")
    try:
        if isinstance(data, str) and data:
            dt = datetime.fromisoformat(data.replace("Z", "+00:00"))
        elif isinstance(data, datetime):
            dt = data
        else:
            dt = None
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            idade_horas = (_agora_utc() - dt).total_seconds() / 3600
            if idade_horas <= 1:
                score += 15
            elif idade_horas <= 2:
                score += 8
    except Exception:
        pass

    if pauta.get("autor"):
        score += 10
    if pauta.get("imagem") or pauta.get("imagens"):
        score += 5
    if canal:
        score += 5

    score_original = int(pauta.get("score") or 0)
    return max(score_original, min(100, score))


def deduplicar_pautas_combinadas(pautas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Interface pública exigida pela spec: deduplica preservando maior score."""
    return _deduplicar_mantendo_maior_score(pautas)


async def hidratar_pautas_v111(
    pautas: List[Dict[str, Any]],
    min_chars: Optional[int] = None,
    max_concorrencia: int = 3,
) -> List[Dict[str, Any]]:
    """
    Interface pública exigida pela spec para hidratação.

    Os parâmetros são aplicados via ambiente de forma temporária para reaproveitar
    a implementação operacional `_hidratar_pautas`.
    """
    old_min = os.environ.get("URURAU_V111_GNEWS_MIN_CHARS_FONTE")
    old_conc = os.environ.get("URURAU_V111_MAX_CONCORRENCIA_HIDRATA")
    try:
        if min_chars is not None:
            os.environ["URURAU_V111_GNEWS_MIN_CHARS_FONTE"] = str(min_chars)
        if max_concorrencia is not None:
            os.environ["URURAU_V111_MAX_CONCORRENCIA_HIDRATA"] = str(max_concorrencia)
        return await _hidratar_pautas(pautas)
    finally:
        if old_min is None:
            os.environ.pop("URURAU_V111_GNEWS_MIN_CHARS_FONTE", None)
        else:
            os.environ["URURAU_V111_GNEWS_MIN_CHARS_FONTE"] = old_min
        if old_conc is None:
            os.environ.pop("URURAU_V111_MAX_CONCORRENCIA_HIDRATA", None)
        else:
            os.environ["URURAU_V111_MAX_CONCORRENCIA_HIDRATA"] = old_conc


# ---------------------------------------------------------------------------
# DEDUPLICAÇÃO INTELIGENTE
# ---------------------------------------------------------------------------

def _deduplicar_mantendo_maior_score(
    pautas: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Deduplica por URL normalizada.
    Quando há conflito, mantém a pauta com MAIOR SCORE.
    Se scores iguais, mantém a mais recente.
    """
    mapa: Dict[str, Dict[str, Any]] = {}

    for p in pautas:
        url = p.get("url", "")
        chave = _normalizar_url_para_chave(url)
        if not chave:
            continue

        existente = mapa.get(chave)
        if existente is None:
            mapa[chave] = p
        else:
            # Compara score; se igual, compara data
            score_novo = p.get("score", 0)
            score_velho = existente.get("score", 0)
            if score_novo > score_velho:
                mapa[chave] = p
            elif score_novo == score_velho:
                data_novo = p.get("data_publicacao", "")
                data_velho = existente.get("data_publicacao", "")
                if data_novo > data_velho:
                    mapa[chave] = p

    return list(mapa.values())


# ---------------------------------------------------------------------------
# FILTRO TEMPORAL
# ---------------------------------------------------------------------------

def _filtrar_janela_temporal(
    pautas: List[Dict[str, Any]],
    horas: int,
) -> List[Dict[str, Any]]:
    """Remove pautas publicadas há mais de N horas."""
    agora = _agora_utc()
    limite = timedelta(hours=horas)
    resultado = []

    for p in pautas:
        data_str = p.get("data_publicacao")
        if not data_str:
            # Sem data: assume válida (não filtra)
            resultado.append(p)
            continue
        try:
            if isinstance(data_str, str):
                dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
            elif isinstance(data_str, datetime):
                dt = data_str
            else:
                resultado.append(p)
                continue

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            if (agora - dt) <= limite:
                resultado.append(p)
        except Exception:
            # Erro de parse: mantém a pauta
            resultado.append(p)

    return resultado


# ---------------------------------------------------------------------------
# HIDRATAÇÃO (texto + imagem)
# ---------------------------------------------------------------------------

async def _hidratar_pautas(
    pautas: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Extrai texto e imagem das pautas que estão incompletas."""
    min_chars = _env_int("URURAU_V111_GNEWS_MIN_CHARS_FONTE", 1200)
    max_conc = _env_int("URURAU_V111_MAX_CONCORRENCIA_HIDRATA", 3)
    semaphore = asyncio.Semaphore(max_conc)

    pautas_hidratadas = 0
    pautas_falhas = 0
    resultado = []

    async def _hidratar_uma(p: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal pautas_hidratadas, pautas_falhas
        async with semaphore:
            url = p.get("url")
            chars_atual = len(p.get("texto_fonte", "") or "")

            # Só hidrata se texto insuficiente OU sem imagem
            precisa_texto = chars_atual < min_chars
            precisa_imagem = not p.get("imagem") and os.environ.get("URURAU_V111_BUSCAR_IMAGEM_OG") == "1"

            if not precisa_texto and not precisa_imagem:
                return p

            try:
                extracao = await extrair_fonte_v111(url)
                if extracao.get("suficiente"):
                    p["texto_fonte"] = extracao["texto"]
                    p["chars_fonte"] = extracao["chars"]
                    p["metodo_extracao"] = extracao["metodo"]
                    pautas_hidratadas += 1
                    print(f"[V111.1][HIDRATA][OK] {extracao['chars']} chars via {extracao['metodo']}: {url[:60]}")
                else:
                    pautas_falhas += 1
                    print(f"[V111.1][HIDRATA][FALHA] Texto insuficiente ({extracao.get('chars', 0)} chars): {url[:60]}")

                # Imagem (se ainda não tem)
                if not p.get("imagem") and extracao.get("imagens"):
                    p["imagem"] = extracao["imagens"][0]
                    p["imagens"] = extracao["imagens"]

            except Exception as e:
                pautas_falhas += 1
                print(f"[V111.1][HIDRATA][ERRO] {e}: {url[:60]}")

            return p

    tasks = [_hidratar_uma(p) for p in pautas]
    resultado = await asyncio.gather(*tasks)

    print(f"[V111.1][HIDRATA] {pautas_hidratadas} OK, {pautas_falhas} falhas")
    return list(resultado)


# ---------------------------------------------------------------------------
# CAMPOS LEGADOS (compatibilidade com v100-v110)
# ---------------------------------------------------------------------------

def _garantir_campos_legados(p: Dict[str, Any]) -> None:
    """
    Preenche campos legados que o restante do robô espera.
    Isso garante que o monitor v100-v110 consiga processar a pauta.
    """
    # Mapeamentos diretos
    p.setdefault("titulo_origem", p.get("titulo", ""))
    p.setdefault("link_origem", p.get("url", ""))
    p.setdefault("resumo_origem", p.get("descricao", ""))
    p.setdefault("fonte_nome", p.get("fonte_nome", "Google News"))
    p.setdefault("fonte_id", p.get("fonte_id", "gnews_v111_1"))
    p.setdefault("canal_forcado", p.get("canal_sugerido", ""))
    p.setdefault("cleaned_source_text", p.get("texto_fonte", ""))
    p.setdefault("raw_source_text", p.get("texto_fonte", ""))
    p.setdefault("dossie", {})

    # Garante que score existe
    if "score" not in p:
        p["score"] = 50

    # Garante status
    p.setdefault("status", "pendente")


# ---------------------------------------------------------------------------
# MODO DRY-RUN (para testes sem publicar)
# ---------------------------------------------------------------------------

async def coletar_ciclo_combinado_dry_run(
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Mesmo que coletar_ciclo_combinado_v111, mas:
    - Não hidrata (não faz requisições externas)
    - Retorna pautas sem tentar extrair texto
    - Útil para testar configuração e grupos
    """
    print("[V111.1][DRY-RUN] Modo teste — sem requisicoes externas")

    # Desliga hidratacao temporariamente
    old_hidratar = os.environ.get("URURAU_V111_HIDRATAR_SEM_TEXTO")
    os.environ["URURAU_V111_HIDRATAR_SEM_TEXTO"] = "0"

    try:
        # Sobrescreve max para não estourar
        kwargs.setdefault("max_total", 10)
        kwargs.setdefault("max_por_grupo", 2)
        return await coletar_ciclo_combinado_v111(**kwargs)
    finally:
        if old_hidratar is not None:
            os.environ["URURAU_V111_HIDRATAR_SEM_TEXTO"] = old_hidratar
        else:
            os.environ.pop("URURAU_V111_HIDRATAR_SEM_TEXTO", None)
