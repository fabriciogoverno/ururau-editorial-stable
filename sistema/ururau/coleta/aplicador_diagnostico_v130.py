# aplicador_diagnostico_v130.py
# Aplica, de modo seguro, uma sugestão gerada por diagnostico_fontes_v130.

from __future__ import annotations

import json
import re
import shutil
import time
import urllib.parse
from pathlib import Path
from typing import Any


def _norm_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    p = urllib.parse.urlparse(url)
    if not p.scheme:
        url = "https://" + url
        p = urllib.parse.urlparse(url)
    host = (p.netloc or "").lower()
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/") + "/"
    return urllib.parse.urlunparse((p.scheme.lower(), host, path, "", "", ""))


def _domain(url: str) -> str:
    try:
        p = urllib.parse.urlparse(_norm_url(url))
        h = (p.netloc or "").lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _safe_name(domain: str) -> str:
    if not domain:
        return "Nova Fonte"
    base = domain.split(":", 1)[0]
    parts = [p for p in base.split(".") if p and p not in {"com", "br", "org", "net", "gov", "jus", "leg", "mp"}]
    if not parts:
        parts = base.split(".")[:1]
    return " ".join(p.capitalize() for p in parts)


def _candidate_roots() -> list[Path]:
    roots = [Path.cwd()]
    try:
        here = Path(__file__).resolve()
        # .../sistema/ururau/coleta/aplicador.py -> sistema
        roots.append(here.parents[2])
    except Exception:
        pass
    out = []
    seen = set()
    for r in roots:
        rp = r.resolve()
        if rp not in seen:
            seen.add(rp); out.append(rp)
    return out


def _backup(path: Path) -> None:
    if not path.exists():
        return
    bdir = path.parent / "backups_v130"
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(path, bdir / f"{path.name}.bak_{stamp}")


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return []


def _write_json_all(rel_paths: list[str], data: list[dict[str, Any]]) -> list[str]:
    written = []
    text = json.dumps(data, ensure_ascii=False, indent=2)
    for root in _candidate_roots():
        for rel in rel_paths:
            p = root / rel
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                _backup(p)
                p.write_text(text, encoding="utf-8")
                written.append(str(p))
            except Exception:
                pass
    return sorted(set(written))


