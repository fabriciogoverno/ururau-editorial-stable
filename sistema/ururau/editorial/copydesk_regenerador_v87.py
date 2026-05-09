"""
ururau/editorial/copydesk_regenerador_v87.py

Regenerador de matéria completa para o Copydesk.
Usa o texto real já extraído na aba Fonte para reconstruir a matéria quando
redação/pacote geraram corpo curto demais ou fraco.
"""
from __future__ import annotations

try:
    from ururau.fixes.v121_status_guard import aplicar_status_guard_v121
    aplicar_status_guard_v121()
except Exception as _e_v121_status:
    print(f"[V121][STATUS][AVISO] guard não aplicado: {_e_v121_status}")

import json
import os
import re
from typing import Any, Optional

try:
    from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101, limpar_corpo_publicacao_v101, score_texto_artigo_v101
except Exception:
    def limpar_texto_artigo_v101(texto: str, titulo: str = "", max_chars: int = 16000) -> str:
        return re.sub(r"\s+", " ", texto or "").strip()[:max_chars]
    def limpar_corpo_publicacao_v101(corpo: str) -> str:
        return re.sub(r"\s+", " ", corpo or "").strip()
    def score_texto_artigo_v101(texto: str, titulo: str = "") -> int:
        return len(texto or "")


def _get(obj: Any, key: str, default: str = "") -> str:
    try:
        if isinstance(obj, dict):
            v = obj.get(key, default)
        else:
            v = getattr(obj, key, default)
        if v is None:
            return default
        return str(v)
    except Exception:
        return default


def _limpar(txt: str, titulo: str = "") -> str:
    try:
        return limpar_texto_artigo_v101(txt or "", titulo=titulo, max_chars=16000).strip()
    except Exception:
        try:
            from ururau.coleta.limpeza_texto_v81 import limpar_texto_fonte_v81
            return limpar_texto_fonte_v81(txt or "").strip()
        except Exception:
            return re.sub(r"\s+", " ", txt or "").strip()

def extrair_texto_fonte_copydesk(md: dict, pauta: dict) -> str:
    """Busca a fonte completa em todos os campos conhecidos do projeto.

    v96: também lê os campos preenchidos pela aba Fonte do painel
    (_fonte_aba_texto, fonte_aba_texto, leitura_fonte_texto). Se o texto
    salvo na pauta/matéria for curto, tenta hidratar novamente pela URL com
    ler_fonte_pauta().
    """
    candidatos = [
        _get(md, "_fonte_aba_texto"),
        _get(md, "fonte_aba_texto"),
        _get(md, "leitura_fonte_texto"),
        _get(md, "cleaned_source_text"),
        _get(md, "original_source_text"),
        _get(md, "raw_source_text"),
        _get(md, "texto_fonte"),
        _get(md, "dossie"),
        _get(pauta, "_fonte_aba_texto"),
        _get(pauta, "fonte_aba_texto"),
        _get(pauta, "leitura_fonte_texto"),
        _get(pauta, "cleaned_source_text"),
        _get(pauta, "dossie"),
        _get(pauta, "texto_fonte"),
        _get(pauta, "raw_source_text"),
        _get(pauta, "resumo_origem"),
    ]
    titulo_ref = _get(pauta, "titulo_origem") or _get(md, "titulo_seo") or _get(md, "titulo")
    melhor = ""
    melhor_score = -10**9
    for c in candidatos:
        c = _limpar(c, titulo=titulo_ref)
        sc = score_texto_artigo_v101(c, titulo=titulo_ref)
        if sc > melhor_score or (sc == melhor_score and len(c) > len(melhor)):
            melhor = c
            melhor_score = sc

    if len(melhor) < 800:
        link = (_get(pauta, "link_origem") or _get(md, "link_origem") or _get(md, "link_da_fonte")).strip()
        if link.startswith("http"):
            try:
                from ururau.coleta.leitura_fonte import ler_fonte_pauta
                pauta_tmp = dict(pauta or {})
                pauta_tmp.setdefault("link_origem", link)
                resultado = ler_fonte_pauta(pauta_tmp, forcar_refresh=False)
                if getattr(resultado, "sucesso", False):
                    txt = _limpar(getattr(resultado, "texto_limpo", "") or "", titulo=titulo_ref)
                    if len(txt) > len(melhor):
                        melhor = txt
                        try:
                            pauta["_fonte_aba_texto"] = txt
                            pauta["cleaned_source_text"] = txt
                            pauta["raw_source_text"] = txt
                            pauta["texto_fonte"] = txt[:12000]
                            pauta["dossie"] = txt[:12000]
                        except Exception:
                            pass
            except Exception:
                pass
    return melhor


