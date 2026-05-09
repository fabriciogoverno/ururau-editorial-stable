"""Limpeza segura de caches temporários — v129.12.

Não remove configurações, banco, credenciais, matérias geradas, imagens finais
ou histórico de publicação. A limpeza automática é conservadora e roda no
máximo uma vez por intervalo, para não pesar na inicialização.
"""
from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Iterable

ROOT = Path.cwd()
LOG_DIR = ROOT / "logs"
MARKER = ROOT / "data" / "ultima_limpeza_cache_v12912.json"

# Retenção em segundos
H24 = 24 * 3600
D3 = 3 * 24 * 3600
D7 = 7 * 24 * 3600

PROTECTED_NAMES = {
    ".env", "fontes_rss.json", "fontes_especiais_v129.json", "termos_watchlist_v98.json",
    "fontes_xml_sitemap_vfinal.txt", "database.json", "ururau.db", "historico.json",
}
PROTECTED_DIR_PARTS = {
    "config", "configuracoes", "credenciais", "ururau", "venv", ".venv", "__pycache__"
}

RULES: list[tuple[str, int, tuple[str, ...]]] = [
    ("cache", H24, ("*",)),
    (".cache", H24, ("*",)),
    ("tmp", H24, ("*",)),
    ("temp", H24, ("*",)),
    ("data/cache", H24, ("*",)),
    ("html_cache", H24, ("*",)),
    ("logs", D7, ("*.log", "*.txt")),
    ("diagnosticos", D7, ("*.txt", "*.json")),
    ("relatorios", D7, ("diagnostico_*.txt", "diagnostico_*.json", "relatorio_diagnostico_*.txt", "relatorio_diagnostico_*.json")),
    ("imagens/thumbs", D3, ("*.jpg", "*.jpeg", "*.png", "*.webp")),
    ("imagens/_preview_cache_v12910", D3, ("*.jpg", "*.jpeg", "*.png", "*.webp")),
    ("_preview_cache_v12910", D3, ("*.jpg", "*.jpeg", "*.png", "*.webp")),
    # Originais são grandes e podem ser recriados/baixados; finais de publicação não entram aqui.
    ("imagens", D3, ("*_original.jpg", "*_original.jpeg", "*_original.png", "*_tmp.*", "*_temp.*")),
]


def _now() -> float:
    return time.time()


def _is_protected(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except Exception:
        rel = path
    parts = {p.lower() for p in rel.parts}
    if path.name in PROTECTED_NAMES:
        return True
    if parts & PROTECTED_DIR_PARTS and not ("logs" in parts or "cache" in parts or "tmp" in parts or "temp" in parts):
        return True
    # Nunca apaga imagem final de publicação.
    low = path.name.lower()
    if "_final" in low or low.endswith("final.jpg") or low.endswith("final.jpeg") or low.endswith("final.png"):
        return True
    return False


def _candidate_files(base: Path, patterns: Iterable[str]):
    if not base.exists() or not base.is_dir():
        return []
    out = []
    for pat in patterns:
        try:
            out.extend([p for p in base.rglob(pat) if p.is_file()])
        except Exception:
            pass
    return out


def simular_limpeza_cache_v12912() -> dict:
    agora = _now()
    itens = []
    total = 0
    for rel_dir, idade, patterns in RULES:
        base = ROOT / rel_dir
        for f in _candidate_files(base, patterns):
            try:
                if _is_protected(f):
                    continue
                st = f.stat()
                if agora - st.st_mtime < idade:
                    continue
                size = st.st_size
                total += size
                itens.append({"path": str(f), "bytes": size, "idade_h": round((agora - st.st_mtime)/3600, 1), "regra": rel_dir})
            except Exception:
                continue
    return {"total_bytes": total, "total_arquivos": len(itens), "itens": itens[:5000]}


def executar_limpeza_cache_v12912(dry_run: bool = False, forcar: bool = False) -> dict:
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    if not forcar and MARKER.exists():
        try:
            data = json.loads(MARKER.read_text(encoding="utf-8"))
            if _now() - float(data.get("timestamp", 0)) < 6 * 3600:
                return {"executado": False, "motivo": "intervalo_6h", "apagados": 0, "bytes": 0}
        except Exception:
            pass
    sim = simular_limpeza_cache_v12912()
    apagados = 0
    bytes_del = 0
    erros = []
    if not dry_run:
        for item in sim.get("itens", []):
            f = Path(item["path"])
            try:
                if _is_protected(f):
                    continue
                size = f.stat().st_size if f.exists() else 0
                f.unlink(missing_ok=True)
                apagados += 1
                bytes_del += size
            except Exception as e:
                erros.append(f"{f}: {e}")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    resumo = {
        "executado": True,
        "dry_run": dry_run,
        "candidatos": sim.get("total_arquivos", 0),
        "candidatos_bytes": sim.get("total_bytes", 0),
        "apagados": apagados,
        "bytes": bytes_del,
        "erros": erros[:30],
        "timestamp": _now(),
    }
    try:
        (LOG_DIR / "limpeza_cache_v12912.log").open("a", encoding="utf-8").write(json.dumps(resumo, ensure_ascii=False) + "\n")
        MARKER.write_text(json.dumps({"timestamp": _now()}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return resumo


def executar_limpeza_automatica_segura_v12912() -> None:
    try:
        r = executar_limpeza_cache_v12912(dry_run=False, forcar=False)
        if r.get("executado"):
            mb = (r.get("bytes", 0) or 0) / (1024 * 1024)
            print(f"[CACHE v129.12] limpeza automática: {r.get('apagados', 0)} arquivo(s), {mb:.1f} MB")
    except Exception as e:
        print(f"[CACHE v129.12] limpeza automática ignorada: {e}")
