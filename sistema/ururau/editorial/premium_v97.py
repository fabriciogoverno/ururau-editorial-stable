"""
premium_v97.py — camada de redação premium do Ururau.
Impede que GPT-4.1-mini produza apenas resumo/1 parágrafo quando há fonte suficiente.
"""
from __future__ import annotations
import json, re
try:
    from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101, limpar_corpo_publicacao_v101
except Exception:
    def limpar_texto_artigo_v101(texto: str, titulo: str = "", max_chars: int = 16000) -> str: return str(texto or "").strip()[:max_chars]
    def limpar_corpo_publicacao_v101(corpo: str) -> str: return str(corpo or "").strip()
from typing import Any

def _norm(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", str(text or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip()

def paragraphs(text: str) -> list[str]:
    body = str(text or "").replace("\r\n", "\n").strip()
    pars = [p.strip() for p in re.split(r"\n\s*\n+", body) if p.strip()]
    if len(pars) <= 1 and len(body) > 900:
        parts = re.split(r"(?<=[.!?])\s+", body)
        pars, cur = [], []
        for s in parts:
            s = s.strip()
            if not s: continue
            cur.append(s)
            if len(" ".join(cur)) >= 260:
                pars.append(" ".join(cur).strip()); cur = []
        if cur: pars.append(" ".join(cur).strip())
    return pars

def min_requirements(source_text: str) -> tuple[int, int]:
    n = len(str(source_text or "").strip())
    if n >= 4200: return 7, 2600
    if n >= 2600: return 6, 2100
    if n >= 1400: return 5, 1500
    if n >= 800: return 4, 1000
    return 3, 650

def is_thin(body: str, source_text: str) -> tuple[bool, str]:
    body = str(body or "").strip()
    if len(str(source_text or "")) < 800: return False, ""
    min_p, min_c = min_requirements(source_text)
    ps = paragraphs(body)
    if len(ps) < min_p: return True, f"{len(ps)} parágrafos; mínimo {min_p}"
    if len(body) < min_c: return True, f"{len(body)} caracteres; mínimo {min_c}"
    return False, ""

def clean_body(text: str) -> str:
    t = str(text or "").replace("—", ",").replace("–", "-")
    for pat in [r"(?i)\bacende o alerta\b", r"(?i)\bvale lembrar que\b", r"(?i)\bé importante destacar que\b", r"(?i)\bcabe ressaltar que\b", r"(?i)\bnesse contexto\b", r"(?i)\bem meio a\b", r"(?i)\bnovas informações serão divulgadas\b", r"(?i)\bo caso segue em andamento\b"]:
        t = re.sub(pat, "", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def source_sentences(source_text: str) -> list[str]:
    source_text = limpar_texto_artigo_v101(source_text or "", max_chars=16000)
    raw = re.sub(r"<[^>]+>", " ", str(source_text or ""))
    raw = re.sub(r"\s+", " ", raw).strip()
    parts = re.split(r"(?<=[.!?])\s+", raw)
    bad = ("publicidade", "leia também", "leia tambem", "compartilhe", "newsletter", "cookies", "todos os direitos", "foto:", "reprodução", "volte ao menu", "inscreva-se")
    out, seen = [], set()
    for s in parts:
        s = re.sub(r"\s+", " ", s or "").strip(" -•\t\n\r")
        low = s.lower()
        if len(s) < 45 or any(x in low for x in bad): continue
        key = _norm(s)[:150]
        if key not in seen:
            seen.add(key); out.append(s)
    return out

def fallback_body(source_text: str, article_type: str = "", channel: str = "") -> str:
    sents = source_sentences(source_text)
    if not sents: return ""
    min_p, min_c = min_requirements(source_text)
    blocks = []
    lead = " ".join(sents[:2]) if len(sents) > 1 and len(sents[0]) < 170 else sents[0]
    blocks.append(lead.strip())
    i = 2 if lead != sents[0] else 1
    h = 0
    while i < len(sents) and (len(blocks) < min_p or len("\n\n".join(blocks)) < min_c):
        chunk = []
        while i < len(sents) and len(" ".join(chunk)) < 260:
            chunk.append(sents[i]); i += 1
            if len(chunk) >= 3: break
        txt = " ".join(chunk).strip()
        if not txt: continue
        blocks.append(txt)
    return limpar_corpo_publicacao_v101(clean_body("\n\n".join(blocks)))

def parse_json(raw: str) -> dict:
    txt = (raw or "").strip()
    txt = re.sub(r"^```(?:json)?\s*", "", txt, flags=re.I).strip()
    txt = re.sub(r"\s*```$", "", txt).strip()
    try: return json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt, flags=re.S)
        if m:
            try: return json.loads(m.group(0))
            except Exception: return {}
    return {}

def tags_from_source(source_text: str, title: str, channel: str) -> str:
    text = (title + " " + source_text[:3000]).lower()
    pairs = [("STF","stf"),("Alerj","alerj"),("Rio de Janeiro","rio de janeiro"),("Campos dos Goytacazes","campos"),("Norte Fluminense","norte fluminense"),("Ministério Público","ministério público"),("Polícia Civil","polícia civil"),("Polícia Militar","polícia militar"),("Saúde","saúde"),("Educação","educação")]
    tags = []
    if channel and channel.lower() not in ("geral", "redação"): tags.append(channel)
    for label, key in pairs:
        if key in text: tags.append(label)
    for m in re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+){0,2}\b", title + " " + source_text[:1200]):
        if 3 <= len(m) <= 45: tags.append(m)
    seen, out = set(), []
    for t in tags:
        nt = _norm(t)
        if not nt or nt in seen or nt in {"noticia", "noticias", "ururau"}: continue
        seen.add(nt); out.append(t)
    return ", ".join(out[:12])