def _obter_client(client=None):
    if client is not None:
        return client
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except Exception:
        return None


def _parse_json(raw: str) -> dict:
    txt = (raw or "").strip()
    txt = re.sub(r"^```(?:json)?\s*", "", txt, flags=re.I).strip()
    txt = re.sub(r"\s*```$", "", txt).strip()
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"\{.*\}", txt, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise


def _sentencas(texto: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", _limpar(texto))
    return [p.strip() for p in parts if len(p.strip()) > 35]


def _safe_title(texto: str, limite: int) -> str:
    texto = re.sub(r"\s+", " ", texto or "").strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0].strip()
    return corte or texto[:limite].strip()


def _fallback_local(md: dict, pauta: dict, fonte: str) -> dict:
    """Fallback determinístico se OpenAI não estiver disponível."""
    titulo = (
        _get(md, "titulo_seo") or _get(md, "titulo") or
        _get(pauta, "titulo_origem") or "Matéria em revisão"
    )
    titulo = _safe_title(titulo, 89)
    sents = _sentencas(fonte)
    paragrafos: list[str] = []
    for i in range(0, min(len(sents), 10), 2):
        par = " ".join(sents[i:i+2]).strip()
        if len(par) >= 80:
            paragrafos.append(par)
        if len("\n\n".join(paragrafos)) >= 1800:
            break
    if not paragrafos and fonte:
        blocos = [b.strip() for b in fonte.split("\n") if len(b.strip()) > 80]
        paragrafos = blocos[:6]
    corpo = limpar_corpo_publicacao_v101("\n\n".join(paragrafos).strip())
    subtitulo = _safe_title(_get(md, "subtitulo_curto") or _get(md, "subtitulo") or (sents[0] if sents else titulo), 140)
    tags_base = _get(md, "tags") or _get(pauta, "canal_forcado") or _get(pauta, "canal") or "Ururau"
    return {
        "titulo_seo": titulo,
        "titulo_capa": _safe_title(_get(md, "titulo_capa") or titulo, 60),
        "retranca": _safe_title(_get(md, "retranca") or _get(pauta, "canal_forcado") or _get(pauta, "canal") or "Cidades", 30),
        "subtitulo_curto": subtitulo,
        "subtitulo": subtitulo,
        "legenda_curta": _safe_title(_get(md, "legenda_curta") or _get(md, "legenda") or titulo, 140),
        "meta_description": _safe_title(subtitulo or titulo, 160),
        "tags": tags_base,
        "nome_da_fonte": _get(md, "nome_da_fonte") or _get(pauta, "fonte_nome") or "Redação",
        "link_da_fonte": _get(md, "link_da_fonte") or _get(pauta, "link_origem"),
        "creditos_da_foto": _get(md, "creditos_da_foto") or "Reprodução",
        "corpo_materia": corpo,
        "conteudo": corpo,
        "resumo_curto": _safe_title(subtitulo or titulo, 240),
        "chamada_social": _safe_title(titulo, 220),
        "modo_copydesk_v87": "fallback_local_fonte",
        "modo_geracao": "fallback_sem_ia",
        "ia_provider": "local",
        "ia_modelo": "",
        "ia_status": "fallback_local_copydesk_v87",
        "ia_etapa": "copydesk_regenerador_v87",
        "ia_chamada_ok": False,
        "ia_fallback_motivo": "Copydesk/regenerador usou fallback local baseado na fonte.",
        "ia_erros": [],
    }


