"""
criterio_aceite_v90.py
Módulo de critérios de aceite editorial para conteúdo coletado (v90).
Avalia se um texto atinge os critérios mínimos para ser aceito como notícia válida.
"""

import logging
import re

logger = logging.getLogger(__name__)

def safe_get(obj, key, default=None):
    """Helper seguro para evitar AttributeError em dict.get()."""
    return obj.get(key, default) if isinstance(obj, dict) else default


def _contar_paragrafos_uteis(texto: str) -> int:
    """
    Conta parágrafos úteis: >= 60 caracteres, não repetitivos, não snippets.
    """
    if not texto or not isinstance(texto, str):
        return 0

    paragrafos = re.split(r"\n\s*\n|\r\n\s*\r\n|\n|\r\n", texto.strip())
    uteis = 0
    vistos = set()

    for par in paragrafos:
        par_limp = par.strip()
        if len(par_limp) < 60:
            continue
        if par_limp in vistos:
            continue
        if _parece_snippet(par_limp):
            continue
        vistos.add(par_limp)
        uteis += 1

    return uteis


def _contar_caracteres_uteis(texto: str) -> int:
    """
    Conta caracteres úteis excluindo snippets, repetidos e texto promocional óbvio.
    """
    if not texto or not isinstance(texto, str):
        return 0

    texto_limpo = re.sub(r"\s+", " ", texto.strip())
    paragrafos = re.split(r"(?<=\.)\s+(?=[A-Z])|(?<=\n)", texto_limpo)

    total = 0
    vistos = set()
    for par in paragrafos:
        par_limp = par.strip()
        if len(par_limp) < 20:
            continue
        if par_limp in vistos:
            continue
        if _parece_snippet(par_limp):
            continue
        vistos.add(par_limp)
        total += len(par_limp)

    return total


def _parece_snippet(paragrafo: str) -> bool:
    """Detecta se um parágrafo parece snippet/resumo genérico ou repetitivo."""
    padroes_snippet = [
        r"^Leia\s+(mais|tamb[ée]m)",
        r"^Confira\s+(tamb[ée]m|abaixo)",
        r"^Veja\s+(tamb[ée]m|abaixo)",
        r"^Saiba\s+mais",
        r"^Acompanhe",
        r"^Fique\s+por\s+dentro",
        r"^Continue\s+lendo",
        r"^Clique\s+aqui",
        r"^Assine",
        r"^Inscreva-se",
        r"^Receba\s+not[íi]cias",
        r"^Not[íi]cias\s+recomendadas",
        r"^Voc[êe]\s+pode\s+gostar",
        r"^Publicidade",
        r"^An[úu]ncio",
        r"^Propaganda",
        r"^Mais\s+lidas",
        r"^Trending",
        r"^Recommended",
        r"^Read\s+more",
        r"^See\s+also",
        r"^Related\s+articles",
    ]
    for padrao in padroes_snippet:
        if re.search(padrao, paragrafo, re.IGNORECASE):
            return True
    return False


def _detectar_bloqueios(texto: str) -> str:
    """
    Detecta textos indicativos de paywall, login ou CAPTCHA.
    Retorna o motivo do bloqueio ou string vazia se livre.
    """
    if not texto or not isinstance(texto, str):
        return ""

    padroes_paywall = [
        r"assine\s+para\s+continuar",
        r"content\s+behind\s+paywall",
        r"paywall",
        r"assinante",
        r"exclusivo\s+para\s+assinantes",
        r"fa[çc]a\s+login",
        r"entrar\s+com\s+sua\s+conta",
        r"cadastre-se\s+para\s+ler",
        r"verifique\s+que\s+voc[êe]\s+n[ãa]o\s+[ée]\s+um\s+rob[ôo]",
        r"captcha",
        r"recaptcha",
        r"g-recaptcha",
        r"desafio\s+de\s+seguran[çc]a",
        r"bloqueado\s+por\s+seguran[çc]a",
        r"sua\s+sess[ãa]o\s+expirou",
        r"autentica[çc][ãa]o\s+necess[áa]ria",
        r"[ée]\s+preciso\s+assinar",
    ]

    texto_lower = texto.lower()
    for padrao in padroes_paywall:
        if re.search(padrao, texto_lower):
            return f"paywall/login/captcha detectado (padrao: {padrao})"

    return ""


