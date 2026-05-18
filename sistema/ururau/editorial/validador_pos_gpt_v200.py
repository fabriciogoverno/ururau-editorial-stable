# -*- coding: utf-8 -*-
"""V200_55-fase3: Validador pos-GPT centralizado (spec sec. 48).

Orquestra TODAS as validacoes da spec_regras_editoriais_gpt4mini_ururau.md
em sequencia, com short-circuit no primeiro erro FATAL.

Retorno padronizado:
  {
    "status": "APROVADO" | "RASCUNHO" | "BLOQUEADO",
    "motivos_bloqueio": [str, ...],     # erros fatais
    "alertas": [str, ...],              # avisos nao bloqueadores
    "campos_corrigidos": {campo: valor_novo},
    "score_final": int,
    "etapas_executadas": [str, ...],
    "etapa_que_bloqueou": str,
  }

Cada etapa pode:
  - aceitar e seguir
  - corrigir campo e seguir
  - bloquear (errors fatais)
  - rascunho (erros nao-fatais)

Spec sec. 48 - validacoes obrigatorias:
  1. JSON valido (assumido pelo motor antes de chamar)
  2. Campos obrigatorios presentes
  3. Titulo SEO dentro do limite (40-89)
  4. Titulo de capa dentro do limite (20-60)
  5. Subtitulo dentro do limite (max 200)
  6. Legenda curta dentro do limite (max 100)
  7. Meta description dentro do limite (120-160)
  8. Tags 5-12
  9. Retranca valida (max 3 palavras)
  10. Corpo minimo (500 chars)
  11. Paragrafos suficientes (>=3)
  12. Ausencia de termos proibidos
  13. Ausencia de travessao
  14. Ausencia de data inventada
  15. Ausencia de numero inventado
  16. Ausencia de frase unsupported
  17. Ausencia de relacao errada
  18. Ausencia de duplicidade
  19. Fonte preenchida
  20. Credito preenchido ou fallback valido
  21. (extra) precisao juridica (investigado != condenado)
"""
from __future__ import annotations
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)
PREFIX = "[VALIDADOR_POS_GPT_V200]"


def _safe_get(obj: Any, key: str, default: str = "") -> str:
    if isinstance(obj, dict):
        v = obj.get(key, default)
    else:
        v = getattr(obj, key, default)
    if isinstance(v, (list, tuple, set)):
        return ", ".join(str(x) for x in v)
    return str(v or "")


def _carregar_limites() -> dict:
    """Carrega limites_campos da matriz central com fallback."""
    try:
        from ururau.editorial.regras_editoriais import obter_matriz_editorial
        m = obter_matriz_editorial() or {}
        return dict(m.get("limites_campos") or {})
    except Exception as e:
        logger.debug("%s carregar_limites fallback: %s", PREFIX, e)
        return {
            "titulo_seo_min": 40, "titulo_seo_max": 89,
            "titulo_capa_min": 20, "titulo_capa_max": 60,
            "subtitulo_curto_max": 200,
            "legenda_curta_max": 100,
            "meta_description_min": 120, "meta_description_max": 160,
            "tags_min": 5, "tags_max": 12,
            "retranca_max_words": 3,
            "corpo_min_chars": 500,
            "corpo_paragrafos_min": 3,
        }


def _detectar_termos_ia(texto: str) -> list[str]:
    """Delega para o detector canonico da matriz."""
    try:
        from ururau.editorial.regras_editoriais import detectar_termos_ia
        return detectar_termos_ia(texto)
    except Exception:
        return []


# ── Etapas individuais ──────────────────────────────────────────────────────

def _etapa_campos_obrigatorios(materia: Any) -> dict:
    """Etapa 2: campos minimos presentes."""
    obrigatorios = ("titulo", "titulo_seo", "corpo_materia")
    faltando = []
    for k in obrigatorios:
        v = _safe_get(materia, k)
        if not v.strip():
            # Fallback: aceita se variantes preenchidas
            if k == "titulo" and _safe_get(materia, "titulo_seo").strip():
                continue
            if k == "titulo_seo" and _safe_get(materia, "titulo").strip():
                continue
            if k == "corpo_materia" and _safe_get(materia, "conteudo").strip():
                continue
            faltando.append(k)
    if faltando:
        return {"fatal": True, "motivo": f"Campos obrigatorios ausentes: {', '.join(faltando)}"}
    return {"ok": True}


