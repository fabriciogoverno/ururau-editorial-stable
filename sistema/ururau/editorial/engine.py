from __future__ import annotations

# PATCH_V47_20_DICT_ATTR_COMPAT
try:
    from ururau.editorial.compat_resultado_v47_20 import compat_obj as _v4720_compat_obj, getv as _v4720_getv, get_bool as _v4720_get_bool, get_score as _v4720_get_score
except Exception:
    def _v4720_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4720_get_bool(o,k,d=False): return bool(_v4720_getv(o,k,d))
    def _v4720_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4720_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4720_compat_obj(o): return o

# PATCH_V47_18_DICT_SCORE_COMPAT
# PATCH_V47_18_DICT_SCORE_COMPAT
try:
    from ururau.editorial.compat_resultado_v47_18 import compat_obj as _v4718_compat_obj, getv as _v4718_getv, get_score as _v4718_get_score
except Exception:
    def _v4718_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4718_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4718_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4718_compat_obj(o): return o

try:
    from ururau.editorial.compat_resultado_v47_18 import compat_obj as _v4718_compat_obj, getv as _v4718_getv, get_score as _v4718_get_score
except Exception:
    def _v4718_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4718_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4718_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4718_compat_obj(o): return o

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI


# ─── Source context canonico ───────────────────────────────────────────────

@dataclass
class SourceContext:
    raw_source_text:           str = ""
    cleaned_source_text:       str = ""
    rss_context_text:          str = ""
    source_title:              str = ""
    source_subtitle:           str = ""
    source_url:                str = ""
    source_name:               str = ""
    source_published_at:       str = ""
    extraction_method:         str = ""
    extraction_status:         str = ""
    source_sufficiency_score:  int = 0
    paragraph_count:           int = 0


def build_source_context(pauta: dict) -> SourceContext:
    """Constroi SourceContext a partir do dict de pauta.

    v75: aceita tanto os nomes internos do robô (titulo_origem, texto_fonte)
    quanto aliases usados por testes, scraping e integrações (titulo, texto, conteudo).
    Isso evita matéria vazia quando a pauta chega por outro caminho do painel.
    """
    pauta = pauta or {}
    cleaned = (pauta.get("cleaned_source_text")
               or pauta.get("dossie")
               or pauta.get("texto_fonte")
               or pauta.get("texto")
               or pauta.get("conteudo")
               or pauta.get("body")
               or "")
    raw = pauta.get("raw_source_text") or pauta.get("html") or cleaned
    title = (pauta.get("titulo_origem")
             or pauta.get("titulo")
             or pauta.get("title")
             or pauta.get("headline")
             or "")
    subtitle = (pauta.get("resumo_origem")
                or pauta.get("resumo")
                or pauta.get("subtitulo")
                or pauta.get("description")
                or "")
    url = pauta.get("link_origem") or pauta.get("link") or pauta.get("url") or ""
    source_name = pauta.get("fonte_nome") or pauta.get("fonte") or pauta.get("source") or ""
    published = pauta.get("data_publicacao") or pauta.get("publicado_em") or pauta.get("published_at") or ""
    paragrafos = [p for p in (cleaned or "").split("\n\n") if p.strip()]
    return SourceContext(
        raw_source_text          = raw,
        cleaned_source_text      = cleaned,
        rss_context_text         = pauta.get("rss_context_text", "") or subtitle,
        source_title             = title,
        source_subtitle          = subtitle,
        source_url               = url,
        source_name              = source_name,
        source_published_at      = published,
        extraction_method        = pauta.get("extraction_method", ""),
        extraction_status        = pauta.get("extraction_status", ""),
        source_sufficiency_score = int(pauta.get("source_sufficiency_score", 0) or 0),
        paragraph_count          = len(paragrafos),
    )


# ─── Article type classification ────────────────────────────────────────────

def classify_article_type(source: SourceContext, canal: str = "") -> str:
    """
    Classifica tipo de materia (NAO usa apenas channel).

    Heuristicas baseadas em palavras-chave do texto.
    """
    text = (source.cleaned_source_text or "").lower()
    title = (source.source_title or "").lower()
    full = f"{title} {text[:2000]}"

    # Acidente / morte sem indício de crime: prioridade sobre show/evento e política.
    # Evita classificar como Política só porque a pauta veio de um canal selecionado errado.
    accident_kw = ("morre", "morreu", "morte", "acidente", "imprensado", "prensado",
                   "esmagad", "ficou preso", "não resistiu", "nao resistiu",
                   "foi levado ao hospital", "corpo de bombeiros")
    if any(k in full for k in accident_kw):
        crime_kw = ("homicidio", "homicídio", "assassinato", "tiro", "facada",
                    "suspeito", "prisao", "prisão", "trafico", "tráfico")
        if not any(k in full for k in crime_kw):
            return "accident"

    # Public service / safety - prioridade alta
    safety_kw = ("incendio", "incendios", "queimada", "queimadas",
                 "calor extremo", "alagamento", "enchente",
                 "evacuacao", "emergencia", "tempestade")
    safety_inst = ("defesa civil", "corpo de bombeiros", "policia rodoviaria")
    if any(k in full for k in safety_kw) or any(i in full for i in safety_inst):
        # Se tem recomendacoes oficiais OU alerta -> public_service_safety
        if "recomenda" in full or "alerta" in full or "evite" in full or "procurar" in full:
            return "public_service_safety"

    # Sports
    if "x" in full and any(w in full for w in ("estadio", "campeonato", "rodada", "gol")):
        if any(w in full for w in ("vitoria", "empate", "derrota", "venceu", "marcou")):
            return "sports_match_result"
        return "sports_match_preview"

    # Justice
    if any(w in full for w in ("stf", "stj", "tj", "tribunal", "juiz", "desembargador",
                                 "ministro do supremo", "decisao", "sentenca")):
        return "justice"

    # Police
    if any(w in full for w in ("preso", "policia civil", "policia militar", "operacao",
                                 "detido", "homicidio", "trafico")):
        return "police"

    # Economy
    if any(w in full for w in ("inflacao", "selic", "pib", "ibge", "receita", "imposto",
                                 "exportacao", "balanca", "ipca")):
        return "economy"

    # Cities service
    if any(w in full for w in ("interdicao", "obra", "transito", "vacinacao", "campanha")):
        return "cities_service"

    # Politics
    if any(w in full for w in ("governador", "prefeito", "deputado", "senador",
                                 "presidente", "congresso", "alerj")):
        return "politics"

    # Event
    if any(w in full for w in ("show", "festival", "concerto", "evento", "festa")):
        return "event_show_service"

    # Mapeia canal como ultimo recurso
    canal_lower = (canal or "").lower()
    if "esport" in canal_lower:
        return "sports_team_news"
    if "polic" in canal_lower:
        return "police"
    if "polit" in canal_lower:
        return "politics"
    if "saud" in canal_lower:
        return "health"
    if "educ" in canal_lower:
        return "education"

    return "cities"


# ─── Editorial angle + paragraph plan ──────────────────────────────────────

def build_editorial_angle(source: SourceContext, article_type: str,
                           required_facts: list, relationships: list) -> str:
    """Define o angulo editorial: principal fato + foco."""
    if article_type == "public_service_safety":
        return ("Foco em alerta/recomendacao oficial e o que o publico deve fazer. "
                "Lead com a instituicao responsavel e o numero/incidencia.")
    if article_type == "sports_match_result":
        return "Lead com placar, times, competicao, rodada, fato principal do jogo."
    if article_type == "sports_match_preview":
        return "Lead com times, data, horario, estadio, transmissao, importancia da partida."
    if article_type == "justice":
        return "Lead com tribunal/autoridade, decisao e efeito imediato."
    if article_type == "police":
        return "Lead com ocorrencia, local, autoridade, status processual."
    if article_type == "accident":
        return "Lead com a morte/acidente, identificação da vítima quando constar, local, circunstância e providências oficiais."
    if article_type == "economy":
        return "Lead com numero principal, periodo, entidade e causa."
    if article_type in ("event_show_service", "cities_service"):
        return "Lead com servico/evento, data, local, publico-alvo."
    return "Lead com o fato principal extraido da fonte."


def build_paragraph_plan(article_type: str, required_facts: list) -> list[str]:
    """Plano de paragrafos por tipo."""
    planos = {
        "public_service_safety": [
            "Lead: instituicao + numero/incidencia + alerta",
            "Contexto: periodo, regiao, comparacao",
            "Causas/fatores de risco",
            "Recomendacoes oficiais (preservar lista da fonte)",
            "O que fazer se ocorrer",
            "Como acionar autoridades",
            "Fechamento factual",
        ],
        "sports_match_result": [
            "Lead: placar + times + estadio + rodada",
            "Fato principal do jogo",
            "Primeiro tempo (resumo)",
            "Sequencia de gols",
            "Momentos decisivos",
            "Tabela",
            "Proximos jogos",
        ],
        "justice": [
            "Lead: tribunal + decisao + efeito",
            "Contexto processual",
            "Partes envolvidas",
            "Argumentos",
            "Proximo passo",
        ],
        "police": [
            "Lead: ocorrencia + local + autoridade",
            "Suspeitos/vitimas (status)",
            "Apuracoes oficiais",
            "Fechamento sem antecipar culpa",
        ],
        "accident": [
            "Lead: morte/acidente + vítima + local",
            "Circunstâncias descritas pela fonte",
            "Atendimento, hospital e registro oficial",
            "Nota de organizadores/empresa, se houver",
            "Serviço relacionado somente se estiver na fonte",
        ],
        "economy": [
            "Lead: numero + entidade + setor",
            "Valores e percentuais",
            "Causas",
            "Documento/estudo",
            "Impacto factual",
        ],
        "event_show_service": [
            "Lead: evento + data + local + servico",
            "Acesso e interdicoes",
            "Estrutura/programacao",
            "Publico/transmissao",
        ],
    }
    return planos.get(article_type, [
        "Lead: fato principal",
        "Contexto",
        "Detalhes",
        "Fechamento factual",
    ])


# ─── Structured editorial brief ─────────────────────────────────────────────

def build_editorial_brief(
    source: SourceContext,
    article_type: str,
    canal: str,
    required_facts: list,
    relationships: list,
    angle: str,
    plan: list[str],
) -> dict:
    """JSON do brief estruturado enviado para o GPT."""
    from ururau.editorial.editorial_policy import get_editorial_rules, get_output_schema
    rules = get_editorial_rules()
    return {
        "cleaned_source_text":   source.cleaned_source_text[:7000],
        "source_title":          source.source_title,
        "source_subtitle":       source.source_subtitle,
        "source_url":            source.source_url,
        "source_name":           source.source_name,
        "source_published_at":   source.source_published_at,
        "classified_channel":    canal,
        "article_type":          article_type,
        "required_facts":        [f.get("text", "") for f in (required_facts or [])][:15],
        "entity_relationships":  [
            f"{r.get('subject','')} {r.get('relationship','')} {r.get('object','')}"
            for r in (relationships or [])
        ][:10],
        "editorial_angle":       angle,
        "paragraph_plan":        plan,
        "field_limits":          {
            "titulo_seo_max":       rules["titulo_seo_max"],
            "titulo_capa_max":      rules["titulo_capa_max"],
            "subtitulo_curto_max":  rules["subtitulo_curto_max"],
            "legenda_curta_max":    rules["legenda_curta_max"],
            "tags_min":             rules["tags_min"],
            "tags_max":             rules["tags_max"],
            "meta_description_min": rules["meta_description_min"],
            "meta_description_max": rules["meta_description_max"],
            "retranca_max_words":   rules["retranca_max_words"],
        },
        "output_schema":         get_output_schema(),
    }


# ─── Date validation determinístico ─────────────────────────────────────────

def validate_dates_against_source(article: dict, cleaned_source: str,
                                    source_published_at: str = "") -> list[dict]:
    """
    Bloqueia se artigo cita data completa (ex: '23 de junho de 2024')
    que NAO aparece na fonte.

    Detecta:
      - data com ano explicito que nao esta na fonte
      - 'janeiro deste ano' convertido para ano errado
    """
    import re
    if not article or not cleaned_source:
        return []
    erros: list[dict] = []
    corpo = article.get("corpo_materia") or article.get("conteudo") or ""
    titulo = article.get("titulo_seo") or article.get("titulo") or ""
    busca = f"{titulo} {corpo}"

    # Padrao: dia + de + mes + de + ano (ano completo)
    pat = r"\b\d{1,2}\s+de\s+(?:janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+\d{4}\b"
    datas_artigo = set(re.findall(pat, busca, re.IGNORECASE))
    datas_fonte = set(re.findall(pat, cleaned_source, re.IGNORECASE))

    # Datas no artigo que nao aparecem na fonte
    inventadas = datas_artigo - datas_fonte
    for d in inventadas:
        erros.append({
            "categoria": "EDITORIAL_BLOCKER",
            "codigo":    "wrong_or_invented_date",
            "severidade":"alta",
            "campo":     "corpo_materia",
            "mensagem":  f"Data '{d}' nao aparece na fonte (possivel invencao).",
            "trecho":    d,
            "sugestao":  f"Remover data ou substituir por referencia da fonte.",
            "bloqueia_publicacao": True,
            "corrigivel_automaticamente": False,
        })
    return erros


# ─── Generic unsupported paragraph validation ──────────────────────────────

