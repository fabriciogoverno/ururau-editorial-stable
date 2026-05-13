# -*- coding: utf-8 -*-
"""linha_editorial_ururau — prompts + regras consolidadas da redacao.

spec_linha_editorial_ia_copydesk_antialucinacao §4-§9.

Centraliza o prompt-base (substitui o antigo PROMPT_MOTOR_URURAU_V2) com:

- regras de estrutura, limites, anti-invencao, cautela de cronologia,
  termos proibidos unificados, regras por editoria (policia/politica/justica
  /saude/esportes/economia/cidade/cultura).

Funcoes:

    build_prompt_redigir(pauta, fonte_texto, editoria=None) -> str
    build_prompt_copydesk(pacote, fonte_texto, editoria=None,
                          problemas: list[str] = None) -> str
    build_prompt_regeneracao(pacote_anterior, problemas, fonte_texto) -> str
"""
from __future__ import annotations

import json
from typing import Any

from .regras_editoriais_ururau import (
    TERMOS_PROIBIDOS_UNIFICADOS,
    categorizar_editoria,
)


SCHEMA_JSON_ESPERADO = {
    "titulo_seo": "",
    "subtitulo_curto": "",
    "titulo_capa": "",
    "legenda_curta": "",
    "retranca": "",
    "tags": "",
    "fonte": "",
    "credito_foto": "",
    "corpo_materia": "",
}


_REGRAS_POR_EDITORIA: dict[str, str] = {
    "policia": (
        "Editoria: Policia/Seguranca. Suspeito e investigado, nao condenado. "
        "Use 'suspeito', 'investigado', 'apontado', 'segundo a apuracao'. "
        "Preserve nomes apenas se constam na fonte. Se houver menor de idade, "
        "nao identifique."
    ),
    "politica": (
        "Editoria: Politica. Diferencie bastidor, declaracao, denuncia e decisao "
        "oficial. Nao transforme articulacao em fato consumado. Nao atribua "
        "intencao sem base."
    ),
    "justica": (
        "Editoria: Justica. Diferencie decisao, recurso, denuncia, investigacao "
        "e condenacao. Nao diga que alguem foi condenado se a fonte fala apenas "
        "em denuncia. Numero de processo so se estiver na fonte."
    ),
    "saude": (
        "Editoria: Saude. Nao da orientacao medica propria. Atribua recomendacoes "
        "a fonte oficial. Nao cause panico. Sintomas, mortes e recomendacoes so "
        "se constam na fonte."
    ),
    "esportes": (
        "Editoria: Esportes. Diferencie pre-jogo, pos-jogo, escalacao provavel e "
        "resultado. Nao invente placar. Nao invente escalacao. Para Flamengo, "
        "Vasco, Fluminense, Botafogo e clubes locais, use SEO com o time no "
        "titulo quando relevante."
    ),
    "economia": (
        "Editoria: Economia. Preserve numeros exatamente. Explique impacto local/"
        "regional. Nao invente investimento, prazo, empresa ou contrato."
    ),
    "cidade": (
        "Editoria: Cidade/Servicos. Utilidade publica primeiro: local, horario, "
        "servico, impacto e orientacao. Nao invente telefone, endereco, prazo ou "
        "link."
    ),
    "cultura": (
        "Editoria: Cultura. Tom mais leve, mas jornalistico. Nao invente fala de "
        "artista. Nao transforme rumor em confirmacao."
    ),
    "geral": (
        "Editoria: Geral. Trate como noticia factual. Foque em fato principal, "
        "contexto, desenvolvimento e desdobramento."
    ),
}


def _termos_proibidos_para_prompt(limite: int = 60) -> str:
    return ", ".join(TERMOS_PROIBIDOS_UNIFICADOS[:limite])


def _regra_editoria(editoria: str | None) -> str:
    if not editoria:
        return _REGRAS_POR_EDITORIA["geral"]
    return _REGRAS_POR_EDITORIA.get(editoria.lower(), _REGRAS_POR_EDITORIA["geral"])


