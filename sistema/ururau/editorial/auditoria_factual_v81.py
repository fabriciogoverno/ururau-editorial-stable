"""
ururau/editorial/auditoria_factual_v81.py
Auditoria factual rígida para publicação automática.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from ururau.coleta.limpeza_texto_v81 import limpar_texto_fonte_v81, texto_util_chars

_NUM_RE = re.compile(r"\b(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?:\s?%|\s?milh(?:ão|oes|ões)|\s?mil|\s?pontos? percentuais)?\b", re.I)
_REG_RE = re.compile(r"\b[A-Z]{2}-\d{4,8}/\d{4}\b")
_PARTIDO_RE = re.compile(r"\b(?:PSD|PL|PT|Republicanos|DC|União Brasil|MDB|PP|PSB|PDT|PSOL|Novo|Podemos|Avante|Solidariedade)\b", re.I)

_EXPANSOES = {
    "segundo_turno": ["segundo turno", "2º turno", "2° turno"],
    "senado": ["senado", "senador", "senadora"],
    "avaliacao_governo": ["avaliação do governo", "avaliação negativa", "regular", "positivo", "negativo"],
    "decisao_stf": ["stf", "supremo tribunal federal", "decisão do supremo"],
    "crise_institucional": ["crise institucional", "dupla vacância", "governador-tampão", "governador tampão"],
}

def _norm(s: str) -> str:
    s = str(s or "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9%/.-]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _get(obj: Any, key: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get(key, default) or "")
    return str(getattr(obj, key, default) or "")

def _set(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = value
    else:
        try:
            setattr(obj, key, value)
        except Exception:
            pass

def _article_text(materia: Any) -> str:
    campos = [
        "titulo", "titulo_seo", "titulo_capa", "subtitulo", "meta_description",
        "resumo_curto", "chamada_social", "tags", "conteudo", "corpo_materia", "legenda"
    ]
    return "\n".join(_get(materia, c) for c in campos if _get(materia, c))

def extrair_evidencias(texto_fonte: str) -> dict:
    fonte_limpa = limpar_texto_fonte_v81(texto_fonte or "")
    norm = _norm(fonte_limpa)
    numeros = set(_norm(m.group(0)) for m in _NUM_RE.finditer(fonte_limpa))
    for m in _REG_RE.finditer(fonte_limpa):
        numeros.add(_norm(m.group(0)))
    partidos = set(m.group(0).upper() for m in _PARTIDO_RE.finditer(fonte_limpa))
    return {
        "texto_limpo": fonte_limpa,
        "norm": norm,
        "chars_uteis": texto_util_chars(fonte_limpa),
        "numeros": sorted(numeros),
        "partidos": sorted(partidos),
    }

def _valor_suportado(valor_norm: str, evidencias: dict) -> bool:
    fonte_norm = evidencias["norm"]
    if not valor_norm:
        return True
    if valor_norm in fonte_norm:
        return True
    alt = valor_norm.replace(".", "").replace(",", ".")
    if alt and alt in fonte_norm:
        return True
    # aceita quando número foi capturado com palavra "pontos percentuais" mas fonte só tem o numeral
    base = re.sub(r"\s+(mil|milhoes|milh[ao]o|pontos? percentuais)$", "", valor_norm).strip()
    return bool(base and base in fonte_norm)

def _termo_existe_no_fonte(termos: list[str], evidencias: dict) -> bool:
    fonte_norm = evidencias["norm"]
    return any(_norm(t) in fonte_norm for t in termos)

def _limpar_tags_sem_evidencia(tags: str, evidencias: dict, texto_artigo_norm: str) -> str:
    saida = []
    for tag in [t.strip() for t in re.split(r"[,;]", tags or "") if t.strip()]:
        tn = _norm(tag)
        if tn in {"politica", "policia", "estado rj", "cidades", "brasil e mundo", "esportes", "saude", "educacao", "economia"}:
            saida.append(tag)
            continue
        if tn in evidencias["norm"] or tn in texto_artigo_norm:
            saida.append(tag)
    seen = set(); final = []
    for t in saida:
        k = _norm(t)
        if k not in seen:
            seen.add(k); final.append(t)
    return ", ".join(final[:12])

def _corrigir_meta(meta: str) -> str:
    meta = re.sub(r"\s+", " ", meta or "").strip()
    if len(meta) > 155:
        meta = meta[:155].rsplit(" ", 1)[0].strip()
    if meta and meta[-1] not in ".!?":
        meta += "."
    return meta

def auditar_factualmente(materia: Any, texto_fonte: str) -> dict:
    evid = extrair_evidencias(texto_fonte)
    texto_artigo = _article_text(materia)
    texto_norm = _norm(texto_artigo)

    motivos: list[str] = []
    claims_sem_evidencia: list[str] = []
    contradicoes: list[str] = []
    campos_corrigidos: dict[str, Any] = {}
    score = 100

    if evid["chars_uteis"] < 500:
        motivos.append(f"Fonte útil insuficiente para publicação automática: {evid['chars_uteis']} caracteres.")
        score -= 35

    nums_artigo = set(_norm(m.group(0)) for m in _NUM_RE.finditer(texto_artigo))
    for m in _REG_RE.finditer(texto_artigo):
        nums_artigo.add(_norm(m.group(0)))
    for n in sorted(nums_artigo):
        if not _valor_suportado(n, evid):
            claims_sem_evidencia.append(f"Número/registro sem evidência no fonte: {n}")
            score -= 20

    for chave, termos in _EXPANSOES.items():
        if any(_norm(t) in texto_norm for t in termos) and not _termo_existe_no_fonte(termos, evid):
            claims_sem_evidencia.append(f"Expansão não comprovada no fonte: {chave}")
            score -= 18

    if "claudio castro" in texto_norm:
        fala_atual = any(x in texto_norm for x in [
            "atual governador claudio castro",
            "governo do atual governador claudio castro",
            "governador claudio castro",
        ])
        fala_saida = any(x in texto_norm for x in ["renuncia", "cassacao", "cassado", "dupla vacancia", "afastamento"])
        if fala_atual and fala_saida:
            contradicoes.append("Texto chama Cláudio Castro de atual governador e também menciona renúncia/cassação/dupla vacância.")
            score -= 40

    lixo = ["beneficio do assinante", "benefício do assinante", "copiar link", "salvar para ler depois", "assine a folha"]
    if any(_norm(x) in texto_norm for x in lixo):
        motivos.append("Texto final contém metadados/paywall da fonte.")
        score -= 25

    tags = _get(materia, "tags")
    if tags:
        tags_limpas = _limpar_tags_sem_evidencia(tags, evid, texto_norm)
        if tags_limpas != tags:
            campos_corrigidos["tags"] = tags_limpas
            _set(materia, "tags", tags_limpas)

    meta = _get(materia, "meta_description")
    if meta:
        meta2 = _corrigir_meta(meta)
        if meta2 != meta:
            campos_corrigidos["meta_description"] = meta2
            _set(materia, "meta_description", meta2)

    credito = _get(materia, "creditos_da_foto") or _get(materia, "credito_foto")
    if not credito:
        _set(materia, "creditos_da_foto", "Reprodução")
        campos_corrigidos["creditos_da_foto"] = "Reprodução"

    corpo = _get(materia, "conteudo") or _get(materia, "corpo_materia")
    if len(corpo.strip()) < 800 and evid["chars_uteis"] >= 1500:
        motivos.append("Corpo curto demais para fonte completa.")
        score -= 10

    proibidas = ["acende o alerta", "em meio a um cenário", "reforça a importância"]
    for p in proibidas:
        if _norm(p) in texto_norm:
            motivos.append(f"Expressão proibida/IA detectada: {p}")
            score -= 8

    titulo = _get(materia, "titulo")
    titulo_capa = _get(materia, "titulo_capa")
    if len(titulo) > 89:
        score -= 8; motivos.append(f"Título SEO acima de 89 caracteres: {len(titulo)}")
    if titulo_capa and len(titulo_capa) > 60:
        score -= 8; motivos.append(f"Título de capa acima de 60 caracteres: {len(titulo_capa)}")

    score = max(0, min(100, score))
    bloqueio_grave = bool(claims_sem_evidencia or contradicoes)
    if bloqueio_grave or score < 75:
        status = "reprovado"; pode_publicar = False
    elif score < 95:
        status = "rascunho"; pode_publicar = False
    else:
        status = "aprovado"; pode_publicar = True

    return {
        "score": score,
        "status": status,
        "pode_publicar": pode_publicar,
        "motivos": motivos,
        "claims_sem_evidencia": claims_sem_evidencia,
        "contradicoes": contradicoes,
        "campos_corrigidos": campos_corrigidos,
        "evidencias_resumo": {
            "chars_uteis": evid["chars_uteis"],
            "numeros": evid["numeros"][:30],
            "partidos": evid["partidos"][:20],
        },
    }

def aplicar_gate_publicacao_v81(materia: Any, auditoria: dict) -> Any:
    score = int(auditoria.get("score", 0))
    status = auditoria.get("status", "reprovado")
    motivos = []
    motivos.extend(auditoria.get("motivos") or [])
    motivos.extend(auditoria.get("claims_sem_evidencia") or [])
    motivos.extend(auditoria.get("contradicoes") or [])

    _set(materia, "score_qualidade", score)
    _set(materia, "auditoria_factual_v81", auditoria)
    if status == "aprovado":
        _set(materia, "status_validacao", "aprovado")
        _set(materia, "status_publicacao_sugerido", "publicar_direto")
        _set(materia, "status_pipeline", "publicar_direto")
        _set(materia, "auditoria_aprovada", True)
        _set(materia, "auditoria_bloqueada", False)
        _set(materia, "revisao_humana_necessaria", False)
    elif status == "rascunho":
        _set(materia, "status_validacao", "pendente")
        _set(materia, "status_publicacao_sugerido", "salvar_rascunho")
        _set(materia, "status_pipeline", "salvar_rascunho")
        _set(materia, "auditoria_aprovada", False)
        _set(materia, "auditoria_bloqueada", False)
        _set(materia, "revisao_humana_necessaria", True)
    else:
        _set(materia, "status_validacao", "reprovado")
        _set(materia, "status_publicacao_sugerido", "bloquear")
        _set(materia, "status_pipeline", "bloquear")
        _set(materia, "auditoria_aprovada", False)
        _set(materia, "auditoria_bloqueada", True)
        _set(materia, "revisao_humana_necessaria", True)

    _set(materia, "auditoria_erros", motivos)
    try:
        gj = getattr(materia, "generated_article_json", {}) or {}
        gj["auditoria_factual_v81"] = auditoria
        gj["modo_auditoria"] = "v81_factual_rigida"
        setattr(materia, "generated_article_json", gj)
    except Exception:
        pass
    return materia

def aplicar_auditoria_materia_v81(materia: Any, pauta: Any | None = None, texto_fonte: str | None = None) -> Any:
    if texto_fonte is None:
        if isinstance(pauta, dict):
            texto_fonte = (
                pauta.get("cleaned_source_text") or pauta.get("dossie") or pauta.get("texto_fonte")
                or pauta.get("raw_source_text") or pauta.get("resumo_origem") or ""
            )
        else:
            texto_fonte = (
                _get(materia, "cleaned_source_text") or _get(materia, "raw_source_text")
                or _get(materia, "original_source_text") or ""
            )
    auditoria = auditar_factualmente(materia, texto_fonte or "")
    print(f"[v81] auditoria_factual: score={auditoria['score']} status={auditoria['status']} claims={len(auditoria['claims_sem_evidencia'])} contrad={len(auditoria['contradicoes'])}")
    if auditoria.get("claims_sem_evidencia"):
        print(f"[v81] claims_sem_evidencia: {auditoria['claims_sem_evidencia'][:3]}")
    if auditoria.get("contradicoes"):
        print(f"[v81] contradicoes: {auditoria['contradicoes'][:3]}")
    return aplicar_gate_publicacao_v81(materia, auditoria)
