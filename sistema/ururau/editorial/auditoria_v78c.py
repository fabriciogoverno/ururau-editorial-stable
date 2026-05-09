"""
ururau.editorial.auditoria_v78c — auditoria editorial determinística v78c.

Camada final de qualidade para impedir publicação de matéria fraca. Não chama IA.
Pode ser usada pelo painel, monitor 24h, fallback local e gates de publicação.
"""
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

import re
import unicodedata
from typing import Any

# URURAU v47.2: carrega blocklist única quando disponível.
try:
    from ururau.editorial.regras_editoriais import obter_termos_ia_proibidos as _v472_termos_ia
except Exception:
    _v472_termos_ia = None

FRASES_PROIBIDAS = (
    "acende o alerta",
    "fique atento",
    "confira todos os detalhes",
    "saiba mais",
    "veja abaixo",
    "vale lembrar",
    "cabe ressaltar",
    "nesse contexto",
    "é importante destacar",
    "e importante destacar",
    "é importante ressaltar",
    "e importante ressaltar",
    "o caso segue em andamento",
    "as autoridades seguem apurando",
    "as autoridades seguem com as apurações",
)

LIXO_SCRAPING = (
    "publicidade",
    "newsletter",
    "receba no whatsapp",
    "siga no google",
    "cookies",
    "todos os direitos reservados",
)

MESES = (
    "janeiro", "fevereiro", "março", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _get(obj: Any, nome: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get(nome, default) or "")
    return str(getattr(obj, nome, default) or "")


def _set(obj: Any, nome: str, valor: Any) -> None:
    if isinstance(obj, dict):
        obj[nome] = valor
    else:
        setattr(obj, nome, valor)


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto or ""))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip().lower()


