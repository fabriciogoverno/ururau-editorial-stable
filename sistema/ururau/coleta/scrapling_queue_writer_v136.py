# -*- coding: utf-8 -*-
"""Scrapling Queue Writer v136.

Recebe links descobertos pelo Scrapling e grava somente pautas novas no banco,
respeitando bloqueios, descartadas/reprovadas e deduplicação básica.

Foi desenhado para rodar fora do painel visual.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[3]
SISTEMA = ROOT / "sistema"
DB = SISTEMA / "data" / "ururau.db"
OUT_DIR = SISTEMA / "relatorios_scrapling_v136"
OUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class QueueWriteResultV136:
    analisados: int = 0
    inseridos: int = 0
    duplicados: int = 0
    bloqueados: int = 0
    erros: list[str] = None

    def __post_init__(self):
        if self.erros is None:
            self.erros = []


def _norm_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, flags=re.I):
        url = "https://" + url.lstrip("/")
    p = urlparse(url)
    path = re.sub(r"/{2,}", "/", p.path or "/")
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))


def _title_key(title: str) -> str:
    title = str(title or "").lower()
    title = re.sub(r"[^a-z0-9áéíóúãõâêôç]+", "", title)
    return title[:180]


def _hash_url(url: str) -> str:
    return hashlib.sha1(_norm_url(url).encode("utf-8", errors="ignore")).hexdigest()


def _cols(con: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def _ensure_col(con: sqlite3.Connection, table: str, col: str, typ: str = "TEXT") -> None:
    if col not in _cols(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def _setup(con: sqlite3.Connection) -> None:
    if not _table_exists(con, "pautas"):
        con.execute(
            "CREATE TABLE pautas (id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, link_origem TEXT, fonte TEXT, status TEXT, criado_em TEXT)"
        )
    for col in [
        "titulo", "link_origem", "fonte", "status", "criado_em", "url_hash_v136",
        "titulo_hash_v136", "origem_v136", "score_v136", "dominio_v136"
    ]:
        _ensure_col(con, "pautas", col)

    if not _table_exists(con, "links_bloqueados"):
        con.execute("CREATE TABLE links_bloqueados (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, motivo TEXT, criado_em TEXT)")
    for col in ["link", "motivo", "criado_em"]:
        _ensure_col(con, "links_bloqueados", col)
    con.commit()


def _blocked_urls(con: sqlite3.Connection) -> set[str]:
    out = set()
    try:
        for row in con.execute("SELECT link FROM links_bloqueados"):
            u = _norm_url(row[0] or "")
            if u:
                out.add(u)
    except Exception:
        pass
    return out


def _existing(con: sqlite3.Connection) -> tuple[set[str], set[str]]:
    urls = set()
    titles = set()
    for row in con.execute("SELECT link_origem, titulo FROM pautas"):
        u = _norm_url(row[0] or "")
        t = _title_key(row[1] or "")
        if u:
            urls.add(u)
        if t:
            titles.add(t)
    return urls, titles


def inserir_candidatos_v136(candidatos: list[dict[str, Any]], db_path: Path | None = None) -> QueueWriteResultV136:
    db_path = db_path or DB
    res = QueueWriteResultV136()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=20)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=20000")
    except Exception:
        pass
    _setup(con)

    blocked = _blocked_urls(con)
    existing_urls, existing_titles = _existing(con)

    for item in candidatos or []:
        res.analisados += 1
        try:
            url = _norm_url(item.get("url") or "")
            title = str(item.get("titulo") or "").strip()
            if not url:
                res.erros.append("sem_url")
                continue
            if url in blocked:
                res.bloqueados += 1
                continue
            tkey = _title_key(title)
            if url in existing_urls or (tkey and tkey in existing_titles):
                res.duplicados += 1
                continue

            con.execute(
                "INSERT INTO pautas (titulo, link_origem, fonte, status, criado_em, url_hash_v136, titulo_hash_v136, origem_v136, score_v136, dominio_v136) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    title or url,
                    url,
                    item.get("fonte") or item.get("dominio") or "Scrapling v136",
                    "captada",
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    _hash_url(url),
                    tkey,
                    item.get("origem") or item.get("metodo") or "scrapling_v136",
                    str(item.get("score") or 0),
                    item.get("dominio") or urlparse(url).netloc,
                ),
            )
            existing_urls.add(url)
            if tkey:
                existing_titles.add(tkey)
            res.inseridos += 1
            if res.inseridos % 10 == 0:
                con.commit()
        except Exception as exc:
            res.erros.append(f"{type(exc).__name__}: {exc}")
    con.commit()
    return res


def salvar_resultado_writer_v136(result: QueueWriteResultV136) -> str:
    path = OUT_DIR / ("queue_writer_v136_" + time.strftime("%Y%m%d_%H%M%S") + ".json")
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


__all__ = ["QueueWriteResultV136", "inserir_candidatos_v136", "salvar_resultado_writer_v136"]
