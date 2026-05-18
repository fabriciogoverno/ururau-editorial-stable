# -*- coding: utf-8 -*-
"""V200_62: Validador de atribuicao apuracao vs confirmacao oficial.

Resolve o caso classico em que a IA recebe um texto-fonte que e APURACAO
JORNALISTICA (colunista, programa, site apurou X) e transforma em
CONFIRMACAO OFICIAL ("X confirmou", "anunciou"), inventando autoridade
que nao esta na fonte.

Exemplo do bug capturado (pauta Neymar/Ancelotti, Band 18/05/2026):

  FONTE: "Ancelotti entrou em contato com o jogador para confirmar
          sua presenca na lista. A informacao foi divulgada por
          Leo Dias no Melhor da Tarde."

  IA GEROU: "Ancelotti confirmou nesta segunda-feira a convocacao
            de Neymar para a Copa do Mundo 2026."

  ERRO: a fonte e apuracao do Leo Dias. A IA omitiu a apuracao e
        afirmou como confirmacao direta do tecnico.

Logica:
  1. Detecta na FONTE marcadores de apuracao jornalistica (>= 1).
  2. Detecta na MATERIA marcadores de confirmacao oficial (>= 1).
  3. Detecta na MATERIA atribuicao a fonte/coluna ("segundo X
     publicou", "de acordo com a coluna", "a coluna informou").
  4. Se fonte=apuracao E materia=confirmacao E materia NAO atribui a
     fonte -> BLOQUEIO.
  5. Se fonte=apuracao E materia=confirmacao E materia ATRIBUI fonte
     parcialmente -> RASCUNHO (alerta).

Cobertura: funciona para QUALQUER materia. Padroes genericos.
"""
from __future__ import annotations
import re
import unicodedata


def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower()).strip()


# ── Padroes que indicam APURACAO JORNALISTICA na fonte ──────────────────────
# Cobrem: colunista, programa, site, rede, agencia, blog, fontes anonimas,
# reportagem propria, exclusividade.
_PADROES_APURACAO_FONTE = [
    r"\bfoi divulgad[ao] (?:por|pelo|pela)",
    r"\bsegundo apurou\b",
    r"\b(?:apurou|apuram|apurado por|a reportagem apurou)\b",
    r"\bsoube (?:com exclusividade|em primeira mao|a coluna)",
    r"\b(?:a coluna|o blog|o programa|o site|o portal|o jornal) (?:[a-zà-ÿ ]+ )?(?:publicou|revelou|informou|antecipou|adiantou|noticiou|divulgou|apurou|trouxe)\b",
    r"\b(?:de acordo com|conforme)(?:\s+a)?\s+(?:reportagem|publicacao|coluna|blog|programa|apuracao|fontes? ouvidas?)\b",
    r"\bfontes? ouvidas? (?:pel[oa]|por)",
    r"\b(?:soube|revelou|antecipou|adiantou|publicou em primeira mao|publicou primeiro)\b",
    r"\b(?:exclusiv[oa]|com exclusividade)\b",
    r"\b(?:teria|teriam) (?:dito|afirmado|comunicado|decidido|confirmado|anunciado|enviado)\b",
    r"\bsegun?do (?:colunistas?|colunista|fontes?|interlocutor(?:es)?|reportagem)\b",
    r"\bem (?:coluna|reportagem|texto|publicacao|blog|site) (?:do|da|de)",
    r"\b(?:informacao|noticia) (?:foi )?(?:antecipad[ao]|divulgad[ao]|publicad[ao]|trazid[ao]) (?:por|pel[oa])",
    r"\b(?:apurou-se|sabe-se que)\b",
]

# ── Padroes que indicam CONFIRMACAO OFICIAL na materia ──────────────────────
# Verbos/expressoes que afirmam ato oficial direto.
_PADROES_CONFIRMACAO_MATERIA = [
    r"\bconfirmou (?:que |a |o |sua |seu |em |nesta|nesse|para)",
    r"\b(?:anunciou (?:oficialmente|formalmente|publicamente)|anunciou em|anunciou que)",
    r"\b(?:oficializou|formalizou|comunicou oficialmente)",
    r"\b(?:decidiu (?:que|por|nomear|convocar|publicar)|decretou|sancionou|promulgou)",
    r"\b(?:declarou em entrevista|em declaracao oficial|em pronunciamento oficial)",
    r"\bfoi (?:oficializad[ao]|confirmad[ao] oficialmente|anunciad[ao] oficialmente)",
    r"\b(?:est[aá]) (?:oficializad[oa]|confirmad[oa] oficialmente)",
    r"\b(?:divulgou (?:nesta|nesse|hoje|ontem) (?:a |o |em ))(?!.*coluna|.*blog|.*programa|.*site)",
    r"\b(?:representa (?:o fim|a confirmacao oficial))",
    r"\b(?:encerra (?:as duvidas|o periodo de incertezas|as especulacoes))",
]