def _limpar(texto: str) -> str:
    texto = re.sub(r"<[^>]+>", " ", str(texto or ""))
    texto = texto.replace("—", "-").replace("–", "-")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _paragraphs(corpo: str) -> list[str]:
    raw = str(corpo or "").replace("\r\n", "\n")
    if "<p" in raw.lower():
        raw = re.sub(r"</p>", "\n\n", raw, flags=re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n+", raw) if p.strip()]


def _tags_lista(tags: Any) -> list[str]:
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    if isinstance(tags, (list, tuple, set)):
        return [str(t).strip() for t in tags if str(t).strip()]
    return []


def _word_count(texto: str) -> int:
    return len(re.findall(r"\b[\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç-]{2,}\b", str(texto or "")))


def _numbers_and_dates(texto: str) -> set[str]:
    texto_n = _norm(texto)
    achados: set[str] = set()
    for m in re.findall(r"\b\d{1,3}(?:[\.\s]?\d{3})*(?:,\d+)?%?\b", texto_n):
        if m in {"10", "100", "120", "160", "500", "650", "900", "675"}:
            continue
        achados.add(re.sub(r"\s+", "", m))
    meses_re = "|".join(MESES)
    for m in re.findall(rf"\b\d{{1,2}}\s+de\s+(?:{meses_re})(?:\s+de\s+\d{{4}})?\b", texto_n):
        achados.add(m)
    for m in re.findall(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", texto_n):
        achados.add(m)
    return achados


def _erro(codigo: str, mensagem: str, categoria: str = "FIXABLE_FIELD", bloqueia: bool = False) -> dict:
    return {
        "categoria": categoria,
        "codigo": codigo,
        "mensagem": mensagem,
        "bloqueia_publicacao": bool(bloqueia),
        "corrigivel_automaticamente": categoria != "EDITORIAL_BLOCKER",
    }


def auditar_materia_10(materia: Any, texto_fonte: str = "", modo: str = "panel") -> dict:
    """Calcula score 0-100 e decisão editorial v78c sem chamar IA."""
    modo = (modo or "panel").lower()
    titulo = _get(materia, "titulo") or _get(materia, "titulo_seo")
    titulo_capa = _get(materia, "titulo_capa")
    subtitulo = _get(materia, "subtitulo") or _get(materia, "subtitulo_curto")
    retranca = _get(materia, "retranca") or _get(materia, "canal")
    corpo = _get(materia, "conteudo") or _get(materia, "corpo_materia") or _get(materia, "texto_final")
    meta = _get(materia, "meta_description")
    fonte = _get(materia, "nome_da_fonte") or _get(materia, "fonte_nome")
    credito = _get(materia, "creditos_da_foto") or _get(materia, "credito_foto")
    link = _get(materia, "link_origem") or _get(materia, "linkfonte")
    tags = _tags_lista(_get(materia, "tags"))
    if not tags and isinstance(materia, dict):
        tags = _tags_lista(materia.get("tags"))

    erros: list[dict] = []
    score = 100

    def penalizar(pontos: int, codigo: str, mensagem: str, categoria: str = "FIXABLE_FIELD", bloqueia: bool = False) -> None:
        nonlocal score
        score -= pontos
        erros.append(_erro(codigo, mensagem, categoria, bloqueia))

    # Campos essenciais
    if not titulo or len(titulo.strip()) < 18:
        penalizar(18, "titulo_fraco", "Título ausente ou curto demais.", "EDITORIAL_BLOCKER", True)
    elif len(titulo) > 89:
        penalizar(10, "titulo_seo_longo", f"Título SEO tem {len(titulo)} caracteres; limite é 89.")

    if not titulo_capa:
        penalizar(5, "titulo_capa_ausente", "Título de capa ausente.")
    elif len(titulo_capa) > 60:
        penalizar(8, "titulo_capa_longo", f"Título de capa tem {len(titulo_capa)} caracteres; limite é 60.")

    if not subtitulo or len(subtitulo.strip()) < 35:
        penalizar(8, "subtitulo_fraco", "Subtítulo ausente ou pouco informativo.")
    elif len(subtitulo) > 220:
        penalizar(3, "subtitulo_longo", "Subtítulo está longo demais.")

    palavras_retranca = [p for p in retranca.split() if p]
    if not palavras_retranca:
        penalizar(5, "retranca_ausente", "Retranca/editoria ausente.")
    elif len(palavras_retranca) > 1:
        penalizar(4, "retranca_longa", "Retranca deve ter uma palavra.")

    pars = _paragraphs(corpo)
    corpo_limpo = _limpar(corpo)
    corpo_len = len(corpo_limpo)
    fonte_len = len(_limpar(texto_fonte or ""))
    fonte_curta = 120 <= fonte_len < 500
    fonte_minima = fonte_len < 120

    if not corpo_limpo:
        penalizar(45, "corpo_ausente", "Corpo da matéria ausente.", "EDITORIAL_BLOCKER", True)
    elif corpo_len < 220:
        penalizar(35, "corpo_muito_curto", f"Corpo tem {corpo_len} caracteres; não há material jornalístico suficiente.", "EDITORIAL_BLOCKER", True)
    elif corpo_len < 500:
        if fonte_minima:
            penalizar(30, "corpo_curto_fonte_minima", f"Corpo tem {corpo_len} caracteres e a fonte é mínima; bloquear por segurança.", "EDITORIAL_BLOCKER", True)
        elif fonte_curta:
            penalizar(14, "corpo_curto_fonte_curta", f"Corpo tem {corpo_len} caracteres; fonte original também é curta, portanto salvar como rascunho.")
        else:
            penalizar(30, "corpo_curto", f"Corpo tem {corpo_len} caracteres; mínimo seguro é 500.", "EDITORIAL_BLOCKER", True)
    elif corpo_len < 900 and fonte_len >= 900:
        penalizar(12, "corpo_pouco_desenvolvido", f"Corpo tem {corpo_len} caracteres; ideal é acima de 900 quando a fonte permitir.")
    elif corpo_len < 900 and fonte_len >= 500:
        penalizar(6, "corpo_moderado", f"Corpo tem {corpo_len} caracteres; aceitável, mas ainda curto para material mais completo.")

    if pars and len(pars) < 3 and corpo_len >= 500:
        penalizar(8, "poucos_paragrafos", "Texto tem poucos parágrafos para padrão de portal profissional.")
    elif pars and len(pars) < 2 and corpo_len >= 220:
        penalizar(6, "texto_pouco_segmentado", "Texto tem pouca segmentação em parágrafos.")

    # Repetição e estilo
    norm_pars = [_norm(p) for p in pars if len(p) > 40]
    if len(norm_pars) != len(set(norm_pars)):
        penalizar(8, "paragrafo_repetido", "Há parágrafos repetidos.")

    corpo_norm = _norm(corpo)
    frases_editoriais = list(FRASES_PROIBIDAS)
    try:
        if _v472_termos_ia:
            frases_editoriais = list(dict.fromkeys(frases_editoriais + list(_v472_termos_ia())))
    except Exception:
        pass
    for frase in frases_editoriais:
        if _norm(frase) in corpo_norm:
            penalizar(14, "termo_ia_ou_frase_proibida", f"Expressão proibida ou termo de IA encontrado: {frase!r}.", "EDITORIAL_BLOCKER", True)

    if "—" in str(corpo) or "–" in str(corpo):
        penalizar(6, "travessao_no_corpo", "Corpo contém travessão; usar vírgula, dois-pontos ou ponto.")

    for lixo in LIXO_SCRAPING:
        if lixo in corpo_norm:
            penalizar(10, "lixo_scraping", f"Conteúdo contém ruído de scraping: {lixo!r}.")

    if not meta or len(meta) < 70:
        penalizar(5, "meta_description_fraca", "Meta description ausente ou curta.")
    elif len(meta) > 160:
        penalizar(4, "meta_description_longa", "Meta description acima de 160 caracteres.")

    if not fonte:
        penalizar(6, "fonte_ausente", "Nome da fonte ausente.")
    elif _word_count(fonte) > 4:
        penalizar(2, "fonte_longa", "Nome da fonte deve ter até 4 palavras no CMS.")

    if not credito:
        penalizar(5, "credito_foto_ausente", "Crédito da foto ausente.")
    elif _word_count(credito) > 6:
        penalizar(2, "credito_foto_longo", "Crédito da foto deve ter até 6 palavras.")

    if not link:
        penalizar(6, "link_fonte_ausente", "Link da fonte original ausente.")

    tags_norm = [_norm(t) for t in tags]
    if len(tags) < 5:
        penalizar(6, "tags_insuficientes", "Menos de 5 tags úteis.")
    if len(tags) > 12:
        penalizar(3, "tags_excesso", "Mais de 12 tags; reduzir para SEO mais limpo.")
    if len(tags_norm) != len(set(tags_norm)):
        penalizar(5, "tags_duplicadas", "Tags duplicadas.")

    # Coerência editorial entre pauta, canal, retranca, legenda e tags.
    contexto_norm = _norm(" ".join([titulo, titulo_capa, subtitulo, corpo, texto_fonte]))
    metadados_norm = _norm(" ".join([retranca, _get(materia, "canal"), _get(materia, "legenda") or _get(materia, "legenda_curta"), " ".join(tags)]))
    politicos = (
        "quaest", "pesquisa eleitoral", "intencao de voto", "intencoes de voto", "intenção de voto", "intenções de voto",
        "governo do rj", "governo do rio", "alerj", "stf", "tse", "tre", "palacio guanabara", "palácio guanabara",
        "eduardo paes", "douglas ruas", "garotinho", "wilson witzel", "rodrigo bacellar", "governador", "mandato",
    )
    servico_economia = (
        "pis", "pasep", "fgts", "repis", "nis", "caixa economica", "caixa econômica", "dinheiro esquecido", "tesouro nacional",
    )
    esporte = ("flamengo", "vasco", "botafogo", "fluminense", "brasileirao", "brasileirão", "libertadores", "gol", "placar")
    contexto_politico = any(x in contexto_norm for x in politicos)
    if contexto_politico and any(x in metadados_norm for x in servico_economia):
        penalizar(
            35,
            "metadados_contaminados_por_servico_economia",
            "Matéria política recebeu legenda, tags ou retranca de PIS/FGTS/Repis/Caixa.",
            "EDITORIAL_BLOCKER",
            True,
        )
    if contexto_politico and "esporte" in metadados_norm and not any(x in contexto_norm for x in esporte):
        penalizar(
            28,
            "canal_esportes_incompativel_com_politica",
            "Matéria política foi marcada como Esportes sem termos esportivos reais na fonte.",
            "EDITORIAL_BLOCKER",
            True,
        )
    if contexto_politico and "economia" in metadados_norm and not any(x in contexto_norm for x in servico_economia):
        penalizar(
            22,
            "retranca_economia_incompativel_com_politica",
            "Matéria política foi marcada como Economia sem assunto econômico real na fonte.",
            "EDITORIAL_BLOCKER",
            True,
        )

    # Checagem simples de números/datas inventados.
    if texto_fonte:
        nums_corpo = _numbers_and_dates(corpo)
        nums_fonte = _numbers_and_dates(texto_fonte)
        ausentes = sorted(n for n in nums_corpo if n and n not in nums_fonte)
        if ausentes:
            penalizar(
                min(18, 6 + len(ausentes) * 3),
                "numero_ou_data_sem_fonte",
                "Número/data aparece no texto final, mas não foi localizado na fonte: " + ", ".join(ausentes[:5]),
                "EDITORIAL_BLOCKER",
                True,
            )

    # Status sistêmico nunca pode passar.
    status_validacao = _get(materia, "status_validacao")
    if status_validacao in {"erro_configuracao", "erro_extracao", "reprovado"}:
        penalizar(30, "status_validacao_bloqueante", f"Status de validação bloqueante: {status_validacao}.", "EDITORIAL_BLOCKER", True)

    score = max(0, min(100, int(score)))
    bloqueadores = [e for e in erros if e.get("bloqueia_publicacao") or e.get("categoria") == "EDITORIAL_BLOCKER"]

    if bloqueadores or score < 75:
        decisao = "rejeitar"
        status_validacao_final = "reprovado"
        status_pipeline = "bloquear"
    elif score < 90:
        decisao = "salvar_rascunho"
        status_validacao_final = "pendente"
        status_pipeline = "salvar_rascunho"
    else:
        decisao = "publicar"
        status_validacao_final = "aprovado"
        status_pipeline = "publicar_direto" if modo in {"monitor", "direct", "publicar"} else "salvar_rascunho"

    resumo = (
        f"v78c: score {score}/100; decisão={decisao}; "
        f"bloqueadores={len(bloqueadores)}; avisos={len(erros) - len(bloqueadores)}."
    )

    return {
        "score_qualidade": score,
        "score_risco": 100 - score,
        "aprovado": decisao == "publicar",
        "decisao": decisao,
        "status_validacao": status_validacao_final,
        "status_pipeline": status_pipeline,
        "auditoria_bloqueada": decisao == "rejeitar",
        "revisao_humana_necessaria": decisao != "publicar",
        "erros": erros,
        "bloqueadores": bloqueadores,
        "resumo_auditoria": resumo,
    }


def aplicar_auditoria_v78c(materia: Any, texto_fonte: str = "", modo: str = "panel", modo_geracao: str = "") -> Any:
    """Aplica a auditoria v78c ao objeto Materia ou dict e devolve o mesmo objeto."""
    if not materia:
        return materia
    if not texto_fonte:
        texto_fonte = _get(materia, "cleaned_source_text") or _get(materia, "raw_source_text")

    auditoria = auditar_materia_10(materia, texto_fonte=texto_fonte, modo=modo)
    erros_atuais = []
    try:
        erros_atuais = list(getattr(materia, "erros_validacao", []) or []) if not isinstance(materia, dict) else list(materia.get("erros_validacao", []) or [])
    except Exception:
        erros_atuais = []
    codigos = {e.get("codigo") for e in erros_atuais if isinstance(e, dict)}
    erros_final = erros_atuais + [e for e in auditoria["erros"] if isinstance(e, dict) and e.get("codigo") not in codigos]

    _set(materia, "score_qualidade", auditoria["score_qualidade"])
    _set(materia, "score_editorial", auditoria["score_qualidade"])
    _set(materia, "score_risco_validacao", auditoria["score_risco"])
    _set(materia, "score_risco", auditoria["score_risco"])
    _set(materia, "auditoria_aprovada", auditoria["decisao"] == "publicar")
    _set(materia, "auditoria_bloqueada", auditoria["auditoria_bloqueada"])
    _set(materia, "status_validacao", auditoria["status_validacao"])
    _set(materia, "status_publicacao_sugerido", auditoria["decisao"] if auditoria["decisao"] != "rejeitar" else "bloquear")
    _set(materia, "status_pipeline", auditoria["status_pipeline"])
    _set(materia, "revisao_humana_necessaria", auditoria["revisao_humana_necessaria"])
    _set(materia, "erros_validacao", erros_final)

    # Metadados e JSON interno para painel/relatórios.
    try:
        meta = dict(getattr(materia, "metadados_apurados", {}) or {}) if not isinstance(materia, dict) else dict(materia.get("metadados_apurados", {}) or {})
        meta["auditoria_v78c"] = auditoria
        meta["modo_geracao"] = modo_geracao or meta.get("modo_geracao") or "indefinido"
        _set(materia, "metadados_apurados", meta)
    except Exception:
        pass

    try:
        gj = dict(getattr(materia, "generated_article_json", {}) or {}) if not isinstance(materia, dict) else dict(materia.get("generated_article_json", {}) or {})
        gj.update({
            "score_qualidade": auditoria["score_qualidade"],
            "score_risco": auditoria["score_risco"],
            "resumo_auditoria": auditoria["resumo_auditoria"],
            "decisao_auditoria": auditoria["decisao"],
            "modo_geracao": modo_geracao or gj.get("modo_geracao") or "indefinido",
            "erros_validacao": erros_final,
        })
        _set(materia, "generated_article_json", gj)
    except Exception:
        pass

    return materia
