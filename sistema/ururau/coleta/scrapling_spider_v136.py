# -*- coding: utf-8 -*-
"""Scrapling Spider/Runner v136.

Worker externo de captação. Usa Scrapling como motor principal para descobrir
links novos por fonte, sem executar dentro do painel visual.

Fluxo:
1. Carrega fontes configuradas.
2. Roda discovery por fonte com ScraplingEngineV136.
3. Grava candidatos novos via QueueWriterV136.
4. Salva relatórios JSON/JSONL.

Não remove nem substitui módulos legados; serve como motor v136 de captação.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from ururau.coleta.scrapling_source_discovery_v136 import (
    diagnosticar_fonte_scrapling_v136,
    salvar_diagnostico_v136,
)
from ururau.coleta.scrapling_queue_writer_v136 import (
    inserir_candidatos_v136,
    salvar_resultado_writer_v136,
)

ROOT = Path(__file__).resolve().parents[3]
SISTEMA = ROOT / "sistema"
OUT_DIR = SISTEMA / "relatorios_scrapling_v136"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SOURCES = [
    {"nome": "G1 Globo", "url": "https://g1.globo.com/"},
    {"nome": "Band", "url": "https://www.band.com.br/"},
    {"nome": "Campos 24 Horas", "url": "https://campos24horas.com.br/"},
    {"nome": "NF Noticias", "url": "https://nfnoticias.com.br/"},
    {"nome": "Diario do Rio", "url": "https://diariodorio.com/feed/"},
    {"nome": "RJ News Noticias", "url": "https://rjnewsnoticias.com.br/feed/"},
    {"nome": "Poder360", "url": "https://www.poder360.com.br/"},
    {"nome": "Metropoles", "url": "https://www.metropoles.com/"},
    {"nome": "Manchete RJ", "url": "https://mancheterj.com/"},
]


def _load_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return None


def _iter_urls_from_config(data: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str) and item.startswith("http"):
                out.append({"nome": f"Fonte {i+1}", "url": item})
            elif isinstance(item, dict):
                url = item.get("url") or item.get("link") or item.get("feed") or item.get("rss") or item.get("site")
                nome = item.get("nome") or item.get("fonte") or item.get("name") or item.get("label") or url
                if isinstance(url, str) and url.startswith("http"):
                    out.append({"nome": str(nome or url), "url": url})
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and value.startswith("http"):
                out.append({"nome": str(key), "url": value})
            elif isinstance(value, list):
                out.extend(_iter_urls_from_config(value))
            elif isinstance(value, dict):
                out.extend(_iter_urls_from_config([value]))
    return out


def carregar_fontes_v136() -> list[dict[str, str]]:
    paths = [
        SISTEMA / "config" / "fontes_rss.json",
        SISTEMA / "config" / "fontes_links.json",
        SISTEMA / "configuracoes" / "fontes_rss.json",
        SISTEMA / "fontes_rss.json",
    ]
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in paths:
        data = _load_json(path)
        for item in _iter_urls_from_config(data):
            url = item.get("url") or ""
            if url and url not in seen:
                out.append(item)
                seen.add(url)
    if not out:
        out = DEFAULT_SOURCES
    return out


def salvar_resumo_v136(resumo: dict[str, Any]) -> str:
    path = OUT_DIR / ("coleta_scrapling_v136_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    path.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def executar_coleta_scrapling_v136(limit_fontes: int = 20, limit_links_por_fonte: int = 40, gravar: bool = True) -> dict[str, Any]:
    fontes = carregar_fontes_v136()[:limit_fontes]
    resumo: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "fontes_total": len(fontes),
        "fontes": [],
        "candidatos_total": 0,
        "inseridos_total": 0,
        "duplicados_total": 0,
        "bloqueados_total": 0,
        "erros": [],
    }

    for fonte in fontes:
        nome = fonte.get("nome") or fonte.get("url") or "Fonte"
        url = fonte.get("url") or ""
        if not url:
            continue
        print(f"[V136][SCRAPLING][FONTE] {nome} | {url}", flush=True)
        try:
            diag = diagnosticar_fonte_scrapling_v136(nome, url, limite=limit_links_por_fonte)
            paths = salvar_diagnostico_v136(diag)
            writer_result = None
            if gravar and diag.candidatos:
                writer_result = inserir_candidatos_v136(diag.candidatos)
                salvar_resultado_writer_v136(writer_result)
                resumo["inseridos_total"] += int(writer_result.inseridos)
                resumo["duplicados_total"] += int(writer_result.duplicados)
                resumo["bloqueados_total"] += int(writer_result.bloqueados)
            resumo["candidatos_total"] += int(diag.candidatos_total)
            resumo["fontes"].append({
                "nome": nome,
                "url": url,
                "ok": diag.ok,
                "estrategia": diag.estrategia,
                "candidatos": diag.candidatos_total,
                "inseridos": getattr(writer_result, "inseridos", 0) if writer_result else 0,
                "duplicados": getattr(writer_result, "duplicados", 0) if writer_result else 0,
                "bloqueados": getattr(writer_result, "bloqueados", 0) if writer_result else 0,
                "relatorios": paths,
                "erros": diag.erros[:5],
            })
        except Exception as exc:
            msg = f"{nome} | {url} | {type(exc).__name__}: {exc}"
            print(f"[V136][SCRAPLING][ERRO] {msg}", flush=True)
            resumo["erros"].append(msg)

    resumo_path = salvar_resumo_v136(resumo)
    resumo["relatorio"] = resumo_path
    print("=" * 90)
    print("[V136][SCRAPLING] RELATORIO:", resumo_path)
    print("[V136][SCRAPLING] CANDIDATOS:", resumo["candidatos_total"])
    print("[V136][SCRAPLING] INSERIDOS:", resumo["inseridos_total"])
    print("[V136][SCRAPLING] DUPLICADOS:", resumo["duplicados_total"])
    print("[V136][SCRAPLING] BLOQUEADOS:", resumo["bloqueados_total"])
    print("=" * 90)
    return resumo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fontes", type=int, default=int(os.getenv("URURAU_SCRAPLING_V136_FONTES", "20") or "20"))
    parser.add_argument("--links", type=int, default=int(os.getenv("URURAU_SCRAPLING_V136_LINKS", "40") or "40"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    executar_coleta_scrapling_v136(limit_fontes=args.fontes, limit_links_por_fonte=args.links, gravar=not args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