def build_prompt(source_text: str, current: dict, meta: dict) -> str:
    min_p, min_c = min_requirements(source_text)
    return f'''
Você é editor sênior do Ururau. Reescreva a matéria em padrão jornalístico profissional, com densidade real, SEO e autenticidade.

TAREFA CENTRAL:
Transformar o TEXTO-FONTE em matéria AUTÊNTICA, não em resumo. Use apenas fatos do texto-fonte, mas reorganize a narrativa com lead, contexto, desenvolvimento, efeitos práticos e fechamento factual.

REGRAS INEGOCIÁVEIS:
1. Use somente fatos comprovados no TEXTO-FONTE. Não invente dado, data, cargo, órgão, valor, declaração ou consequência.
2. Não copie blocos inteiros da fonte. Reescreva com linguagem própria jornalística.
3. Corpo com no mínimo {min_p} parágrafos e pelo menos {min_c} caracteres quando a fonte permitir.
4. Proibido entregar 1 parágrafo. Proibido entregar só subtítulo.
5. Primeiro parágrafo: lead completo com fato principal, personagem/instituição, local e consequência imediata, quando constarem na fonte.
6. Depois do lead, desenvolva contexto, antecedentes, detalhes concretos, impacto público e próximo passo documentado.
7. Não use intertítulos no corpo. Escreva apenas parágrafos jornalísticos corridos.
8. Não use travessão. Não use "acende o alerta". Evite "vale lembrar", "cabe ressaltar", "nesse contexto", "em meio a" e "reforça" como muleta textual.
9. SEO: título SEO até 89 caracteres, título de capa até 60, meta description entre 120 e 160 caracteres, retranca de uma palavra, tags entre 8 e 12 separadas por vírgula.
10. Texto em padrão G1/UOL/Estadão, factual, sem opinião e sem tom institucional.

DADOS:
Canal: {meta.get("channel", "")}
Tipo: {meta.get("article_type", "")}
Título original: {meta.get("title", "")}
Subtítulo original: {meta.get("subtitle", "")}
Fonte: {meta.get("source_name", "")}
Link: {meta.get("source_url", "")}

MATÉRIA ATUAL:
Título: {current.get("titulo", "")}
Subtítulo: {current.get("subtitulo", "")}
Corpo atual: {current.get("conteudo", "")[:1000]}

TEXTO-FONTE COMPLETO:
{source_text[:14000]}

Retorne APENAS JSON válido, sem markdown, com estes campos:
{{
  "titulo_seo": "",
  "titulo_capa": "",
  "retranca": "",
  "subtitulo_curto": "",
  "legenda_curta": "",
  "meta_description": "",
  "tags": "",
  "nome_da_fonte": "",
  "link_da_fonte": "",
  "creditos_da_foto": "",
  "corpo_materia": "",
  "resumo_curto": "",
  "chamada_social": ""
}}
'''.strip()

