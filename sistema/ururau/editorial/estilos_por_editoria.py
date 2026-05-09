"""
ururau.editorial.estilos_por_editoria — v74
Variação automática de estilo por editoria/tipo de matéria.

Não substitui a política editorial: adiciona uma camada curta, objetiva e
operacional para o motor de redação escolher ritmo, estrutura e vocabulário.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EditorialStyle:
    canal: str
    article_type: str
    tom: str
    estrutura: tuple[str, ...]
    evitar: tuple[str, ...]
    prioridade: tuple[str, ...]


_STYLE_MAP: dict[str, EditorialStyle] = {
    "Política": EditorialStyle(
        canal="Política",
        article_type="politics",
        tom="institucional, analítico, sem torcida e sem adjetivação",
        estrutura=("lead com ator público, cargo, decisão/declaração e efeito prático", "contexto político documentado", "contraponto ou histórico quando constar", "próximos passos"),
        evitar=("tom de bastidor sem fonte", "frases opinativas", "ataques pessoais", "reacende", "reforça"),
        prioridade=("cargo correto", "partido/órgão quando constar", "data", "efeito público"),
    ),
    "Economia": EditorialStyle(
        canal="Economia",
        article_type="economy",
        tom="serviço claro, objetivo e útil ao leitor",
        estrutura=("lead com decisão, benefício, valor ou prazo", "quem é afetado", "como consultar ou acessar", "calendário/prazo", "contexto sem alongar"),
        evitar=("afirmar média como valor fixo", "promessa de pagamento sem fonte", "jargão bancário sem explicação"),
        prioridade=("quem recebe", "valor quando oficial", "prazo", "canal de consulta", "órgão responsável"),
    ),
    "Polícia": EditorialStyle(
        canal="Polícia",
        article_type="police",
        tom="factual, cauteloso e jurídico",
        estrutura=("lead com ocorrência, local e fonte oficial", "vítima/suspeito conforme status", "ação policial", "investigação"),
        evitar=("condenar suspeito", "detalhes mórbidos", "especulação", "sensacionalismo"),
        prioridade=("local", "data", "delegacia/órgão", "status da investigação"),
    ),
    "Geral": EditorialStyle(
        canal="Geral",
        article_type="hard_news",
        tom="direto, humano e factual",
        estrutura=("lead com fato principal", "circunstâncias", "providências oficiais", "nota/posição quando houver", "contexto mínimo"),
        evitar=("fechamento genérico", "dramatização", "culpa sem apuração"),
        prioridade=("quem", "o quê", "quando", "onde", "órgão acionado"),
    ),
    "Cidades": EditorialStyle(
        canal="Cidades",
        article_type="cities_service",
        tom="local, prático e orientado ao serviço",
        estrutura=("lead com impacto local", "serviço ao morador", "horário/local", "orientação pública", "contexto"),
        evitar=("texto nacionalizado demais", "intertítulo vazio", "frase de assessoria"),
        prioridade=("bairro/cidade", "órgão municipal", "serviço afetado", "prazo"),
    ),
    "Esportes": EditorialStyle(
        canal="Esportes",
        article_type="sports",
        tom="dinâmico, informativo e sem torcida",
        estrutura=("lead com jogo/resultado", "competição e rodada", "personagens", "tabela/próximo compromisso"),
        evitar=("torcida", "deboche", "hipérbole"),
        prioridade=("placar", "time", "competição", "data", "local"),
    ),
}


def obter_estilo_editorial(canal: str = "", article_type: str = "") -> EditorialStyle:
    canal = (canal or "").strip()
    article_type = (article_type or "").strip()
    if canal in _STYLE_MAP:
        return _STYLE_MAP[canal]
    if article_type in ("service_economy", "economy"):
        return _STYLE_MAP["Economia"]
    if article_type in ("accident", "hard_news"):
        return _STYLE_MAP["Geral"]
    if article_type == "politics":
        return _STYLE_MAP["Política"]
    if article_type == "police":
        return _STYLE_MAP["Polícia"]
    if article_type.startswith("sports"):
        return _STYLE_MAP["Esportes"]
    return _STYLE_MAP["Geral"]


def bloco_estilo_para_prompt(canal: str = "", article_type: str = "") -> str:
    e = obter_estilo_editorial(canal, article_type)
    return (
        "== ESTILO V74 POR EDITORIA ==\n"
        f"Canal: {e.canal}\n"
        f"Tipo: {article_type or e.article_type}\n"
        f"Tom: {e.tom}\n"
        "Estrutura recomendada:\n- " + "\n- ".join(e.estrutura) + "\n"
        "Priorizar:\n- " + "\n- ".join(e.prioridade) + "\n"
        "Evitar:\n- " + "\n- ".join(e.evitar)
    )
