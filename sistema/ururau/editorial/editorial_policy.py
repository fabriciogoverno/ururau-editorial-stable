"""
editorial/editorial_policy.py - Source of truth UNICO da linha editorial Ururau (v70).

Re-exporta o SYSTEM_PROMPT_EDITORIAL_URURAU do agente canonico
e expoe funcoes de acesso a regras, schema e templates.

Toda chamada de IA em producao (geracao, copydesk, regenerate) deve
importar daqui:

    from ururau.editorial.editorial_policy import (
        get_editorial_system_prompt,
        get_editorial_user_prompt_template,
        get_editorial_rules,
        get_output_schema,
    )
"""
from __future__ import annotations

# Importa o prompt mestre do agente canonico (source of truth)
try:
    from ururau.agents.agente_editorial_ururau import SYSTEM_PROMPT_EDITORIAL_URURAU as _SYS
except Exception:
    _SYS = ""

# Limites canonicos
from ururau.editorial.field_limits import (
    TITULO_SEO_MAX, TITULO_CAPA_MAX,
    SUBTITULO_CURTO_MAX, LEGENDA_CURTA_MAX,
    TAGS_MIN, TAGS_MAX,
    META_DESCRIPTION_MIN, META_DESCRIPTION_MAX,
    RETRANCA_MAX_WORDS,
    COVERAGE_PANEL_MIN, COVERAGE_MONITOR_MIN,
    SCORE_QUALIDADE_PANEL_MIN, SCORE_QUALIDADE_MONITOR_MIN,
)


def get_editorial_system_prompt() -> str:
    """Retorna o system prompt mestre do Ururau."""
    return _SYS


def get_editorial_rules() -> dict:
    """Retorna o conjunto de regras editoriais (limites, palavras proibidas, etc.)."""
    return {
        "titulo_seo_max":        TITULO_SEO_MAX,
        "titulo_capa_max":       TITULO_CAPA_MAX,
        "subtitulo_curto_max":   SUBTITULO_CURTO_MAX,
        "legenda_curta_max":     LEGENDA_CURTA_MAX,
        "tags_min":              TAGS_MIN,
        "tags_max":              TAGS_MAX,
        "meta_description_min":  META_DESCRIPTION_MIN,
        "meta_description_max":  META_DESCRIPTION_MAX,
        "retranca_max_words":    RETRANCA_MAX_WORDS,
        "coverage_panel_min":    COVERAGE_PANEL_MIN,
        "coverage_monitor_min":  COVERAGE_MONITOR_MIN,
        "score_qualidade_panel_min":   SCORE_QUALIDADE_PANEL_MIN,
        "score_qualidade_monitor_min": SCORE_QUALIDADE_MONITOR_MIN,
        "expressoes_proibidas": [
            "vale lembrar", "e importante destacar", "cabe ressaltar",
            "em meio a", "cenario complexo", "nesse contexto",
            "novas informacoes serao divulgadas", "o caso segue em andamento",
            "a populacao deve ficar atenta", "mantem o monitoramento",
            "garantir a seguranca", "impacto social", "periodo de maior movimentacao",
            "a medida deve fortalecer", "os proximos passos anunciados",
        ],
    }


def get_output_schema() -> dict:
    """JSON schema completo do pacote editorial Ururau."""
    return {
        "titulo_seo":               "",
        "subtitulo_curto":          "",
        "retranca":                 "",
        "titulo_capa":              "",
        "tags":                     "",
        "legenda_curta":            "",
        "corpo_materia":            "",
        "legenda_instagram":        "",
        "meta_description":         "",
        "nome_da_fonte":            "",
        "link_da_fonte":            "",
        "creditos_da_foto":         "",
        "status_validacao":         "",
        "erros_validacao":          [],
        "observacoes_editoriais":   [],
    }