def regenerar_materia_com_fonte_v87(
    md: dict,
    pauta: dict,
    client=None,
    modelo: str = "gpt-4.1-mini",
    min_fonte_chars: int = 800,
) -> dict:
    """Regenera matéria completa usando a fonte extraída na aba Fonte."""
    fonte = extrair_texto_fonte_copydesk(md, pauta)
    if len(fonte) < min_fonte_chars:
        raise ValueError(f"Fonte insuficiente para regenerar matéria: {len(fonte)} caracteres")

    modelo = modelo or os.getenv("OPENAI_MODEL", "gpt-4.1-mini") or "gpt-4.1-mini"
    client = _obter_client(client)
    if client is None:
        dados_fb = _fallback_local(md, pauta, fonte)
        try:
            from ururau.ia.diagnostico import trace_fallback, aplicar_trace_em_dados
            _tr = trace_fallback("copydesk_regenerador_v87", modelo, "Client OpenAI ausente no regenerador; fallback local aplicado.", origem="copydesk_regenerador_sem_client")
            dados_fb = aplicar_trace_em_dados(dados_fb, _tr, fallback_motivo=_tr.get("erro_mensagem", ""))
        except Exception:
            pass
        return dados_fb

    titulo_origem = _get(pauta, "titulo_origem") or _get(md, "titulo_seo") or _get(md, "titulo")
    canal = _get(pauta, "canal_forcado") or _get(pauta, "canal") or _get(md, "canal") or "Cidades"
    fonte_nome = _get(pauta, "fonte_nome") or _get(md, "nome_da_fonte") or "Redação"
    link = _get(pauta, "link_origem") or _get(md, "link_da_fonte")

    prompt = f"""
Você é o copydesk do jornal Ururau. Refaça a matéria completa usando APENAS os fatos do TEXTO-FONTE.

PROBLEMA: a matéria atual ficou curta demais ou incompleta. A fonte tem conteúdo suficiente.

REGRAS OBRIGATÓRIAS:
- Não invente nenhum dado, nome, número, data, cargo, órgão, valor ou declaração.
- Não use informação que não esteja no TEXTO-FONTE.
- Não crie aspas que não existam.
- Não use travessão no corpo.
- Não use frases genéricas de IA.
- Não use a expressão "acende o alerta".
- Texto em padrão jornalístico profissional, claro, semelhante a G1/UOL.
- Lead direto no primeiro parágrafo.
- Corpo com 5 a 8 parágrafos, proporcional à fonte.
- Não use intertítulos no corpo. Proibido usar linhas isoladas como Contexto, Detalhes, Efeitos práticos ou Próximos passos.
- PROIBIDO entregar matéria com apenas 1 parágrafo. Se a fonte tiver mais de 1.000 caracteres, o corpo deve ter no mínimo 4 parágrafos.
- Se a fonte for serviço/utilidade pública, priorize prazo, público-alvo, local, inscrição, custo e órgão responsável.
- Título SEO com até 89 caracteres.
- Título capa com até 60 caracteres.
- Subtítulo com até 140 caracteres.
- Meta description até 160 caracteres, sem cortar frase no meio.
- Tags: 6 a 10, separadas por vírgula.
- Retranca: uma palavra.

DADOS ATUAIS:
Título original: {titulo_origem}
Canal: {canal}
Fonte: {fonte_nome}
Link: {link}
Título atual: {_get(md, 'titulo_seo')}
Subtítulo atual: {_get(md, 'subtitulo_curto') or _get(md, 'subtitulo')}
Corpo atual: {(_get(md, 'corpo_materia') or _get(md, 'conteudo'))[:800]}

TEXTO-FONTE COMPLETO EXTRAÍDO:
{fonte[:9000]}

Retorne APENAS JSON válido, sem markdown, com exatamente estes campos:
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
""".strip()

    try:
        resp = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Você é um editor profissional. Responda somente JSON válido."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.25,
            max_tokens=3500,
        )
        raw = resp.choices[0].message.content or ""
        dados = _parse_json(raw)
        try:
            from ururau.ia.diagnostico import trace_openai_ok, aplicar_trace_em_dados
            _tr_ok = trace_openai_ok("copydesk_regenerador_v87", modelo)
            dados = aplicar_trace_em_dados(dados, _tr_ok)
        except Exception:
            dados.setdefault("modo_geracao", "openai_gpt4mini")
            dados.setdefault("ia_provider", "openai")
            dados.setdefault("ia_modelo", modelo)
            dados.setdefault("ia_status", "openai_ok")
            dados.setdefault("ia_chamada_ok", True)
    except Exception as exc:
        print(f"[COPYDESK v87] chamada OpenAI falhou; fallback local: {exc}")
        dados_fb = _fallback_local(md, pauta, fonte)
        try:
            from ururau.ia.diagnostico import trace_openai_erro, aplicar_trace_em_dados
            _tr = trace_openai_erro("copydesk_regenerador_v87", modelo, exc)
            dados_fb = aplicar_trace_em_dados(dados_fb, _tr, fallback_motivo=_tr.get("erro_mensagem", ""))
        except Exception:
            dados_fb["ia_status"] = "openai_call_failed"
            dados_fb["ia_fallback_motivo"] = str(exc)[:500]
        return dados_fb

    # Normalização e preservação de campos essenciais.
    corpo = limpar_corpo_publicacao_v101(str(dados.get("corpo_materia") or dados.get("conteudo") or "").strip())
    paras_corpo = [p.strip() for p in re.split(r"\n\s*\n", corpo) if p.strip()]
    # v96: defesa contra resposta curta da IA. Se ela voltar com 1 parágrafo
    # apesar de fonte longa, monta corpo jornalístico por fallback local baseado
    # exclusivamente nas sentenças da fonte.
    if len(fonte) >= 1000 and (len(paras_corpo) < 3 or len(corpo) < 850):
        fb = _fallback_local(md, pauta, fonte)
        corpo_fb = str(fb.get("corpo_materia") or "").strip()
        paras_fb = [p.strip() for p in re.split(r"\n\s*\n", corpo_fb) if p.strip()]
        if len(paras_fb) >= 3 and len(corpo_fb) > len(corpo):
            corpo = corpo_fb
            for k, v in fb.items():
                dados.setdefault(k, v)
            dados["modo_copydesk_v87"] = "ia_curta_corrigida_por_fallback_fonte_v96"
            dados["modo_geracao"] = "fallback_sem_ia"
            dados["ia_provider"] = "local"
            dados["ia_status"] = "openai_ok_resposta_curta_fallback_local"
            dados["ia_chamada_ok"] = True
            dados["ia_fallback_motivo"] = "OpenAI respondeu no copydesk v87, mas corpo veio curto; corpo final substituído por fallback local baseado na fonte."
    dados["conteudo"] = corpo
    dados["corpo_materia"] = corpo
    dados["titulo"] = dados.get("titulo_seo") or _get(md, "titulo") or titulo_origem
    dados["subtitulo"] = dados.get("subtitulo_curto") or dados.get("subtitulo") or ""
    dados["legenda"] = dados.get("legenda_curta") or dados.get("legenda") or ""
    dados["fonte_nome"] = dados.get("nome_da_fonte") or fonte_nome
    dados["link_origem"] = dados.get("link_da_fonte") or link
    dados["canal"] = canal
    dados["cleaned_source_text"] = fonte
    if not str(dados.get("modo_copydesk_v87") or "").startswith("ia_curta_corrigida"):
        dados["modo_copydesk_v87"] = "ia_gpt4mini_fonte_extraida"
        dados.setdefault("modo_geracao", "openai_gpt4mini")
        dados.setdefault("ia_provider", "openai")
        dados.setdefault("ia_modelo", modelo)
        dados.setdefault("ia_status", "openai_ok")
        dados.setdefault("ia_chamada_ok", True)

    # Limites básicos defensivos.
    dados["titulo_seo"] = _safe_title(str(dados.get("titulo_seo") or titulo_origem), 89)
    dados["titulo_capa"] = _safe_title(str(dados.get("titulo_capa") or dados["titulo_seo"]), 60)
    dados["subtitulo_curto"] = _safe_title(str(dados.get("subtitulo_curto") or dados.get("subtitulo") or ""), 140)
    dados["meta_description"] = _safe_title(str(dados.get("meta_description") or dados["subtitulo_curto"] or dados["titulo_seo"]), 160)
    dados["legenda_curta"] = _safe_title(str(dados.get("legenda_curta") or dados.get("legenda") or dados["titulo_seo"]), 140)
    dados["retranca"] = " ".join(str(dados.get("retranca") or canal).split()[:1])
    return dados


