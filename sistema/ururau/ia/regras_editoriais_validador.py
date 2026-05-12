# -*- coding: utf-8 -*-
"""regras_editoriais_validador — validador de pacote editorial do Ururau.

spec_claudio_ia_real_gpt4mini_regras_editoriais §6: aplica as regras
de estrutura, limites, estilo e termos proibidos ao JSON gerado pela IA.

Uso:

    validar_pacote_editorial(conteudo) -> dict

    {
      "ok": bool,
      "erros": list[str],
      "avisos": list[str],
      "termos_proibidos_encontrados": list[str],
      "campos_ausentes": list[str],
      "estatisticas": {
          "titulo_seo_len": int,
          "titulo_capa_len": int,
          "retranca_palavras": int,
          "paragrafos_corpo": int,
          "chars_corpo": int,
      }
    }
"""
from __future__ import annotations

import re
from typing import Any

CAMPOS_OBRIGATORIOS = (
    "titulo_seo", "subtitulo_curto", "titulo_capa", "legenda_curta",
    "retranca", "tags", "fonte", "credito_foto", "corpo_materia",
)

MAX_TITULO_SEO = 89
MAX_TITULO_CAPA = 60
MAX_PARAGRAFO = 650
MIN_PARAGRAFOS = 4
MIN_RETRANCA_PALAVRAS = 1
MAX_RETRANCA_PALAVRAS = 3

# spec §6.4: lista consolidada de termos proibidos (case-insensitive).
TERMOS_PROIBIDOS: tuple[str, ...] = (
    "acende o alerta",
    "acendeu o alerta",
    "sinal de alerta",
    "chama atencao", "chama atenção",
    "chamou atencao", "chamou atenção",
    "ganha destaque",
    "ganhou destaque",
    "e destaque",
    "reforca a importancia", "reforça a importância",
    "reforca o compromisso", "reforça o compromisso",
    "reforca a necessidade", "reforça a necessidade",
    "destaca a importancia", "destaca a importância",
    "evidencia a importancia", "evidencia a importância",
    "mostra a importancia", "mostra a importância",
    "vale destacar",
    "vale ressaltar",
    "e importante destacar", "é importante destacar",
    "cabe destacar",
    "nesse sentido",
    "desta forma",
    "dessa forma",
    "diante desse cenario", "diante desse cenário",
    "em meio a",
    "o caso evidencia",
    "o caso mostra",
    "o caso reforca", "o caso reforça",
    "traz a tona", "traz à tona",
    "reacende o debate",
    "joga luz sobre",
    "coloca em xeque",
    "no centro das atencoes", "no centro das atenções",
    "segue dando o que falar",
    "movimenta os bastidores",
    "promete movimentar",
    "populacao fica em alerta", "população fica em alerta",
    "autoridades seguem acompanhando",
    "medidas cabiveis", "medidas cabíveis",
    "providencias cabiveis", "providências cabíveis",
    "ate o fechamento desta materia", "até o fechamento desta matéria",
    "ate a publicacao desta reportagem", "até a publicação desta reportagem",
    # adicionados pelo spec
    "reafirma",
    "reforca", "reforça",
    "destaca",
    "ressalta",
    "importante ressaltar",
    "importante lembrar",
    "nas redes sociais, internautas",
    "clima de",
    "bastidores fervem",
)


def _normalizar(t: Any) -> str:
    s = str(t or "")
    # remove acentos para comparacao
    import unicodedata
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def _contar_paragrafos(corpo: str) -> list[str]:
    if not corpo:
        return []
    raw = re.split(r"\n\s*\n+", str(corpo).replace("\r", "\n"))
    paragrafos = [p.strip() for p in raw if p.strip()]
    return paragrafos


def detectar_termos_proibidos(texto: str) -> list[str]:
    if not texto:
        return []
    norm = _normalizar(texto)
    achados = []
    vistos = set()
    for termo in TERMOS_PROIBIDOS:
        if termo in vistos:
            continue
        tnorm = _normalizar(termo)
        if tnorm in norm:
            achados.append(termo)
            vistos.add(termo)
    return achados