def get_editorial_user_prompt_template() -> str:
    """Template de user prompt usando structured editorial brief."""
    return (
        "TIPO DE MATERIA: {article_type}\n"
        "CANAL: {classified_channel}\n"
        "ANGULO EDITORIAL: {editorial_angle}\n"
        "PLANO DE PARAGRAFOS: {paragraph_plan}\n\n"
        "FATOS OBRIGATORIOS DA FONTE:\n{required_facts}\n\n"
        "RELACOES FACTUAIS (preservar subject->relationship->object):\n{entity_relationships}\n\n"
        "FONTE LIMPA (use APENAS estes fatos):\n{cleaned_source_text}\n\n"
        "TITULO ORIGINAL: {source_title}\n"
        "SUBTITULO ORIGINAL: {source_subtitle}\n"
        "URL: {source_url}\n"
        "FONTE: {source_name}\n"
        "PUBLICADA EM: {source_published_at}\n\n"
        "LIMITES OBRIGATORIOS: {field_limits}\n\n"
        "RETORNE JSON com este schema:\n{output_schema}\n"
    )

# URURAU v97 — complemento premium para aproveitar melhor modelos mini
_BASE_GET_EDITORIAL_SYSTEM_PROMPT_V97 = get_editorial_system_prompt

def get_editorial_system_prompt() -> str:  # type: ignore[override]
    base = _BASE_GET_EDITORIAL_SYSTEM_PROMPT_V97() or ""
    premium = """
== URURAU v97: PADRÃO PREMIUM DE REDAÇÃO ==
Você não é um resumidor. Você é editor de redação profissional. A saída deve transformar a fonte em matéria jornalística completa, autêntica e publicável, sem copiar blocos da origem e sem inventar fatos.

Regras de produção:
- Use somente fatos que estejam na fonte limpa, no título original, no subtítulo original ou nos fatos obrigatórios.
- Se a fonte tiver mais de 1.400 caracteres, entregue pelo menos 5 parágrafos; acima de 2.600 caracteres, pelo menos 6; acima de 4.200 caracteres, pelo menos 7.
- Nunca entregue corpo de matéria com apenas 1 parágrafo.
- O primeiro parágrafo deve ser lead jornalístico completo: fato principal, agente, local, data/tempo e efeito imediato quando constarem na fonte.
- Desenvolva contexto, antecedentes, detalhes concretos, impacto prático e próximo passo documentado.
- Não use travessão no corpo. Não use “acende o alerta”. Evite “vale lembrar”, “cabe ressaltar”, “nesse contexto”, “em meio a”, “reforça” como muleta textual.
- SEO obrigatório: título SEO até 89 caracteres; título capa até 60; meta description entre 120 e 160; retranca com uma palavra; tags de 8 a 12 itens, separadas por vírgula quando o campo for texto.
- Linguagem: padrão G1/UOL/Estadão, factual, clara, sem opinião, sem tom institucional e sem fecho ornamental.
- Retorne somente JSON válido, sem markdown.
""".strip()
    return (base.rstrip() + "\n\n" + premium).strip()

_BASE_GET_EDITORIAL_USER_PROMPT_TEMPLATE_V97 = get_editorial_user_prompt_template

def get_editorial_user_prompt_template() -> str:  # type: ignore[override]
    base = _BASE_GET_EDITORIAL_USER_PROMPT_TEMPLATE_V97()
    extra = """
EXIGÊNCIA V97 DE QUALIDADE:
A matéria deve ser completa e proporcional à FONTE LIMPA. Não resuma em um parágrafo. Reescreva com estrutura de reportagem: lead, contexto, desenvolvimento, consequências/efeitos e fechamento factual. Preserve precisão factual e otimize para SEO sem sensacionalismo.
""".strip()
    return base + "\n" + extra + "\n"

# URURAU v47.2 — prompt/rules pela matriz editorial única
try:
    from ururau.editorial.regras_editoriais import montar_bloco_prompt_editorial as _bp, obter_termos_ia_proibidos as _terms, limites as _lim
    _BASE_GET_EDITORIAL_SYSTEM_PROMPT_V472=get_editorial_system_prompt
    def get_editorial_system_prompt() -> str: return ((_BASE_GET_EDITORIAL_SYSTEM_PROMPT_V472() or '').rstrip()+'\n\n'+_bp()).strip()
    _BASE_GET_EDITORIAL_RULES_V472=get_editorial_rules
    def get_editorial_rules() -> dict:
        r=_BASE_GET_EDITORIAL_RULES_V472() or {}; r.update(_lim()); r['expressoes_proibidas']=_terms(); r['fonte_regras']='sistema/config/regras_editoriais.json'; return r
except Exception: pass
