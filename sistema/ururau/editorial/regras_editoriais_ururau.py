# -*- coding: utf-8 -*-
"""regras_editoriais_ururau — termos proibidos e categorizacao versionada.

Consolida em um unico ponto a lista de termos proibidos e a metadata
editorial. Une os 40 termos historicos do motor_gpt_spec_v2 com os termos
adicionais do validador (60+ no total) sem duplicacao.

Tambem expoe:

- TERMOS_PROIBIDOS_UNIFICADOS  (tupla, case+acento insensitive)
- categorizar_editoria(titulo, fonte_texto, link)  ->  'policia'|'politica'|...
- detectar_termos_proibidos(texto) -> list[str]
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


# Origem 1: motor_gpt_spec_v2 (40 termos historicos)
_TERMOS_MOTOR_V2 = (
    "acende o alerta", "acendeu o alerta", "sinal de alerta",
    "chama atencao", "chama atenção", "chamou atencao", "chamou atenção",
    "ganha destaque", "ganhou destaque", "e destaque", "é destaque",
    "reforca a importancia", "reforça a importância",
    "reforca o compromisso", "reforça o compromisso",
    "reforca a necessidade", "reforça a necessidade",
    "destaca a importancia", "destaca a importância",
    "evidencia a importancia", "evidencia a importância",
    "mostra a importancia", "mostra a importância",
    "vale destacar", "vale ressaltar",
    "e importante destacar", "é importante destacar",
    "cabe destacar",
    "nesse sentido", "desta forma", "dessa forma",
    "diante desse cenario", "diante desse cenário",
    "em meio a",
    "o caso evidencia", "o caso mostra",
    "o caso reforca", "o caso reforça",
    "traz a tona", "traz à tona",
    "reacende o debate",
    "joga luz sobre",
    "coloca em xeque",
    "no centro das atencoes", "no centro das atenções",
    "segue dando o que falar",
    "movimenta os bastidores", "bastidores fervem",
    "promete movimentar",
    "populacao fica em alerta", "população fica em alerta",
    "autoridades seguem acompanhando",
    "medidas cabiveis", "medidas cabíveis",
    "providencias cabiveis", "providências cabíveis",
    "ate o fechamento desta materia", "até o fechamento desta matéria",
    "ate a publicacao desta reportagem", "até a publicação desta reportagem",
)

# Origem 2: spec_claudio §6 acrescentou
_TERMOS_SPEC_ADICIONAIS = (
    "reafirma", "reforca", "reforça",
    "destaca", "ressalta",
    "importante ressaltar", "importante lembrar",
    "nas redes sociais, internautas",
    "clima de",
)


def _normalizar(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


# Tupla unificada, deduplicada por forma normalizada (mantem original com acento).
def _unificar(*grupos: tuple[str, ...]) -> tuple[str, ...]:
    vistos: set[str] = set()
    out: list[str] = []
    for grupo in grupos:
        for termo in grupo:
            chave = _normalizar(termo)
            if chave and chave not in vistos:
                vistos.add(chave)
                out.append(termo)
    return tuple(out)


TERMOS_PROIBIDOS_UNIFICADOS: tuple[str, ...] = _unificar(
    _TERMOS_MOTOR_V2, _TERMOS_SPEC_ADICIONAIS
)


def detectar_termos_proibidos(texto: Any) -> list[str]:
    if not texto:
        return []
    norm = _normalizar(texto)
    achados: list[str] = []
    vistos: set[str] = set()
    for termo in TERMOS_PROIBIDOS_UNIFICADOS:
        chave = _normalizar(termo)
        if chave and chave in norm and chave not in vistos:
            achados.append(termo)
            vistos.add(chave)
    return achados


# ─────────────────────────────────────────────────────────────────────────────
# Categorizacao por editoria (spec §8)
# ─────────────────────────────────────────────────────────────────────────────

_PADROES_POR_EDITORIA: dict[str, tuple[str, ...]] = {
    "policia": (
        "policia", "policial", "prisao", "preso", "presa",
        "criminoso", "arma", "armas", "tiro", "tiros", "troca de tiros",
        "trafico", "drogas", "apreensao", "operacao",
        "homicidio", "assassinato", "roubo", "furto", "arrombamento",
        "boletim de ocorrencia", "delegacia", "suspeito", "suspeita",
    ),
    "politica": (
        "prefeitura", "camara", "vereador", "vereadora", "deputado",
        "deputada", "governador", "presidente", "ministro", "ministra",
        "alerj", "palacio guanabara", "senado", "licitacao",
        "cassacao", "eleicao", "eleicoes", "campanha",
        "candidato", "candidata", "partido",
    ),
    "justica": (
        "stf", "stj", "tjrj", "tjsp", "mpf", "mprj", "tre", "tse",
        "denuncia", "investigacao", "processo", "habeas corpus",
        "recurso", "condenacao", "absolvicao", "sentenca", "vara",
        "audiencia", "magistrado", "juiz", "juiza",
    ),
    "saude": (
        "saude", "hospital", "vacina", "dengue", "covid",
        "sus", "secretaria de saude", "doenca", "epidemia", "sintoma",
        "diagnostico", "tratamento", "medico", "medica", "uti",
    ),
    "esportes": (
        "flamengo", "vasco", "fluminense", "botafogo",
        "campeonato", "rodada", "treino", "tecnico", "jogador",
        "gol", "placar", "vitoria", "derrota", "empate",
        "libertadores", "brasileirao", "carioca",
    ),
    "economia": (
        "investimento", "porto do acu", "porto", "industria",
        "fabrica", "petroleo", "royalties", "emprego", "vagas",
        "inflacao", "ibge", "ipca", "dolar", "economia",
    ),
    "cidade": (
        "campos", "goytacazes", "guarus", "macae",
        "sao joao da barra", "rio das ostras",
        "asfalto", "iluminacao", "trafego",
        "transito", "agua", "energia", "lixo", "saneamento",
    ),
    "cultura": (
        "show", "musica", "cantor", "cantora", "espetaculo",
        "teatro", "festival", "cinema", "exposicao", "artista",
    ),
}

_PADROES_LIXO_TITULO = (
    re.compile(r"\bmelhores\s+gols\b", re.I),
    re.compile(r"\bmelhores\s+momentos\b", re.I),
    re.compile(r"\bmelhores\s+defesas\b", re.I),
    re.compile(r"\bcharge\b", re.I),
    re.compile(r"\bfrase\s+do\s+dia\b", re.I),
    re.compile(r"\benquete\b", re.I),
)


def categorizar_editoria(titulo: Any = "", fonte_texto: Any = "",
                         link: Any = "") -> str:
    """Devolve a editoria primaria detectada (mais especifica vence)."""
    blob = _normalizar(" ".join(str(x) for x in (titulo, fonte_texto, link) if x))
    pontos: dict[str, int] = {}
    for editoria, termos in _PADROES_POR_EDITORIA.items():
        for t in termos:
            if t in blob:
                pontos[editoria] = pontos.get(editoria, 0) + 1
    if not pontos:
        return "geral"
    return max(pontos.items(), key=lambda kv: kv[1])[0]


def eh_lixo_visivel(titulo: Any) -> bool:
    """Pauta esportiva/visual sem corpo jornalistico (gols, charges, etc)."""
    t = str(titulo or "")
    return any(rx.search(t) for rx in _PADROES_LIXO_TITULO)


__all__ = [
    "TERMOS_PROIBIDOS_UNIFICADOS",
    "detectar_termos_proibidos",
    "categorizar_editoria",
    "eh_lixo_visivel",
]
