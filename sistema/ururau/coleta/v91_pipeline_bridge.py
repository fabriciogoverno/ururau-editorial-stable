"""
v91_pipeline_bridge.py
Ponte entre a camada premium v90 e o projeto real do Ururau.

Objetivo:
- usar Source Hunter/Resolver/Extract Pipeline v90;
- converter resultado para o formato real do painel/monitor;
- não usar fila JSON paralela;
- preservar painel, monitor, copydesk, preview e CMS existentes.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _uid(link: str, titulo: str) -> str:
    return hashlib.md5(f"v91:{link}:{titulo}".encode("utf-8", errors="ignore")).hexdigest()[:16]


def _first_text(d: dict, *keys: str) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def normalizar_pauta_v90_para_ururau_v91(item: dict) -> dict:
    texto = _first_text(item, "texto_fonte", "texto", "cleaned_source_text", "raw_source_text", "dossie")
    titulo = _first_text(item, "titulo_origem", "titulo", "title")
    link_final = _first_text(item, "link_origem", "url_final", "url", "url_original")
    link_original = _first_text(item, "url_original", "link_original") or link_final
    fonte = _first_text(item, "fonte_nome", "fonte", "source", "dominio", "domain")
    resumo = _first_text(item, "resumo_origem", "resumo", "summary") or texto[:500]

    paragrafos = item.get("paragrafos")
    if isinstance(paragrafos, list):
        parag_count = len(paragrafos)
    else:
        try:
            parag_count = int(paragrafos or 0)
        except Exception:
            parag_count = 0

    chars = int(item.get("chars") or item.get("chars_fonte") or len(texto or ""))

    pauta = {
        **item,
        "_uid": item.get("_uid") or _uid(link_final, titulo),
        "uid": item.get("uid") or item.get("_uid") or _uid(link_final, titulo),
        "status": "captada",
        "titulo_origem": titulo,
        "link_origem": link_final,
        "url_original": link_original,
        "url_final": link_final,
        "fonte_nome": fonte,
        "resumo_origem": resumo[:500],
        "texto_fonte": texto,
        "raw_source_text": texto,
        "cleaned_source_text": texto,
        "dossie": texto,
        "canal_forcado": item.get("canal_forcado") or item.get("canal") or "",
        "imagem_url": item.get("imagem") or item.get("imagem_url") or "",
        "metodo_extracao": item.get("metodo_extracao") or item.get("metodo") or "",
        "chars_fonte": chars,
        "paragrafos_fonte": parag_count,
        "motivo_aceite": item.get("motivo_aceite") or item.get("motivo") or "",
        "tentativas_v90": item.get("tentativas") or item.get("tentativas_v90") or [],
        "sinal_source_hunter_v91": True,
        "captada_em": item.get("data_captura") or datetime.now().isoformat(timespec="seconds"),
        "_source_hunter_metadata": {
            "v91": True,
            "url_original": link_original,
            "url_final": link_final,
            "metodo_extracao": item.get("metodo_extracao") or item.get("metodo") or "",
            "chars_fonte": chars,
            "paragrafos_fonte": parag_count,
            "motivo_aceite": item.get("motivo_aceite") or item.get("motivo") or "",
            "tentativas_v90": item.get("tentativas") or item.get("tentativas_v90") or [],
        },
    }

    # Score inicial moderado; o scoring real ainda roda depois.
    try:
        pauta["score_editorial"] = max(int(pauta.get("score_editorial") or 0), 65)
    except Exception:
        pauta["score_editorial"] = 65

    return pauta


def processar_pauta_com_v91(pauta: dict) -> dict:
    """
    Processa uma pauta bruta pelo pipeline v90 quando possível.
    Retorna formato Ururau.
    """
    from ururau.coleta.link_resolver_v90 import resolver_url_final_v90
    from ururau.coleta.url_variants_v90 import gerar_variantes_url_v90
    from ururau.coleta.extract_pipeline_v90 import extrair_materia_v90

    url = _first_text(pauta, "link_origem", "url", "url_original", "url_final")
    titulo = _first_text(pauta, "titulo_origem", "titulo", "title")
    fonte = _first_text(pauta, "fonte_nome", "fonte", "source")
    if not url:
        return {"status": "bloqueada", "motivo_bloqueio": "sem_url", **pauta}

    resolvido = resolver_url_final_v90(url, titulo=titulo, fonte=fonte)
    if not resolvido.get("ok"):
        return {"status": "bloqueada", "motivo_bloqueio": resolvido.get("status", "url_nao_resolvida"), **pauta, "tentativas_v90": resolvido.get("tentativas", [])}

    url_final = resolvido.get("url_final") or url
    if "news.google.com" in url_final.lower():
        return {"status": "bloqueada", "motivo_bloqueio": "google_news_nao_resolvido", **pauta}

    from urllib.parse import urlparse
    dominio = urlparse(url_final).netloc.lower()
    tipo = pauta.get("tipo_site") or pauta.get("type") or ""

    variantes = gerar_variantes_url_v90(url_final, dominio, tipo) or [url_final]
    tentativas = []
    for i, variante in enumerate(variantes[:8], 1):
        try:
            res = extrair_materia_v90(variante, dominio, tipo)
            tentativas.append({"n": i, "url": variante, "aceita": bool(res.get("aceita")), "metodo": res.get("metodo"), "motivo": res.get("motivo")})
            if res.get("aceita"):
                res["url_original"] = url
                res["url_final"] = res.get("url_final") or variante
                res["fonte"] = fonte or dominio
                res["tentativas"] = tentativas + (res.get("tentativas") or [])
                return normalizar_pauta_v90_para_ururau_v91(res)
        except Exception as e:
            tentativas.append({"n": i, "url": variante, "erro": str(e)[:180]})
            continue
    return {"status": "bloqueada", "motivo_bloqueio": "extracao_v91_falhou", **pauta, "tentativas_v90": tentativas}


def coletar_e_prevalidar_v91(limite: int = 120, janela_horas: int = 4) -> list[dict]:
    """
    Coleta premium v91 usando módulos v90 integrados e devolve pautas no formato real.
    Não salva em fila paralela.
    """
    if os.getenv("URURAU_V91_SOURCE_HUNTER", "1").strip().lower() not in {"1", "true", "sim", "yes", "s"}:
        return []

    from ururau.coleta.source_hunter_v90 import coletar_pautas_premium_v90

    itens = coletar_pautas_premium_v90(limite=limite, janela=janela_horas)
    out = []
    for item in itens:
        try:
            p = normalizar_pauta_v90_para_ururau_v91(item)
            texto = p.get("texto_fonte") or ""
            if len(texto.strip()) < 120:
                continue
            out.append(p)
        except Exception as e:
            print(f"[v91][BRIDGE] falha normalizando pauta: {e}")
    print(f"[v91][BRIDGE] {len(out)} pautas premium normalizadas para o fluxo real")
    return out


def salvar_resultado_v91_na_fila_real(resultado: dict) -> dict:
    from ururau.core.database import get_db
    p = normalizar_pauta_v90_para_ururau_v91(resultado)
    db = get_db()
    uid = db.salvar_pauta(p)
    p["uid"] = uid
    p["_uid"] = uid
    return p