__all__ = ["regenerar_materia_com_fonte_v87", "extrair_texto_fonte_copydesk"]

# URURAU v97 — Copydesk premium contra matéria rasa
_OLD_REGENERAR_MATERIA_COM_FONTE_V87_V97 = regenerar_materia_com_fonte_v87

def regenerar_materia_com_fonte_v87(md: dict, pauta: dict, client=None, modelo: str = "gpt-4.1-mini", min_fonte_chars: int = 800) -> dict:  # type: ignore[override]
    fonte = extrair_texto_fonte_copydesk(md, pauta)
    dados = _OLD_REGENERAR_MATERIA_COM_FONTE_V87_V97(md, pauta, client=client, modelo=modelo, min_fonte_chars=min_fonte_chars)
    try:
        from ururau.editorial import premium_v97
        corpo = limpar_corpo_publicacao_v101(str(dados.get("corpo_materia") or dados.get("conteudo") or "").strip())
        thin, why = premium_v97.is_thin(corpo, fonte)
        if thin:
            print(f"[COPYDESK v97] Corpo raso detectado ({why}). Reprocessando pela fonte integral.")
            min_p, min_c = premium_v97.min_requirements(fonte)
            cli = _obter_client(client)
            novo = {}
            if cli is not None:
                try:
                    prompt = premium_v97.build_prompt(
                        fonte,
                        {
                            "titulo": dados.get("titulo_seo") or dados.get("titulo") or _get(pauta, "titulo_origem"),
                            "subtitulo": dados.get("subtitulo_curto") or dados.get("subtitulo"),
                            "conteudo": corpo,
                        },
                        {
                            "channel": _get(pauta, "canal_forcado") or _get(pauta, "canal") or dados.get("retranca") or "Cidades",
                            "article_type": dados.get("article_type") or "",
                            "title": _get(pauta, "titulo_origem") or dados.get("titulo_seo") or dados.get("titulo"),
                            "subtitle": _get(pauta, "resumo_origem") or dados.get("subtitulo_curto") or dados.get("subtitulo"),
                            "source_name": _get(pauta, "fonte_nome") or dados.get("nome_da_fonte"),
                            "source_url": _get(pauta, "link_origem") or dados.get("link_da_fonte"),
                        },
                    )
                    resp = cli.chat.completions.create(
                        model=modelo or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                        messages=[
                            {"role": "system", "content": "Você é copydesk sênior. Responda somente JSON válido, com matéria completa e SEO."},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.22,
                        max_tokens=5200,
                    )
                    novo = premium_v97.parse_json(resp.choices[0].message.content or "")
                    try:
                        from ururau.ia.diagnostico import trace_openai_ok, aplicar_trace_em_dados
                        _tr_ok = trace_openai_ok("copydesk_v97_premium", modelo or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
                        novo = aplicar_trace_em_dados(novo, _tr_ok)
                    except Exception:
                        novo.setdefault("modo_geracao", "openai_gpt4mini")
                        novo.setdefault("ia_status", "openai_ok")
                        novo.setdefault("ia_chamada_ok", True)
                except Exception as exc:
                    print(f"[COPYDESK v97] chamada premium falhou: {exc}")
                    try:
                        from ururau.ia.diagnostico import trace_openai_erro, aplicar_trace_em_dados
                        _tr = trace_openai_erro("copydesk_v97_premium", modelo or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), exc)
                        novo = aplicar_trace_em_dados({}, _tr, fallback_motivo=_tr.get("erro_mensagem", ""))
                    except Exception:
                        novo = {"modo_geracao": "fallback_sem_ia", "ia_status": "openai_call_failed", "ia_chamada_ok": False, "ia_fallback_motivo": str(exc)}
            else:
                novo = {"modo_geracao": "fallback_sem_ia", "ia_provider": "local", "ia_status": "fallback_local_copydesk_v97_sem_client", "ia_chamada_ok": False, "ia_fallback_motivo": "Client OpenAI ausente no reforço premium v97."}
            novo_corpo = str(novo.get("corpo_materia") or novo.get("conteudo") or "").strip()
            thin2, _ = premium_v97.is_thin(novo_corpo, fonte)
            if thin2:
                novo["corpo_materia"] = premium_v97.fallback_body(fonte, "", _get(pauta, "canal") or "")
                novo["modo_geracao"] = "fallback_sem_ia"
                novo["ia_provider"] = "local"
                novo["ia_status"] = "fallback_local_copydesk_v97_corpo_raso"
                novo["ia_chamada_ok"] = bool(novo.get("ia_chamada_ok", False))
                novo["ia_fallback_motivo"] = "Reforço premium v97 retornou corpo raso/vazio; corpo final gerado por fallback local."
            dados.update({k:v for k,v in novo.items() if v})
            corpo_final = str(dados.get("corpo_materia") or dados.get("conteudo") or "").strip()
            dados["corpo_materia"] = corpo_final
            dados["conteudo"] = corpo_final
            dados["texto_final"] = corpo_final
            dados["modo_copydesk_v87"] = "premium_v97_fonte_integral"
    except Exception as exc:
        print(f"[COPYDESK v97] reforço premium falhou sem bloquear: {exc}")
    return dados