def validar_pacote_editorial(conteudo: dict | None,
                             *, exigir_minimo_paragrafos: bool = True) -> dict:
    """Aplica as regras editoriais oficiais. Retorna diagnostico estruturado."""
    out: dict = {
        "ok": False,
        "erros": [],
        "avisos": [],
        "termos_proibidos_encontrados": [],
        "campos_ausentes": [],
        "estatisticas": {
            "titulo_seo_len": 0,
            "titulo_capa_len": 0,
            "retranca_palavras": 0,
            "paragrafos_corpo": 0,
            "chars_corpo": 0,
        },
    }
    if not isinstance(conteudo, dict):
        out["erros"].append("conteudo_nao_e_dict")
        return out

    # 1) Campos obrigatorios.
    for c in CAMPOS_OBRIGATORIOS:
        if not str(conteudo.get(c, "") or "").strip():
            out["campos_ausentes"].append(c)
    if out["campos_ausentes"]:
        out["erros"].append(
            "campos_ausentes_ou_vazios:" + ",".join(out["campos_ausentes"])
        )

    # 2) Limites.
    t_seo = str(conteudo.get("titulo_seo", "") or "").strip()
    t_capa = str(conteudo.get("titulo_capa", "") or "").strip()
    retranca = str(conteudo.get("retranca", "") or "").strip()
    corpo = str(conteudo.get("corpo_materia", "") or "").strip()

    out["estatisticas"]["titulo_seo_len"] = len(t_seo)
    out["estatisticas"]["titulo_capa_len"] = len(t_capa)

    if len(t_seo) > MAX_TITULO_SEO:
        out["erros"].append(f"titulo_seo_excede_{MAX_TITULO_SEO}:{len(t_seo)}")
    if len(t_capa) > MAX_TITULO_CAPA:
        out["erros"].append(f"titulo_capa_excede_{MAX_TITULO_CAPA}:{len(t_capa)}")

    palavras_retranca = [p for p in re.split(r"\s+", retranca) if p]
    out["estatisticas"]["retranca_palavras"] = len(palavras_retranca)
    if not (MIN_RETRANCA_PALAVRAS <= len(palavras_retranca) <= MAX_RETRANCA_PALAVRAS):
        out["erros"].append(
            f"retranca_fora_1_a_3_palavras:{len(palavras_retranca)}"
        )

    paragrafos = _contar_paragrafos(corpo)
    out["estatisticas"]["paragrafos_corpo"] = len(paragrafos)
    out["estatisticas"]["chars_corpo"] = len(corpo)

    if len(paragrafos) <= 1:
        out["erros"].append("paragrafo_unico_ou_vazio")
    elif exigir_minimo_paragrafos and len(paragrafos) < MIN_PARAGRAFOS:
        out["erros"].append(f"abaixo_de_{MIN_PARAGRAFOS}_paragrafos:{len(paragrafos)}")

    longos = [i for i, p in enumerate(paragrafos) if len(p) > MAX_PARAGRAFO]
    if longos:
        out["avisos"].append(f"paragrafos_acima_de_{MAX_PARAGRAFO}_chars:{longos}")

    if "—" in corpo or "–" in corpo:
        out["erros"].append("travessao_no_corpo")

    # 3) Termos proibidos em qualquer campo de texto.
    texto_total = " ".join([
        t_seo, t_capa,
        str(conteudo.get("subtitulo_curto", "") or ""),
        str(conteudo.get("legenda_curta", "") or ""),
        retranca, corpo,
    ])
    achados = detectar_termos_proibidos(texto_total)
    out["termos_proibidos_encontrados"] = achados
    if achados:
        out["erros"].append(
            "termos_proibidos_encontrados:" + ",".join(achados[:10])
        )

    out["ok"] = not out["erros"]
    return out


__all__ = [
    "CAMPOS_OBRIGATORIOS",
    "MAX_TITULO_SEO",
    "MAX_TITULO_CAPA",
    "MAX_PARAGRAFO",
    "MIN_PARAGRAFOS",
    "MIN_RETRANCA_PALAVRAS",
    "MAX_RETRANCA_PALAVRAS",
    "TERMOS_PROIBIDOS",
    "detectar_termos_proibidos",
    "validar_pacote_editorial",
]
