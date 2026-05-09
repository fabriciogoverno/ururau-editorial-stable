from __future__ import annotations
import hashlib, json, os, re
from pathlib import Path
from urllib.parse import urlparse
from ururau.coleta.url_discovery_v88 import UrlCandidataV88, dedup_urls, descobrir_por_google_news_terms, descobrir_por_pagina, descobrir_por_sitemap, dominio
from ururau.coleta.opportunity_score_v88 import calcular_opportunity_score_v88

def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in {"1","true","sim","yes","s","on"}

def _load_json(path: str, default):
    try:
        p = Path(path)
        if p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[v88][CONFIG] falha lendo {path}: {e}")
    return default

def _uid(link: str, titulo: str) -> str:
    return hashlib.md5(f"v88:{link}:{titulo}".encode("utf-8", errors="ignore")).hexdigest()[:16]

def _limpar_titulo(t: str) -> str:
    t = re.sub(r"\s+", " ", (t or "")).strip()
    t = re.sub(r"\s+-\s+[^-]{2,40}$", "", t).strip()
    return t[:180]

def _parece_artigo(url: str, titulo: str = "") -> bool:
    low = (url or "").lower()
    if not low.startswith("http"): return False
    bloqueios = ("/tag/","/tags/","/author/","/autor/","/category/","/categoria/","/video/","/videos/","/podcast","/login","/assine","/newsletter")
    if any(x in low for x in bloqueios): return False
    path = urlparse(low).path
    if len(path.strip("/")) < 8 and len(titulo) < 25: return False
    return True

def _candidata_para_pauta(c: UrlCandidataV88, config: dict) -> dict:
    titulo = _limpar_titulo(c.titulo) or c.url
    p = {
        "titulo_origem": titulo,
        "link_origem": c.url,
        "fonte_nome": c.fonte_nome or dominio(c.url),
        "resumo_origem": f"Pauta descoberta por {c.origem}. Fonte: {c.fonte_nome}."[:600],
        "canal_forcado": c.canal_forcado or "",
        "data_pub_fonte": c.published or "",
        "origem_feed": c.origem,
        "_uid": _uid(c.url, titulo),
        "prioridade": 2,
        "sinal_source_hunter_v88": True,
        "_source_hunter_score": int(c.score_descoberta or 0),
        "_source_hunter_metadata": c.metadata or {},
    }
    score, motivos = calcular_opportunity_score_v88(p, config)
    p["_opportunity_score_v88"] = score
    p["_opportunity_motivos_v88"] = motivos
    p["score_editorial"] = max(int(p.get("score_editorial") or 0), score)
    return p

def coletar_source_hunter_v88(config_path: str = "source_hunter_config_v88.json") -> list[dict]:
    if not _bool_env("URURAU_V88_SOURCE_HUNTER", True): return []
    config = _load_json(config_path, {})
    fontes = [f for f in (config.get("fontes") or []) if f.get("ativo", True)]
    max_urls = int(os.getenv("URURAU_V88_MAX_URLS_POR_FONTE", str(config.get("max_urls_por_fonte", 45))))
    max_fontes = int(os.getenv("URURAU_V88_MAX_FONTES", "12"))
    min_score = int(os.getenv("URURAU_V88_MIN_OPPORTUNITY", str(config.get("min_score_oportunidade", 45))))
    candidatas = []
    for fonte in fontes[:max_fontes]:
        nome = fonte.get("nome") or fonte.get("id") or "Fonte"
        locais = []
        try:
            if _bool_env("URURAU_V88_USAR_SITEMAP", True): locais += descobrir_por_sitemap(fonte, max_urls=max_urls//2)
            if _bool_env("URURAU_V88_USAR_PAGINA_EDITORIA", True): locais += descobrir_por_pagina(fonte, max_urls=max_urls//2)
            if _bool_env("URURAU_V88_USAR_GNEWS_DOMINIO", True): locais += descobrir_por_google_news_terms(fonte, max_por_termo=int(os.getenv("URURAU_V88_GNEWS_POR_TERMO", "4")))
        except Exception as e:
            print(f"[v88][{nome}] falha geral: {str(e)[:180]}")
        locais = [c for c in dedup_urls(locais) if _parece_artigo(c.url, c.titulo)]
        print(f"[v88][{nome}] {len(locais)} URLs candidatas")
        candidatas.extend(locais[:max_urls])
    pautas, vistos = [], set()
    for c in dedup_urls(candidatas):
        p = _candidata_para_pauta(c, config)
        u = p.get("link_origem")
        if not u or u in vistos: continue
        vistos.add(u)
        if int(p.get("_opportunity_score_v88") or 0) >= min_score: pautas.append(p)
    pautas.sort(key=lambda x: int(x.get("_opportunity_score_v88") or 0), reverse=True)
    limite = int(os.getenv("URURAU_V88_MAX_TOTAL", "120"))
    print(f"[v88][SOURCE_HUNTER] {len(pautas)} pautas premium aprovadas para pré-validação")
    try:
        from ururau.coleta.intel_editorial import enriquecer_pauta_com_intel
        pautas = [enriquecer_pauta_com_intel(p) for p in pautas]
    except Exception: pass
    return pautas[:limite]