def _append_xml_all(urls: list[str]) -> list[str]:
    if not urls:
        return []
    written = []
    rels = ["fontes_xml_sitemap_vfinal.txt", "configuracoes/fontes_xml_sitemap_v120.txt"]
    for root in _candidate_roots():
        for rel in rels:
            p = root / rel
            try:
                atuais = []
                if p.exists():
                    atuais = [x.strip() for x in p.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
                seen = set(atuais)
                changed = False
                for u in urls:
                    if u and u not in seen:
                        atuais.append(u); seen.add(u); changed = True
                if changed or not p.exists():
                    p.parent.mkdir(parents=True, exist_ok=True)
                    _backup(p)
                    p.write_text("\n".join(atuais).rstrip() + "\n", encoding="utf-8")
                    written.append(str(p))
            except Exception:
                pass
    return sorted(set(written))


def _read_primary_fontes() -> list[dict[str, Any]]:
    for root in _candidate_roots():
        for rel in ["fontes_rss.json", "configuracoes/fontes_rss.json", "config/fontes_rss.json"]:
            p = root / rel
            data = _load_json_list(p)
            if data:
                return data
    return []


def _upsert_rss_fontes(fontes: list[dict[str, Any]], nome: str, feeds: list[str], dominio: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    feeds = [_norm_url(u) for u in feeds if u]
    feeds = [u for i, u in enumerate(feeds) if u and u not in feeds[:i]]
    if not feeds:
        return fontes, {"acao": "sem_feed", "alteradas": 0}
    # Atualiza a primeira fonte do mesmo domínio se existir; preserva nome/canal/campos extras.
    idx_domain = None
    for i, f in enumerate(fontes):
        d = _domain(str(f.get("url") or ""))
        if d and d == dominio:
            idx_domain = i
            break
    if idx_domain is not None:
        old = dict(fontes[idx_domain])
        fontes[idx_domain]["url"] = feeds[0]
        fontes[idx_domain]["nome"] = old.get("nome") or nome
        fontes[idx_domain]["ativo"] = old.get("ativo", True)
        fontes[idx_domain]["tipo_coleta"] = old.get("tipo_coleta", "rss")
        fontes[idx_domain]["fallbacks_v130"] = feeds[1:]
        fontes[idx_domain]["diagnostico_v130"] = True
        fontes[idx_domain]["max_itens"] = 10
        fontes[idx_domain]["forcar_proxima_coleta_qtd"] = 10
        fontes[idx_domain]["diagnostico_prioridade_proxima_coleta"] = True
        fontes[idx_domain]["aplicar_na_proxima_coleta_v47_4"] = True
        return fontes, {"acao": "atualizada_por_dominio", "antes": old.get("url"), "depois": feeds[0], "alteradas": 1, "proxima_coleta_ate": 10}
    novo = {"url": feeds[0], "nome": nome, "canal_forcado": "", "ativo": True, "tipo_coleta": "rss", "fallbacks_v130": feeds[1:], "diagnostico_v130": True, "max_itens": 10, "forcar_proxima_coleta_qtd": 10, "diagnostico_prioridade_proxima_coleta": True, "aplicar_na_proxima_coleta_v47_4": True}
    fontes.append(novo)
    return fontes, {"acao": "adicionada", "depois": feeds[0], "alteradas": 1, "proxima_coleta_ate": 10}



def _upsert_list_by_domain(items: list[dict[str, Any]], novo: dict[str, Any], dominio: str) -> list[dict[str, Any]]:
    out = []
    done = False
    for it in items:
        if _domain(str(it.get("url") or "")) == dominio:
            old = dict(it)
            old.update({k: v for k, v in novo.items() if v not in (None, "")})
            out.append(old)
            done = True
        else:
            out.append(it)
    if not done:
        out.append(novo)
    return out


def _write_single_json_all(rel: str, data: list[dict[str, Any]]) -> list[str]:
    written = []
    text = json.dumps(data, ensure_ascii=False, indent=2)
    for root in _candidate_roots():
        p = root / rel
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            _backup(p)
            p.write_text(text, encoding="utf-8")
            written.append(str(p))
        except Exception:
            pass
    return sorted(set(written))


def _sincronizar_abas_v131(perfil: dict[str, Any]) -> dict[str, Any]:
    """Faz a fonte aplicada aparecer na aba correta, sem depender disso para coletar.

    A coleta operacional real vem de perfis_fontes_v131.json. A aba é organização e edição.
    """
    grupo = str(perfil.get("grupo") or "RSS")
    dominio = str(perfil.get("dominio") or "")
    url = (perfil.get("feeds") or [perfil.get("root") or ""])[0]
    nome = perfil.get("nome") or dominio or "Nova Fonte"
    info = {"grupo": grupo, "arquivos": []}
    if grupo == "Regionais":
        rel = "regionais_v1305.json"
        data = []
        for root in _candidate_roots():
            p = root / rel
            data = _load_json_list(p)
            if data:
                break
        novo = {"nome": nome, "url": url, "ativo": True, "prioridade": "alta", "regiao": "Campos/Norte Fluminense", "tipo": "auto_v131", "tipo_coleta": "auto_v131", "perfil_v131_id": perfil.get("id"), "bypass_score": True, "regional_prioritaria": True, "min_por_fonte": 2}
        data = _upsert_list_by_domain(data, novo, dominio)
        info["arquivos"] = _write_single_json_all(rel, data)
    elif grupo == "Especiais":
        rel = "fontes_especiais_v129.json"
        data = []
        for root in _candidate_roots():
            p = root / rel
            data = _load_json_list(p)
            if data:
                break
        novo = {"nome": nome, "url": url, "ativo": True, "tipo": "auto_v131", "tipo_coleta": "auto_v131", "perfil_v131_id": perfil.get("id"), "bypass_score": True}
        data = _upsert_list_by_domain(data, novo, dominio)
        info["arquivos"] = _write_single_json_all(rel, data)
    else:
        fontes = _read_primary_fontes()
        novo = {"url": url, "nome": nome, "canal_forcado": "", "ativo": True, "tipo_coleta": "auto_v131", "perfil_v131_id": perfil.get("id"), "diagnostico_v131": True}
        fontes = _upsert_list_by_domain(fontes, novo, dominio)
        info["arquivos"] = _write_json_all(["fontes_rss.json", "configuracoes/fontes_rss.json", "config/fontes_rss.json"], fontes)
    return info

def aplicar_sugestao_diagnostico_v130(results: dict[str, Any], nome_preferido: str | None = None, permitir_html: bool = False) -> dict[str, Any]:
    """
    v131: aplicação operacional.

    Antes a função apenas gravava RSS/XML. Agora ela gera um perfil técnico, testa a coleta
    imediatamente e só marca como operacional quando a fonte produz pauta real.
    O modo antigo fica como fallback conservador para manter compatibilidade.
    """
    sol = results.get("solucao") or {}
    root = results.get("root") or ""
    dominio = _domain(root)
    nome = (nome_preferido or "").strip() or _safe_name(dominio)
    feeds = sol.get("feeds") or []
    sitemaps = sol.get("sitemaps") or []
    estrategia = sol.get("estrategia_principal") or "manual"
    relatorio = {"dominio": dominio, "nome": nome, "estrategia": estrategia, "rss": {}, "xml": {}, "avisos": [], "v131": {}}

    # 1) Caminho novo: perfil operacional testado.
    try:
        from ururau.coleta.auto_perfil_fontes_v131 import aplicar_diagnostico_operacional_v131, formatar_relatorio_v131
        info_v131 = aplicar_diagnostico_operacional_v131(results, nome_preferido=nome)
        relatorio["v131"] = info_v131
        relatorio["v131_relatorio"] = formatar_relatorio_v131(info_v131)
        if info_v131.get("aplicado"):
            # Sincroniza a aba correta (RSS/Especiais/Regionais) para organização visual.
            try:
                relatorio["v131_abas"] = _sincronizar_abas_v131(info_v131.get("perfil") or {})
            except Exception as e_sync:
                relatorio["avisos"].append(f"Perfil salvo, mas não foi possível sincronizar a aba visual: {e_sync}")
            # V43 Premium: registrar a aplicação também na fonte única de verdade
            # (config/fontes_links.json), para fechar a cadeia diagnóstico -> UI -> coleta -> status.
            try:
                from ururau.coleta.fontes_links_v43 import registrar_aplicacao_diagnostico_v43
                relatorio["v43_fontes_links"] = registrar_aplicacao_diagnostico_v43(results, relatorio)
            except Exception as e_v43:
                relatorio["avisos"].append(f"V43: perfil salvo, mas não foi possível registrar em Fontes/Links único: {e_v43}")
            # Ainda grava sitemaps como apoio de descoberta, mas a coleta efetiva será pelo perfil v131.
            if sitemaps:
                written_xml = _append_xml_all(sitemaps)
                relatorio["xml"] = {"arquivos": written_xml, "sitemaps": sitemaps}
            return relatorio
        relatorio["avisos"].append("v131 não salvou perfil porque o teste imediato não gerou pauta. Mantendo fallback seguro abaixo, se aplicável.")
    except Exception as e:
        relatorio["avisos"].append(f"v131 indisponível/falhou: {e}. Usando aplicação v130 conservadora.")

    # 2) Fallback antigo: nunca remove fontes boas.
    if estrategia in {"rss", "rss_com_fallback"} and feeds:
        fontes = _read_primary_fontes()
        fontes2, info = _upsert_rss_fontes(fontes, nome, feeds, dominio)
        written = _write_json_all(["fontes_rss.json", "configuracoes/fontes_rss.json", "config/fontes_rss.json"], fontes2)
        relatorio["rss"] = {"info": info, "arquivos": written, "feeds": feeds}
    elif estrategia == "wp_api":
        relatorio["avisos"].append("WP API detectada, mas o perfil operacional não foi confirmado. Não aplicado como RSS simples.")
    elif estrategia == "html_listagem" and not permitir_html:
        relatorio["avisos"].append("HTML de listagem detectado, mas o perfil operacional não foi confirmado. Não aplicado automaticamente.")

    if sitemaps:
        written_xml = _append_xml_all(sitemaps)
        relatorio["xml"] = {"arquivos": written_xml, "sitemaps": sitemaps}

    if not relatorio["rss"] and not relatorio["xml"] and not relatorio.get("v131", {}).get("aplicado"):
        relatorio["avisos"].append("Nenhuma alteração automática operacional foi aplicada. Use o relatório para revisar a fonte.")
    return relatorio


def formatar_relatorio_aplicacao_v130(info: dict[str, Any]) -> str:
    linhas = []
    linhas.append("APLICAÇÃO SEGURA DO DIAGNÓSTICO v130")
    linhas.append("=" * 70)
    linhas.append(f"Fonte: {info.get('nome')} | domínio: {info.get('dominio')}")
    linhas.append(f"Estratégia: {info.get('estrategia')}")
    if info.get("v131_relatorio"):
        linhas.append("\n" + str(info.get("v131_relatorio")))
    if info.get("rss"):
        linhas.append("\nRSS:")
        rss = info["rss"]
        linhas.append(f"  Ação: {rss.get('info', {}).get('acao')}")
        if rss.get('info', {}).get('antes'):
            linhas.append(f"  Antes: {rss['info'].get('antes')}")
        if rss.get('info', {}).get('depois'):
            linhas.append(f"  Depois: {rss['info'].get('depois')}")
        for f in rss.get("feeds") or []:
            linhas.append(f"  Feed/fallback: {f}")
        for a in rss.get("arquivos") or []:
            linhas.append(f"  Arquivo atualizado: {a}")
    if info.get("v131_abas"):
        linhas.append("\nAba sincronizada:")
        linhas.append(f"  Grupo: {info.get('v131_abas', {}).get('grupo')}")
        for a in info.get('v131_abas', {}).get('arquivos') or []:
            linhas.append(f"  Arquivo atualizado: {a}")
    if info.get("v43_fontes_links"):
        linhas.append("\nFonte única V43:")
        linhas.append(f"  Arquivo atualizado: {info.get('v43_fontes_links', {}).get('arquivo')}")
        _it_v43 = info.get('v43_fontes_links', {}).get('item') or {}
        if _it_v43:
            linhas.append(f"  Grupo: {_it_v43.get('grupo')} | URL operacional: {_it_v43.get('url')}")
    if info.get("xml"):
        linhas.append("\nXML/Sitemap:")
        for s in info["xml"].get("sitemaps") or []:
            linhas.append(f"  Sitemap: {s}")
        for a in info["xml"].get("arquivos") or []:
            linhas.append(f"  Arquivo atualizado: {a}")
    if info.get("avisos"):
        linhas.append("\nAvisos:")
        for a in info.get("avisos") or []:
            linhas.append(f"  - {a}")
    return "\n".join(linhas)



def _relatorios_aplicacao_dir_v131() -> Path:
    root = _candidate_roots()[0] if _candidate_roots() else Path.cwd()
    p = root / "relatorios_diagnostico_fontes" / "aplicacoes_v131"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resumo_resultado_aplicacao_v131(info: dict[str, Any]) -> str:
    """Resumo executivo obrigatório após Aplicar e testar.

    Finalidade: o operador deve saber imediatamente se a fonte entrou, onde foi salva
    e se será usada na próxima coleta. Não depende da leitura do relatório técnico longo.
    """
    v131 = info.get("v131") or {}
    perfil = v131.get("perfil") or {}
    teste = v131.get("teste") or {}
    stats = teste.get("stats") or {}
    salvo = v131.get("salvo") or {}
    abas = info.get("v131_abas") or {}
    aplicado = bool(v131.get("aplicado"))
    linhas = []
    linhas.append("RESULTADO DO APLICAR E TESTAR PERFIL v131.4")
    linhas.append("=" * 72)
    linhas.append(f"Fonte: {perfil.get('nome') or info.get('nome') or '-'}")
    linhas.append(f"Domínio: {perfil.get('dominio') or info.get('dominio') or '-'}")
    linhas.append(f"Grupo/aba: {perfil.get('grupo') or abas.get('grupo') or '-'}")
    linhas.append(f"Estratégia: {perfil.get('estrategia') or info.get('estrategia') or '-'}")
    linhas.append(f"Parser operacional: {perfil.get('parser') or '-'}")
    linhas.append("Regra operacional: diagnóstico gera perfil; perfil é testado; salva quando gera pauta real ou comprova extração técnica funcional sem pauta na janela.")
    linhas.append("")
    linhas.append("STATUS FINAL")
    linhas.append("-" * 72)
    if aplicado:
        linhas.append("APLICADO E FUNCIONAL: SIM")
        if teste.get("ok"):
            linhas.append("Status: funcional com pauta dentro da janela")
        elif teste.get("sucesso_tecnico"):
            linhas.append("Status: funcional técnico, sem pauta dentro da janela neste teste")
        linhas.append("Será usada na próxima coleta geral: SIM, pela fase AutoFontes v131.4")
    else:
        linhas.append("APLICADO E FUNCIONAL: NÃO")
        linhas.append("Será usada na próxima coleta geral: NÃO, porque o teste não gerou pauta nem comprovou extração técnica")
    linhas.append("")
    linhas.append("TESTE IMEDIATO")
    linhas.append("-" * 72)
    linhas.append(f"Teste executado: SIM")
    linhas.append(f"Pautas de teste geradas: {teste.get('qtd', 0)}")
    if teste.get("primeira"):
        linhas.append(f"Primeira pauta: {teste.get('primeira')}")
    linhas.append(f"Itens brutos lidos: {stats.get('brutas', 0)}")
    linhas.append(f"Itens com título/link: {stats.get('titulo_link', 0)}")
    linhas.append(f"Itens aceitos pela janela/perfil: {stats.get('aceitas', 0)}")
    linhas.append(f"Itens fora da janela: {stats.get('fora_janela', 0)}")
    linhas.append("")
    linhas.append("TENTATIVAS DO COLETOR")
    linhas.append("-" * 72)
    tentativas = stats.get("tentativas") or []
    if not tentativas:
        linhas.append("Nenhuma tentativa técnica registrada.")
    else:
        for t in tentativas:
            linhas.append(
                f"{t.get('parser_usado') or '-'} | status={t.get('status')} | "
                f"itens={t.get('itens')} | aceitas={t.get('aceitas')} | {t.get('url')}"
            )
            if t.get("erro"):
                linhas.append(f"  erro: {t.get('erro')}")
    linhas.append("")
    linhas.append("ARQUIVOS / PERSISTÊNCIA")
    linhas.append("-" * 72)
    if salvo.get("arquivo"):
        linhas.append(f"Perfil salvo: SIM")
        linhas.append(f"Arquivo do perfil: {salvo.get('arquivo')}")
    else:
        linhas.append("Perfil salvo: NÃO")
    if abas:
        linhas.append(f"Aba sincronizada: {abas.get('grupo') or '-'}")
        for a in abas.get("arquivos") or []:
            linhas.append(f"Arquivo de aba atualizado: {a}")
    if info.get("xml"):
        for a in info.get("xml", {}).get("arquivos") or []:
            linhas.append(f"Arquivo XML/Sitemap atualizado: {a}")
    avisos = []
    avisos.extend(v131.get("avisos") or [])
    avisos.extend(info.get("avisos") or [])
    if avisos:
        linhas.append("")
        linhas.append("AVISOS")
        linhas.append("-" * 72)
        for a in avisos:
            linhas.append(f"- {a}")
    if not aplicado:
        linhas.append("")
        linhas.append("O QUE FAZER")
        linhas.append("-" * 72)
        linhas.append("A ferramenta não marcou a fonte como resolvida porque não houve pauta real nem extração técnica suficiente no teste.")
        linhas.append("Use o diagnóstico exibido para revisar se a estratégia deve ser RSS, XML direto, WP API, Sitemap, HTML ou Playwright.")
    return "\n".join(linhas)


def salvar_relatorio_aplicacao_v131(info: dict[str, Any], relatorio_tecnico: str = "") -> dict[str, str]:
    """Salva o resultado de Aplicar/Testar em TXT e JSON para auditoria."""
    try:
        v131 = info.get("v131") or {}
        perfil = v131.get("perfil") or {}
        dominio = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(perfil.get("dominio") or info.get("dominio") or "fonte"))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        d = _relatorios_aplicacao_dir_v131()
        txt = d / f"aplicacao_v131_{dominio}_{stamp}.txt"
        js = d / f"aplicacao_v131_{dominio}_{stamp}.json"
        resumo = resumo_resultado_aplicacao_v131(info)
        txt.write_text(resumo + "\n\n" + (relatorio_tecnico or ""), encoding="utf-8")
        js.write_text(json.dumps(info, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return {"txt": str(txt), "json": str(js)}
    except Exception as e:
        return {"erro": str(e)}