def _eh_promocional_sem_noticia(texto: str, titulo: str = "") -> str:
    """
    Detecta textos puramente promocionais sem conteúdo jornalístico.
    Retorna motivo ou string vazia.
    """
    if not texto or not isinstance(texto, str):
        return ""

    texto_lower = texto.lower()
    titulo_lower = titulo.lower() if titulo else ""

    # Verifica se é puramente promocional
    palavras_promo = [
        "compre agora", "promoção", "promocao", "oferta", "desconto",
        "black friday", "cupom", "cashback", "parcele em", "frete grátis",
        "leve 3 pague 2", " compre ", " adquira ", " garanta já",
    ]
    palavras_noticia = [
        "disse", "afirmou", "declarou", "segundo", "de acordo com",
        "polícia", "governo", "ministério", "tribunal", "decisão",
        "acidente", "morte", "nascimento", "pesquisa", "estudo",
        "entrevista", "coletiva", "pronunciamento", "projeto", "lei",
    ]

    score_promo = sum(1 for p in palavras_promo if p in texto_lower)
    score_noticia = sum(1 for n in palavras_noticia if n in texto_lower)

    # Se tem mais de 3 indicadores promocionais e nenhum de notícia
    if score_promo >= 3 and score_noticia == 0:
        return f"texto puramente promocional (indicadores: {score_promo})"

    # Se título é só chamada promocional e texto é curto
    titulo_promo = any(p.strip() in titulo_lower for p in [
        "promoção", "oferta", "desconto", "compre", "black friday", "cupom"
    ])
    if titulo_promo and len(texto) < 300:
        return "titulo e texto promocional sem conteudo jornalistico"

    return ""


def _eh_somente_resumo(texto: str) -> bool:
    """Detecta se o texto é apenas resumo/snippet sem conteúdo real."""
    if not texto or not isinstance(texto, str):
        return True

    texto_limpo = texto.strip()
    if len(texto_limpo) < 80:
        return True

    # Verifica se é uma única frase sem desenvolvimento
    frases = re.split(r"(?<=[.!?])\s+", texto_limpo)
    if len(frases) <= 1 and len(texto_limpo) < 150:
        return True

    # Verifica proporção de palavras-chave de resumo
    padroes_resumo = ["leia mais", "continue lendo", "saiba mais", "clique aqui",
                      "acesse", "leia na íntegra", "veja abaixo", "confira"]
    score_resumo = sum(1 for p in padroes_resumo if p in texto_limpo.lower())
    if score_resumo >= 2 and len(texto_limpo) < 200:
        return True

    return False