def apply_to_materia(m: Any, data: dict, source_text: str, meta: dict) -> Any:
    try:
        from ururau.editorial.safe_title import safe_title, safe_truncate
    except Exception:
        def safe_title(x, n): return str(x or "")[:n].rstrip()
        def safe_truncate(x, n): return str(x or "")[:n].rstrip()
    body = limpar_corpo_publicacao_v101(clean_body(data.get("corpo_materia") or data.get("conteudo") or ""))
    thin, why_thin = is_thin(body, source_text)
    if thin:
        body = fallback_body(source_text, meta.get("article_type", ""), meta.get("channel", ""))
        data.setdefault("modo_geracao", "fallback_sem_ia")
        data.setdefault("ia_provider", "local")
        data.setdefault("ia_status", "fallback_local_premium_v97_corpo_raso")
        data.setdefault("ia_chamada_ok", False)
        data.setdefault("ia_fallback_motivo", f"Resposta da IA ausente/curta na camada premium_v97: {why_thin}")
    title = safe_title(data.get("titulo_seo") or getattr(m, "titulo", "") or meta.get("title", ""), 89)
    capa = safe_title(data.get("titulo_capa") or title, 60)
    subt = safe_truncate(data.get("subtitulo_curto") or getattr(m, "subtitulo", "") or meta.get("subtitle", "") or title, 140)
    meta_desc = safe_truncate(data.get("meta_description") or subt or title, 160)
    if len(meta_desc) < 115:
        sents = source_sentences(source_text)
        meta_desc = safe_truncate((subt + " " + (" ".join(sents[:1]) if sents else "")).strip(), 160)
    tags = data.get("tags") or tags_from_source(source_text, title, meta.get("channel", ""))
    setattr(m,"titulo",title); setattr(m,"titulo_capa",capa); setattr(m,"subtitulo",subt); setattr(m,"conteudo",body)
    setattr(m,"meta_description",meta_desc); setattr(m,"tags", tags if isinstance(tags,str) else ", ".join(tags))
    setattr(m,"retranca", " ".join(str(data.get("retranca") or getattr(m,"retranca","") or meta.get("channel","")).split()[:1]))
    setattr(m,"legenda", safe_truncate(data.get("legenda_curta") or getattr(m,"legenda","") or subt, 140))
    setattr(m,"nome_da_fonte", data.get("nome_da_fonte") or getattr(m,"nome_da_fonte","") or meta.get("source_name","") or "Redação")
    setattr(m,"link_origem", data.get("link_da_fonte") or getattr(m,"link_origem","") or meta.get("source_url",""))
    setattr(m,"creditos_da_foto", data.get("creditos_da_foto") or getattr(m,"creditos_da_foto","") or "Reprodução")
    gj = dict(getattr(m,"generated_article_json",{}) or {})
    gj.update({"titulo_seo":getattr(m,"titulo",""),"titulo":getattr(m,"titulo",""),"titulo_capa":getattr(m,"titulo_capa",""),"subtitulo_curto":getattr(m,"subtitulo",""),"subtitulo":getattr(m,"subtitulo",""),"legenda_curta":getattr(m,"legenda",""),"legenda":getattr(m,"legenda",""),"retranca":getattr(m,"retranca",""),"corpo_materia":getattr(m,"conteudo",""),"conteudo":getattr(m,"conteudo",""),"texto_final":getattr(m,"conteudo",""),"meta_description":getattr(m,"meta_description",""),"tags":getattr(m,"tags",""),"nome_da_fonte":getattr(m,"nome_da_fonte",""),"link_da_fonte":getattr(m,"link_origem",""),"creditos_da_foto":getattr(m,"creditos_da_foto",""),"modo_redacao_v97":"premium_fonte_integral"})
    for _k in ("modo_geracao", "ia_provider", "ia_modelo", "ia_status", "ia_etapa", "ia_chamada_ok", "ia_fallback_motivo", "ia_erros", "ia_trace", "_ia_trace"):
        if _k in data:
            gj[_k] = data[_k]
            try:
                if hasattr(m, _k):
                    setattr(m, _k, data[_k])
            except Exception:
                pass
    setattr(m,"generated_article_json",gj)
    return m