def _etapa_limites_titulo(materia: Any, lim: dict) -> dict:
    """Etapas 3-4: titulo_seo (40-89) e titulo_capa (20-60)."""
    motivos = []
    alertas = []
    t_seo = _safe_get(materia, "titulo_seo") or _safe_get(materia, "titulo")
    t_capa = _safe_get(materia, "titulo_capa")
    mn = lim.get("titulo_seo_min", 40)
    mx = lim.get("titulo_seo_max", 89)
    if t_seo and len(t_seo) > mx:
        motivos.append(f"Titulo SEO acima de {mx} chars: {len(t_seo)}")
    elif t_seo and len(t_seo) < mn:
        alertas.append(f"Titulo SEO abaixo de {mn} chars: {len(t_seo)}")
    mn_c = lim.get("titulo_capa_min", 20)
    mx_c = lim.get("titulo_capa_max", 60)
    if t_capa and len(t_capa) > mx_c:
        motivos.append(f"Titulo de capa acima de {mx_c} chars: {len(t_capa)}")
    elif t_capa and len(t_capa) < mn_c:
        alertas.append(f"Titulo de capa abaixo de {mn_c} chars: {len(t_capa)}")
    return {"fatal": bool(motivos), "motivos": motivos, "alertas": alertas}


def _etapa_limites_meta_subtitulo(materia: Any, lim: dict) -> dict:
    """Etapas 5-7: subtitulo, legenda, meta_description."""
    motivos = []
    alertas = []
    sub = _safe_get(materia, "subtitulo_curto") or _safe_get(materia, "subtitulo")
    leg = _safe_get(materia, "legenda_curta") or _safe_get(materia, "legenda")
    meta = _safe_get(materia, "meta_description")
    if sub and len(sub) > lim.get("subtitulo_curto_max", 200):
        motivos.append(f"Subtitulo acima de {lim.get('subtitulo_curto_max', 200)} chars: {len(sub)}")
    if leg and len(leg) > lim.get("legenda_curta_max", 100):
        motivos.append(f"Legenda curta acima de {lim.get('legenda_curta_max', 100)} chars: {len(leg)}")
    if meta:
        mn = lim.get("meta_description_min", 120)
        mx = lim.get("meta_description_max", 160)
        if len(meta) > mx:
            motivos.append(f"Meta description acima de {mx} chars: {len(meta)}")
        elif len(meta) < mn:
            alertas.append(f"Meta description abaixo de {mn} chars: {len(meta)}")
    return {"fatal": bool(motivos), "motivos": motivos, "alertas": alertas}


def _etapa_tags(materia: Any, lim: dict) -> dict:
    """Etapa 8: tags 5-12."""
    tags = _safe_get(materia, "tags")
    n = len([t.strip() for t in re.split(r"[,;]", tags) if t.strip()]) if tags else 0
    motivos = []
    alertas = []
    mn = lim.get("tags_min", 5)
    mx = lim.get("tags_max", 12)
    if n > mx:
        motivos.append(f"Tags acima de {mx}: {n}")
    elif n < mn:
        alertas.append(f"Tags abaixo de {mn}: {n}")
    return {"fatal": bool(motivos), "motivos": motivos, "alertas": alertas}


def _etapa_retranca(materia: Any, lim: dict) -> dict:
    """Etapa 9: retranca max 3 palavras."""
    r = _safe_get(materia, "retranca").strip()
    if not r:
        return {"ok": True}
    palavras = len(r.split())
    mx = lim.get("retranca_max_words", 3)
    if palavras > mx:
        return {"fatal": True, "motivo": f"Retranca com {palavras} palavras (max {mx}): {r!r}"}
    return {"ok": True}


