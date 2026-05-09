"""
source_config_loader_v91.py
Loader compatível para configs v90/v91.

Aceita:
- config/source_domains_config_v90.json
- source_domains_config_v90.json
- ururau/config/source_domains_config_v90.json
- formatos {"sources": [...]} e {"fontes": [...]}

Normaliza campos PT/EN para o pipeline real.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    # .../ururau/coleta/source_config_loader_v91.py -> raiz do projeto
    return Path(__file__).resolve().parents[2]


def _candidate_paths(path: str | None = None) -> list[Path]:
    root = _project_root()
    names = []
    if path:
        names.append(Path(path))
    names += [
        root / "config" / "source_domains_config_v90.json",
        root / "config" / "source_domains_config_v91.json",
        root / "source_domains_config_v90.json",
        root / "source_domains_config_v91.json",
        root / "ururau" / "config" / "source_domains_config_v90.json",
        root / "ururau" / "config" / "source_domains_config_v91.json",
    ]
    out: list[Path] = []
    for p in names:
        if not p.is_absolute():
            p = root / p
        if p not in out:
            out.append(p)
    return out


def _as_list(v: Any) -> list:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        return [x.strip() for x in v.splitlines() if x.strip()]
    return []


def normalizar_fonte_v91(fonte: dict) -> dict:
    if not isinstance(fonte, dict):
        return {}
    nome = fonte.get("nome") or fonte.get("name") or fonte.get("id") or fonte.get("domain") or fonte.get("dominio") or "Fonte"
    dominio = fonte.get("domain") or fonte.get("dominio") or ""
    tipo = fonte.get("tipo") or fonte.get("type") or "auto"
    homepages = _as_list(fonte.get("homepages") or fonte.get("paginas") or fonte.get("urls") or fonte.get("homepage"))
    sections = _as_list(fonte.get("sections") or fonte.get("editorias") or fonte.get("secao") or fonte.get("section"))
    rss = _as_list(fonte.get("rss") or fonte.get("rss_urls") or fonte.get("feeds"))
    sitemaps = _as_list(fonte.get("sitemaps") or fonte.get("sitemap"))
    terms = _as_list(fonte.get("terms") or fonte.get("termos") or fonte.get("watchlist_terms"))

    enabled = fonte.get("enabled", fonte.get("ativo", fonte.get("ativa", True)))
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() not in {"0", "false", "nao", "não", "no", "off"}

    try:
        priority = int(fonte.get("priority", fonte.get("prioridade", 70)) or 70)
    except Exception:
        priority = 70

    # Se o domínio veio vazio, tenta derivar do primeiro link.
    if not dominio:
        from urllib.parse import urlparse
        for u in homepages + sections + rss + sitemaps:
            try:
                d = urlparse(u).netloc.lower()
                if d:
                    dominio = d
                    break
            except Exception:
                pass

    return {
        **fonte,
        "nome": nome,
        "name": nome,
        "domain": dominio,
        "dominio": dominio,
        "type": tipo,
        "tipo": tipo,
        "priority": priority,
        "prioridade": priority,
        "homepages": homepages,
        "sections": sections,
        "editorias": sections,
        "rss": rss,
        "rss_urls": rss,
        "sitemaps": sitemaps,
        "terms": terms,
        "termos": terms,
        "enabled": bool(enabled),
        "ativo": bool(enabled),
        "ativa": bool(enabled),
    }


def carregar_config_fontes_v91(path: str | None = None) -> dict:
    last_error = ""
    found_path = ""
    raw = None
    for p in _candidate_paths(path):
        try:
            if p.exists():
                raw = json.loads(p.read_text(encoding="utf-8"))
                found_path = str(p)
                break
        except Exception as e:
            last_error = f"{p}: {e}"

    if not isinstance(raw, dict):
        raw = {"sources": []}

    fontes_raw = raw.get("sources")
    if fontes_raw is None:
        fontes_raw = raw.get("fontes")
    if fontes_raw is None:
        fontes_raw = []

    fontes = [normalizar_fonte_v91(f) for f in fontes_raw if isinstance(f, dict)]
    fontes = [f for f in fontes if f.get("domain") or f.get("homepages") or f.get("sections") or f.get("rss")]

    return {
        **raw,
        "versao": raw.get("versao") or raw.get("version") or "v91",
        "version": raw.get("version") or raw.get("versao") or "v91",
        "sources": fontes,
        "fontes": fontes,
        "_config_path": found_path,
        "_last_error": last_error,
    }


def listar_fontes_ativas_v91(path: str | None = None) -> list[dict]:
    cfg = carregar_config_fontes_v91(path)
    return [f for f in cfg.get("fontes", []) if f.get("ativo", True) and f.get("enabled", True)]


def salvar_config_fontes_v91(config: dict, path: str | None = None) -> str:
    root = _project_root()
    destino = Path(path) if path else root / "config" / "source_domains_config_v90.json"
    if not destino.is_absolute():
        destino = root / destino
    destino.parent.mkdir(parents=True, exist_ok=True)

    fontes = config.get("sources") if isinstance(config, dict) else []
    if fontes is None:
        fontes = config.get("fontes", []) if isinstance(config, dict) else []
    norm = [normalizar_fonte_v91(f) for f in fontes if isinstance(f, dict)]
    out = {**(config if isinstance(config, dict) else {}), "sources": norm, "fontes": norm, "versao": "v91"}
    destino.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(destino)