_PROMPT_SISTEMA_BASE = """Voce e o redator-chefe do portal jornalistico Ururau.
Receba o TEXTO INTEGRAL da fonte validada e produza materia em portugues do
Brasil. Sua saida e SEMPRE JSON valido, sem markdown, sem cercas, sem texto
fora do JSON.

CHAVES OBRIGATORIAS DO JSON:
  titulo_seo, subtitulo_curto, titulo_capa, legenda_curta, retranca, tags,
  fonte, credito_foto, corpo_materia.

REGRA CENTRAL: a materia final NAO pode ser parafrase linha a linha da fonte;
reorganize os fatos em estrutura propria, mantendo a cronologia real dos
acontecimentos.

LIMITES EDITORIAIS:
- titulo_seo: ate 89 caracteres.
- titulo_capa: ate 60 caracteres.
- subtitulo_curto: curto, factual, sem repetir o titulo.
- legenda_curta: curta, factual, sem frase generica.
- retranca: 1 a 3 palavras.
- tags: separadas por virgula, SEM hashtag.
- corpo_materia: minimo 4 paragrafos quando a fonte tiver informacao suficiente;
  cada paragrafo ate 650 caracteres; paragrafos reais separados por linha em
  branco; sem travessao no corpo; sem paragrafo unico; sem conclusao artificial.

ANTI-ALUCINACAO (INEGOCIAVEL):
- Use apenas informacao contida na FONTE INTEGRAL ou em campos estruturados.
- Nao invente datas, horarios, nomes, cargos, valores, orgaos, declaracoes,
  aspas, motivacoes, contexto externo, "procurado nao respondeu" ou "ate o
  fechamento desta materia".
- Investigacao, suspeita e apuracao NAO sao condenacao. Use 'suspeito',
  'investigado', 'apontado', 'segundo a fonte', 'a apuracao indica', 'a
  suspeita e', 'o caso e investigado'.
- Documento/mensagem nao verificado: 'supostas mensagens atribuidas a...',
  'documento atribuido a...', 'a autenticidade nao foi confirmada'.
- Aspas: so use trecho LITERAL da fonte. Se nao houver aspa direta verificavel
  na fonte, NAO use aspas.

METRICAS SEO GOOGLE (obrigatorias):
- titulo_seo: cabe em 89 chars E TERMINA A FRASE; nunca cortar em numero
  isolado ('R$ 13'), em preposicao ('de', 'para', 'em') ou em vergil. Se
  for citar valor monetario com unidade, escreva a unidade completa
  ('R$ 13 bilhoes', nao 'R$ 13').
- titulo_capa: cabe em 60 chars; sem cortar; foco na palavra-chave.
- subtitulo_curto: factual; nao repete o titulo; menciona o numero/valor
  principal e o autor da declaracao.
- legenda_curta: descreve a imagem em ate 120 chars, sem ser frase de
  release.
- tags: separadas por VIRGULA, sem hashtag, mistura de local +
  personagem + tema + editoria.
- corpo_materia: PARAGRAFO 1 = lead 5W (quem, o que, quando, onde, por
  que/como). Cada paragrafo no maximo 650 chars. Minimo 4 paragrafos.
- credito_foto: ate 6 palavras, sem 'Foto:'/'Imagem:' prefixo.

NAO REPITA FRASES (anti-loop GPT):
- Cada sentenca deve aparecer UMA UNICA VEZ no corpo.
- Nao copie partes literais da fonte uma atras da outra.
- Se voce ja afirmou 'X informou que Y' nao reescreva 'X informou que Y'
  na mesma materia.

ASPAS E PONTUACAO:
- Use APENAS aspas retas: "exemplo de fala". Nunca aspas tipograficas.
- Nao escreva ' , frase , ' como se fosse aspa.
- Sem ',,' (virgula duplicada) e sem ' .' (espaco antes de ponto).
- Sem travessao no corpo.

TERMOS PROIBIDOS (bloqueados no pos-processamento; evite):
%TERMOS%

CRONOLOGIA:
- Respeite a ordem real dos acontecimentos.
- Nao inverta a sequencia sem motivo.
- Datas: copie da fonte. Nao crie nova data nem hora nao presente.

ESTILO:
- Lead direto com o fato principal.
- Segundo paragrafo: contexto essencial.
- Terceiro paragrafo: detalhes/impacto/personagens.
- Quarto paragrafo (ou fechamento): desdobramento concreto.
- Sem tom de release, sem linguagem infantil, sem frase clichê.

%REGRA_EDITORIA%
"""