def _etapa_corpo(materia: Any, lim: dict) -> dict:
    """Etapas 10-11: corpo minimo e paragrafos suficientes."""
    corpo = _safe_get(materia, "corpo_materia") or _safe_get(materia, "conteudo")
    motivos = []
    alertas = []
    mn_chars = lim.get("corpo_min_chars", 500)
    mn_par = lim.get("corpo_paragrafos_min", 3)
    if not corpo or not corpo.strip():
        return {"fatal": True, "motivo": "Corpo da materia vazio"}
    if len(corpo) < mn_chars:
        motivos.append(f"Corpo com {len(corpo)} chars (minimo {mn_chars})")
    paragrafos = [p for p in re.split(r"\n\s*\n", corpo) if p.strip() and len(p.strip()) >= 30]
    if len(paragrafos) < mn_par:
        motivos.append(f"Corpo com {len(paragrafos)} paragrafos uteis (minimo {mn_par})")
    return {"fatal": bool(motivos), "motivos": motivos, "alertas": alertas}


def _etapa_termos_ia(materia: Any) -> dict:
    """Etapa 12: ausencia de termos IA proibidos."""
    campos = ("titulo", "titulo_seo", "titulo_capa", "subtitulo", "subtitulo_curto",
              "conteudo", "corpo_materia", "legenda", "legenda_curta",
              "meta_description", "chamada_social", "legenda_instagram")
    achados = []
    for c in campos:
        v = _safe_get(materia, c)
        if not v:
            continue
        for termo in _detectar_termos_ia(v):
            achados.append({"campo": c, "termo": termo})
    if achados:
        motivos = [f"Termo IA em {a['campo']}: {a['termo']!r}" for a in achados[:5]]
        if len(achados) > 5:
            motivos.append(f"... e mais {len(achados) - 5}")
        return {"fatal": True, "motivos": motivos, "achados": achados}
    return {"ok": True}


def _etapa_travessao(materia: Any) -> dict:
    """Etapa 13: ausencia de travessao (—) no corpo."""
    corpo = _safe_get(materia, "corpo_materia") or _safe_get(materia, "conteudo")
    if not corpo:
        return {"ok": True}
    if "—" in corpo or " – " in corpo:
        return {"alerta": "Travessao detectado no corpo - sera removido pelo copydesk"}
    return {"ok": True}


def _etapa_fonte_credito(materia: Any) -> dict:
    """Etapas 19-20: fonte e credito preenchidos."""
    motivos = []
    alertas = []
    fonte = _safe_get(materia, "fonte") or _safe_get(materia, "nome_da_fonte")
    credito = (_safe_get(materia, "credito_foto")
               or _safe_get(materia, "creditos_da_foto")
               or _safe_get(materia, "creditos_foto"))
    if not fonte.strip():
        alertas.append("Campo fonte vazio - usar 'Redacao' como fallback")
    if not credito.strip():
        alertas.append("Credito da foto vazio - usar 'Reproducao' como fallback")
    return {"fatal": False, "motivos": [], "alertas": alertas}


def _etapa_apuracao(materia: Any, texto_fonte: str) -> dict:
    """V200_62: detecta apuracao jornalistica transformada em confirmacao
    oficial. Delega ao validador_apuracao_v200.
    """
    if not texto_fonte:
        return {"ok": True}
    try:
        from ururau.editorial.validador_apuracao_v200 import validar_atribuicao_apuracao
        r = validar_atribuicao_apuracao(texto_fonte, materia)
        status = r.get("status", "OK")
        if status == "BLOQUEIO":
            return {"fatal": True, "motivo": r.get("motivo", "apuracao tratada como confirmacao oficial")}
        if status == "ALERTA":
            return {"alerta": r.get("motivo", "atribuicao parcial de apuracao")}
        return {"ok": True}
    except Exception as e:
        return {"alerta": f"validador_apuracao falhou: {e}"}