def regenerate_materia_if_thin(m: Any, source_text: str, meta: dict, client: Any, model: str) -> Any:
    body = getattr(m, "conteudo", "") or ""
    thin, why = is_thin(body, source_text)
    if not thin: return m
    print(f"[V97] Matéria rasa detectada ({why}). Regerando com fonte integral e SEO premium.")
    data = {}
    if client is not None:
        try:
            prompt = build_prompt(source_text, {"titulo":getattr(m,"titulo",""),"subtitulo":getattr(m,"subtitulo",""),"conteudo":body}, meta)
            resp = client.chat.completions.create(model=model, messages=[{"role":"system","content":"Você é editor sênior. Responda somente JSON válido, com matéria completa e SEO."},{"role":"user","content":prompt}], temperature=0.22, max_tokens=5200)
            data = parse_json(resp.choices[0].message.content or "")
            try:
                from ururau.ia.diagnostico import trace_openai_ok, aplicar_trace_em_dados
                _tr_ok = trace_openai_ok("premium_v97_regeneracao", model, uid=str(meta.get("uid") or ""), detalhe={"motivo": why})
                data = aplicar_trace_em_dados(data, _tr_ok)
            except Exception:
                data.setdefault("modo_geracao", "openai_gpt4mini")
                data.setdefault("ia_provider", "openai")
                data.setdefault("ia_modelo", model or "")
                data.setdefault("ia_status", "openai_ok")
                data.setdefault("ia_chamada_ok", True)
        except Exception as exc:
            print(f"[V97] Regeneração GPT premium falhou: {exc}")
            try:
                from ururau.ia.diagnostico import trace_openai_erro, aplicar_trace_em_dados
                _tr_err = trace_openai_erro("premium_v97_regeneracao", model, exc, uid=str(meta.get("uid") or ""), detalhe={"motivo": why})
                data = aplicar_trace_em_dados({}, _tr_err, fallback_motivo=_tr_err.get("erro_mensagem", ""))
            except Exception:
                data = {"modo_geracao": "fallback_sem_ia", "ia_status": "openai_call_failed", "ia_chamada_ok": False, "ia_fallback_motivo": str(exc)}
    if not data or not (data.get("corpo_materia") or data.get("conteudo")):
        data = dict(data or {})
        data["corpo_materia"] = fallback_body(source_text, meta.get("article_type",""), meta.get("channel",""))
        data.setdefault("modo_geracao", "fallback_sem_ia")
        data.setdefault("ia_provider", "local")
        data.setdefault("ia_status", "fallback_local_premium_v97")
        data.setdefault("ia_chamada_ok", False)
        data.setdefault("ia_fallback_motivo", "premium_v97 usou corpo local porque a OpenAI falhou ou retornou vazio.")
    return apply_to_materia(m, data, source_text, meta)
