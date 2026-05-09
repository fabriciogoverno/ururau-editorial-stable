"""fontes_links_v43.py — saneamento estrutural de fontes/links do Ururau V43 Premium.

Objetivo: criar uma fonte única de verdade para RSS, XML/Sitemap, Especiais,
Regionais e AutoFontes; atualizar status das fontes a partir dos relatórios
reais de coleta; e transformar diagnóstico de fonte em ação operacional visível.

Este módulo é deliberadamente leve: usa apenas stdlib, JSON e regex. Não faz
requisições de rede e não altera o motor de coleta pesado.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

VERSAO = "V43 Premium"


def base_dir() -> Path:
    try:
        return Path(__file__).resolve().parents[2]  # sistema/
    except Exception:
        return Path.cwd()


def config_dir() -> Path:
    p = base_dir() / "config"
    p.mkdir(parents=True, exist_ok=True)
    return p


def fontes_links_path() -> Path:
    return config_dir() / "fontes_links.json"


def status_fontes_path() -> Path:
    return config_dir() / "status_fontes.json"


def memoria_aplicacoes_path() -> Path:
    return config_dir() / "memoria_diagnosticos_aplicados_v43.json"


def _norm_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    matches = list(re.finditer(r"https?://", url, re.I))
    if len(matches) > 1:
        url = url[matches[-1].start():]
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    try:
        p = urllib.parse.urlparse(url)
        if not p.netloc:
            return ""
        path = p.path or "/"
        return urllib.parse.urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query or "", ""))
    except Exception:
        return url


def _domain(url: str) -> str:
    try:
        h = (urllib.parse.urlparse(_norm_url(url)).netloc or "").lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _root(url: str) -> str:
    try:
        p = urllib.parse.urlparse(_norm_url(url))
        return f"{p.scheme}://{p.netloc}/" if p.scheme and p.netloc else ""
    except Exception:
        return ""


def _safe_read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return default


def _safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        bdir = path.parent / "backups_v43"
        bdir.mkdir(parents=True, exist_ok=True)
        try:
            import shutil
            shutil.copy2(path, bdir / f"{path.name}.bak_{time.strftime('%Y%m%d_%H%M%S')}")
        except Exception:
            pass
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json_list(rel_paths: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen = set()
    for rel in rel_paths:
        p = base_dir() / rel
        data = _safe_read_json(p, [])
        if isinstance(data, dict) and isinstance(data.get("fontes"), list):
            data = data.get("fontes")
        if isinstance(data, list):
            for it in data:
                if isinstance(it, dict):
                    url = _norm_url(str(it.get("url") or ""))
                    key = _domain(url) or url or (it.get("nome") or it.get("fonte_nome") or "")
                    if key and key not in seen:
                        seen.add(key)
                        out.append(dict(it, url=url or it.get("url") or ""))
    return out


def _read_txt_urls(rel_paths: list[str]) -> list[str]:
    urls: list[str] = []
    seen = set()
    for rel in rel_paths:
        p = base_dir() / rel
        try:
            if not p.exists():
                continue
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                url = _norm_url(line.split("|", 1)[0].strip())
                if url and url not in seen:
                    seen.add(url); urls.append(url)
        except Exception:
            pass
    return urls


def _load_perfis() -> list[dict[str, Any]]:
    p = base_dir() / "perfis_fontes_v131.json"
    data = _safe_read_json(p, [])
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def _item(group: str, nome: str, url: str, **extra: Any) -> dict[str, Any]:
    url = _norm_url(url)
    dominio = _domain(url)
    return {
        "id": extra.get("id") or dominio or url,
        "nome": nome or dominio or url,
        "url": url,
        "dominio": dominio,
        "grupo": group,
        "ativo": bool(extra.get("ativo", True)),
        "origem_config": extra.get("origem_config") or group.lower(),
        "tipo_coleta": extra.get("tipo_coleta") or extra.get("tipo") or group.lower(),
        "perfil_v131_id": extra.get("perfil_v131_id") or extra.get("perfil_id") or "",
        "estrategia": extra.get("estrategia") or "",
        "parser": extra.get("parser") or "",
        "fallbacks": extra.get("fallbacks") or [],
        "sitemaps": extra.get("sitemaps") or [],
        "wp_api": extra.get("wp_api") or "",
        "playwright": bool(extra.get("playwright", False)),
        "prioridade": extra.get("prioridade") or "",
        "regiao": extra.get("regiao") or "",
        "status": extra.get("status") or "desconhecido",
        "motivo_status": extra.get("motivo_status") or "Aguardando primeira leitura de relatório.",
        "atualizado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }



def _extra_without_core(f: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in dict(f or {}).items() if k not in {"url", "nome", "fonte_nome", "id", "dominio", "grupo"}}

def consolidar_fontes_links_v43() -> dict[str, Any]:
    """Cria/atualiza config/fontes_links.json a partir dos arquivos legados.

    Não remove arquivos legados nesta etapa. Eles continuam existindo para
    compatibilidade. A fonte única passa a funcionar como índice central e status.
    """
    status = carregar_status_fontes_v43()
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(it: dict[str, Any]) -> None:
        if not it.get("url") and it.get("grupo") != "AutoFontes":
            return
        key = (_domain(it.get("url", "")) or it.get("id") or it.get("url", ""), it.get("grupo", ""))
        # Se o mesmo domínio entrou como AutoFontes, manter AutoFontes como fonte operacional;
        # as abas visuais podem continuar, mas ficam marcadas como organizacionais.
        if key in seen:
            return
        st = status.get(it.get("dominio") or _domain(it.get("url", "")) or it.get("id", ""), {})
        if st:
            it["status"] = st.get("status", it.get("status"))
            it["motivo_status"] = st.get("motivo", it.get("motivo_status"))
            it["ultima_coleta"] = st.get("ultima_coleta", "")
            it["encontradas"] = st.get("encontradas", 0)
            it["enviadas"] = st.get("enviadas", 0)
        seen.add(key)
        items.append(it)

    for f in _read_json_list(["fontes_rss.json", "configuracoes/fontes_rss.json", "config/fontes_rss.json"]):
        add(_item("RSS", f.get("nome") or f.get("fonte_nome") or _domain(f.get("url", "")), f.get("url", ""), **_extra_without_core(f)))

    for url in _read_txt_urls(["fontes_xml_sitemap_vfinal.txt", "configuracoes/fontes_xml_sitemap_v120.txt"]):
        add(_item("XML/Sitemap", _domain(url) or url, url, tipo_coleta="xml_sitemap"))

    for f in _read_json_list(["fontes_especiais_v129.json", "configuracoes/fontes_especiais_v129.json"]):
        add(_item("Especiais", f.get("nome") or f.get("fonte_nome") or _domain(f.get("url", "")), f.get("url", ""), **_extra_without_core(f)))

    for f in _read_json_list(["regionais_v1305.json"]):
        add(_item("Regionais", f.get("nome") or f.get("fonte_nome") or _domain(f.get("url", "")), f.get("url", ""), **_extra_without_core(f)))

    for p in _load_perfis():
        url = (p.get("feeds") or [p.get("root") or ""])[0]
        add(_item("AutoFontes", p.get("nome") or p.get("dominio") or _domain(url), url,
                  id=p.get("id"), origem_config="perfis_fontes_v131", tipo_coleta="auto_v43",
                  perfil_v131_id=p.get("id"), estrategia=p.get("estrategia"), parser=p.get("parser"),
                  fallbacks=(p.get("feeds") or [])[1:], sitemaps=p.get("sitemaps") or [],
                  wp_api=p.get("wp_api") or "", playwright=p.get("playwright"),
                  ativo=p.get("ativo", True)))

    payload = {
        "version": "V43 Premium",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "items": items,
        "summary": {
            "total": len(items),
            "rss": sum(1 for x in items if x.get("grupo") == "RSS"),
            "xml_sitemap": sum(1 for x in items if x.get("grupo") == "XML/Sitemap"),
            "especiais": sum(1 for x in items if x.get("grupo") == "Especiais"),
            "regionais": sum(1 for x in items if x.get("grupo") == "Regionais"),
            "autofontes": sum(1 for x in items if x.get("grupo") == "AutoFontes"),
        },
    }
    _safe_write_json(fontes_links_path(), payload)
    return payload


def carregar_fontes_links_v43() -> dict[str, Any]:
    data = _safe_read_json(fontes_links_path(), None)
    if not isinstance(data, dict) or "items" not in data:
        return consolidar_fontes_links_v43()
    return data


def carregar_status_fontes_v43() -> dict[str, Any]:
    data = _safe_read_json(status_fontes_path(), {})
    return data if isinstance(data, dict) else {}


def _status_from_motivo(motivo: str, encontradas: int, enviadas: int, erro: str = "") -> str:
    m = (motivo or "").lower()
    if enviadas > 0:
        return "ok"
    if erro or "erro_http" in m or "404" in m or "403" in m or "302" in m or "falha" in m:
        return "erro"
    if encontradas > 0 and ("fora da janela" in m or "sem envio" in m or "já estava" in m or "duplic" in m):
        return "sem_envio"
    if encontradas > 0:
        return "atencao"
    return "sem_coleta"


def atualizar_status_por_relatorio_v43(texto: str) -> dict[str, Any]:
    """Lê o relatório técnico final e atualiza status_fontes.json.

    Reconhece blocos do tipo:
      709. SEM ENVIO | Tribuna NF | encontradas=3 | enviadas=0 | itens fora...
      URL: ...
      Tipo detectado/configurado: ...
    """
    texto = texto or ""
    blocos = re.split(r"\n(?=\d{3}\.\s+(?:OK|SEM COLETA|SEM ENVIO|FALHA)\s+\|)", "\n" + texto)
    status = carregar_status_fontes_v43()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    count = 0
    for b in blocos:
        m = re.search(r"(\d{3})\.\s+(OK|SEM COLETA|SEM ENVIO|FALHA)\s+\|\s+([^|\n]+)\s*\|\s*encontradas=(\d+)\s*\|\s*enviadas=(\d+)\s*\|\s*([^\n]+)", b)
        if not m:
            continue
        ordem, situacao, nome, enc, env, motivo = m.groups()
        url_m = re.search(r"\n\s*URL:\s*([^\n]+)", b)
        tipo_m = re.search(r"\n\s*Tipo detectado/configurado:\s*([^\n]+)", b)
        url = _norm_url(url_m.group(1).strip()) if url_m else ""
        dominio = _domain(url) or re.sub(r"\W+", "_", nome.strip().lower())
        erro_m = re.search(r"erro(?:=|:)([^\n]+)", b, re.I)
        erro = erro_m.group(1).strip() if erro_m else ""
        entry = status.get(dominio, {}) if isinstance(status.get(dominio), dict) else {}
        fail_count = int(entry.get("falhas_consecutivas") or 0)
        ok_count = int(entry.get("ok_consecutivos") or 0)
        st = _status_from_motivo(motivo, int(enc), int(env), erro)
        if st in {"erro", "sem_coleta"}:
            fail_count += 1; ok_count = 0
        elif st == "ok":
            ok_count += 1; fail_count = 0
        else:
            # sem envio por janela/duplicidade não é falha técnica.
            ok_count += 1; fail_count = 0
        quarentena = fail_count >= 5
        status[dominio] = {
            "nome": nome.strip(),
            "url": url,
            "dominio": dominio,
            "status": "quarentena" if quarentena else st,
            "situacao_relatorio": situacao,
            "motivo": motivo.strip(),
            "tipo": tipo_m.group(1).strip() if tipo_m else "",
            "encontradas": int(enc),
            "enviadas": int(env),
            "ultima_coleta": stamp,
            "falhas_consecutivas": fail_count,
            "ok_consecutivos": ok_count,
            "quarentena": quarentena,
            "acao_sugerida": "Rodar Diagnóstico de Fonte e substituir solução" if st in {"erro", "sem_coleta"} else "Manter ativo",
            "ordem_relatorio": int(ordem),
        }
        count += 1
    _safe_write_json(status_fontes_path(), status)
    try:
        consolidar_fontes_links_v43()
    except Exception:
        pass
    return {"atualizadas": count, "arquivo": str(status_fontes_path())}


def _classificar_grupo_por_dominio(url: str, nome: str = "") -> str:
    d = _domain(url)
    s = (d + " " + (nome or "")).lower()
    regionais = {"tribunanf.com.br", "nfnoticias.com.br", "campos24horas.com.br", "folha1.com.br", "j3news.com", "portalviu.com.br", "sfnoticias.com.br", "odebateon.com.br", "parahybano.com.br", "campos.rj.gov.br"}
    if d in regionais:
        return "Regionais"
    if any(x in s for x in [".gov.br", ".jus.br", ".leg.br", ".mp.br", "alerj", "mprj", "tce", "tjrj", "tre-"]):
        return "Especiais"
    return "RSS"


def registrar_aplicacao_diagnostico_v43(results: dict[str, Any], aplicacao: dict[str, Any]) -> dict[str, Any]:
    """Registra a solução aplicada no índice único.

    Esta função é chamada depois do aplicador v130/v131/v132.5. Ela não substitui
    o perfil operacional; apenas garante rastreabilidade e presença visual.
    """
    root = results.get("root") or ""
    sol = results.get("solucao") or {}
    v131 = aplicacao.get("v131") or {}
    perfil = v131.get("perfil") or {}
    nome = perfil.get("nome") or aplicacao.get("nome") or results.get("name") or _domain(root)
    feeds = perfil.get("feeds") or sol.get("feeds") or []
    url = (feeds or [root])[0]
    grupo = perfil.get("grupo") or _classificar_grupo_por_dominio(url or root, nome)
    item = _item(grupo, nome, url or root,
                 id=perfil.get("id"), origem_config="diagnostico_aplicado_v43",
                 tipo_coleta="auto_v43", perfil_v131_id=perfil.get("id"),
                 estrategia=perfil.get("estrategia") or sol.get("estrategia_principal"),
                 parser=perfil.get("parser") or "auto_universal", fallbacks=(feeds or [])[1:],
                 sitemaps=perfil.get("sitemaps") or sol.get("sitemaps") or [],
                 wp_api=perfil.get("wp_api") or sol.get("wp_api") or "",
                 playwright=perfil.get("playwright") or sol.get("playwright"),
                 status="aplicada", motivo_status="Aplicada por Diagnóstico de Fonte; aguardando próxima coleta real.")
    data = carregar_fontes_links_v43()
    items = [x for x in data.get("items", []) if not (x.get("dominio") == item.get("dominio") and x.get("grupo") == item.get("grupo"))]
    items.append(item)
    data["items"] = items
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _safe_write_json(fontes_links_path(), data)
    mem = _safe_read_json(memoria_aplicacoes_path(), {"version": VERSAO, "items": []})
    if not isinstance(mem, dict):
        mem = {"version": VERSAO, "items": []}
    mem.setdefault("items", []).append({"quando": data["updated_at"], "nome": nome, "dominio": item.get("dominio"), "grupo": grupo, "url": item.get("url"), "resultado": (v131.get("teste") or {}).get("status_operacional") or "aplicado"})
    mem["items"] = mem["items"][-500:]
    _safe_write_json(memoria_aplicacoes_path(), mem)
    return {"arquivo": str(fontes_links_path()), "item": item}


def status_prefixo_v43(url: str = "", nome: str = "") -> str:
    status = carregar_status_fontes_v43()
    key = _domain(url) or re.sub(r"\W+", "_", (nome or "").lower())
    st = status.get(key, {}) if key else {}
    if not st:
        return "🧪"
    m = st.get("status")
    return {"ok": "✅", "sem_envio": "🟡", "atencao": "⚠️", "erro": "❌", "sem_coleta": "❌", "quarentena": "⏸️"}.get(m, "🧪")