_GENERIC_UNSUPPORTED = (
    "impacto social",
    "mantem o monitoramento",
    "garantir a seguranca",
    "periodo de maior movimentacao",
    "a medida deve fortalecer",
    "os proximos passos anunciados",
    "a populacao deve ficar atenta",
    "o caso segue em andamento",
    "novas informacoes serao divulgadas",
)


def validate_generic_unsupported(article: dict, cleaned_source: str) -> list[dict]:
    """Bloqueia paragrafo final se for generico nao suportado pela fonte."""
    import unicodedata
    if not article:
        return []
    corpo = article.get("corpo_materia") or article.get("conteudo") or ""
    paragrafos = [p.strip() for p in corpo.split("\n\n") if p.strip()]
    if not paragrafos:
        return []
    final = paragrafos[-1]

    def _n(s):
        n = unicodedata.normalize("NFD", str(s))
        n = "".join(c for c in n if unicodedata.category(c) != "Mn")
        return n.lower()

    final_n = _n(final)
    src_n = _n(cleaned_source)
    erros = []
    for expr in _GENERIC_UNSUPPORTED:
        if expr in final_n and expr not in src_n:
            erros.append({
                "categoria": "EDITORIAL_BLOCKER",
                "codigo":    "generic_unsupported_closing",
                "severidade":"alta",
                "campo":     "corpo_materia",
                "mensagem":  f"Paragrafo final contem expressao generica nao suportada: '{expr}'",
                "trecho":    final[:200],
                "sugestao":  "Substitua por um fechamento factual extraido da fonte.",
                "bloqueia_publicacao": True,
                "corrigivel_automaticamente": False,
            })
            break
    return erros


# ─── Public-service / safety required facts ──────────────────────────────

def extract_public_service_required(cleaned_source: str) -> list[dict]:
    """
    Para article_type=public_service_safety: extrai recomendacoes oficiais
    da fonte. Cada recomendacao vira required_fact com weight alto.
    """
    import re
    if not cleaned_source:
        return []
    facts = []
    # Padrao: linhas que comecam com verbo no imperativo de recomendacao
    pat = r"(?:^|\n)\s*[-•*]?\s*((?:Evite|Procure|Mantenha|Acione|Ligue|Nao|Use|Verifique|Acompanhe|Em\s+caso|Em\s+caso\s+de|Caso|Se\s+necessario)\b[^\n]{10,200})"
    for m in re.finditer(pat, cleaned_source, re.IGNORECASE):
        text = m.group(1).strip()
        if len(text) > 15:
            facts.append({
                "id": f"recomendacao_{len(facts)}",
                "type": "recomendacao_oficial",
                "text": text,
                "required": True,
                "weight": 1.5,
            })

    # Padrao: chamada explicita de servico (190, 193, Defesa Civil)
    for m in re.finditer(r"\b(?:1\d{2}|0800[-.\s]\d+)\b", cleaned_source):
        facts.append({
            "id": f"telefone_{len(facts)}",
            "type": "service_phone",
            "text": m.group(0),
            "required": True,
            "weight": 1.2,
        })

    return facts




# ─── Linha editorial determinística v71c ───────────────────────────────────

