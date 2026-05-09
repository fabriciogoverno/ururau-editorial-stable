"""
ururau.editorial.fallback_local — fallback editorial forte v78c.

Gera matéria local conservadora quando a IA falha ou está indisponível. A regra
é usar apenas dados presentes na fonte, montar texto limpo e submeter tudo à
auditoria v78c antes de qualquer publicação.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from ururau.core.models import Materia
from ururau.editorial.auditoria_v78c import aplicar_auditoria_v78c

LIXO = [
    "publicidade", "alertas grátis", "alertas gratis", "inscreva-se",
    "volte ao menu", "saiba mais", "veja também", "veja tambem",
    "veja abaixo", "leia também", "leia tambem", "concordo com os termos",
    "receba no whatsapp", "siga no google", "telegram", "whatsapp",
    "newsletter", "cookies", "todos os direitos reservados",
]

FRASES_PROIBIDAS = [
    "fique atento", "confira todos os detalhes", "acende o alerta",
    "cabe ressaltar", "vale lembrar", "nesse contexto",
    "é importante destacar", "e importante destacar",
]

STOP_SLUG = {"do", "da", "de", "dos", "das", "em", "no", "na", "nos", "nas", "a", "o", "e", "para", "com", "por"}


def _get(obj: Any, nome: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get(nome, default) or "")
    return str(getattr(obj, nome, default) or "")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _strip_accents(str(s or "")).lower()).strip()


def _cortar_frase(texto: str, limite: int) -> str:
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()
    if len(texto) <= limite:
        return texto.rstrip(" ,;:-")
    corte = texto[:limite].rstrip()
    pont = max(corte.rfind("."), corte.rfind(";"))
    if pont >= int(limite * 0.65):
        return corte[:pont + 1].strip()
    sp = corte.rfind(" ")
    if sp >= int(limite * 0.55):
        corte = corte[:sp]
    return corte.rstrip(" ,;:-")


def limpar_texto_fonte(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r"<script.*?</script>|<style.*?</style>", " ", texto, flags=re.I | re.S)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = texto.replace("—", "-").replace("–", "-").replace("🔎", "")
    texto = re.sub(r"https?://\S+", " ", texto)
    linhas = []
    for raw in texto.splitlines():
        linha = re.sub(r"\s+", " ", raw).strip(" -|\t\n")
        if not linha:
            continue
        low = _norm(linha)
        if any(x in low for x in LIXO):
            continue
        if re.search(r"\b(foto|copyright|reproducao|reprodução)\b", low) and len(linha) < 180:
            continue
        if linha.startswith(("▶", "🔗", "📌")):
            continue
        linhas.append(linha)
    texto = "\n".join(linhas)
    texto = re.sub(r"\s+([,.!?;:])", r"\1", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return texto.strip()


def _sentencas(texto: str) -> list[str]:
    texto = re.sub(r"\s+", " ", texto or "").strip()
    partes = re.split(r"(?<=[.!?])\s+", texto)
    out: list[str] = []
    seen: set[str] = set()
    for p in partes:
        p = p.strip(" -\t\n")
        if len(p) < 35:
            continue
        if len(p) > 560:
            p = _cortar_frase(p, 520)
        key = _norm(p)[:140]
        if key in seen:
            continue
        if any(x in key for x in ["publicidade", "veja abaixo", "saiba mais", "foto:", "newsletter"]):
            continue
        seen.add(key)
        out.append(p)
    return out


def classificar_canal_v78(titulo: str, resumo: str = "", canal_atual: str = "") -> str:
    """Classificador determinístico final por conteúdo real, não por ruído de fonte."""
    bruto = f"{titulo} {resumo}"
    txt = _norm(bruto)
    fonte_ruido = [
        "jornal o fluminense", "o fluminense", "ururau", "g1", "folha", "metropoles",
        "poder360", "cnn brasil", "extra", "odia", "o dia", "jornal", "rjnews",
    ]
    txt_sem_fonte = txt
    for f in fonte_ruido:
        txt_sem_fonte = txt_sem_fonte.replace(f, " ")
    txt_sem_fonte = re.sub(r"\s+", " ", txt_sem_fonte).strip()

    saude_terms = [
        "saude", "secretaria municipal de saude", "sus", "hospital", "medico", "medicos",
        "vacina", "vacinacao", "cancer", "dengue", "doenca", "surto", "epidemia", "tabagismo",
        "tabagista", "auriculoterapia", "pnaisp", "nicotina", "terapia", "fisioterapeuta",
        "assistencia a saude", "pratica integrativa", "programa de controle do tabagismo",
    ]
    if any(k in txt_sem_fonte for k in saude_terms):
        return "Saúde"

    esporte_contexto = [
        "jogo", "gol", "gols", "brasileirao", "brasileirão", "libertadores", "copa do brasil",
        "copa do mundo", "futebol", "tecnico", "técnico", "treinador", "atacante", "meia",
        "zagueiro", "goleiro", "derrota", "vence", "venceu", "empata", "campeonato", "rodada", "placar",
    ]
    clubes = ["flamengo", "vasco", "botafogo", "fluminense", "palmeiras", "bragantino", "atletico", "atlético", "corinthians"]
    if any(c in txt_sem_fonte for c in clubes) and any(k in txt_sem_fonte for k in esporte_contexto):
        return "Esportes"
    if any(k in txt_sem_fonte for k in esporte_contexto) and "congresso" not in txt_sem_fonte:
        return "Esportes"

    policial_terms = [
        "morre", "morreu", "morte", "acidente", "delegacia", "pericia", "perícia", "bombeiros",
        "preso", "prisao", "prisão", "presidio", "sistema prisional", "privada de liberdade",
        "pf ", "policia", "polícia", "tiro", "crime", "homicidio", "homicídio", "vitima", "vítima", "prensado", "imprensado",
    ]
    if any(k in txt_sem_fonte for k in policial_terms):
        return "Polícia"

    politica_terms = [
        "stf", "stj", "tse", "tre", "alerj", "congresso", "senado", "camara dos deputados", "câmara dos deputados",
        "deputado", "senador", "vereador", "prefeito", "governador", "governo do rj", "governo do rio",
        "palacio guanabara", "palácio guanabara", "eleitor", "eleitores", "voto", "votos", "intencao de voto",
        "intenção de voto", "intencoes de voto", "intenções de voto", "pesquisa eleitoral", "quaest", "genial investimentos",
        "mandato", "cassacao", "cassação", "rodada eleitoral", "eleicao", "eleição", "titulo de eleitor", "bolsonaro",
        "lula", "moraes", "dosimetria", "anistia", "projeto de lei", "ministerio", "ministério", "chanceler",
        "eduardo paes", "douglas ruas", "garotinho", "anthony garotinho", "wilson witzel", "rodrigo bacellar",
    ]
    if any(k in txt_sem_fonte for k in politica_terms):
        return "Política"

    if re.search(r"\b(ira|irã|russia|rússia|putin|eua|estados unidos|trump|obama|israel|hamas|ucrania|ucrânia)\b", txt_sem_fonte):
        return "Brasil e Mundo"

    if any(k in txt_sem_fonte for k in ["pis", "pasep", "fgts", "caixa", "imposto de renda", "selic", "juros", "dolar", "dólar", "economia", "banco central", "mercado"]):
        return "Economia"

    if any(k in txt_sem_fonte for k in ["campos dos goytacazes", "norte fluminense", "sao joao da barra", "são joão da barra", "macae", "macaé", "quissama", "quissamã", "carapebus"]):
        return "Cidades"

    return canal_atual if canal_atual and canal_atual not in ("Esportes", "Política") else "Brasil e Mundo"


def slugify(titulo: str, limite: int = 80) -> str:
    t = _strip_accents(titulo.lower())
    t = re.sub(r"[^a-z0-9\s-]", "", t)
    palavras = [p for p in re.split(r"[\s-]+", t) if p]
    while palavras and palavras[-1] in STOP_SLUG:
        palavras.pop()
    slug = "-".join(palavras)
    if len(slug) <= limite:
        return slug.strip("-")
    partes = slug[:limite].split("-")[:-1]
    while partes and partes[-1] in STOP_SLUG:
        partes.pop()
    return "-".join(partes).strip("-")


def titulo_limpo(titulo: str, canal: str) -> str:
    t = re.sub(r"\s+", " ", (titulo or "")).strip(" -|\t\n")
    t = re.sub(r"\s+O munic[ií]pio\s+de\s+.+$", "", t, flags=re.I)
    t = re.sub(r"\s+A prefeitura\s+.+$", "", t, flags=re.I)
    t = re.sub(r"\s+O projeto\s+.+$", "", t, flags=re.I)
    t = re.sub(r"\s+em todo o (Brasil|país)$", "", t, flags=re.I)
    t = t.replace("—", "-").replace("–", "-")
    if "r$" in t.lower() and any(k in _norm(t) for k in ["pis", "pasep", "dinheiro esquecido"]):
        t = re.sub(r"\s*R\$\s*[\d\.,]+\s*(mil|mi|bilhões|bilhoes)?\s*", " ", t, flags=re.I)
        t = re.sub(r"\s+", " ", t).strip()
        if "caixa" in _norm(t) and "pis" in _norm(t):
            t = "Caixa libera novo lote do dinheiro esquecido do PIS/Pasep nesta segunda"
    return _cortar_frase(t, 89).rstrip(" ,.;:-")


def _meta(texto: str, titulo: str) -> str:
    base = _sentencas(texto)
    m = base[0] if base else titulo
    if len(m) < 80 and len(base) > 1:
        m = f"{m} {base[1]}"
    return _cortar_frase(m, 155).rstrip(" ,.;:-")


def _tags(titulo: str, texto: str, canal: str) -> str:
    full = _norm(f"{titulo} {texto}")
    tags: list[str] = []
    def add(x: str) -> None:
        x = str(x or "").strip(" .,;:()[]")
        if not x:
            return
        if _norm(x) not in [_norm(t) for t in tags]:
            tags.append(x)
    politica_pura = "politica" in _norm(canal)
    termos_servico_economia = {"pis", "pasep", "fgts", "caixa", "repis", "tesouro nacional"}
    for chave, tag in [
        ("pis", "PIS/Pasep"), ("pasep", "PIS/Pasep"), ("fgts", "FGTS"),
        ("caixa", "Caixa Econômica Federal"), ("repis", "Repis Cidadão"),
        ("tesouro nacional", "Tesouro Nacional"), ("stf", "STF"), ("tse", "TSE"),
        ("alerj", "Alerj"), ("policia federal", "Polícia Federal"), ("pf ", "Polícia Federal"),
        ("auriculoterapia", "Auriculoterapia"), ("tabagismo", "Tabagismo"),
        ("secretaria municipal de saude", "Secretaria Municipal de Saúde"),
        ("sus", "SUS"), ("pnaisp", "PNAISP"), ("presidio carlos tinoco", "Presídio Carlos Tinoco"),
        ("campos dos goytacazes", "Campos dos Goytacazes"), ("norte fluminense", "Norte Fluminense"),
        ("flamengo", "Flamengo"), ("vasco", "Vasco"), ("botafogo", "Botafogo"),
        ("fluminense", "Fluminense"), ("atletico-mg", "Atlético-MG"), ("atlético-mg", "Atlético-MG"),
        ("palmeiras", "Palmeiras"), ("corinthians", "Corinthians"),
        ("rio de janeiro", "Rio de Janeiro"), ("belo horizonte", "Belo Horizonte"),
        ("brasileirao", "Brasileirão"), ("brasileirão", "Brasileirão"),
        ("campeonato brasileiro", "Campeonato Brasileiro"), ("libertadores", "Libertadores"),
    ]:
        if politica_pura and chave in termos_servico_economia:
            continue
        if chave in full:
            add(tag)
    add(canal)

    # Extrai poucas entidades próprias remanescentes só quando ainda faltam tags úteis.
    if len(tags) < 5:
        original = re.sub(r"[.!?;:]", " ", f"{titulo} {texto}")
        for ent in re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç-]+(?:\s+(?:de|da|do|dos|das|e|[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç-]+)){0,3}", original):
            if len(tags) >= 7:
                break
            ent = re.sub(r"\s+(e|de|da|do|dos|das)$", "", ent.strip(), flags=re.I)
            ent_n = _norm(ent)
            if ent_n in {"com", "por", "segundo", "nesta", "neste", "foto", "reproducao"}:
                continue
            if len(ent) >= 4:
                add(ent)

    for tag in ["Ururau", "Notícia"]:
        if len(tags) < 5:
            add(tag)
    return ", ".join(tags[:10])


def _subtitulo(sentencas: list[str], titulo: str, resumo: str = "") -> str:
    candidatos = sentencas[:]
    if resumo:
        candidatos.insert(0, resumo)
    titulo_n = _norm(titulo)
    for s in candidatos:
        if len(s) >= 35 and _norm(s)[:45] not in titulo_n:
            return _cortar_frase(s, 145).rstrip(" ,.;:-")
    return _cortar_frase(titulo, 120).rstrip(" ,.;:-")


def _nome_fonte_curto(fonte: str) -> str:
    fonte = re.sub(r"\s+", " ", str(fonte or "")).strip()
    if not fonte:
        return "Redação"
    palavras = fonte.split()
    if len(palavras) <= 4:
        return fonte
    return " ".join(palavras[:4])


def _sentencas_por_chaves(sentencas: list[str], chaves: list[str]) -> list[str]:
    out: list[str] = []
    for s in sentencas:
        ns = _norm(s)
        if any(k in ns for k in chaves) and _norm(s) not in [_norm(x) for x in out]:
            out.append(s)
    return out


def _montar_paragrafo(label: str, frases: list[str], limite: int = 620) -> str:
    texto = " ".join(f.strip() for f in frases if f and f.strip())
    texto = _cortar_frase(texto, limite)
    if not texto:
        return ""
    if label:
        return f"{label}\n{texto}"
    return texto




def _ja_usado(frase: str, usados: set[str]) -> bool:
    nf = _norm(frase)
    if not nf:
        return True
    for u in usados:
        if not u:
            continue
        if nf == u or (len(nf) > 45 and nf in u) or (len(u) > 45 and u in nf):
            return True
    return False

def _montar_corpo_esportes(titulo: str, resumo: str, sent: list[str], texto_limpo: str) -> str:
    """Monta texto esportivo factual, com organização de portal e sem dado externo."""
    paras: list[str] = []
    if sent:
        lede = sent[0]
        if resumo and _norm(resumo) not in _norm(lede) and len(lede) < 220:
            lede = f"{lede} {resumo}"
        paras.append(_cortar_frase(lede, 560))
    elif resumo:
        paras.append(_cortar_frase(resumo, 520))
    elif titulo:
        paras.append(titulo)

    contexto = _sentencas_por_chaves(sent, [
        "resultado", "vice-lideranca", "vice lideranca", "segunda colocacao", "pontos",
        "campeonato brasileiro", "brasileirao", "temporada", "vitoria seguida", "lider",
    ])
    agenda = _sentencas_por_chaves(sent, [
        "volta", "proxima", "proximo", "enfrenta", "libertadores", "sul-americana", "sul americana",
    ])
    desempenho = _sentencas_por_chaves(sent, [
        "primeiro tempo", "domin", "pressao", "vantagem", "controle", "dificuldade", "reag",
    ])

    usados = {_norm(p) for p in paras}
    for s0 in sent[:1]:
        usados.add(_norm(s0))
    blocos = [contexto, agenda, desempenho]
    for bloco in blocos:
        frases = []
        for s in bloco:
            ns = _norm(s)
            if not _ja_usado(s, usados):
                frases.append(s)
                usados.add(ns)
        if frases:
            paras.append(_montar_paragrafo("", frases[:2]))

    # Completa com outras frases factuais da fonte, sem repetir.
    for s in sent[1:10]:
        if len(paras) >= 6:
            break
        ns = _norm(s)
        if not _ja_usado(s, usados):
            paras.append(s)
            usados.add(ns)

    body = "\n\n".join(p for p in paras if p.strip())
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body


def _montar_corpo_saude(titulo: str, resumo: str, sent: list[str], texto_limpo: str) -> str:
    paras: list[str] = []
    if sent:
        paras.append(_cortar_frase(sent[0], 560))
    elif resumo:
        paras.append(_cortar_frase(resumo, 520))
    elif titulo:
        paras.append(titulo)

    programa = _sentencas_por_chaves(sent, ["programa", "pnaisp", "sus", "secretaria", "iniciativa", "ação", "acao"])
    atendimento = _sentencas_por_chaves(sent, ["atendimento", "tabag", "nicotina", "equipe", "profissionais", "pratica", "prática", "tratamento"])
    continuidade = _sentencas_por_chaves(sent, ["semanas", "monitorado", "novas etapas", "adesao", "adesão", "responsavel", "responsável"])

    usados = {_norm(p) for p in paras}
    for s0 in sent[:1]:
        usados.add(_norm(s0))
    for bloco in [programa, atendimento, continuidade]:
        frases = []
        for s in bloco:
            ns = _norm(s)
            if not _ja_usado(s, usados):
                frases.append(s)
                usados.add(ns)
        if frases:
            paras.append(_montar_paragrafo("", frases[:2]))

    for s in sent[1:10]:
        if len(paras) >= 6:
            break
        ns = _norm(s)
        if not _ja_usado(s, usados):
            paras.append(s)
            usados.add(ns)

    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(p for p in paras if p.strip())).strip()


def _montar_corpo(titulo: str, resumo: str, texto_limpo: str, canal: str) -> str:
    sent = _sentencas(texto_limpo)
    canal_n = _norm(canal)
    low = _norm(titulo + " " + texto_limpo)

    if "esporte" in canal_n or (any(c in low for c in ["flamengo", "vasco", "botafogo", "fluminense", "atletico-mg", "atlético-mg", "palmeiras", "corinthians"]) and any(k in low for k in ["gol", "placar", "brasileirao", "brasileirão", "libertadores", "campeonato"])):
        body = _montar_corpo_esportes(titulo, resumo, sent, texto_limpo)
    elif "saude" in canal_n or "saúde" in canal_n:
        body = _montar_corpo_saude(titulo, resumo, sent, texto_limpo)
    else:
        paras: list[str] = []
        if sent:
            paras.append(sent[0])
        elif resumo:
            paras.append(_cortar_frase(resumo, 420))
        elif titulo:
            paras.append(titulo)

        for s in sent[1:9]:
            if _norm(s) not in [_norm(p) for p in paras]:
                paras.append(s)

        if len("\n\n".join(paras)) < 650 and resumo and _norm(resumo) not in [_norm(p) for p in paras]:
            paras.insert(1, _cortar_frase(resumo, 420))

        if any(k in low for k in ["pis", "pasep", "fgts", "ressarcimento", "consultar", "calendario", "calendário"]):
            consulta = next((s for s in sent if any(k in _norm(s) for k in ["consult", "repis", "aplicativo", "fgts", "site"])), "")
            pedido = next((s for s in sent if any(k in _norm(s) for k in ["ressarcimento", "agencia", "agência", "pedido", "solicit"])), "")
            prazo = next((s for s in sent if any(k in _norm(s) for k in ["setembro de 2028", "25 de maio", "prazo", "recebera", "receberá", "calendario", "calendário"])), "")
            blocos = [paras[0] if paras else ""]
            if consulta:
                blocos.append("Como consultar valores disponíveis\n" + consulta)
            if pedido:
                blocos.append("Como solicitar o ressarcimento\n" + pedido)
            if prazo:
                blocos.append("Prazo final\n" + prazo)
            body = "\n\n".join([b for b in blocos if b.strip()])
        else:
            body = "\n\n".join(paras)

    for expr in FRASES_PROIBIDAS:
        body = re.sub(expr, "", body, flags=re.I)
    body = body.replace("—", "-").replace("–", "-").strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


def gerar_materia_fallback(pauta: Any, canal: str = "", motivo: str = "", auditar: bool = True) -> Materia:
    titulo_origem = _get(pauta, "titulo_origem") or _get(pauta, "titulo") or _get(pauta, "title")
    resumo = _get(pauta, "resumo_origem") or _get(pauta, "resumo") or _get(pauta, "subtitulo")
    texto = (
        _get(pauta, "cleaned_source_text") or _get(pauta, "texto_fonte") or
        _get(pauta, "dossie") or _get(pauta, "conteudo") or resumo or titulo_origem
    )
    fonte = _get(pauta, "fonte_nome") or _get(pauta, "nome_fonte") or _get(pauta, "source") or "Fonte original"
    link = _get(pauta, "link_origem") or _get(pauta, "link") or _get(pauta, "url")
    canal_final = classificar_canal_v78(titulo_origem, resumo + " " + texto, canal or _get(pauta, "canal_forcado"))
    texto_limpo = limpar_texto_fonte(texto)
    sent = _sentencas(texto_limpo)
    titulo = titulo_limpo(titulo_origem, canal_final) or _cortar_frase(sent[0] if sent else resumo, 89)
    body_txt = _montar_corpo(titulo, resumo, texto_limpo, canal_final)
    low = _norm(titulo + " " + texto_limpo)

    m = Materia()
    m.titulo = titulo
    m.titulo_capa = _cortar_frase(titulo, 60).rstrip(" ,.;:-")
    m.subtitulo = _subtitulo(sent, titulo, resumo)
    if "auriculoterapia" in low or "tabagismo" in low:
        m.legenda = "Atendimento integra ação de saúde pública"
    elif "repis" in low or "fgts" in low:
        m.legenda = "Consulta pode ser feita em canais oficiais"
    else:
        m.legenda = _cortar_frase(m.subtitulo or titulo, 100).rstrip(" ,.;:-")
    m.retranca = " ".join(str(canal_final).split()[:1])
    m.slug = slugify(titulo)
    m.meta_description = _meta(texto_limpo or body_txt, titulo)
    m.conteudo = body_txt
    m.resumo_curto = _meta(body_txt, titulo)
    m.chamada_social = (m.meta_description + ".").replace("..", ".")
    m.tags = _tags(titulo, texto_limpo, canal_final)
    m.fonte_nome = fonte
    m.nome_da_fonte = _nome_fonte_curto(fonte)
    m.link_origem = link
    m.canal = canal_final
    m.creditos_da_foto = "Reprodução"
    m.status = "rascunho"
    m.raw_source_text = texto
    m.cleaned_source_text = texto_limpo
    m.extraction_status = "fallback_local_v78c"
    m.extraction_method = "local"
    m.article_type = "fallback_local"
    # v46.7: fallback local explícito, sem mascarar como IA.
    try:
        from ururau.ia.diagnostico import trace_fallback, aplicar_trace_em_materia
        _trace_fb = trace_fallback(
            etapa="fallback_local_v78c",
            modelo="",
            motivo=str(motivo or "Fallback local usado."),
            uid=str(_get(pauta, "uid") or _get(pauta, "_uid") or ""),
            origem="ururau.editorial.fallback_local",
        )
        m.modo_geracao = "fallback_sem_ia"
        m.ia_provider = "local"
        m.ia_modelo = ""
        m.ia_status = "fallback_local"
        m.ia_etapa = "fallback_local_v78c"
        m.ia_chamada_ok = False
        m.ia_fallback_motivo = str(motivo or "Fallback local usado.")
        m.ia_erros = [_trace_fb]
        aplicar_trace_em_materia(m, _trace_fb, fallback_motivo=m.ia_fallback_motivo)
    except Exception:
        pass
    m.coverage_score = 0.92 if len(body_txt) >= 900 else (0.86 if len(body_txt) >= 650 else 0.70)
    if motivo:
        m.historico_correcoes.append({"etapa": "fallback_local_v78c", "motivo": str(motivo)[:500]})

    m.generated_article_json = {
        "titulo_seo": m.titulo,
        "titulo": m.titulo,
        "titulo_capa": m.titulo_capa,
        "subtitulo_curto": m.subtitulo,
        "subtitulo": m.subtitulo,
        "legenda_curta": m.legenda,
        "legenda": m.legenda,
        "retranca": m.retranca,
        "slug": m.slug,
        "tags": [x.strip() for x in m.tags.split(",") if x.strip()],
        "meta_description": m.meta_description,
        "resumo_curto": m.resumo_curto,
        "chamada_social": m.chamada_social,
        "corpo_materia": m.conteudo,
        "conteudo": m.conteudo,
        "texto_final": m.conteudo,
        "nome_da_fonte": m.nome_da_fonte,
        "fonte_nome": m.fonte_nome,
        "link_origem": m.link_origem,
        "creditos_da_foto": "Reprodução",
        "modo_geracao": "fallback_sem_ia",
        "ia_provider": "local",
        "ia_modelo": "",
        "ia_status": "fallback_local",
        "ia_etapa": "fallback_local_v78c",
        "ia_chamada_ok": False,
        "ia_fallback_motivo": str(motivo or "Fallback local usado."),
        "ia_erros": getattr(m, "ia_erros", []),
        "ia_trace": (getattr(m, "ia_erros", []) or [{}])[0] if getattr(m, "ia_erros", []) else {},
    }
    if auditar:
        return aplicar_auditoria_v78c(m, texto_fonte=texto_limpo, modo="panel", modo_geracao="fallback_sem_ia")
    return m
