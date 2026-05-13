# -*- coding: utf-8 -*-
"""validador_boilerplate — detecta e remove lixo de site na fonte.

spec_auditoria_global_linha_editorial_ururau §12.

A solucao e GERAL, nao baseada em um unico site. Detecta padroes universais
de interface, login, newsletter, publicidade, blocos relacionados, rodape,
datas-de-atualizacao soltas, "leia tambem", "compartilhe", politica de
cookies, termos de uso, etc.

API:

    limpar_boilerplate_fonte(texto)      -> dict {'texto_limpo','removidos','padroes'}
    detectar_boilerplate(texto)          -> list[str]   # blocos suspeitos
    fonte_tem_boilerplate_critico(texto) -> bool        # se SIM, Redigir bloqueia
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


# Padroes que indicam linha INTEIRA de boilerplate (qualquer site).
# Cada padrao e (regex_compilado, rotulo).
_PADROES_LINHA: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"^\s*(?:>+\s*)?(?:assine|login|cadastre[\-\s]?se|fazer login|entrar)\s*[:\.\-—]?\s*.*$", re.I | re.M), "auth_cta"),
    (re.compile(r"^\s*(?:tudo em um so lugar|tudo em um único lugar).*$", re.I | re.M), "personalize_acesso"),
    (re.compile(r"^\s*(?:para voce personalizar seu acesso).*$", re.I | re.M), "personalize_acesso"),
    (re.compile(r"^\s*leia uma selecao especial.*$", re.I | re.M), "selecao_especial"),
    (re.compile(r"^\s*receba no seu e[\-\s]?mail.*$", re.I | re.M), "newsletter"),
    (re.compile(r"^\s*newsletter.*$", re.I | re.M), "newsletter"),
    (re.compile(r"^\s*(?:publicidade|conteudo patrocinado|continua apos a publicidade)\s*[:\.]?\s*$", re.I | re.M), "publicidade"),
    (re.compile(r"(?:^|(?<=[\.\n\r])\s*)leia tamb(?:e|é)m\s*[:\.\-—]?\s*$", re.I | re.M), "leia_tambem"),
    (re.compile(r"(?:^|(?<=[\.\n\r])\s*)veja tamb(?:e|é)m\s*[:\.\-—]?\s*$", re.I | re.M), "veja_tambem"),
    (re.compile(r"^\s*relacionad[ao]s?\s*[:\.]?\s*$", re.I | re.M), "relacionados"),
    (re.compile(r"(?:^|(?<=[\.\n\r])\s*)compartilhe(?:\s*[:\-—]?\s*.*)?$", re.I | re.M), "compartilhe"),
    (re.compile(r"^\s*comentarios?\s*[:\.]?\s*$", re.I | re.M), "comentarios"),
    (re.compile(r"^\s*(?:politica de privacidade|politica de cookies|termos de uso)\s*[:\.]?\s*$", re.I | re.M), "termos_legais"),
    (re.compile(r"^\s*(?:atualizado em|publicado em|ultima atualizacao)\b.*$", re.I | re.M), "metadado_data"),
    (re.compile(r"^\s*(?:editado por|escrito por|reportagem por|texto por)\s+.*$", re.I | re.M), "metadado_autor"),
    (re.compile(r"^\s*(?:siga|siga[\-\s]nos|nos siga)\s+(?:no|na)\s+(?:facebook|instagram|twitter|x|telegram|whatsapp|youtube|tiktok|threads).*$", re.I | re.M), "siga_social"),
    (re.compile(r"^\s*(?:foto|imagem|arte|reprodu[çc][ãa]o|divulga[çc][ãa]o)\s*[:\-/].*$", re.I | re.M), "credito_foto_solto"),
    (re.compile(r"^\s*(?:foto:|reproducao:|reprodução:|divulgacao:|divulgação:).*$", re.I | re.M), "credito_foto_solto"),
    (re.compile(r"^\s*([A-Z]{2,}\s*\|\s*).*$", re.M), "manchete_em_caixa_alta"),
    (re.compile(r"^\s*\#\s*\w+(?:\s+\#\w+)+\s*$", re.M), "hashtag_chain"),
    (re.compile(r"^\s*(?:tags?:?|categorias?:?)\s+.*$", re.I | re.M), "tags_label_solto"),
    (re.compile(r"^\s*(?:do nosso whatsapp|entre no nosso grupo do whatsapp).*$", re.I | re.M), "whatsapp_cta"),
    (re.compile(r"^\s*(?:fa[çc]a parte do nosso canal|inscreva[\-\s]se no canal|assine o canal).*$", re.I | re.M), "canal_cta"),
    (re.compile(r"^\s*(?:carregando|continua lendo|veja a seguir)\s*\.*$", re.I | re.M), "ui_loading"),
    (re.compile(r"^\s*cookies?\s*[:\.]?\s*$", re.I | re.M), "cookies"),
)

# Padroes que mesmo dentro de um paragrafo indicam boilerplate critico
# (motivam bloqueio se forem proporcao alta do texto)
_PADROES_INLINE: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"continua apos a publicidade", re.I), "publicidade_inline"),
    (re.compile(r"para acessar este conteudo", re.I), "paywall_inline"),
    (re.compile(r"este conteudo e exclusivo para assinantes", re.I), "paywall_inline"),
    (re.compile(r"clique aqui para receber", re.I), "newsletter_inline"),
    (re.compile(r"tudo em um so lugar para voce personalizar seu acesso", re.I), "personalize_inline"),
    (re.compile(r"voce gostou do conteudo\?", re.I), "engagement_cta"),
    (re.compile(r"compartilhe esta materia", re.I), "compartilhe_inline"),
    (re.compile(r"siga.*no (?:instagram|facebook|twitter|x|telegram|whatsapp|threads)", re.I), "social_inline"),
    # spec_scrapling_artigo_unico §8.3 — padroes RJNEWS / portais
    (re.compile(r"para recuperar a senha", re.I), "recuperar_senha"),
    (re.compile(r"digite seu e[\-\s]?mail", re.I), "digite_email"),
    (re.compile(r"enviaremos um c(?:o|ó)digo", re.I), "envia_codigo"),
    (re.compile(r"participe ativamente do (?:nosso )?portal", re.I), "participe_portal"),
    (re.compile(r"comente,?\s*d(?:e|ê)\s+e\s+receba\s+likes", re.I), "comente_receba_likes"),
    (re.compile(r"marque (?:nosso )?portal como fonte preferencial", re.I), "fonte_preferencial"),
    (re.compile(r"todos os direitos reservados", re.I), "direitos_reservados"),
    (re.compile(r"receba as principais not(?:i|í)cias em seu e[\-\s]?mail", re.I), "receba_principais_noticias"),
    (re.compile(r"©\s*\d{4}", re.I), "copyright_year"),
)


def detectar_boilerplate(texto: Any) -> list[str]:
    """Devolve lista de rotulos de boilerplate encontrados (deduplicados)."""
    if not texto:
        return []
    s = str(texto)
    achados: list[str] = []
    vistos: set[str] = set()
    for rx, rotulo in _PADROES_LINHA:
        if rx.search(s) and rotulo not in vistos:
            achados.append(rotulo)
            vistos.add(rotulo)
    for rx, rotulo in _PADROES_INLINE:
        if rx.search(s) and rotulo not in vistos:
            achados.append(rotulo)
            vistos.add(rotulo)
    return achados


def limpar_boilerplate_fonte(texto: Any) -> dict:
    """Remove linhas e trechos de boilerplate, devolve texto limpo + relatorio.

    Conservador: nao remove paragrafos que tem fato jornalistico misturado.
    So zera LINHAS inteiras que batem nos padroes universais.
    """
    if not texto:
        return {"texto_limpo": "", "removidos": [], "padroes": []}
    s = str(texto).replace("\r\n", "\n").replace("\r", "\n")
    removidos: list[str] = []
    padroes_achados: list[str] = []
    for rx, rotulo in _PADROES_LINHA:
        # captura cada match isolado para log
        for m in rx.finditer(s):
            txt = m.group(0).strip()
            if txt and len(txt) < 240:  # nao engole paragrafo enorme
                removidos.append(txt[:200])
                if rotulo not in padroes_achados:
                    padroes_achados.append(rotulo)
        s = rx.sub("", s)
    # remove linhas com hashtag chain residuais
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = s.strip()
    # se um paragrafo inteiro virou so resto de inline, comprime
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n+", s) if p.strip()]
    s_final = "\n\n".join(paragrafos)
    return {
        "texto_limpo": s_final,
        "removidos": removidos,
        "padroes": padroes_achados,
        "chars_antes": len(str(texto)),
        "chars_depois": len(s_final),
    }


def fonte_tem_boilerplate_critico(texto: Any,
                                  *, proporcao_min: float = 0.40) -> bool:
    """True se mais de proporcao_min do texto e boilerplate.

    Bloqueia fontes em que o conteudo jornalistico real e minoritario.
    """
    if not texto:
        return False
    res = limpar_boilerplate_fonte(texto)
    antes = res["chars_antes"]
    depois = res["chars_depois"]
    if antes <= 0:
        return False
    removido = antes - depois
    if removido / antes >= proporcao_min:
        return True
    # se sobrou pouco texto, tambem e critico
    if depois < 400 and antes - depois > 100:
        return True
    return False


__all__ = [
    "limpar_boilerplate_fonte",
    "detectar_boilerplate",
    "fonte_tem_boilerplate_critico",
]
