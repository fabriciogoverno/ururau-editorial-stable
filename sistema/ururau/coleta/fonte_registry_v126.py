from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import json
import re

NOME_FIXO_DOMINIO = {
    "mancheterj.com": "Manchete RJ",
    "www.mancheterj.com": "Manchete RJ",
    "mancheterio.com.br": "Manchete Rio",
    "www.mancheterio.com.br": "Manchete Rio",
    "campos.rj.gov.br": "Prefeitura de Campos",
    "www.campos.rj.gov.br": "Prefeitura de Campos",
    "campos24horas.com.br": "Campos 24 Horas",
    "www.campos24horas.com.br": "Campos 24 Horas",
}

def _host(url: str) -> str:
    try:
        return urlparse((url or "").strip()).netloc.lower()
    except Exception:
        return ""

def normalizar_nome_fonte_v126(url: str, nome_atual: str | None = None) -> str:
    host = _host(url)
    if host in NOME_FIXO_DOMINIO:
        return NOME_FIXO_DOMINIO[host]
    host_sem_www = host.replace("www.", "")
    if host_sem_www in NOME_FIXO_DOMINIO:
        return NOME_FIXO_DOMINIO[host_sem_www]
    nome = (nome_atual or "").strip()
    if nome:
        return nome
    return host_sem_www or (url or "Fonte")

def detectar_tipo_fonte_v126(url: str) -> str:
    u = (url or "").strip().lower()
    if not u:
        return "vazia"
    if "campos24horas.com.br" in u:
        return "especial_campos24"
    if u.endswith(".xml") or "sitemap" in u:
        return "xml_sitemap"
    if "feed" in u or "rss" in u or "atom" in u or "loadcomponent=xmlfeedrss" in u:
        return "rss"
    return "html_direta"

def normalizar_fonte_v126(fonte: dict, ordem: int = 0, tipo_padrao: str = "rss") -> dict:
    f = dict(fonte or {})
    url = (f.get("url") or f.get("link") or "").strip()
    f["url"] = url
    f["ordem_prioridade_v126"] = int(ordem or f.get("ordem_prioridade_v126") or 0)
    f["tipo_fonte_config_v126"] = f.get("tipo_fonte_config_v126") or detectar_tipo_fonte_v126(url) or tipo_padrao
    f["nome"] = normalizar_nome_fonte_v126(url, f.get("nome") or f.get("fonte_nome"))
    f["fonte_nome"] = f["nome"]
    if "ativo" not in f:
        f["ativo"] = True
    return f

def normalizar_fontes_config_v126(fontes: list[dict], tipo_padrao: str = "rss") -> list[dict]:
    saida = []
    vistos = set()
    for idx, fonte in enumerate(fontes or [], start=1):
        f = normalizar_fonte_v126(fonte, idx, tipo_padrao=tipo_padrao)
        url_key = (f.get("url") or "").strip().lower().rstrip("/")
        if not url_key or url_key in vistos:
            continue
        vistos.add(url_key)
        saida.append(f)
    return saida

def carregar_json_lista_v126(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

def listar_sitemaps_configurados_v126(path: str | Path = "fontes_xml_sitemap_vfinal.txt") -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    fontes = []
    for idx, raw in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        url = raw.strip()
        if not url or url.startswith("#"):
            continue
        fontes.append(normalizar_fonte_v126({"url": url, "nome": normalizar_nome_fonte_v126(url)}, idx, tipo_padrao="xml_sitemap"))
    return fontes

def configs_incluem_campos24_v126(fontes_rss: list[dict] | None = None, sitemap_path: str | Path = "fontes_xml_sitemap_vfinal.txt") -> bool:
    for f in fontes_rss or []:
        if "campos24horas.com.br" in (f.get("url") or "").lower():
            return True
    try:
        for f in listar_sitemaps_configurados_v126(sitemap_path):
            if "campos24horas.com.br" in (f.get("url") or "").lower():
                return True
    except Exception:
        pass
    return False