def avaliar_aceite_editorial_v90(
    titulo: str,
    texto: str,
    metodo: str = "",
    origem: str = ""
) -> dict:
    """
    Avalia se um texto atende aos critérios editoriais para aceite.

    Regras:
    - Título + 3 parágrafos úteis (60+ chars, não repetitivo, não snippet): aceita
    - 4 parágrafos úteis: aceita
    - 500+ caracteres úteis + 2 parágrafos úteis: aceita
    - Só título, só snippet RSS, só resumo Google News: bloqueia
    - Paywall/login/CAPTCHA detectado: bloqueia
    - Texto promocional sem notícia: bloqueia

    Retorna dict com:
        aceita (bool), motivo (str), paragrafos_uteis (int), chars_uteis (int)
    """
    logger.info("[v90][CRITERIO_ACEITE] Iniciando avaliacao: titulo=%r origem=%r metodo=%r",
                titulo[:80] if titulo else "", origem, metodo)

    # Normalização
    titulo = titulo.strip() if titulo and isinstance(titulo, str) else ""
    texto = texto.strip() if texto and isinstance(texto, str) else ""

    paragrafos_uteis = _contar_paragrafos_uteis(texto)
    chars_uteis = _contar_caracteres_uteis(texto)

    # --- BLOQUEIOS PRIORITÁRIOS ---

    # 1. Somente título ou resumo
    if not texto or len(texto) < 40:
        logger.warning("[v90][CRITERIO_ACEITE] Bloqueado: texto vazio ou muito curto (%d chars)", len(texto))
        return {
            "aceita": False,
            "motivo": "texto vazio ou muito curto (apenas titulo/snippet)",
            "paragrafos_uteis": paragrafos_uteis,
            "chars_uteis": chars_uteis,
        }

    # 2. Paywall / login / CAPTCHA (prioridade alta)
    bloqueio = _detectar_bloqueios(texto)
    if bloqueio:
        logger.warning("[v90][CRITERIO_ACEITE] Bloqueado: %s", bloqueio)
        return {
            "aceita": False,
            "motivo": f"bloqueio detectado: {bloqueio}",
            "paragrafos_uteis": paragrafos_uteis,
            "chars_uteis": chars_uteis,
        }

    # 3. Só resumo/snippet
    if _eh_somente_resumo(texto):
        logger.warning("[v90][CRITERIO_ACEITE] Bloqueado: texto eh apenas resumo/snippet")
        return {
            "aceita": False,
            "motivo": "texto eh apenas resumo/snippet sem conteudo real",
            "paragrafos_uteis": paragrafos_uteis,
            "chars_uteis": chars_uteis,
        }

    # 4. Texto promocional sem notícia
    bloqueio_promo = _eh_promocional_sem_noticia(texto, titulo)
    if bloqueio_promo:
        logger.warning("[v90][CRITERIO_ACEITE] Bloqueado: %s", bloqueio_promo)
        return {
            "aceita": False,
            "motivo": f"conteudo bloqueado: {bloqueio_promo}",
            "paragrafos_uteis": paragrafos_uteis,
            "chars_uteis": chars_uteis,
        }

    # --- CRITÉRIOS DE ACEITE ---

    # Regra 1: Título + 3 parágrafos úteis
    if titulo and paragrafos_uteis >= 3:
        logger.info("[v90][CRITERIO_ACEITE] Aceito: titulo + %d paragrafos uteis", paragrafos_uteis)
        return {
            "aceita": True,
            "motivo": f"titulo presente + {paragrafos_uteis} paragrafos uteis (>=60 chars)",
            "paragrafos_uteis": paragrafos_uteis,
            "chars_uteis": chars_uteis,
        }

    # Regra 2: 4 parágrafos úteis (mesmo sem título)
    if paragrafos_uteis >= 4:
        logger.info("[v90][CRITERIO_ACEITE] Aceito: %d paragrafos uteis", paragrafos_uteis)
        return {
            "aceita": True,
            "motivo": f"{paragrafos_uteis} paragrafos uteis (>=60 chars cada)",
            "paragrafos_uteis": paragrafos_uteis,
            "chars_uteis": chars_uteis,
        }

    # Regra 3: 500+ chars úteis + 2 parágrafos úteis
    if chars_uteis >= 500 and paragrafos_uteis >= 2:
        logger.info("[v90][CRITERIO_ACEITE] Aceito: %d chars uteis + %d paragrafos uteis",
                    chars_uteis, paragrafos_uteis)
        return {
            "aceita": True,
            "motivo": f"{chars_uteis} caracteres uteis + {paragrafos_uteis} paragrafos uteis",
            "paragrafos_uteis": paragrafos_uteis,
            "chars_uteis": chars_uteis,
        }

    # --- REJEIÇÃO FINAL ---
    motivo = (
        f"nao atende criterios minimos: "
        f"titulo={'sim' if titulo else 'nao'}, "
        f"paragrafos_uteis={paragrafos_uteis}, "
        f"chars_uteis={chars_uteis}"
    )
    logger.info("[v90][CRITERIO_ACEITE] Rejeitado: %s", motivo)
    return {
        "aceita": False,
        "motivo": motivo,
        "paragrafos_uteis": paragrafos_uteis,
        "chars_uteis": chars_uteis,
    }