# ── Padroes que indicam ATRIBUICAO A FONTE de apuracao na materia ───────────
# Quando presente, "absolve" o uso de verbos de confirmacao porque ficou
# claro que a informacao veio de apuracao.
_PADROES_ATRIBUICAO_VALIDA_MATERIA = [
    r"\bsegundo (?:apurou|apuracao|reportagem|publicacao|coluna|colunista|blog|programa|site|portal|jornal|fontes?)",
    r"\b(?:de acordo|conforme) (?:com )?(?:a |o )?(?:reportagem|publicacao|coluna|colunista|blog|programa|site|portal|jornal|apuracao|fontes?)",
    r"\b(?:a coluna|o blog|o programa|o site|o portal|o jornal) (?:[a-zà-ÿ ]+ )?(?:publicou|revelou|informou|antecipou|adiantou|noticiou|apurou|trouxe|divulgou)\b",
    r"\b(?:em informacao (?:publicada|divulgada|noticiada|antecipada|trazida) (?:por|pel[ao]))",
    r"\b(?:em (?:reportagem|coluna|texto|publicacao|blog|programa) (?:do|da|de))",
    r"\b(?:apurou-se|sabe-se|reportagem apurou|fontes? ouvidas?)",
    r"\b(?:de acordo com (?:apuracao|fontes?))",
    r"\b(?:teria|teriam) (?:dito|afirmado|comunicado|decidido|confirmado|anunciado)\b",
    r"\b(?:foi divulgad[ao] (?:por|pelo|pela))",
    r"\b(?:noticiou|publicou|revelou|antecipou|adiantou)(?: que| em| no| na)\b",
]


def _conta_padroes(texto: str, padroes: list[str]) -> tuple[int, list[str]]:
    """Conta quantos padroes batem no texto. Retorna (n, lista_exemplos)."""
    t = _norm(texto)
    n = 0
    achados: list[str] = []
    for p in padroes:
        try:
            m = re.search(p, t, re.I)
            if m:
                n += 1
                achados.append(m.group(0))
        except Exception:
            continue
    return n, achados


def validar_atribuicao_apuracao(texto_fonte: str, materia: dict | object) -> dict:
    """Valida se a materia gerada preserva o carater de apuracao da fonte.

    Args:
        texto_fonte: texto-fonte original.
        materia: dict ou objeto com campos `corpo_materia` / `conteudo`,
                 `titulo` / `titulo_seo`, `subtitulo`.

    Returns:
        {
          "status": "OK" | "ALERTA" | "BLOQUEIO",
          "motivo": str,
          "evidencias_fonte": [str, ...],    # marcadores apuracao
          "evidencias_materia": [str, ...],  # marcadores confirmacao
          "atribuicoes_materia": [str, ...], # padroes que "absolvem"
          "score": int,                      # 0-100
        }
    """
    # Coleta texto da materia
    def _g(obj, k, d=""):
        if isinstance(obj, dict):
            return str(obj.get(k, d) or "")
        return str(getattr(obj, k, d) or "")

    corpo = _g(materia, "corpo_materia") or _g(materia, "conteudo")
    titulo = _g(materia, "titulo_seo") or _g(materia, "titulo")
    subt = _g(materia, "subtitulo_curto") or _g(materia, "subtitulo")
    texto_materia = "\n".join([titulo, subt, corpo]).strip()

    if not texto_fonte or not texto_materia:
        return {"status": "OK", "motivo": "texto vazio - skip",
                "evidencias_fonte": [], "evidencias_materia": [],
                "atribuicoes_materia": [], "score": 100}

    # 1. Detecta apuracao na fonte
    n_ap, ev_ap = _conta_padroes(texto_fonte, _PADROES_APURACAO_FONTE)

    # 2. Detecta confirmacao na materia
    n_conf, ev_conf = _conta_padroes(texto_materia, _PADROES_CONFIRMACAO_MATERIA)

    # 3. Detecta atribuicoes validas na materia
    n_atrib, ev_atrib = _conta_padroes(texto_materia, _PADROES_ATRIBUICAO_VALIDA_MATERIA)

    # 4. Decisao
    score = 100
    if n_ap == 0:
        # Fonte nao e apuracao - nao tem como inventar oficialidade.
        return {"status": "OK", "motivo": "fonte nao indica apuracao",
                "evidencias_fonte": [], "evidencias_materia": ev_conf,
                "atribuicoes_materia": ev_atrib, "score": 100}

    # Fonte E apuracao
    if n_conf == 0:
        # Materia nao usa verbo de confirmacao oficial - OK
        return {"status": "OK", "motivo": "materia nao trata como confirmacao oficial",
                "evidencias_fonte": ev_ap, "evidencias_materia": [],
                "atribuicoes_materia": ev_atrib, "score": 100}

    # Fonte=apuracao + materia=confirmacao
    if n_atrib >= 1:
        # Tem atribuicao valida - reduz gravidade
        score -= 20 * max(1, n_conf - n_atrib)
        if n_atrib >= n_conf:
            # Atribuicoes cobrem todas as confirmacoes
            return {"status": "OK", "motivo": "materia preserva atribuicao a fonte de apuracao",
                    "evidencias_fonte": ev_ap, "evidencias_materia": ev_conf,
                    "atribuicoes_materia": ev_atrib, "score": max(60, score)}
        return {"status": "ALERTA",
                "motivo": f"materia tem {n_conf} verbo(s) de confirmacao mas so {n_atrib} atribuicao(oes) a fonte de apuracao",
                "evidencias_fonte": ev_ap, "evidencias_materia": ev_conf,
                "atribuicoes_materia": ev_atrib, "score": max(40, score)}

    # Pior caso: fonte=apuracao, materia=confirmacao, ZERO atribuicao
    score = max(0, 100 - 30 * n_conf - 10 * n_ap)
    return {
        "status": "BLOQUEIO",
        "motivo": (f"FONTE e apuracao jornalistica ({n_ap} marcadores: {ev_ap[:2]}) "
                   f"mas materia trata como confirmacao oficial direta "
                   f"({n_conf} verbos: {ev_conf[:2]}) SEM atribuir a fonte de apuracao. "
                   f"Spec sec.22-23: atribuir corretamente."),
        "evidencias_fonte": ev_ap,
        "evidencias_materia": ev_conf,
        "atribuicoes_materia": ev_atrib,
        "score": score,
    }


__all__ = ["validar_atribuicao_apuracao"]
