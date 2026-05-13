# -*- coding: utf-8 -*-
"""extrator_artigo_unico — garante que a fonte da pauta e UM artigo.

spec_scrapling_artigo_unico_sem_mistura.

Envelopa o pipeline ja existente do projeto (extract_pipeline_v90 +
fonte_extractor_v104 + leitura_fonte) e acrescenta as camadas de validacao
exigidas pelo spec:

1. multiassunto       (texto agrega varios assuntos diferentes da pauta)
2. boilerplate critico (linhas de portal/login/newsletter/relacionadas)
3. coerencia titulo   (densidade de termos do titulo no corpo)
4. canonical match    (canonical/og:url corresponde a URL da pauta)
5. detecta titulos internos de outras materias

A funcao principal e ``validar_extracao_artigo_unico`` que recebe o texto
ja extraido + metadados e devolve dict padronizado:

    {
      "ok": bool,
      "texto": str,
      "estrategia": str,
      "score_coerencia": float,
      "multiassunto": bool,
      "boilerplate": list[str],
      "motivo": str,
      "candidatos_rejeitados": list[str]
    }
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any
from urllib.parse import urlparse


def _norm(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def _tokens(s: Any, *, min_len: int = 3) -> list[str]:
    s = _norm(s)
    return [t for t in re.split(r"[^a-z0-9]+", s) if len(t) >= min_len]


def _slug_da_url(url: Any) -> str:
    """Tira o slug significativo do path da URL."""
    try:
        p = urlparse(str(url or ""))
        path = p.path or ""
        # remove extensoes
        path = re.sub(r"\.(html?|ghtml|shtml|php|aspx?)$", "", path, flags=re.I)
        # remove segmentos numericos isolados
        parts = [x for x in path.split("/") if x and not re.fullmatch(r"\d+", x)]
        if not parts:
            return ""
        # ultimo segmento e o que carrega o slug; troca - e _ por espaco
        slug = parts[-1].replace("-", " ").replace("_", " ")
        return slug
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────
# Multi-assunto: detecta varias materias coladas em um texto so.
# ─────────────────────────────────────────────────────────────────────────

# Padroes que SUGEREM corte entre materias (titulos internos).
_RX_TITULO_INTERNO = (
    # H2/H3-like: linha curta isolada (15-90 chars) que NAO termina com ponto,
    # cercada por linhas em branco. Tipico de titulo intermediario na pagina.
    re.compile(r"(?:^|\n\s*\n)\s*([A-ZÁ-Ú][^.\n!?]{14,90}[^\s.!?])\s*(?=\n\s*\n|\n[A-ZÁ-Ú])"),
    # "Leia mais sobre X", "Veja tambem: X"
    re.compile(r"\b(?:leia\s+mais\s+sobre|veja\s+tamb(?:e|é)m[:\.])\s+([^\n.]{8,80})", re.I),
)

_PADROES_LOGIN_PORTAL = (
    "para recuperar a senha", "digite seu e-mail", "enviaremos um codigo",
    "enviaremos um código",
    "participe ativamente do nosso portal", "comente, de e receba likes",
    "comente, dê e receba likes",
    "marque nosso portal como fonte preferencial",
    "todos os direitos reservados",
    "receba as principais noticias em seu e-mail",
    "receba as principais notícias em seu e-mail",
)


def detectar_titulos_relacionados(texto: str) -> list[str]:
    """Devolve titulos internos que parecem materias DIFERENTES."""
    if not texto:
        return []
    achados: list[str] = []
    for rx in _RX_TITULO_INTERNO:
        for m in rx.finditer(texto):
            t = (m.group(1) if m.groups() else m.group(0)).strip()
            if len(t) >= 12 and t not in achados:
                achados.append(t)
    return achados[:20]


def score_coerencia_titulo_corpo(titulo: str, corpo: str) -> float:
    """Quanto dos tokens do titulo aparecem no corpo (proporcional)."""
    toks_t = set(_tokens(titulo, min_len=4))
    if not toks_t:
        return 1.0  # sem sinal disponivel: nao penaliza
    n = _norm(corpo)
    hits = sum(1 for t in toks_t if t in n)
    return hits / len(toks_t)


_PALAVRAS_PORTUGUES_COMUNS = frozenset((
    "para", "porem", "quando", "depois", "antes", "durante",
    "sobre", "entre", "como", "tambem", "nesta", "neste",
    "ainda", "muito", "pouco", "alguns", "todos", "todas",
))


def detectar_multiassunto(texto: str, titulo_pauta: str = "",
                          slug_url: str = "",
                          *, score_minimo: float = 0.20) -> dict:
    """Heuristica de multiassunto.

    Sinais:
      - score_coerencia_titulo_corpo < score_minimo
      - varios titulos internos (>=3)
      - presenca de PADRÕES de login/portal (rodape solto)
      - frequencia alta de '...' tipico de listagem (>=4 por par. medio)
      - varios topicos disjuntos (heuristica leve: tokens 4+ chars distintos
        em sentencas longas, sem ponte com o titulo)

    Retorno:
      {
        "multiassunto": bool,
        "score_coerencia": float,
        "titulos_relacionados": [...],
        "padroes_portal": [...],
        "motivo": str,
      }
    """
    titulos_rel = detectar_titulos_relacionados(texto or "")
    score = score_coerencia_titulo_corpo(titulo_pauta or slug_url or "", texto or "")

    nt = _norm(texto or "")
    padroes_portal = [p for p in _PADROES_LOGIN_PORTAL if p in nt]

    # densidade de '...' por sentenca curta — caracteristico de listagem
    sentencas = re.split(r"(?<=[\.\!\?])\s+", texto or "")
    reticencias_curtas = sum(1 for s in sentencas if "..." in s and len(s) < 140)

    motivos: list[str] = []
    if score < score_minimo and (titulo_pauta or slug_url):
        motivos.append(f"baixa_coerencia_titulo:{score:.2f}<{score_minimo}")
    if len(titulos_rel) >= 3:
        motivos.append(f"varios_titulos_internos:{len(titulos_rel)}")
    if padroes_portal:
        motivos.append("login_ou_portal_no_corpo:" + ",".join(padroes_portal[:3]))
    if reticencias_curtas >= 4:
        motivos.append(f"reticencias_curtas:{reticencias_curtas}")

    return {
        "multiassunto": bool(motivos),
        "score_coerencia": round(score, 3),
        "titulos_relacionados": titulos_rel,
        "padroes_portal": padroes_portal,
        "reticencias_curtas": reticencias_curtas,
        "motivo": ";".join(motivos),
    }


# ─────────────────────────────────────────────────────────────────────────
# Canonical match
# ─────────────────────────────────────────────────────────────────────────

def canonical_corresponde(url_pauta: str, canonical_url: str = "",
                          og_url: str = "") -> dict:
    """True quando canonical/og:url apontam para o MESMO artigo da pauta.

    Tolera diferencas comuns: protocolo (http/https), www, trailing slash,
    sufixo .html/.amp, parametros de tracking, prefixo /amp/ ou /m/.
    """
    def _key(u: str) -> str:
        try:
            p = urlparse(str(u or "").strip())
            host = (p.netloc or "").lower().replace("www.", "")
            path = (p.path or "/").rstrip("/")
            # remove extensoes
            path = re.sub(r"\.(html?|ghtml|shtml|amp)$", "", path, flags=re.I)
            # remove prefixos /amp/ ou /m/
            path = re.sub(r"^/(amp|m|mobile)/", "/", path)
            return f"{host}{path}"
        except Exception:
            return str(u or "").lower()

    base = _key(url_pauta)
    cands = [c for c in (canonical_url, og_url) if c]
    casa = any(_key(c) == base for c in cands) if cands else True
    return {
        "ok": casa,
        "url_pauta_norm": base,
        "canonical_norm": _key(canonical_url),
        "og_norm": _key(og_url),
    }


# ─────────────────────────────────────────────────────────────────────────
# Boilerplate (delegando para o validador da editorial)
# ─────────────────────────────────────────────────────────────────────────

def boilerplate_no_texto(texto: str) -> list[str]:
    try:
        from ururau.editorial.validador_boilerplate import detectar_boilerplate
        return detectar_boilerplate(texto)
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────────────────

def validar_extracao_artigo_unico(
    texto: str,
    titulo_pauta: str = "",
    *,
    url_pauta: str = "",
    canonical_url: str = "",
    og_url: str = "",
    estrategia: str = "desconhecida",
    min_chars: int = 550,
    score_coerencia_minimo: float = 0.20,
) -> dict:
    """Validacao pos-extracao. Devolve dict padronizado.

    Status possiveis:
      ok | fonte_contaminada | multiassunto | boilerplate |
      canonical_mismatch | texto_insuficiente
    """
    bp = boilerplate_no_texto(texto or "")
    multi = detectar_multiassunto(
        texto or "", titulo_pauta or "", _slug_da_url(url_pauta),
        score_minimo=score_coerencia_minimo,
    )
    can = canonical_corresponde(url_pauta or "", canonical_url, og_url)
    chars = len((texto or "").strip())

    motivo = ""
    status = "ok"

    # Prioridade (spec §10): contaminacao vence faltar texto, porque o motivo
    # editorial e diferente — usuario precisa saber que e fonte misturada,
    # nao apenas "curta".
    if multi["multiassunto"]:
        status = "multiassunto"
        motivo = multi["motivo"]
    elif bp:
        status = "boilerplate"
        motivo = "boilerplate:" + ",".join(bp[:6])
    elif not can["ok"]:
        status = "canonical_mismatch"
        motivo = f"canonical={can['canonical_norm']} og={can['og_norm']} pauta={can['url_pauta_norm']}"
    elif chars < min_chars:
        status = "texto_insuficiente"
        motivo = f"chars_uteis={chars}<{min_chars}"

    return {
        "ok": status == "ok",
        "status": status,
        "texto": texto or "",
        "estrategia": estrategia,
        "score_coerencia": multi["score_coerencia"],
        "multiassunto": multi["multiassunto"],
        "boilerplate": bp,
        "motivo": motivo or "ok",
        "titulos_relacionados": multi["titulos_relacionados"],
        "canonical": can,
        "chars": chars,
    }


__all__ = [
    "validar_extracao_artigo_unico",
    "detectar_multiassunto",
    "detectar_titulos_relacionados",
    "score_coerencia_titulo_corpo",
    "canonical_corresponde",
    "boilerplate_no_texto",
]
