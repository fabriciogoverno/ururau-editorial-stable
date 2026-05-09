"""
ururau/coleta/config_unificada.py — carregamento conservador e unificado de fontes.

Objetivo V47.7:
  - não reduzir capacidade: ler todas as fontes existentes nos arquivos legados;
  - resolver duplicações por URL sem apagar os arquivos originais;
  - priorizar fontes aplicadas pelo Diagnóstico de Fonte na próxima coleta;
  - fornecer um ponto comum para painel, monitor 24h e validadores.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse


def base_sistema() -> Path:
    try:
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path.cwd()


def caminhos_candidatos(*relativos: str) -> list[Path]:
    base = base_sistema()
    out: list[Path] = []
    for rel in relativos:
        for p in (Path(rel), base / rel):
            if p not in out:
                out.append(p)
    return out


def carregar_json_lista_multiplos(relativos: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    itens: list[dict[str, Any]] = []
    arquivos: list[str] = []
    for p in caminhos_candidatos(*relativos):
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding='utf-8', errors='ignore'))
            if isinstance(data, dict):
                if isinstance(data.get('fontes'), list):
                    data = data.get('fontes')
                elif isinstance(data.get('items'), list):
                    data = data.get('items')
                else:
                    continue
            if not isinstance(data, list):
                continue
            arquivos.append(str(p))
            for item in data:
                if isinstance(item, dict):
                    item2 = dict(item)
                    item2.setdefault('_origem_arquivo_config', str(p))
                    itens.append(item2)
        except Exception:
            continue
    return itens, arquivos


def normalizar_url(url: str) -> str:
    url = str(url or '').strip()
    if not url:
        return ''
    # Corrige colagens duplicadas do tipo https://site/https://site/
    matches = list(re.finditer(r'https?://', url, flags=re.I))
    if len(matches) > 1:
        url = url[matches[-1].start():]
    if not re.match(r'^https?://', url, re.I):
        url = 'https://' + url
    try:
        p = urlparse(url)
        if not p.netloc:
            return ''
        return urlunparse((p.scheme.lower() or 'https', p.netloc.lower(), p.path or '/', '', p.query or '', ''))
    except Exception:
        return url


def dominio(url: str) -> str:
    try:
        host = urlparse(normalizar_url(url)).netloc.lower()
        return host[4:] if host.startswith('www.') else host
    except Exception:
        return ''


def _bool_ativo(item: dict[str, Any]) -> bool:
    v = item.get('ativo', True)
    if isinstance(v, str):
        return v.strip().lower() not in {'0', 'false', 'nao', 'não', 'off', 'inativo'}
    return bool(v)


def _parece_feed(url: str, item: dict[str, Any] | None = None) -> bool:
    u = normalizar_url(url).lower()
    tipo = str((item or {}).get('tipo_coleta') or (item or {}).get('tipo') or '').lower()
    if 'rss' in tipo or 'feed' in tipo or 'atom' in tipo:
        return True
    return any(x in u for x in ('rss', 'feed', 'atom', '.xml'))


def _merge_item(atual: dict[str, Any], novo: dict[str, Any]) -> dict[str, Any]:
    merged = dict(atual)
    # Nunca apaga informação existente; só preenche vazios e preserva marcadores operacionais fortes.
    for k, v in novo.items():
        if k not in merged or merged.get(k) in (None, '', [], {}):
            merged[k] = v
    for k in ('diagnostico_prioridade_proxima_coleta', 'aplicar_na_proxima_coleta_v47_4', 'diagnostico_v130', 'diagnostico_v131', 'bypass_score', 'regional_prioritaria'):
        if novo.get(k):
            merged[k] = novo.get(k)
    for k in ('max_itens', 'max_por_link', 'forcar_proxima_coleta_qtd'):
        try:
            merged[k] = max(int(merged.get(k) or 0), int(novo.get(k) or 0)) or merged.get(k) or novo.get(k)
        except Exception:
            pass
    origem = list(dict.fromkeys(str(x) for x in ([merged.get('_origem_arquivo_config')] + [novo.get('_origem_arquivo_config')]) if x))
    if origem:
        merged['_origens_arquivo_config'] = origem
        merged['_origem_arquivo_config'] = origem[0]
    return merged


def deduplicar_por_url(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    por_url: dict[str, dict[str, Any]] = {}
    ordem: list[str] = []
    for raw in itens:
        item = dict(raw)
        url = normalizar_url(item.get('url') or item.get('feed') or item.get('link') or '')
        if not url:
            continue
        item['url'] = url
        key = url.rstrip('/').lower()
        if key in por_url:
            por_url[key] = _merge_item(por_url[key], item)
        else:
            por_url[key] = item
            ordem.append(key)
    out = [por_url[k] for k in ordem]
    def score_ordem(f: dict[str, Any]):
        diag = 0 if (f.get('diagnostico_prioridade_proxima_coleta') or f.get('aplicar_na_proxima_coleta_v47_4')) else 1
        ativo = 0 if _bool_ativo(f) else 1
        try:
            ordem_num = int(f.get('ordem') or f.get('prioridade_num') or 999)
        except Exception:
            ordem_num = 999
        return (diag, ativo, ordem_num, str(f.get('nome') or f.get('fonte_nome') or dominio(f.get('url',''))).lower())
    out.sort(key=score_ordem)
    return out


def carregar_fontes_rss_unificadas() -> list[dict[str, Any]]:
    """Lê RSS de todos os arquivos compatíveis, sem escolher apenas o primeiro."""
    rels = [
        'fontes_rss.json',
        'config/fontes_rss.json',
        'configuracoes/fontes_rss.json',
        'fontes_oficiais_prioritarias.json',
        'configuracoes/fontes_oficiais_prioritarias.json',
    ]
    itens, _arquivos = carregar_json_lista_multiplos(rels)

    # Índice visual unificado: aproveita apenas itens que realmente parecem RSS/feed.
    fl_items, _ = carregar_json_lista_multiplos(['config/fontes_links.json'])
    for it in fl_items:
        grupo = str(it.get('grupo') or '').lower()
        url = it.get('url') or ''
        if grupo == 'rss' or _parece_feed(url, it):
            novo = dict(it)
            novo.setdefault('tipo_coleta', 'rss')
            itens.append(novo)

    # Normalização conservadora: mantém extras, remove apenas inativos/vazios.
    ativos = [f for f in itens if _bool_ativo(f) and (f.get('url') or f.get('feed') or f.get('link'))]
    try:
        from ururau.coleta.fonte_registry_v126 import normalizar_fontes_config_v126
        ativos = normalizar_fontes_config_v126(ativos, tipo_padrao='rss')
    except Exception:
        pass
    return deduplicar_por_url(ativos)


__all__ = [
    'base_sistema', 'carregar_json_lista_multiplos', 'carregar_fontes_rss_unificadas',
    'normalizar_url', 'dominio', 'deduplicar_por_url'
]