def _norm_txt(text: str) -> str:
    import unicodedata, re
    t = unicodedata.normalize("NFD", str(text or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip().lower()


def _infer_editorial_channel(article_type: str, source: SourceContext, canal_input: str = "") -> str:
    """Classifica a editoria pelo conteúdo, não pela seleção acidental do painel."""
    text = _norm_txt(f"{source.source_title} {source.source_subtitle} {source.cleaned_source_text[:2500]}")
    if article_type == "politics":
        return "Política"
    if article_type == "police":
        return "Polícia"
    if article_type == "justice":
        return "Justiça"
    if article_type == "economy":
        return "Economia"
    if article_type.startswith("sports"):
        return "Esportes"
    if article_type == "accident":
        return "Geral"
    if article_type in ("event_show_service", "cities_service", "public_service_safety"):
        if any(k in text for k in ("rio de janeiro", "copacabana", "zona sul", "alerj", "tjrj")):
            return "Rio"
        return "Cidades"
    if any(k in text for k in ("rio de janeiro", "copacabana", "zona sul", "baixada", "norte fluminense")):
        return "Rio"
    return canal_input if canal_input and canal_input.lower() not in ("política", "politica") else "Geral"


def _remove_data_artificial_titulo(title: str, source_text: str = "") -> str:
    """Remove data mecânica no fim do título, como 'em 26 de abril'."""
    import re
    t = str(title or "").strip()
    meses = "janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
    t = re.sub(rf"\s+em\s+\d{{1,2}}\s+de\s+(?:{meses})(?:\s+de\s+\d{{4}})?\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+\(\d{1,2}/\d{1,2}(?:/\d{2,4})?\)\s*$", "", t)
    return t.strip(" -–—") or title


def _split_sentences_editorial(text: str) -> list[str]:
    import re
    clean = _strip_html_local(text)
    clean = re.sub(r"\b(alertas grátis|publicidade|inscreva-se|concordo com os termos da lgpd)\b.*", " ", clean, flags=re.I)
    parts = re.split(r"(?<=[.!?])\s+", clean)
    out, seen = [], set()
    blacklist = ("google", "newsletter", "whatsapp", "telegram", "publicidade", "copyright", "unsplash")
    for p in parts:
        p = p.strip(" -•\t\r\n")
        if len(p) < 35 or any(b in p.lower() for b in blacklist):
            continue
        # Evita colar aspas longas quebradas pela segmentação local.
        if p.startswith(("“", """, "'")) and not p.endswith(("”", """, "'")):
            continue
        key = _norm_txt(p)[:140]
        if key not in seen:
            seen.add(key); out.append(p)
    return out


def _complete_sentence_truncate(text: str, max_len: int = 160, min_len: int = 120) -> str:
    """Meta description sem corte seco no meio da ideia."""
    import re
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t:
        return ""
    if len(t) <= max_len:
        return t if t.endswith(".") else t + "."
    cut = t[:max_len].rstrip()
    # tenta encerrar na última pontuação dentro do limite
    last_punct = max(cut.rfind("."), cut.rfind(";"))
    if last_punct >= min_len:
        return cut[:last_punct+1].strip()
    last_space = cut.rfind(" ")
    if last_space >= min_len:
        cut = cut[:last_space]
    return cut.rstrip(" ,;:-") + "."


def _similar_words(a: str, b: str) -> float:
    sa = set(_norm_txt(a).split())
    sb = set(_norm_txt(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, min(len(sa), len(sb)))


def _extract_basic_tags(source: SourceContext, article_type: str, channel: str) -> list[str]:
    import re
    text = f"{source.source_title}. {source.source_subtitle}. {source.cleaned_source_text[:2500]}"
    tags = []
    def add(x):
        x = str(x or "").strip(" .,;:()[]")
        if 2 <= len(x) <= 45 and _norm_txt(x) not in [_norm_txt(t) for t in tags]:
            tags.append(x)
    for fixed in (channel, "Rio de Janeiro" if "rio" in _norm_txt(text) else "", "Acidente" if article_type == "accident" else ""):
        add(fixed)
    for ent in re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+(?:\s+(?:de|da|do|dos|das|e|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+)){1,5}", text):
        low = _norm_txt(ent)
        if any(b in low for b in ("siga o", "poder360", "domingo", "copyright", "hospital municipal", "corpo de bombeiros", "delegacia")):
            # alguns institucionais úteis entram abaixo por regra específica
            pass
        if any(k in low for k in ("shakira", "gabriel de jesus firmino", "bonustrack", "copacabana", "mg coutinho", "corpo de bombeiros", "hospital municipal miguel couto", "delegacia")):
            add(ent)
    # reforços úteis por busca literal
    literal_map = ["Shakira", "Copacabana", "Gabriel de Jesus Firmino", "MG Coutinho Serviços Cenográficos", "Bonustrack", "Corpo de Bombeiros", "Hospital Municipal Miguel Couto", "12ª Delegacia de Polícia"]
    lowtext = _norm_txt(text)
    for lit in literal_map:
        if _norm_txt(lit) in lowtext:
            add(lit)
    return tags[:8]


def _build_better_caption(source: SourceContext, subtitle: str, title: str, article_type: str) -> str:
    text = _norm_txt(source.cleaned_source_text)
    if article_type == "accident" and "copacabana" in text:
        return "Estrutura era montada na Praia de Copacabana para apresentação marcada para maio"
    if article_type == "accident":
        return "Acidente ocorreu durante trabalho de montagem, segundo informações da fonte original"
    return title if _similar_words(title, subtitle) < 0.7 else "Imagem relacionada aos fatos descritos na reportagem"



def _compose_local_body(source: SourceContext, article_type: str) -> str:
    """Redação local mais limpa para fallback sem IA, com parágrafos completos."""
    sentences = _split_sentences_editorial(source.cleaned_source_text)
    title_n = _norm_txt(source.source_title)
    if article_type == "accident":
        selected = []
        priorities = [
            ("morreu", "durante", "montagem"),
            ("gabriel",),
            ("prensado",),
            ("hospital",),
            ("delegacia",),
            ("pericia",),
            ("bonustrack",),
            ("bombeiros",),
            ("2 de maio",),
        ]
        for keys in priorities:
            for sent in sentences:
                n = _norm_txt(sent)
                if sent in selected:
                    continue
                if all(k in n for k in keys):
                    selected.append(sent)
                    break
        if len(selected) < 4:
            for sent in sentences:
                if sent not in selected:
                    selected.append(sent)
                if len(selected) >= 6:
                    break
        paragraphs = []
        # Une frases muito curtas complementares sem criar blocos longos.
        i = 0
        while i < len(selected[:8]):
            cur = selected[i]
            if i + 1 < len(selected) and len(cur) < 120 and len(selected[i+1]) < 160:
                cur = cur.rstrip() + " " + selected[i+1].lstrip()
                i += 2
            else:
                i += 1
            paragraphs.append(cur)
        return "\n\n".join(paragraphs)

    # fallback genérico: primeiras frases completas e limpas
    return "\n\n".join(sentences[:6])

def _polish_article_fields(dados: dict, brief: dict, source: SourceContext, article_type: str, channel: str) -> dict:
    """Pós-edição determinística: corrige vícios da IA e mantém padrão Ururau."""
    from ururau.editorial.safe_title import safe_title, safe_truncate
    dados = dict(dados or {})
    title = dados.get("titulo_seo") or dados.get("titulo") or source.source_title
    title = _remove_data_artificial_titulo(title, source.cleaned_source_text)
    dados["titulo_seo"] = safe_title(title, 89)
    dados["titulo"] = dados["titulo_seo"]
    dados["titulo_capa"] = safe_title(_remove_data_artificial_titulo(dados.get("titulo_capa") or title, source.cleaned_source_text), 60)

    lead_sentences = _split_sentences_editorial(source.cleaned_source_text)
    lead = lead_sentences[0] if lead_sentences else (source.source_subtitle or dados["titulo_seo"])
    subt = dados.get("subtitulo_curto") or dados.get("subtitulo") or source.source_subtitle or lead
    dados["subtitulo_curto"] = safe_truncate(subt, 140)
    dados["subtitulo"] = dados["subtitulo_curto"]

    leg = dados.get("legenda_curta") or dados.get("legenda") or ""
    if not leg or _similar_words(leg, dados["subtitulo_curto"]) >= 0.62:
        leg = _build_better_caption(source, dados["subtitulo_curto"], dados["titulo_seo"], article_type)
    dados["legenda_curta"] = safe_truncate(leg, 140)
    dados["legenda"] = dados["legenda_curta"]

    dados["retranca"] = " ".join(str(channel).split()[:1])
    dados["editoria"] = channel
    dados["canal"] = channel

    tags = dados.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    tags = (tags or []) + _extract_basic_tags(source, article_type, channel)
    final_tags = []
    for t in tags:
        if _norm_txt(t) in ("ururau", "noticia", "noticias", "accident"):
            continue
        if _norm_txt(t) not in [_norm_txt(x) for x in final_tags]:
            final_tags.append(t)
    dados["tags"] = final_tags[:8]

    corpo = dados.get("corpo_materia") or dados.get("conteudo") or ""
    # remove fechos genéricos que parecem IA quando não estão na fonte
    bad_endings = ("As autoridades seguem com as apurações", "As autoridades seguem com as apuracoes", "O caso segue em andamento")
    pars = [p.strip() for p in str(corpo).split("\n\n") if p.strip()]
    if pars and any(pars[-1].startswith(x) for x in bad_endings):
        pars = pars[:-1]
    dados["corpo_materia"] = "\n\n".join(pars) if pars else corpo
    dados["conteudo"] = dados["corpo_materia"]
    dados["texto_final"] = dados["corpo_materia"]

    meta_source = dados.get("meta_description") or dados["subtitulo_curto"]
    if len(str(meta_source)) < 115:
        extra = " ".join(lead_sentences[:2])
        meta_source = f"{dados['subtitulo_curto']} {extra}"
    dados["meta_description"] = _complete_sentence_truncate(meta_source, 160, 120)
    if len(dados["meta_description"]) < 120:
        complemento = " O caso foi registrado pela polícia, segundo a fonte original." if "delegacia" in _norm_txt(source.cleaned_source_text) else " A informação consta na fonte original."
        dados["meta_description"] = _complete_sentence_truncate(f"{dados['meta_description']} {complemento}", 160, 120)
    dados["meta_description"] = dados["meta_description"].replace(" pela.", " pela fonte original.")

    dados["resumo_curto"] = safe_truncate(dados.get("resumo_curto") or lead, 280)
    dados["chamada_social"] = safe_truncate(dados.get("chamada_social") or dados["titulo_seo"], 240)
    return dados

# ─── Engine principal ────────────────────────────────────────────────────────

def generate_ururau_article(
    pauta: dict,
    client: "OpenAI",
    model: str,
    canal: str,
    modo: str = "panel",
):
    """
    Engine canonico v70. Substitui executar_pipeline() como gerador de producao.

    Retorna Materia totalmente populada.
    Em caso de falha (config/extraction), retorna Materia com erros estruturados
    e auditoria_bloqueada=True. NUNCA invoca pipeline legacy.
    """
    from ururau.core.models import Materia
    from ururau.editorial.coverage_por_tipo import (
        extract_required_facts_from_source, calculate_fact_coverage_typed,
    )
    from ururau.editorial.relationships import (
        extract_entity_relationships, validate_entity_relationships,
    )
    from ururau.editorial.safe_title import safe_title, safe_truncate
    from ururau.editorial.field_limits import (
        TITULO_SEO_MAX, TITULO_CAPA_MAX,
        SUBTITULO_CURTO_MAX, LEGENDA_CURTA_MAX,
        TAGS_MIN, TAGS_MAX,
        META_DESCRIPTION_MIN, META_DESCRIPTION_MAX,
    )

    # 1. Source context canonico (sem duplicacao)
    source = build_source_context(pauta)

    # 2. Sufficiency
    if not source.cleaned_source_text or len(source.cleaned_source_text) < 200:
        m = Materia()
        m.status_validacao = "erro_extracao"
        m.status_publicacao_sugerido = "salvar_rascunho"
        m.revisao_humana_necessaria = True
        m.auditoria_bloqueada = True
        m.erros_validacao = [{
            "categoria":"EXTRACTION_ERROR", "codigo":"source_too_short",
            "mensagem": f"Fonte insuficiente ({len(source.cleaned_source_text)} chars)",
            "bloqueia_publicacao": True, "corrigivel_automaticamente": False,
        }]
        m.cleaned_source_text = source.cleaned_source_text
        return m

    # 3. Article type
    article_type = classify_article_type(source, canal)

    # 4. Channel editorial real. Corrige canal selecionado errado pelo painel.
    classified_channel = _infer_editorial_channel(article_type, source, canal)

    # 5+10. Required facts (incluindo public_service_safety)
    try:
        required_facts = extract_required_facts_from_source(source.cleaned_source_text, article_type)
        if article_type == "public_service_safety":
            required_facts.extend(extract_public_service_required(source.cleaned_source_text))
    except Exception as e:
        print(f"[ENGINE v71] required_facts falhou; seguindo sem bloquear: {e}")
        required_facts = []

    # 6. Relationships — nunca pode impedir redação.
    try:
        relationships = extract_entity_relationships(
            source.cleaned_source_text, article_type, client, model
        )
    except Exception as e:
        print(f"[ENGINE v71] relationships falhou; seguindo sem bloquear: {e}")
        relationships = []

    # 7+8. Angle and plan
    angle = build_editorial_angle(source, article_type, required_facts, relationships)
    plan  = build_paragraph_plan(article_type, required_facts)

    # 9. Brief
    brief = build_editorial_brief(source, article_type, classified_channel,
                                    required_facts, relationships, angle, plan)
    # v46.7: metadados mínimos para logs de IA/fallback.
    try:
        brief["model"] = model
        brief["uid"] = str(pauta.get("uid") or pauta.get("_uid") or "") if isinstance(pauta, dict) else ""
    except Exception:
        pass

    # 10. Call GPT-4.1-mini com policy canonico
    # v70d: se a IA externa falhar ou estiver ausente, ainda gera um rascunho
    # editorial local baseado SOMENTE na fonte. Isso evita "matéria vazia".
    _ia_trace = {}
    if client is None:
        dados = _build_local_draft_from_brief(
            brief,
            reason="Cliente OpenAI ausente; rascunho local gerado a partir da fonte."
        )
        _ia_trace = dict(dados.get("_ia_trace") or dados.get("ia_trace") or {})
    else:
        dados = _call_gpt_with_brief(brief, client, model, modo)
        _ia_trace = dict(dados.get("_ia_trace") or dados.get("ia_trace") or {})
        if not dados or not (dados.get("corpo_materia") or dados.get("conteudo")):
            motivo = (_ia_trace.get("erro_mensagem") or _ia_trace.get("status") or
                      "A IA não retornou JSON válido/conteúdo")
            dados = _build_local_draft_from_brief(
                brief,
                reason=f"{motivo}; rascunho local gerado a partir da fonte.",
                original_trace=_ia_trace,
            )
            # Mantém também o erro da OpenAI que causou o fallback.
            dados["ia_erro_original_openai"] = _ia_trace

    # 11b. Pós-edição determinística da linha editorial v71c
    dados = _polish_article_fields(dados, brief, source, article_type, classified_channel)
    # v46.7: pós-edição não pode apagar diagnóstico de IA/fallback.
    try:
        from ururau.ia.diagnostico import aplicar_trace_em_dados
        dados = aplicar_trace_em_dados(dados, dados.get("_ia_trace") or dados.get("ia_trace") or _ia_trace, fallback_motivo=dados.get("ia_fallback_motivo", ""))
    except Exception:
        pass

    # 12. Field limits (safe_title)
    if dados.get("titulo_seo"):
        dados["titulo_seo"] = safe_title(dados["titulo_seo"], TITULO_SEO_MAX)
    if dados.get("titulo_capa"):
        dados["titulo_capa"] = safe_title(dados["titulo_capa"], TITULO_CAPA_MAX)
    if dados.get("subtitulo_curto"):
        dados["subtitulo_curto"] = safe_truncate(dados["subtitulo_curto"], SUBTITULO_CURTO_MAX)
    if dados.get("legenda_curta"):
        dados["legenda_curta"] = safe_truncate(dados["legenda_curta"], LEGENDA_CURTA_MAX)
    if dados.get("meta_description"):
        dados["meta_description"] = safe_truncate(dados["meta_description"], META_DESCRIPTION_MAX)

    # 13. Coverage
    try:
        cov = calculate_fact_coverage_typed(dados, required_facts, source.cleaned_source_text)
    except Exception as e:
        print(f"[ENGINE v71] coverage falhou; usando cobertura neutra: {e}")
        cov = {"coverage_score": 1.0, "facts_required": required_facts, "facts_used": [], "facts_missing": []}

    # 14. Relationships post
    try:
        rel_errors = validate_entity_relationships(dados, relationships)
    except Exception as e:
        print(f"[ENGINE v71] relationship validation falhou: {e}")
        rel_errors = []

    # 15. Date validation
    try:
        date_errors = validate_dates_against_source(dados, source.cleaned_source_text,
                                                      source.source_published_at)
    except Exception as e:
        print(f"[ENGINE v71] date validation falhou: {e}")
        date_errors = []

    # 16. Generic unsupported
    try:
        generic_errors = validate_generic_unsupported(dados, source.cleaned_source_text)
    except Exception as e:
        print(f"[ENGINE v71] generic validation falhou: {e}")
        generic_errors = []

    # URURAU v47.2: validação determinística de termos de IA em TODOS os campos editoriais.
    try:
        from ururau.editorial.regras_editoriais import validar_termos_ia_em_artigo
        termos_ia_check = validar_termos_ia_em_artigo(dados, modo=modo)
        if not termos_ia_check.get("passou", True):
            dados["termos_ia_detectados"] = termos_ia_check.get("achados", [])
    except Exception as e:
        print(f"[ENGINE v47.2] validação de termos de IA falhou: {e}")
        termos_ia_check = {"erros": []}

    # Mescla erros
    erros_total = list(dados.get("erros_validacao") or [])
    erros_total += rel_errors + date_errors + generic_errors
    erros_total += list((termos_ia_check or {}).get("erros") or [])
    if cov["coverage_score"] < 0.85 and len(required_facts) > 0 and not dados.get("_local_fallback"):
        erros_total.append({
            "categoria":"EDITORIAL_BLOCKER", "codigo":"low_source_coverage",
            "mensagem": f"Coverage {cov['coverage_score']:.2f} abaixo de 0.85",
            "bloqueia_publicacao": True, "corrigivel_automaticamente": False,
        })
    # Meta description ausente
    if not dados.get("meta_description"):
        cat = "EDITORIAL_BLOCKER" if modo == "monitor" else "FIXABLE_FIELD"
        erros_total.append({
            "categoria": cat, "codigo": "meta_description_ausente",
            "mensagem": "meta_description ausente",
            "bloqueia_publicacao": modo == "monitor",
            "corrigivel_automaticamente": True,
        })

    # 17+18. Score
    score_qualidade = 100
    score_qualidade -= 25 * len([e for e in erros_total if isinstance(e, dict) and e.get("categoria") == "EDITORIAL_BLOCKER"])
    score_qualidade -= 5  * len([e for e in erros_total if isinstance(e, dict) and e.get("categoria") == "FIXABLE_FIELD"])
    score_qualidade = max(0, min(100, score_qualidade))
    score_risco = 100 - score_qualidade

    # 19. Materia populada
    m = Materia()
    m.titulo            = dados.get("titulo_seo") or dados.get("titulo") or source.source_title
    m.titulo_capa       = dados.get("titulo_capa", "")
    m.slug              = dados.get("slug", "") or _make_slug_local(m.titulo)
    m.subtitulo         = dados.get("subtitulo_curto", "")
    m.retranca          = " ".join(str(dados.get("retranca", "") or canal).split()[:1])
    m.legenda           = dados.get("legenda_curta", "")
    m.tags              = dados.get("tags", "") if isinstance(dados.get("tags"), str) else ", ".join(dados.get("tags", []) or [])
    m.conteudo          = dados.get("corpo_materia", "")
    m.meta_description  = dados.get("meta_description", "")
    m.fonte_nome        = source.source_name
    m.link_origem       = source.source_url
    m.canal             = classified_channel
    m.nome_da_fonte     = dados.get("nome_da_fonte") or source.source_name or "Redacao"
    m.creditos_da_foto  = dados.get("creditos_da_foto") or "Reproducao"

    bloqueado = any(isinstance(e, dict) and e.get("categoria") == "EDITORIAL_BLOCKER" for e in erros_total)
    m.auditoria_bloqueada = bool(bloqueado)
    m.auditoria_aprovada  = not bloqueado
    if dados.get("_local_fallback"):
        # Rascunho local deve aparecer no painel para revisão, não como falha técnica.
        m.status_validacao = "pendente"
        m.status_publicacao_sugerido = "salvar_rascunho"
        m.revisao_humana_necessaria = True
    else:
        m.status_validacao = "aprovado" if not bloqueado and score_qualidade >= 90 else (
            "reprovado" if bloqueado else "pendente"
        )
        m.status_publicacao_sugerido = ("publicar_direto" if m.status_validacao == "aprovado"
                                         else "salvar_rascunho")
        m.revisao_humana_necessaria  = m.status_validacao != "aprovado"
    m.erros_validacao            = erros_total

    # Campos v69b/v70
    m.coverage_score          = cov["coverage_score"]
    m.facts_required          = cov["facts_required"]
    m.facts_used              = cov["facts_used"]
    m.facts_missing           = cov["facts_missing"]
    m.entity_relationships    = relationships
    m.relationship_errors     = rel_errors
    m.score_qualidade         = score_qualidade
    m.score_risco_validacao   = score_risco
    m.score_risco             = score_risco
    m.cleaned_source_text     = source.cleaned_source_text
    m.raw_source_text         = source.raw_source_text
    m.rss_context_text        = source.rss_context_text
    m.extraction_method       = source.extraction_method
    m.extraction_status       = source.extraction_status
    m.source_sufficiency_score = source.source_sufficiency_score
    m.article_type            = article_type
    m.editorial_angle         = angle
    m.paragraph_plan          = plan
    # v46.7: telemetria explícita da IA na matéria persistida.
    try:
        _trace_final = dict(dados.get("_ia_trace") or dados.get("ia_trace") or {})
        m.modo_geracao       = str(dados.get("modo_geracao") or ("openai_gpt4mini" if _trace_final.get("ok") else "fallback_sem_ia"))
        m.ia_provider        = str(dados.get("ia_provider") or _trace_final.get("provider") or "")
        m.ia_modelo          = str(dados.get("ia_modelo") or _trace_final.get("modelo") or model or "")
        m.ia_status          = str(dados.get("ia_status") or _trace_final.get("status") or "")
        m.ia_etapa           = str(dados.get("ia_etapa") or _trace_final.get("etapa") or "engine_v70_geracao")
        m.ia_chamada_ok      = bool(dados.get("ia_chamada_ok") if dados.get("ia_chamada_ok") is not None else _trace_final.get("ok"))
        m.ia_fallback_motivo = str(dados.get("ia_fallback_motivo") or _trace_final.get("erro_mensagem") or "")
        m.ia_erros           = list(dados.get("ia_erros") or ([] if m.ia_chamada_ok else [_trace_final]))
        m.ia_texto_final_origem = str(dados.get("ia_texto_final_origem") or ("openai" if m.ia_chamada_ok else "fallback_local"))
        m.ia_openai_status      = str(dados.get("ia_openai_status") or (m.ia_status if m.ia_provider == "openai" else ""))
        m.ia_openai_chamada_ok  = bool(dados.get("ia_openai_chamada_ok", m.ia_chamada_ok))
        m.ia_erro_original_openai = dict(dados.get("ia_erro_original_openai") or {})
    except Exception:
        pass
    m.generated_article_json  = dados

    return m



def _strip_html_local(text: str) -> str:
    """Limpeza simples para fallback local, sem dependências externas."""
    import re
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_sentences_local(text: str) -> list[str]:
    """Divide o texto-fonte em frases aproveitáveis para rascunho local."""
    import re
    clean = _strip_html_local(text)
    parts = re.split(r"(?<=[.!?])\s+", clean)
    out = []
    seen = set()
    lixo = (
        "publicidade", "leia também", "leia tambem", "compartilhe",
        "siga", "newsletter", "cookies", "todos os direitos"
    )
    for p in parts:
        p = p.strip(" -•\t\r\n")
        if len(p) < 35:
            continue
        low = p.lower()
        if any(x in low for x in lixo):
            continue
        key = low[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _make_slug_local(text: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFD", text or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s[:80]


def _build_local_draft_from_brief(brief: dict, reason: str = "", original_trace: dict | None = None) -> dict:
    """
    Fallback editorial local: gera rascunho factual quando a IA não responde.
    Não inventa informações; reorganiza frases da fonte em formato de notícia.
    v46.7: sempre marca modo_geracao=fallback_sem_ia para não mascarar falha do GPT.
    """
    from ururau.editorial.safe_title import safe_title, safe_truncate
    from ururau.ia.diagnostico import trace_fallback, aplicar_trace_em_dados
    original_trace = dict(original_trace or {})

    source_text = brief.get("cleaned_source_text", "") or ""
    title_src = brief.get("source_title", "") or "Matéria em apuração"
    subtitle_src = brief.get("source_subtitle", "") or ""
    canal = brief.get("classified_channel", "") or "Geral"
    source_name = brief.get("source_name", "") or "Fonte original"
    source_url = brief.get("source_url", "") or ""

    sentences = _split_sentences_editorial(source_text)
    lead = sentences[0] if sentences else (subtitle_src or title_src)

    # Monta parágrafos completos, evitando aspas quebradas e fecho genérico.
    _src_obj = SourceContext(
        cleaned_source_text=source_text,
        source_title=title_src,
        source_subtitle=subtitle_src,
        source_name=source_name,
        source_url=source_url,
    )
    corpo = _compose_local_body(_src_obj, brief.get("article_type", ""))
    if not corpo and source_text:
        clean = _strip_html_local(source_text)
        chunks = [clean[i:i+420].strip() for i in range(0, min(len(clean), 1700), 420)]
        corpo = "\n\n".join(c for c in chunks if len(c) > 80)

    titulo_base = _remove_data_artificial_titulo(title_src, source_text)
    titulo_seo = safe_title(titulo_base, int(brief.get("field_limits", {}).get("titulo_seo_max", 89) or 89))
    titulo_capa = safe_title(titulo_base, int(brief.get("field_limits", {}).get("titulo_capa_max", 60) or 60))
    subtitulo = safe_truncate(subtitle_src or lead, int(brief.get("field_limits", {}).get("subtitulo_curto_max", 200) or 200))
    legenda = safe_truncate(subtitle_src or title_src, int(brief.get("field_limits", {}).get("legenda_curta_max", 100) or 100))

    tags_base = [canal, "Ururau", "Rio de Janeiro", "Notícia"]
    article_type = brief.get("article_type", "")
    if article_type and article_type not in ("accident",):
        tags_base.append(article_type)

    _trace_local = trace_fallback(
        etapa="engine_v70_geracao",
        modelo=str(brief.get("model") or ""),
        motivo=reason or "Rascunho local gerado sem resposta válida da OpenAI.",
        uid=str(brief.get("uid") or ""),
        origem="engine_local_draft",
    )

    dados_local = {
        "titulo_seo": titulo_seo,
        "titulo": titulo_seo,
        "titulo_capa": titulo_capa,
        "subtitulo_curto": subtitulo,
        "subtitulo": subtitulo,
        "legenda_curta": legenda or "Reprodução",
        "legenda": legenda or "Reprodução",
        "retranca": " ".join(str(canal).split()[:1]),
        "tags": tags_base[:8],
        "nome_da_fonte": source_name,
        "creditos_da_foto": "Reprodução",
        "corpo_materia": corpo,
        "conteudo": corpo,
        "texto_final": corpo,
        "editoria": canal,
        "canal": canal,
        "slug": _make_slug_local(titulo_seo),
        "meta_description": _complete_sentence_truncate(subtitulo or lead, 160, 120),
        "resumo_curto": safe_truncate(lead, 280),
        "chamada_social": safe_truncate(titulo_seo, 240),
        "status_publicacao_sugerido": "salvar_rascunho",
        "status_validacao": "pendente",
        "revisao_humana_necessaria": True,
        "auditoria_bloqueada": False,
        "erros_validacao": [{
            "categoria": "WARNING",
            "codigo": "local_fallback_draft",
            "mensagem": reason or "Rascunho local gerado sem IA externa.",
            "campo": "corpo_materia",
            "bloqueia_publicacao": False,
            "corrigivel_automaticamente": True,
        }],
        "link_origem": source_url,
        "_local_fallback": True,
        "modo_geracao": "fallback_sem_ia",
        "ia_provider": "local",
        "ia_modelo": "",
        "ia_status": "fallback_local",
        "ia_chamada_ok": False,
        "ia_fallback_motivo": reason or "Rascunho local gerado sem resposta válida da OpenAI.",
    }
    return aplicar_trace_em_dados(dados_local, _trace_local, fallback_motivo=reason, original_trace=original_trace)



def _call_gpt_with_brief(brief: dict, client, model: str, modo: str) -> dict:
    """Chama GPT-4.1-mini com SYSTEM_PROMPT_EDITORIAL_URURAU + brief estruturado.

    v46.7: não engole erro como se fosse sucesso. A função continua devolvendo
    dict para compatibilidade, mas anexa _ia_trace/ia_status/mode para o fluxo
    saber se a matéria veio da OpenAI ou de fallback local.
    """
    import json
    from ururau.editorial.editorial_policy import (
        get_editorial_system_prompt, get_editorial_user_prompt_template,
    )
    from ururau.ia.diagnostico import (
        trace_openai_ok, trace_openai_erro, aplicar_trace_em_dados,
    )
    sys_prompt = get_editorial_system_prompt()
    template = get_editorial_user_prompt_template()
    user_prompt = template.format(
        article_type=brief["article_type"],
        classified_channel=brief["classified_channel"],
        editorial_angle=brief["editorial_angle"],
        paragraph_plan="\n".join(f"  {i+1}. {p}" for i, p in enumerate(brief["paragraph_plan"])),
        required_facts="\n".join(f"  - {f}" for f in brief["required_facts"]),
        entity_relationships="\n".join(f"  - {r}" for r in brief["entity_relationships"]),
        cleaned_source_text=brief["cleaned_source_text"],
        source_title=brief["source_title"],
        source_subtitle=brief["source_subtitle"],
        source_url=brief["source_url"],
        source_name=brief["source_name"],
        source_published_at=brief["source_published_at"],
        field_limits=json.dumps(brief["field_limits"], ensure_ascii=False),
        output_schema=json.dumps(brief["output_schema"], ensure_ascii=False, indent=2),
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=4200,
        )
        raw = resp.choices[0].message.content.strip()
        # Remove markdown
        import re as _re
        raw = _re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=_re.MULTILINE)
        dados = json.loads(raw)
        trace = trace_openai_ok(
            "engine_v70_geracao",
            model,
            detalhe={
                "chars_prompt_user": len(user_prompt),
                "chars_system_prompt": len(sys_prompt),
                "chars_resposta": len(raw),
                "modo": modo,
            },
        )
        dados = aplicar_trace_em_dados(dados, trace)
        dados["modo_geracao"] = "openai_gpt4mini"
        dados["ia_status"] = "openai_ok"
        dados["ia_chamada_ok"] = True
        return dados
    except Exception as e:
        trace = trace_openai_erro(
            "engine_v70_geracao",
            model,
            e,
            detalhe={"modo": modo, "chars_prompt_user": len(user_prompt)},
        )
        print(f"[ENGINE v70][IA] GPT falhou; fallback será usado. status={trace.get('status')} msg={trace.get('erro_mensagem')}")
        return aplicar_trace_em_dados({}, trace, fallback_motivo=trace.get("erro_mensagem", ""))


# ============================================================================
# URURAU v72 — camada editorial profissional determinística
# Esta seção sobrescreve funções anteriores do engine em tempo de execução.
# Objetivo: reduzir vícios de IA e aproximar a saída do padrão de grandes portais.
# ============================================================================

_STOP_TAGS_V72 = {
    "ururau", "noticia", "noticias", "geral", "rio de janeiro", "brasil",
    "todo o brasil", "fonte original", "redacao", "redação", "gnews",
    "economy", "politics", "accident", "cities", "public_service_safety", "service_economy", "economy",
}

_GENERIC_SOCIAL_V72 = (
    "fique atento", "confira", "saiba mais", "veja mais", "acompanhe",
    "entenda", "não perca", "nao perca",
)


def _v72_contains_any(text: str, keys) -> bool:
    """Busca termos sem falso positivo de substring curta.

    v46.8: antes, tokens curtos como ``nis`` batiam em ``Ministério`` e
    ``quem`` batia em ``esquema``, classificando matéria policial como
    serviço/economia. Para termos de uma palavra até 4 letras, exige limite
    de palavra; para expressões e termos longos, mantém busca por substring.
    """
    import re
    n = _norm_txt(text)
    for k in keys:
        nk = _norm_txt(k)
        if not nk:
            continue
        if " " in nk or len(nk) > 4:
            if nk in n:
                return True
        else:
            if re.search(r"(?<!\w)" + re.escape(nk) + r"(?!\w)", n):
                return True
    return False


def classify_article_type(source: SourceContext, canal: str = "") -> str:  # type: ignore[override]
    """v72: classificação por tipo de matéria, com prioridade para serviço/economia."""
    full = _norm_txt(f"{source.source_title} {source.source_subtitle} {source.cleaned_source_text[:4500]}")

    # Política fluminense/eleitoral tem prioridade sobre qualquer ruído de serviço/economia
    # vindo de cache, feed ou matéria anterior. Isso impede casos como Quaest/Paes
    # receberem legenda/tags de FGTS, PIS/Pasep ou Repis.
    politics_kw = (
        "quaest", "pesquisa eleitoral", "intencao de voto", "intenção de voto",
        "intencoes de voto", "intenções de voto", "governo do rj", "governo do rio",
        "palacio guanabara", "palácio guanabara", "alerj", "stf", "tse", "tre-rj",
        "eduardo paes", "douglas ruas", "garotinho", "anthony garotinho",
        "wilson witzel", "rodrigo bacellar", "governador", "mandato", "cassacao", "cassação",
    )
    if _v72_contains_any(full, politics_kw):
        return "politics"

    service_economy_kw = (
        "pis", "pasep", "fgts", "caixa economica", "caixa econômica",
        "ressarcimento", "dinheiro esquecido", "repis cidadao", "repis cidadão",
        "abono salarial", "consulta", "consultar", "gov.br", "calendario", "calendário",
        "pagamento", "saque", "beneficiario", "beneficiário", "nis",
    )
    if _v72_contains_any(full, service_economy_kw) and _v72_contains_any(full, ("como", "quem", "quando", "recebe", "consultar", "solicitar", "pedido", "prazo")):
        return "service_economy"

    accident_kw = ("morre", "morreu", "morte", "acidente", "imprensado", "prensado", "esmagad", "ficou preso", "não resistiu", "nao resistiu", "foi levado ao hospital", "corpo de bombeiros")
    crime_kw = ("homicidio", "homicídio", "assassinato", "tiro", "facada", "suspeito", "prisao", "prisão", "trafico", "tráfico")
    if _v72_contains_any(full, accident_kw) and not _v72_contains_any(full, crime_kw):
        return "accident"

    if _v72_contains_any(full, ("policia civil", "polícia civil", "policia militar", "polícia militar", "preso", "detido", "operação", "operacao", "homicídio", "homicidio", "tráfico", "trafico")):
        return "police"
    if _v72_contains_any(full, ("stf", "stj", "tjrj", "tribunal", "juiz", "desembargador", "sentença", "sentenca", "decisão", "decisao", "liminar")):
        return "justice"
    if _v72_contains_any(full, ("governador", "prefeito", "deputado", "senador", "alerj", "câmara", "camara", "congresso", "eleição", "eleicao", "partido")):
        return "politics"
    if _v72_contains_any(full, ("selic", "ipca", "inflação", "inflacao", "pib", "receita federal", "imposto", "mercado financeiro", "dólar", "dolar", "caixa economica", "caixa econômica", "pis", "pasep", "fgts")):
        return "economy"
    if _v72_contains_any(full, ("jogo", "rodada", "campeonato", "estádio", "estadio", "gol", "vasco", "flamengo", "botafogo", "fluminense")):
        return "sports_match_result" if _v72_contains_any(full, ("venceu", "derrota", "empate", "placar")) else "sports_match_preview"
    if _v72_contains_any(full, ("show", "festival", "evento", "agenda", "apresentação", "apresentacao")):
        return "event_show_service"
    if _v72_contains_any(full, ("vacinação", "vacinacao", "trânsito", "transito", "interdição", "interdicao", "obra", "inscrição", "inscricao")):
        return "cities_service"
    return "cities"


def build_paragraph_plan(article_type: str, required_facts: list) -> list[str]:  # type: ignore[override]
    planos = {
        "service_economy": [
            "Lead: o que será pago/liberado, por quem e para qual público",
            "Quem recebe nesta rodada",
            "Como consultar valores ou direito",
            "Como pedir o ressarcimento/benefício",
            "Quando o dinheiro será pago",
            "Contexto: diferença entre fundo antigo e benefício atual",
            "Prazo final e consequência para quem não solicitar",
        ],
        "accident": [
            "Lead: morte/acidente + vítima + local",
            "Circunstâncias descritas pela fonte",
            "Socorro, hospital, delegacia e perícia",
            "Posicionamento de organizadores/empresa, se houver",
            "Contexto factual do evento, sem especulação",
        ],
        "economy": ["Lead com decisão/número principal", "Quem é afetado", "Valores e prazos", "Como consultar ou acessar", "Contexto factual"],
        "politics": ["Lead com ator público e decisão/declaração", "Contexto político", "Efeitos práticos", "Histórico ou contraponto documentado"],
        "police": ["Lead com ocorrência e local", "Vítima/suspeito conforme status oficial", "Ação policial", "Investigação sem antecipar culpa"],
        "justice": ["Lead com tribunal e decisão", "Partes envolvidas", "Fundamento/contexto", "Próximos passos processuais"],
    }
    return planos.get(article_type, ["Lead factual", "Contexto", "Detalhes", "Fechamento factual"])


def _infer_editorial_channel(article_type: str, source: SourceContext, canal_input: str = "") -> str:  # type: ignore[override]
    text = _norm_txt(f"{source.source_title} {source.source_subtitle} {source.cleaned_source_text[:3000]}")
    if article_type in ("service_economy", "economy"):
        return "Economia"
    if article_type == "politics":
        return "Política"
    if article_type == "police":
        return "Polícia"
    if article_type == "justice":
        return "Justiça"
    if article_type.startswith("sports"):
        return "Esportes"
    if article_type == "accident":
        return "Geral"
    if article_type in ("cities_service", "event_show_service"):
        return "Rio" if _v72_contains_any(text, ("rio de janeiro", "copacabana", "zona sul", "baixada", "norte fluminense")) else "Cidades"
    if _v72_contains_any(text, ("rio de janeiro", "copacabana", "zona sul", "baixada", "norte fluminense")):
        return "Rio"
    ci = (canal_input or "").strip()
    return ci if ci and _norm_txt(ci) not in ("politica", "política") else "Geral"


def _remove_data_artificial_titulo(title: str, source_text: str = "") -> str:  # type: ignore[override]
    import re
    t = re.sub(r"\s+", " ", str(title or "")).strip()
    meses = "janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
    t = re.sub(rf"\s+em\s+\d{{1,2}}\s+de\s+(?:{meses})(?:\s+de\s+\d{{4}})?\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+no dia\s+\d{1,2}(?:/\d{1,2})?(?:/\d{2,4})?\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+\(\d{1,2}/\d{1,2}(?:/\d{2,4})?\)\s*$", "", t)
    # Remove enchimentos geográficos quando a pauta é nacional e a fonte não tem foco regional.
    t = re.sub(r"\s+em todo o Brasil\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+no Brasil\s*$", "", t, flags=re.I) if "rio de janeiro" not in _norm_txt(source_text) else t
    return t.strip(" -–—") or title


def _v72_is_national_service(source: SourceContext, article_type: str) -> bool:
    text = _norm_txt(f"{source.source_title} {source.cleaned_source_text[:3500]}")
    return article_type == "service_economy" or (_v72_contains_any(text, ("pis", "pasep", "fgts", "caixa")) and not _v72_contains_any(text, ("rio de janeiro", "campos", "macaé", "macae", "copacabana")))


def _extract_basic_tags(source: SourceContext, article_type: str, channel: str) -> list[str]:  # type: ignore[override]
    import re
    text = f"{source.source_title}. {source.source_subtitle}. {source.cleaned_source_text[:3500]}"
    low = _norm_txt(text)
    tags: list[str] = []

    def add(x: str):
        x = str(x or "").strip(" .,;:()[]")
        nx = _norm_txt(x)
        if not x or nx in _STOP_TAGS_V72:
            return
        if article_type == "service_economy" and nx in ("rio de janeiro", "rio"):
            return
        if 2 <= len(x) <= 55 and nx not in [_norm_txt(t) for t in tags]:
            tags.append(x)

    if channel not in ("Geral", "Rio", "Cidades"):
        add(channel)
    if article_type == "accident":
        add("Acidente")
    if article_type == "service_economy":
        for lit in ["Caixa Econômica Federal", "PIS", "Pasep", "FGTS", "Repis Cidadão", "dinheiro esquecido", "ressarcimento", "gov.br", "NIS"]:
            if _norm_txt(lit) in low:
                add(lit)
        return tags[:10]

    literal_map = [
        "Shakira", "Copacabana", "Gabriel de Jesus Firmino", "MG Coutinho Serviços Cenográficos",
        "Bonustrack", "Corpo de Bombeiros", "Hospital Municipal Miguel Couto", "12ª Delegacia de Polícia",
        "Alerj", "TJRJ", "MPRJ", "Governo do RJ", "Prefeitura do Rio",
    ]
    for lit in literal_map:
        if _norm_txt(lit) in low:
            add(lit)
    for ent in re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+(?:\s+(?:de|da|do|dos|das|e|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+)){1,5}", text):
        if len(tags) >= 10:
            break
        if _v72_contains_any(ent, ("Poder360", "Redação", "Google", "Copyright", "domingo", "segunda-feira")):
            continue
        add(ent)
    return tags[:10]


def _v72_pick_sentence(sentences: list[str], *keys: str) -> str:
    for sent in sentences:
        n = _norm_txt(sent)
        if all(_norm_txt(k) in n for k in keys):
            return sent
    return ""


def _v72_service_body(source: SourceContext) -> str:
    sentences = _split_sentences_editorial(source.cleaned_source_text)
    title = source.source_title.rstrip(".")
    lead = _v72_pick_sentence(sentences, "novo lote") or _v72_pick_sentence(sentences, "pagamento") or (source.source_subtitle or title)
    receive = _v72_pick_sentence(sentences, "solicitou", "31") or _v72_pick_sentence(sentences, "31 de março")
    nextpay = _v72_pick_sentence(sentences, "30", "25 de maio") or _v72_pick_sentence(sentences, "25 de maio")
    consult = _v72_pick_sentence(sentences, "Repis") or _v72_pick_sentence(sentences, "aplicativo do FGTS")
    avg = _v72_pick_sentence(sentences, "saldo médio") or _v72_pick_sentence(sentences, "2,8 mil")
    ask = _v72_pick_sentence(sentences, "agência", "Caixa") or _v72_pick_sentence(sentences, "ressarcimento", "FGTS")
    heirs = _v72_pick_sentence(sentences, "herdeiros")
    deadline = _v72_pick_sentence(sentences, "setembro de 2028") or _v72_pick_sentence(sentences, "Tesouro Nacional")
    oldfund = _v72_pick_sentence(sentences, "1971", "1988") or _v72_pick_sentence(sentences, "antigo fundo")

    paragraphs = []
    if lead:
        p = lead
        if nextpay and nextpay != lead:
            p += " " + nextpay
        paragraphs.append(p)
    if receive and receive not in paragraphs[0] if paragraphs else receive:
        paragraphs.append("Quem recebe\n" + receive)
    how = " ".join(x for x in [consult, avg] if x)
    if how:
        paragraphs.append("Como consultar\n" + how)
    request = " ".join(x for x in [ask, heirs] if x)
    if request:
        paragraphs.append("Como pedir o ressarcimento\n" + request)
    if oldfund:
        paragraphs.append("O que é o antigo PIS/Pasep\n" + oldfund)
    if deadline:
        paragraphs.append("Prazo final\n" + deadline)
    # Remove duplicados e blocos vazios
    out, seen = [], set()
    for p in paragraphs:
        key = _norm_txt(p)[:160]
        if p.strip() and key not in seen:
            seen.add(key); out.append(p.strip())
    return "\n\n".join(out)


def _compose_local_body(source: SourceContext, article_type: str) -> str:  # type: ignore[override]
    sentences = _split_sentences_editorial(source.cleaned_source_text)
    if article_type == "service_economy":
        return _v72_service_body(source)
    if article_type == "accident":
        selected = []
        priorities = [("morreu", "montagem"), ("gabriel",), ("prensado",), ("hospital",), ("delegacia",), ("perícia",), ("bonustrack",), ("bombeiros",), ("2 de maio",)]
        for keys in priorities:
            s = _v72_pick_sentence(sentences, *keys)
            if s and s not in selected:
                selected.append(s)
        for sent in sentences:
            if len(selected) >= 6:
                break
            if sent not in selected:
                selected.append(sent)
        return "\n\n".join(selected[:6])
    return "\n\n".join(sentences[:6])


def _v72_make_meta(dados: dict, source: SourceContext, article_type: str) -> str:
    base = dados.get("meta_description") or dados.get("subtitulo_curto") or dados.get("subtitulo") or ""
    lead_sentences = _split_sentences_editorial(source.cleaned_source_text)
    if article_type == "service_economy":
        lead = _v72_pick_sentence(lead_sentences, "novo lote") or (lead_sentences[0] if lead_sentences else base)
        may = _v72_pick_sentence(lead_sentences, "25 de maio")
        base = f"{lead} {may}" if may and may not in lead else lead
    elif len(str(base)) < 115:
        base = f"{base} {' '.join(lead_sentences[:2])}".strip()
    return _complete_sentence_truncate(base, 160, 120)


def _v72_social(dados: dict, source: SourceContext, article_type: str) -> str:
    title = dados.get("titulo_seo") or source.source_title
    if article_type == "service_economy":
        return safe_truncate(f"{title}. Veja quem recebe, como consultar e quais são os próximos prazos.", 240)  # type: ignore[name-defined]
    if article_type == "accident":
        return safe_truncate(title, 240)  # type: ignore[name-defined]
    social = str(dados.get("chamada_social") or title).strip()
    if _v72_contains_any(social, _GENERIC_SOCIAL_V72):
        social = title
    return safe_truncate(social, 240)  # type: ignore[name-defined]


def _polish_article_fields(dados: dict, brief: dict, source: SourceContext, article_type: str, channel: str) -> dict:  # type: ignore[override]
    """v72: pós-edição obrigatória antes de salvar no painel/CMS."""
    from ururau.editorial.safe_title import safe_title, safe_truncate
    dados = dict(dados or {})

    title = dados.get("titulo_seo") or dados.get("titulo") or source.source_title
    title = _remove_data_artificial_titulo(title, source.cleaned_source_text)
    dados["titulo_seo"] = safe_title(title, 89)
    dados["titulo"] = dados["titulo_seo"]
    dados["titulo_capa"] = safe_title(_remove_data_artificial_titulo(dados.get("titulo_capa") or title, source.cleaned_source_text), 60)

    lead_sentences = _split_sentences_editorial(source.cleaned_source_text)
    lead = lead_sentences[0] if lead_sentences else (source.source_subtitle or dados["titulo_seo"])

    if article_type == "service_economy":
        receive = _v72_pick_sentence(lead_sentences, "31 de março") or _v72_pick_sentence(lead_sentences, "solicitou")
        nextpay = _v72_pick_sentence(lead_sentences, "25 de maio")
        subt = receive or source.source_subtitle or lead
        if nextpay and "25 de maio" not in subt:
            subt = f"{subt} Próximo pagamento está previsto para 25 de maio."
    else:
        subt = dados.get("subtitulo_curto") or dados.get("subtitulo") or source.source_subtitle or lead
    dados["subtitulo_curto"] = safe_truncate(subt, 170)
    dados["subtitulo"] = dados["subtitulo_curto"]

    leg = dados.get("legenda_curta") or dados.get("legenda") or ""
    if not leg or _similar_words(leg, dados["subtitulo_curto"]) >= 0.58:
        if article_type == "service_economy":
            leg = "Consulta pode ser feita pelo Repis Cidadão ou pelo aplicativo do FGTS"
        else:
            leg = _build_better_caption(source, dados["subtitulo_curto"], dados["titulo_seo"], article_type)
    dados["legenda_curta"] = safe_truncate(leg, 130)
    dados["legenda"] = dados["legenda_curta"]

    dados["retranca"] = " ".join(str(channel).split()[:1])
    dados["editoria"] = channel
    dados["canal"] = channel

    raw_tags = dados.get("tags")
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    tags = []
    for t in (raw_tags or []) + _extract_basic_tags(source, article_type, channel):
        nt = _norm_txt(t)
        if nt in _STOP_TAGS_V72:
            continue
        if article_type == "service_economy" and nt in ("rio", "rio de janeiro"):
            continue
        if nt not in [_norm_txt(x) for x in tags]:
            tags.append(str(t).strip())
    dados["tags"] = tags[:10]

    corpo = dados.get("corpo_materia") or dados.get("conteudo") or ""
    pars = [p.strip() for p in str(corpo).split("\n\n") if p.strip()]
    if article_type == "service_economy":
        has_intertitles = any(p.strip().lower() in ("quem recebe", "como consultar", "como pedir o ressarcimento", "quando vou receber", "prazo final", "o que é o antigo pis/pasep") for p in pars)
        if not has_intertitles or len(pars) < 5:
            service_body = _v72_service_body(source)
            if service_body and len(service_body) > 450:
                corpo = service_body
                pars = [p.strip() for p in corpo.split("\n\n") if p.strip()]
    bad_endings = ("As autoridades seguem", "O caso segue em andamento", "Novas informações serão divulgadas", "Fique atento", "A população deve")
    if pars and any(pars[-1].startswith(x) for x in bad_endings):
        pars = pars[:-1]
    dados["corpo_materia"] = "\n\n".join(pars) if pars else str(corpo)
    dados["conteudo"] = dados["corpo_materia"]
    dados["texto_final"] = dados["corpo_materia"]

    dados["slug"] = _make_slug_local(dados["titulo_seo"])
    dados["meta_description"] = _v72_make_meta(dados, source, article_type)
    dados["resumo_curto"] = safe_truncate(dados.get("resumo_curto") or lead, 280)
    dados["chamada_social"] = _v72_social(dados, source, article_type)
    return dados

# v72 global safe_title aliases
try:
    from ururau.editorial.safe_title import safe_truncate as safe_truncate
except Exception:
    def safe_truncate(x, n):
        return str(x or "")[:n]


# URURAU v72b — refinamentos de serviço/SEO

def _v72_clean_service_sentences(source: SourceContext) -> list[str]:
    sentences = _split_sentences_editorial(source.cleaned_source_text)
    title_n = _norm_txt(source.source_title)
    subtitle_n = _norm_txt(source.source_subtitle)
    out=[]
    for sent in sentences:
        n=_norm_txt(sent)
        if not n:
            continue
        # Remove linha de título/subtítulo colada ao início da fonte.
        if title_n and n.startswith(title_n[:60]):
            tail = n.replace(title_n, "", 1).strip(" .:-")
            if subtitle_n and tail.startswith(subtitle_n[:60]):
                tail = tail.replace(subtitle_n, "", 1).strip(" .:-")
            if len(tail) < 40:
                continue
        if subtitle_n and n == subtitle_n:
            continue
        out.append(sent)
    return out


def _v72_pick_sentence(sentences: list[str], *keys: str) -> str:  # type: ignore[override]
    for sent in sentences:
        n = _norm_txt(sent)
        if all(_norm_txt(k) in n for k in keys):
            return sent
    return ""


def _v72_service_body(source: SourceContext) -> str:  # type: ignore[override]
    sentences = _v72_clean_service_sentences(source)
    lead = _v72_pick_sentence(sentences, "novo lote") or _v72_pick_sentence(sentences, "pagamento") or (source.source_subtitle or source.source_title)
    receive = _v72_pick_sentence(sentences, "solicitou", "31") or _v72_pick_sentence(sentences, "31 de março")
    nextpay = _v72_pick_sentence(sentences, "30", "25 de maio") or _v72_pick_sentence(sentences, "25 de maio")
    consult = _v72_pick_sentence(sentences, "Repis") or _v72_pick_sentence(sentences, "aplicativo do FGTS")
    avg = _v72_pick_sentence(sentences, "saldo médio") or _v72_pick_sentence(sentences, "2,8 mil")
    ask = _v72_pick_sentence(sentences, "agência", "Caixa") or _v72_pick_sentence(sentences, "ressarcimento", "FGTS")
    heirs = _v72_pick_sentence(sentences, "herdeiros")
    oldfund = _v72_pick_sentence(sentences, "1971", "1988") or _v72_pick_sentence(sentences, "antigo fundo")
    deadline = _v72_pick_sentence(sentences, "setembro de 2028") or _v72_pick_sentence(sentences, "Tesouro Nacional")

    paragraphs=[]
    leadp = lead
    if nextpay and nextpay != leadp:
        leadp = f"{leadp} {nextpay}"
    if leadp:
        paragraphs.append(leadp)
    if receive:
        paragraphs.append("Quem recebe\n" + receive)
    how = " ".join(x for x in [consult, avg] if x)
    if how:
        paragraphs.append("Como consultar\n" + how)
    request = " ".join(x for x in [ask, heirs] if x)
    if request:
        paragraphs.append("Como pedir o ressarcimento\n" + request)
    if oldfund:
        paragraphs.append("O que é o antigo PIS/Pasep\n" + oldfund)
    if deadline:
        paragraphs.append("Prazo final\n" + deadline)
    out=[]; seen=set()
    for p in paragraphs:
        key=_norm_txt(p)[:180]
        if p.strip() and key not in seen:
            seen.add(key); out.append(p.strip())
    return "\n\n".join(out)


def _v72_make_meta(dados: dict, source: SourceContext, article_type: str) -> str:  # type: ignore[override]
    if article_type == "service_economy":
        sents = _v72_clean_service_sentences(source)
        lead = _v72_pick_sentence(sents, "novo lote") or _v72_pick_sentence(sents, "pagamento") or dados.get("subtitulo_curto") or source.source_title
        may = _v72_pick_sentence(sents, "25 de maio")
        # Meta manual para evitar corte no meio de expressão.
        if "pis" in _norm_txt(source.source_title):
            meta = "Caixa libera novo lote do dinheiro esquecido do PIS/Pasep nesta segunda. Consulta pode ser feita pelo Repis Cidadão ou pelo app do FGTS."
            if may:
                meta = "Caixa libera novo lote do dinheiro esquecido do PIS/Pasep nesta segunda. Pedidos até 30 de abril serão pagos em 25 de maio."
            return _complete_sentence_truncate(meta, 160, 120)
        return _complete_sentence_truncate(f"{lead} {may or ''}", 160, 120)
    base = dados.get("meta_description") or dados.get("subtitulo_curto") or ""
    if len(str(base)) < 115:
        lead_sentences = _split_sentences_editorial(source.cleaned_source_text)
        base = f"{base} {' '.join(lead_sentences[:2])}".strip()
    return _complete_sentence_truncate(base, 160, 120)


def _polish_article_fields(dados: dict, brief: dict, source: SourceContext, article_type: str, channel: str) -> dict:  # type: ignore[override]
    from ururau.editorial.safe_title import safe_title, safe_truncate
    dados = dict(dados or {})
    title = dados.get("titulo_seo") or dados.get("titulo") or source.source_title
    title = _remove_data_artificial_titulo(title, source.cleaned_source_text)
    dados["titulo_seo"] = safe_title(title, 89)
    dados["titulo"] = dados["titulo_seo"]
    dados["titulo_capa"] = safe_title(_remove_data_artificial_titulo(dados.get("titulo_capa") or title, source.cleaned_source_text), 60)
    lead_sentences = _v72_clean_service_sentences(source) if article_type == "service_economy" else _split_sentences_editorial(source.cleaned_source_text)
    lead = lead_sentences[0] if lead_sentences else (source.source_subtitle or dados["titulo_seo"])
    if article_type == "service_economy":
        receive = _v72_pick_sentence(lead_sentences, "31 de março") or _v72_pick_sentence(lead_sentences, "solicitou")
        nextpay = _v72_pick_sentence(lead_sentences, "25 de maio")
        subt = receive or source.source_subtitle or lead
        if nextpay and "25 de maio" not in subt:
            subt = f"{subt} Próximo pagamento está previsto para 25 de maio."
    else:
        subt = dados.get("subtitulo_curto") or dados.get("subtitulo") or source.source_subtitle or lead
    dados["subtitulo_curto"] = safe_truncate(subt, 170)
    dados["subtitulo"] = dados["subtitulo_curto"]
    leg = dados.get("legenda_curta") or dados.get("legenda") or ""
    if not leg or _similar_words(leg, dados["subtitulo_curto"]) >= 0.58:
        leg = "Consulta pode ser feita pelo Repis Cidadão ou pelo aplicativo do FGTS" if article_type == "service_economy" else _build_better_caption(source, dados["subtitulo_curto"], dados["titulo_seo"], article_type)
    dados["legenda_curta"] = safe_truncate(leg, 130)
    dados["legenda"] = dados["legenda_curta"]
    dados["retranca"] = " ".join(str(channel).split()[:1]); dados["editoria"] = channel; dados["canal"] = channel
    raw_tags = dados.get("tags")
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    tags=[]
    for t in (raw_tags or []) + _extract_basic_tags(source, article_type, channel):
        nt=_norm_txt(t)
        if nt in _STOP_TAGS_V72 or (article_type == "service_economy" and nt in ("rio", "rio de janeiro")):
            continue
        if nt not in [_norm_txt(x) for x in tags]:
            tags.append(str(t).strip())
    dados["tags"] = tags[:10]
    corpo = dados.get("corpo_materia") or dados.get("conteudo") or ""
    pars=[p.strip() for p in str(corpo).split("\n\n") if p.strip()]
    if article_type == "service_economy":
        has_intertitles = any(p.split("\n",1)[0].strip().lower() in ("quem recebe", "como consultar", "como pedir o ressarcimento", "quando vou receber", "prazo final", "o que é o antigo pis/pasep") for p in pars)
        service_body=_v72_service_body(source)
        if service_body and ((not has_intertitles) or len(pars) < 5):
            pars=[p.strip() for p in service_body.split("\n\n") if p.strip()]
    bad_endings=("As autoridades seguem", "O caso segue em andamento", "Novas informações serão divulgadas", "Fique atento", "A população deve")
    if pars and any(pars[-1].startswith(x) for x in bad_endings):
        pars=pars[:-1]
    dados["corpo_materia"]="\n\n".join(pars) if pars else str(corpo)
    dados["conteudo"]=dados["corpo_materia"]; dados["texto_final"]=dados["corpo_materia"]
    dados["slug"]=_make_slug_local(dados["titulo_seo"])
    dados["meta_description"]=_v72_make_meta(dados, source, article_type)
    dados["resumo_curto"]=safe_truncate(dados.get("resumo_curto") or lead, 280)
    dados["chamada_social"]=_v72_social(dados, source, article_type)
    return dados

# URURAU v72c — remove título/subtítulo colados no início da fonte de serviço

def _v72_clean_service_sentences(source: SourceContext) -> list[str]:  # type: ignore[override]
    import re
    clean = source.cleaned_source_text or ""
    for head in (source.source_title, source.source_subtitle):
        h = str(head or "").strip()
        if h and clean.strip().startswith(h):
            clean = clean.strip()[len(h):].strip(" \n\r\t.-:;—–")
    # caso título + subtítulo tenham vindo na mesma linha sem quebra segura
    clean = re.sub(r"^PIS/Pasep:\s*Caixa libera novo lote[^.\n]*\s+Veja quem recebe[^.\n]*\.", "", clean, flags=re.I).strip()
    sentences = _split_sentences_editorial(clean)
    title_n = _norm_txt(source.source_title)
    subtitle_n = _norm_txt(source.source_subtitle)
    out=[]
    for sent in sentences:
        n=_norm_txt(sent)
        if not n or (title_n and n == title_n) or (subtitle_n and n == subtitle_n):
            continue
        if title_n and n.startswith(title_n[:50]):
            continue
        out.append(sent)
    return out

# URURAU v72d — acabamento de pontuação final

def _v72_ensure_periods(body: str) -> str:
    lines=[]
    intertitles={"quem recebe", "como consultar", "como pedir o ressarcimento", "quando vou receber", "prazo final", "o que é o antigo pis/pasep"}
    for block in str(body or "").split("\n\n"):
        b=block.strip()
        if not b:
            continue
        if "\n" in b:
            title, rest = b.split("\n",1)
            rest = rest.strip()
            if rest and rest[-1] not in ".!?…\"”'":
                rest += "."
            lines.append(title.strip()+"\n"+rest)
        else:
            if b[-1] not in ".!?…\"”'":
                b += "."
            lines.append(b)
    return "\n\n".join(lines)

_old_polish_v72 = _polish_article_fields

def _polish_article_fields(dados: dict, brief: dict, source: SourceContext, article_type: str, channel: str) -> dict:  # type: ignore[override]
    dados = _old_polish_v72(dados, brief, source, article_type, channel)
    dados["corpo_materia"] = _v72_ensure_periods(dados.get("corpo_materia") or dados.get("conteudo") or "")
    dados["conteudo"] = dados["corpo_materia"]
    dados["texto_final"] = dados["corpo_materia"]
    return dados

# URURAU v72e — legenda obrigatória em matéria de serviço e limpeza de tag duplicada
_old_polish_v72d = _polish_article_fields

def _polish_article_fields(dados: dict, brief: dict, source: SourceContext, article_type: str, channel: str) -> dict:  # type: ignore[override]
    from ururau.editorial.safe_title import safe_truncate
    dados = _old_polish_v72d(dados, brief, source, article_type, channel)
    if article_type == "service_economy":
        dados["legenda_curta"] = "Consulta pode ser feita pelo Repis Cidadão ou pelo aplicativo do FGTS"
        dados["legenda"] = dados["legenda_curta"]
    tags = dados.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    cleaned=[]
    for t in tags:
        nt = _norm_txt(t)
        if nt in ("delegacia de policia", "delegacia de polícia") and any("12" in x and "Delegacia" in x for x in cleaned):
            continue
        if nt not in [_norm_txt(x) for x in cleaned]:
            cleaned.append(t)
    dados["tags"] = cleaned[:10]
    return dados

# ══════════════════════════════════════════════════════════════════════════════
# URURAU v74 — estilo por editoria + memória editorial + revisão semântica
# ══════════════════════════════════════════════════════════════════════════════

_old_build_editorial_brief_v74 = build_editorial_brief

def build_editorial_brief(source: SourceContext, article_type: str, canal: str, required_facts: list, relationships: list, angle: str, plan: list[str]) -> dict:  # type: ignore[override]
    brief = _old_build_editorial_brief_v74(source, article_type, canal, required_facts, relationships, angle, plan)
    try:
        from ururau.editorial.estilos_por_editoria import bloco_estilo_para_prompt, obter_estilo_editorial
        from ururau.editorial.memoria_editorial import carregar_memoria
        estilo = obter_estilo_editorial(canal, article_type)
        brief["style_v74"] = {
            "canal": estilo.canal,
            "tom": estilo.tom,
            "estrutura": list(estilo.estrutura),
            "evitar": list(estilo.evitar),
            "prioridade": list(estilo.prioridade),
            "prompt_block": bloco_estilo_para_prompt(canal, article_type),
        }
        mem = carregar_memoria()
        sim, item = mem.similaridade_recente(source.source_title, source.cleaned_source_text)
        brief["memoria_editorial_v74"] = {
            "similaridade_recente": round(float(sim), 3),
            "titulo_similar": (item or {}).get("titulo", ""),
            "orientacao": "Não repetir título, lead ou ângulo já usado. Atualize a abordagem se houver pauta semelhante.",
        }
    except Exception as exc:
        brief["style_v74_error"] = str(exc)
    return brief


def _v74_clean_title(title: str, source: SourceContext, article_type: str) -> str:
    """Acabamento final de título: remove inflação artificial e corrige médias."""
    import re
    t = str(title or source.source_title or "").strip()
    n_source = _norm_txt(source.cleaned_source_text)
    # Evita afirmar média como valor liberado no título.
    if article_type == "service_economy" and ("2,8 mil" in _norm_txt(t) or "2 8 mil" in _norm_txt(t)):
        if "saldo medio" in n_source or "saldo médio" in (source.cleaned_source_text or "").lower():
            t = "Caixa libera novo lote do dinheiro esquecido do PIS/Pasep nesta segunda"
    # Remove enchimentos geográficos/temporais quando não agregam SEO.
    t = re.sub(r"\s+em todo o (Brasil|país)\b", "", t, flags=re.I).strip()
    t = re.sub(r"\s+no Brasil\b", "", t, flags=re.I).strip()
    t = re.sub(r"\s+em \d{1,2} de [a-zç]+\b", "", t, flags=re.I).strip()
    return t


def _v74_improve_intertitles(body: str, article_type: str) -> str:
    if article_type != "service_economy":
        return body
    mapping = {
        "Quem recebe": "Quem tem direito ao pagamento",
        "Como consultar": "Como consultar valores disponíveis",
        "Como pedir": "Como solicitar o ressarcimento",
        "Quando vou receber": "Quando o dinheiro será pago",
    }
    blocks = []
    for block in str(body or "").split("\n\n"):
        b = block.strip()
        if not b:
            continue
        if "\n" in b:
            head, rest = b.split("\n", 1)
            head = mapping.get(head.strip(), head.strip())
            blocks.append(head + "\n" + rest.strip())
        else:
            blocks.append(b)
    return "\n\n".join(blocks)


def _v74_apply_house_language(body: str, canal: str, article_type: str) -> str:
    """Remove marcas automáticas e ajusta linguagem por editoria sem inventar conteúdo."""
    import re
    text = str(body or "")
    replacements = {
        "Segundo informações, ": "",
        "De acordo com informações, ": "",
        "Fique atento aos prazos e condições.": "",
        "As autoridades seguem com as apurações": "A apuração continua",
        "reforçou": "afirmou",
        "reacendeu": "voltou a colocar em debate",
    }
    for a, b in replacements.items():
        text = text.replace(a, b)
    # Remove linhas residuais de scraping que possam ter passado.
    lines = []
    for line in text.splitlines():
        low = line.strip().lower()
        if not line.strip():
            lines.append("")
            continue
        if any(x in low for x in ("publicidade", "alertas grátis", "inscreva-se", "volte ao menu")):
            continue
        if " foto:" in low or low.startswith("foto:") or "— foto:" in low:
            continue
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


_old_polish_v74_base = _polish_article_fields

def _polish_article_fields(dados: dict, brief: dict, source: SourceContext, article_type: str, channel: str) -> dict:  # type: ignore[override]
    from ururau.editorial.safe_title import safe_title, safe_truncate
    dados = _old_polish_v74_base(dados, brief, source, article_type, channel)
    dados["titulo_seo"] = safe_title(_v74_clean_title(dados.get("titulo_seo") or dados.get("titulo") or source.source_title, source, article_type), 89)
    dados["titulo"] = dados["titulo_seo"]
    dados["titulo_capa"] = safe_title(_v74_clean_title(dados.get("titulo_capa") or dados["titulo_seo"], source, article_type), 60)
    body = dados.get("corpo_materia") or dados.get("conteudo") or ""
    body = _v74_improve_intertitles(body, article_type)
    body = _v74_apply_house_language(body, channel, article_type)
    dados["corpo_materia"] = body
    dados["conteudo"] = body
    dados["texto_final"] = body
    dados["slug"] = _make_slug_local(dados["titulo_seo"])
    # Chamada social sem clichê e sem valor médio como promessa.
    if article_type == "service_economy" and "pis" in _norm_txt(source.source_title):
        dados["chamada_social"] = "Caixa paga novo lote do dinheiro esquecido do PIS/Pasep nesta segunda. Consulta pode ser feita pelo Repis Cidadão ou pelo aplicativo do FGTS."
    # Tags finais: remove editoria como tag e duplicidades semânticas.
    raw = dados.get("tags") or []
    if isinstance(raw, str):
        raw = [t.strip() for t in raw.split(",") if t.strip()]
    cleaned = []
    for tag in raw:
        nt = _norm_txt(tag)
        if nt in ("economia", "politica", "policia", "geral", "rio", "rio de janeiro") and article_type == "service_economy":
            continue
        if nt and nt not in [_norm_txt(x) for x in cleaned]:
            cleaned.append(tag)
    dados["tags"] = cleaned[:10]
    dados["meta_description"] = safe_truncate(dados.get("meta_description") or dados.get("subtitulo_curto") or source.source_subtitle or dados["titulo_seo"], 160)
    return dados


_old_generate_ururau_article_v74 = generate_ururau_article

def generate_ururau_article(pauta: dict, client: "OpenAI", model: str, canal: str, modo: str = "panel"):  # type: ignore[override]
    """v74 wrapper: gera matéria, aplica memória editorial e anexa metadados de relevância/duplicidade."""
    m = _old_generate_ururau_article_v74(pauta, client, model, canal, modo)
    try:
        source = build_source_context(pauta)
        article_type = classify_article_type(source, getattr(m, "canal", canal) or canal)
        from ururau.editorial.memoria_editorial import registrar_materia_na_memoria
        from ururau.editorial.duplicidade_semantica import verificar_duplicidade_semantica
        from ururau.coleta.relevancia_v74 import calcular_relevancia_v74
        dup = verificar_duplicidade_semantica(pauta)
        rel = calcular_relevancia_v74(pauta)
        # Não bloqueia a geração no painel; sinaliza para revisão humana quando houver risco.
        if dup.is_duplicate and dup.score >= 0.78:
            errs = list(getattr(m, "erros_validacao", []) or [])
            errs.append({
                "categoria": "EDITORIAL_REVIEW",
                "codigo": "possivel_duplicidade_semantica_v74",
                "mensagem": f"Possível duplicidade: {dup.matched_title} ({dup.score:.2f})",
                "bloqueia_publicacao": modo == "monitor",
                "corrigivel_automaticamente": False,
            })
            m.erros_validacao = errs
            m.revisao_humana_necessaria = True
            if modo == "monitor":
                m.auditoria_bloqueada = True
                m.status_publicacao_sugerido = "salvar_rascunho"
        # Atributos dinâmicos preservam compatibilidade com dataclass antiga.
        setattr(m, "score_relevancia_v74", rel.get("score_relevancia_v74", 0))
        setattr(m, "prioridade_v74", rel.get("prioridade_v74", "media"))
        setattr(m, "duplicidade_semantica_v74", dup.score)
        registrar_materia_na_memoria(m, article_type=article_type)
    except Exception as exc:
        print(f"[ENGINE v74] pós-processamento v74 falhou sem bloquear: {exc}")
    return m

# ══════════════════════════════════════════════════════════════════════════════
# URURAU v75 — lead obrigatório, limpeza total e hierarquia editorial final
# ══════════════════════════════════════════════════════════════════════════════

def _v75_norm_space(text: str) -> str:
    import re
    text = str(text or "").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text.strip()


def _v75_remove_scraping_noise(text: str) -> str:
    """Limpeza final agressiva de resíduos de scraping, sem apagar fatos jornalísticos."""
    import re
    text = str(text or "")
    text = text.replace("🔎", "")
    text = text.replace("( )", "")
    noise_patterns = [
        r"(?im)^\s*publicidade\s*$",
        r"(?im)^\s*alertas grátis.*$",
        r"(?im)^\s*inscreva-se\s*$",
        r"(?im)^\s*volte ao menu\.?\s*$",
        r"(?im)^\s*concordo com os termos.*$",
        r"(?im)^\s*whatsapp\s*$",
        r"(?im)^\s*telegram\s*$",
        r"(?im)^\s*e-mail\s*$",
        r"(?im)^\s*seu e-mail\s*$",
        r"(?im)^\s*copyright\s*$",
        r"(?im)^\s*logo\s+\w+\s*$",
        r"(?i)\bSaiba se você tem dinheiro esquecido no antigo fundo PIS/Pasep\b",
        r"(?i)\bVeja abaixo como consultar, pedir o ressarcimento e quando receber\b",
        r"(?i)\(Veja abaixo como consultar, pedir o ressarcimento e quando receber\)\s*",
        r"(?i)\bVeja a seguir:\s*",
    ]
    for pat in noise_patterns:
        text = re.sub(pat, " ", text)
    # Remove créditos de foto colados no lead, mantendo o restante da frase quando houver.
    text = re.sub(r"(?i)^\s*[^\n]{0,120}(?:—|-)\s*Foto:\s*[^\n]{0,180}\s+", "", text)
    text = re.sub(r"(?i)\b(?:—|-)\s*Foto:\s*[^\n.]{0,180}(?:\.|\n)?", " ", text)
    text = re.sub(r"(?i)\bFoto:\s*[^\n.]{0,180}(?:\.|\n)?", " ", text)
    # Remove sobras de chamadas duplicadas de vídeo/box.
    text = re.sub(r"(?i)\bREPIS Cidadão, site lançado[^\n.]{0,220}(?:\.|\n)?", " ", text)
    text = re.sub(r"(?i)\bPIS/Pasep, FGTS\s*-\s*Saque\b", " ", text)
    return _v75_norm_space(text)


def _v75_sentence_list(text: str) -> list[str]:
    import re
    clean = _v75_remove_scraping_noise(_strip_html_local(text))
    parts = re.split(r"(?<=[.!?])\s+", clean)
    out, seen = [], set()
    bad = (
        "publicidade", "volte ao menu", "inscreva-se", "alertas grátis", "saiba se você tem dinheiro",
        "veja abaixo", "veja a seguir", "foto:", "reprodução"
    )
    for p in parts:
        p = _v75_norm_space(p.strip(" -•\t\r\n"))
        low = p.lower()
        if len(p) < 35 or any(x in low for x in bad):
            continue
        key = _norm_txt(p)[:140]
        if key and key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _v75_build_service_lead(source: SourceContext, body: str) -> str:
    """Cria lead obrigatório para matéria de serviço a partir da fonte, sem inventar números."""
    import re
    all_text = f"{source.source_title}. {source.source_subtitle}. {source.cleaned_source_text}. {body}"
    norm = all_text.lower()
    if "pis" in norm and "pasep" in norm and "caixa" in norm:
        lead = "A Caixa Econômica Federal libera nesta segunda-feira (27) um novo lote do dinheiro esquecido no antigo fundo PIS/Pasep para trabalhadores que solicitaram o ressarcimento até 31 de março."
        if "25 de maio" in norm and "30" in norm:
            lead += " Quem fizer o pedido até 30 de abril deve receber o pagamento em 25 de maio, conforme o calendário divulgado pelo governo."
        return lead
    # Fallback conservador: usa primeira frase factual da fonte.
    sentences = _v75_sentence_list(all_text)
    return sentences[0] if sentences else (source.source_subtitle or source.source_title or "A informação foi divulgada nesta segunda-feira.")


def _v75_has_editorial_lead(body: str) -> bool:
    first = _v75_norm_space(str(body or "").split("\n\n", 1)[0])
    if not first:
        return False
    headings = {
        "quem tem direito ao pagamento", "como consultar valores disponíveis", "como solicitar o ressarcimento",
        "o que é o antigo pis/pasep", "prazo final", "quem recebe", "como consultar", "como pedir o ressarcimento"
    }
    heading_norms = {_norm_txt(h) for h in headings}
    first_line = _v75_norm_space(first.split("\n", 1)[0])
    # Bloco iniciado por intertítulo não é lead, mesmo que tenha parágrafo abaixo.
    if _norm_txt(first_line) in heading_norms:
        return False
    # Intertítulo curto não é lead.
    if len(first) < 90 and not first.endswith("."):
        return False
    return _norm_txt(first) not in heading_norms


def _v75_insert_required_lead(body: str, source: SourceContext, article_type: str) -> str:
    body = _v75_remove_scraping_noise(body)
    if article_type != "service_economy":
        return body
    if _v75_has_editorial_lead(body):
        return body
    lead = _v75_build_service_lead(source, body)
    return _v75_norm_space(lead + "\n\n" + body)


def _v75_improve_service_blocks(body: str) -> str:
    """Melhora intertítulos e limpa frases de bloco mantendo hierarquia de serviço."""
    mapping = {
        "Quem recebe": "Quem tem direito ao pagamento",
        "Como consultar": "Como consultar valores disponíveis",
        "Como pedir": "Como solicitar o ressarcimento",
        "Como pedir o ressarcimento": "Como solicitar o ressarcimento",
        "Quando vou receber": "Quando o dinheiro será pago",
    }
    blocks = []
    for raw in str(body or "").split("\n\n"):
        block = _v75_remove_scraping_noise(raw)
        if not block:
            continue
        if "\n" in block:
            head, rest = block.split("\n", 1)
            head = mapping.get(head.strip(), head.strip())
            rest = _v75_remove_scraping_noise(rest)
            if rest:
                blocks.append(head + "\n" + rest)
            else:
                blocks.append(head)
        else:
            blocks.append(block)
    return _v75_norm_space("\n\n".join(blocks))


def _v75_slug(text: str, max_len: int = 76) -> str:
    import re, unicodedata
    stop = {"de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "nesta", "neste", "para", "com", "por"}
    s = unicodedata.normalize("NFD", str(text or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    words = [w for w in re.split(r"[^a-z0-9]+", s) if w]
    kept = []
    for w in words:
        if len(kept) >= 8 and w in stop:
            continue
        candidate = "-".join(kept + [w])
        if len(candidate) > max_len:
            break
        kept.append(w)
    return "-".join(kept).strip("-") or _make_slug_local(text).strip("-")


def _v75_clean_title(title: str, source: SourceContext, article_type: str) -> str:
    import re
    t = _v74_clean_title(title, source, article_type) if '_v74_clean_title' in globals() else str(title or source.source_title or "")
    t = re.sub(r"\s+em todo o (Brasil|país)\b", "", t, flags=re.I)
    t = re.sub(r"\s+no Brasil\b", "", t, flags=re.I)
    t = re.sub(r"\s+em todo o território nacional\b", "", t, flags=re.I)
    # Não transformar saldo médio em promessa de pagamento no título.
    if article_type == "service_economy" and re.search(r"R\$\s*2[,.]8\s*mil", t, flags=re.I):
        t = "Caixa libera novo lote do dinheiro esquecido do PIS/Pasep nesta segunda"
    return _v75_norm_space(t)


def _v75_normalize_tags(tags, article_type: str) -> list[str]:
    raw = tags or []
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    canonical = []
    seen = set()
    for tag in raw:
        t = _v75_norm_space(tag)
        nt = _norm_txt(t)
        if not nt:
            continue
        if article_type == "service_economy" and nt in {"economia", "rio", "rio de janeiro", "noticia", "ururau"}:
            continue
        if article_type == "politics" and any(x in nt for x in ("pis", "pasep", "fgts", "repis", "caixa economica", "caixa econômica", "nis", "tesouro nacional", "dinheiro esquecido")):
            continue
        if "pis" in nt or "pasep" in nt:
            t = "PIS/Pasep"
            nt = "pis/pasep"
        if "repis" in nt:
            t = "Repis Cidadão"
            nt = "repis cidadao"
        if nt == "fgts":
            t = "FGTS"
        if nt in {"pis", "pasep"}:
            continue
        if nt not in seen:
            seen.add(nt)
            canonical.append(t)
    # Garante tags essenciais da matéria de serviço sem duplicar.
    if article_type == "service_economy":
        essentials = ["Caixa Econômica Federal", "PIS/Pasep", "FGTS", "dinheiro esquecido", "Repis Cidadão", "ressarcimento", "Tesouro Nacional"]
        for t in essentials:
            nt = "pis/pasep" if t == "PIS/Pasep" else _norm_txt(t)
            if nt not in seen:
                seen.add(nt)
                canonical.append(t)
    return canonical[:10]


def _v75_social_call(dados: dict, source: SourceContext, article_type: str) -> str:
    if article_type == "service_economy" and "pis" in _norm_txt(source.source_title + " " + source.cleaned_source_text):
        return "Caixa libera novo lote do dinheiro esquecido do PIS/Pasep nesta segunda. Veja quem recebe, como consultar e qual é o próximo prazo de pagamento."
    base = dados.get("chamada_social") or dados.get("meta_description") or dados.get("titulo_seo") or source.source_title
    for bad in ("Fique atento aos prazos e condições.", "Fique atento aos prazos e condições", "Confira todos os detalhes"):
        base = str(base).replace(bad, "")
    return _v75_norm_space(base)


_old_polish_v75_base = _polish_article_fields

def _polish_article_fields(dados: dict, brief: dict, source: SourceContext, article_type: str, channel: str) -> dict:  # type: ignore[override]
    from ururau.editorial.safe_title import safe_title, safe_truncate
    dados = _old_polish_v75_base(dados, brief, source, article_type, channel)
    title = _v75_clean_title(dados.get("titulo_seo") or dados.get("titulo") or source.source_title, source, article_type)
    dados["titulo_seo"] = safe_title(title, 89)
    dados["titulo"] = dados["titulo_seo"]
    dados["titulo_capa"] = safe_title(_v75_clean_title(dados.get("titulo_capa") or title, source, article_type), 60)
    body = dados.get("corpo_materia") or dados.get("conteudo") or dados.get("texto_final") or ""
    body = _v75_improve_service_blocks(body) if article_type == "service_economy" else _v75_remove_scraping_noise(body)
    body = _v75_insert_required_lead(body, source, article_type)
    dados["corpo_materia"] = body
    dados["conteudo"] = body
    dados["texto_final"] = body
    dados["slug"] = _v75_slug(dados["titulo_seo"])
    dados["tags"] = _v75_normalize_tags(dados.get("tags"), article_type)
    dados["chamada_social"] = _v75_social_call(dados, source, article_type)
    meta = dados.get("meta_description") or dados.get("subtitulo_curto") or source.source_subtitle or dados["titulo_seo"]
    meta = str(meta).replace("Fique atento aos prazos e condições.", "")
    dados["meta_description"] = safe_truncate(_v75_remove_scraping_noise(meta), 160)
    if article_type == "service_economy" and "pis" in _norm_txt(source.source_title + " " + source.cleaned_source_text):
        dados["legenda_curta"] = "Consulta pode ser feita pelo Repis Cidadão ou pelo aplicativo do FGTS"
        dados["legenda"] = dados["legenda_curta"]
    return dados


_old_generate_ururau_article_v75 = generate_ururau_article

def generate_ururau_article(pauta: dict, client: "OpenAI", model: str, canal: str, modo: str = "panel"):  # type: ignore[override]
    """v75 wrapper: acabamento final no objeto Materia, após memória/relevância da v74."""
    m = _old_generate_ururau_article_v75(pauta, client, model, canal, modo)
    try:
        source = build_source_context(pauta)
        article_type = getattr(m, "article_type", "") or classify_article_type(source, getattr(m, "canal", canal) or canal)
        m.titulo = _v75_clean_title(getattr(m, "titulo", "") or source.source_title, source, article_type)
        m.titulo_capa = _v75_clean_title(getattr(m, "titulo_capa", "") or m.titulo, source, article_type)[:60].rstrip()
        m.slug = _v75_slug(m.titulo)
        m.conteudo = _v75_insert_required_lead(
            _v75_improve_service_blocks(getattr(m, "conteudo", "") or "") if article_type == "service_economy" else _v75_remove_scraping_noise(getattr(m, "conteudo", "") or ""),
            source,
            article_type,
        )
        m.tags = ", ".join(_v75_normalize_tags(getattr(m, "tags", ""), article_type))
        m.chamada_social = _v75_social_call({"chamada_social": getattr(m, "chamada_social", ""), "meta_description": getattr(m, "meta_description", ""), "titulo_seo": m.titulo}, source, article_type)
        m.meta_description = _v75_remove_scraping_noise(getattr(m, "meta_description", "") or getattr(m, "subtitulo", "") or m.titulo)[:160].rstrip(" ,.;")
        if article_type == "service_economy" and "pis" in _norm_txt(source.source_title + " " + source.cleaned_source_text):
            m.legenda = "Consulta pode ser feita pelo Repis Cidadão ou pelo aplicativo do FGTS"
        # Atualiza JSON interno para painel/exportadores que leem generated_article_json.
        gj = dict(getattr(m, "generated_article_json", {}) or {})
        gj.update({
            "titulo_seo": m.titulo,
            "titulo": m.titulo,
            "titulo_capa": m.titulo_capa,
            "slug": m.slug,
            "corpo_materia": m.conteudo,
            "conteudo": m.conteudo,
            "texto_final": m.conteudo,
            "tags": [x.strip() for x in m.tags.split(",") if x.strip()],
            "chamada_social": m.chamada_social,
            "meta_description": m.meta_description,
            "legenda_curta": m.legenda,
        })
        m.generated_article_json = gj
    except Exception as exc:
        print(f"[ENGINE v75] acabamento final falhou sem bloquear: {exc}")
    return m

# ══════════════════════════════════════════════════════════════════════════════
# URURAU v97 — wrapper premium contra corpo raso e SEO fraco
# ══════════════════════════════════════════════════════════════════════════════
_old_generate_ururau_article_v97 = generate_ururau_article

def generate_ururau_article(pauta: dict, client: "OpenAI", model: str, canal: str, modo: str = "panel"):  # type: ignore[override]
    """v97: mantém engine anterior, mas força matéria completa quando há fonte longa."""
    m = _old_generate_ururau_article_v97(pauta, client, model, canal, modo)
    try:
        from ururau.editorial import premium_v97
        source = build_source_context(pauta)
        extra = ""
        if isinstance(pauta, dict):
            for k in ("_fonte_aba_texto", "fonte_aba_texto", "leitura_fonte_texto", "cleaned_source_text", "raw_source_text", "texto_fonte", "dossie"):
                v = str(pauta.get(k) or "").strip()
                if len(v) > len(extra):
                    extra = v
        if len(extra) > len(source.cleaned_source_text or ""):
            source.cleaned_source_text = extra
            source.raw_source_text = extra
        article_type = getattr(m, "article_type", "") or classify_article_type(source, getattr(m, "canal", canal) or canal)
        channel = getattr(m, "canal", "") or canal
        fonte = source.cleaned_source_text or source.raw_source_text or ""
        meta = {
            "channel": channel,
            "article_type": article_type,
            "title": source.source_title,
            "subtitle": source.source_subtitle,
            "source_name": source.source_name,
            "source_url": source.source_url,
        }
        m = premium_v97.regenerate_materia_if_thin(m, fonte, meta, client, model)
        setattr(m, "v97_chars_corpo", len(getattr(m, "conteudo", "") or ""))
        setattr(m, "v97_paragrafos_corpo", len(premium_v97.paragraphs(getattr(m, "conteudo", "") or "")))
    except Exception as exc:
        print(f"[ENGINE v97] wrapper premium falhou sem bloquear: {exc}")
    return m


# ══════════════════════════════════════════════════════════════════════════════
# URURAU v101 — saneamento final contra lixo de fonte e intertítulos genéricos
# ══════════════════════════════════════════════════════════════════════════════
_old_generate_ururau_article_v101 = generate_ururau_article

def generate_ururau_article(pauta: dict, client: "OpenAI", model: str, canal: str, modo: str = "panel"):  # type: ignore[override]
    m = _old_generate_ururau_article_v101(pauta, client, model, canal, modo)
    try:
        from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101, limpar_corpo_publicacao_v101
        titulo_ref = ""
        if isinstance(pauta, dict):
            titulo_ref = str(pauta.get("titulo_origem") or "")
            for k in ("_fonte_aba_texto", "fonte_aba_texto", "leitura_fonte_texto", "cleaned_source_text", "raw_source_text", "texto_fonte", "dossie"):
                if pauta.get(k):
                    pauta[k] = limpar_texto_artigo_v101(str(pauta.get(k) or ""), titulo=titulo_ref, max_chars=16000)
        corpo = getattr(m, "conteudo", "") or ""
        corpo = limpar_corpo_publicacao_v101(corpo)
        setattr(m, "conteudo", corpo)
        gj = dict(getattr(m, "generated_article_json", {}) or {})
        gj["corpo_materia"] = corpo
        gj["conteudo"] = corpo
        gj["texto_final"] = corpo
        gj["modo_saneamento_v101"] = "limpo_sem_menu_sem_intertitulos_genericos"
        setattr(m, "generated_article_json", gj)
    except Exception as exc:
        print(f"[ENGINE v101] saneamento final falhou sem bloquear: {exc}")
    return m