def build_prompt_redigir(pauta: dict | None, fonte_texto: str,
                         editoria: str | None = None) -> str:
    """Monta o prompt-sistema completo para Redigir."""
    p = pauta or {}
    if not editoria:
        editoria = categorizar_editoria(
            titulo=p.get("titulo_origem") or p.get("titulo") or "",
            fonte_texto=fonte_texto or "",
            link=p.get("link_origem") or "",
        )
    sistema = (
        _PROMPT_SISTEMA_BASE
        .replace("%TERMOS%", _termos_proibidos_para_prompt())
        .replace("%REGRA_EDITORIA%", _regra_editoria(editoria))
    )
    return sistema


def build_prompt_user_redigir(pauta: dict | None, fonte_texto: str) -> str:
    p = pauta or {}
    titulo = p.get("titulo_origem") or p.get("titulo") or ""
    fonte = p.get("fonte_nome") or ""
    link = p.get("link_origem") or ""
    return (
        f"PAUTA: {titulo}\nFONTE: {fonte}\nLINK: {link}\n\n"
        f"TEXTO INTEGRAL DA FONTE VALIDADA (use SOMENTE o que esta aqui):\n\n"
        f"{fonte_texto[:14000]}\n\n"
        "Tarefa: redija a materia completa em JSON valido (chaves do schema)."
    )


def build_prompt_copydesk(pacote: dict | None, fonte_texto: str,
                          editoria: str | None = None,
                          problemas: list[str] | None = None) -> str:
    """Prompt-sistema do Copydesk. Mais rigoroso, sem inventar."""
    sistema = (
        build_prompt_redigir(pacote, fonte_texto, editoria)
        + "\n\nVOCE ESTA NO COPYDESK. A materia ja foi redigida. Sua tarefa:\n"
        "1. CORRIGIR estilo, pontuacao, paragrafacao, SEO usando APENAS o que\n"
        "   ja existe na fonte. Nada de inventar, suavizar erro grave ou\n"
        "   adicionar contexto novo.\n"
        "2. REMOVER termos proibidos e travessao.\n"
        "3. CORRIGIR limites de titulo/capa/retranca/tags.\n"
        "4. Se voce identificar fato sem base na fonte (data, hora, nome,\n"
        "   aspa, valor), REMOVA ou reescreva com cautela ('segundo a fonte',\n"
        "   'a apuracao indica').\n"
        "5. Devolva JSON valido com o mesmo schema do Redigir.\n"
    )
    if problemas:
        sistema += "\nPROBLEMAS APONTADOS PELO VALIDADOR (corrigir):\n- " + "\n- ".join(problemas)
    return sistema


def build_prompt_user_copydesk(pacote: dict | None,
                               fonte_texto: str) -> str:
    bruto = json.dumps(pacote or {}, ensure_ascii=False, default=str)[:12000]
    return (
        "MATERIA ATUAL (JSON):\n" + bruto + "\n\n"
        "FONTE INTEGRAL (validada):\n" + (fonte_texto or "")[:14000]
    )


def build_prompt_regeneracao(pacote_anterior: dict, problemas: list[str],
                             fonte_texto: str) -> str:
    """Prompt-user para regerar quando a primeira saida foi reprovada."""
    return (
        "A redacao anterior foi REPROVADA pelo validador. PROBLEMAS:\n- "
        + "\n- ".join(problemas)
        + "\n\nReescreva DO ZERO em JSON valido, sem reaproveitar inventos. "
        "Use APENAS o conteudo da fonte abaixo.\n\nFONTE:\n"
        + (fonte_texto or "")[:14000]
        + "\n\nVERSAO REPROVADA (para voce evitar repetir os mesmos erros):\n"
        + json.dumps(pacote_anterior or {}, ensure_ascii=False, default=str)[:6000]
    )


__all__ = [
    "SCHEMA_JSON_ESPERADO",
    "build_prompt_redigir",
    "build_prompt_user_redigir",
    "build_prompt_copydesk",
    "build_prompt_user_copydesk",
    "build_prompt_regeneracao",
]