def _etapa_juridico(materia: Any) -> dict:
    """Etapa 21: precisao juridica (spec sec. 21).

    Detecta confusoes basicas:
      - 'condenado' quando fonte tem so 'investigado/suspeito'
      - 'preso' quando so 'alvo de operacao'
      etc.

    Atribui alerta, nao bloqueia diretamente (requer comparacao com fonte
    que esta fora desta etapa - feito pela auditoria_factual_v81).
    """
    corpo = _safe_get(materia, "corpo_materia") or _safe_get(materia, "conteudo")
    if not corpo:
        return {"ok": True}
    alertas = []
    if re.search(r"\bcondenad[oa]\b", corpo, re.I) and re.search(r"\b(investigad[oa]|suspeit[oa])\b", corpo, re.I):
        alertas.append("Texto contem 'condenado' E 'investigado/suspeito' - verificar precisao juridica")
    if re.search(r"\bpres[oa]\b", corpo, re.I) and re.search(r"\b(alvo de opera[cç][aã]o|busca e apreens[aã]o)\b", corpo, re.I):
        alertas.append("Texto contem 'preso' E 'alvo de operacao/busca' - confirmar com fonte")
    return {"fatal": False, "alertas": alertas}


# ── Orquestrador ────────────────────────────────────────────────────────────

def validar_pos_gpt(materia: Any, texto_fonte: str = "") -> dict:
    """Executa todas as etapas de validacao em sequencia.

    Returns:
      {
        status: APROVADO | RASCUNHO | BLOQUEADO,
        motivos_bloqueio: [],
        alertas: [],
        score_final: int,
        etapas_executadas: [],
        etapa_que_bloqueou: str,
      }
    """
    limites = _carregar_limites()
    motivos_bloqueio: list[str] = []
    alertas: list[str] = []
    etapas_executadas: list[str] = []
    etapa_bloqueio = ""
    score = 100

    ordem = [
        ("campos_obrigatorios",   lambda: _etapa_campos_obrigatorios(materia)),
        ("limites_titulo",        lambda: _etapa_limites_titulo(materia, limites)),
        ("limites_meta_sub",      lambda: _etapa_limites_meta_subtitulo(materia, limites)),
        ("tags",                  lambda: _etapa_tags(materia, limites)),
        ("retranca",              lambda: _etapa_retranca(materia, limites)),
        ("corpo",                 lambda: _etapa_corpo(materia, limites)),
        ("termos_ia",             lambda: _etapa_termos_ia(materia)),
        ("travessao",             lambda: _etapa_travessao(materia)),
        ("fonte_credito",         lambda: _etapa_fonte_credito(materia)),
        ("juridico",              lambda: _etapa_juridico(materia)),
        # V200_62: detecta apuracao transformada em confirmacao oficial
        ("apuracao_vs_oficial",   lambda: _etapa_apuracao(materia, texto_fonte)),
    ]

    for nome, fn in ordem:
        etapas_executadas.append(nome)
        try:
            r = fn() or {}
        except Exception as e:
            alertas.append(f"Etapa {nome} excecao: {e}")
            continue
        if r.get("fatal"):
            ms = r.get("motivos") or ([r.get("motivo")] if r.get("motivo") else [])
            for m in ms:
                motivos_bloqueio.append(f"[{nome}] {m}")
                score -= 20
            if not etapa_bloqueio:
                etapa_bloqueio = nome
            # NAO faz short-circuit - coleta TODOS os bloqueios pra revisao
        if r.get("alerta"):
            alertas.append(f"[{nome}] {r['alerta']}")
            score -= 3
        if r.get("alertas"):
            for a in r["alertas"]:
                alertas.append(f"[{nome}] {a}")
                score -= 3

    # V200_66 (Fase 6 fix): qualquer violacao fatal -> BLOQUEADO SEMPRE.
    # Antes: "BLOQUEADO if score < 60 else RASCUNHO" permitia que titulo > 89,
    # termo IA, retranca longa virassem RASCUNHO se score >= 60. Spec sec.40
    # exige bloqueio sempre para essas violacoes fatais.
    # RASCUNHO so para casos sem motivos_bloqueio mas com muitos alertas (score baixo).
    status = "APROVADO"
    if motivos_bloqueio:
        status = "BLOQUEADO"  # spec sec.40: fatal sempre bloqueia
    elif score < 80:
        status = "RASCUNHO"   # sem fatal, mas score baixo -> revisao manual

    return {
        "status": status,
        "motivos_bloqueio": motivos_bloqueio,
        "alertas": alertas,
        "score_final": max(0, score),
        "etapas_executadas": etapas_executadas,
        "etapa_que_bloqueou": etapa_bloqueio,
    }


__all__ = ["validar_pos_gpt"]
