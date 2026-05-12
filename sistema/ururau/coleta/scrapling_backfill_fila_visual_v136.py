# -*- coding: utf-8 -*-
"""scrapling_backfill_fila_visual_v136.py

Garante que pautas inseridas pelo Scrapling v136 fiquem visíveis no painel.

O problema observado: o banco recebe as pautas, mas a fila visual pode não
listar porque algumas colunas usadas por filtros/agrupamento/visibilidade do
painel ficam vazias nas linhas v136.

Este script é tolerante ao schema: só atualiza colunas que existirem.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SISTEMA = ROOT / "sistema"
DB_PATH = SISTEMA / "data" / "ururau.db"


def _cols(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return bool(row)


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def executar_backfill_fila_visual_v136(db_path: Path | None = None) -> dict:
    db_path = db_path or DB_PATH
    con = sqlite3.connect(db_path, timeout=20)
    try:
        con.execute("PRAGMA busy_timeout=20000")
        try:
            con.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass

        if not _table_exists(con, "pautas"):
            return {"ok": False, "erro": "tabela pautas inexistente"}

        cols = _cols(con, "pautas")
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        lote = time.strftime("Coleta Scrapling v136 - %H:%M")

        where_parts = []
        params: list[str] = []
        if "uid" in cols:
            where_parts.append("uid LIKE ?")
            params.append("scrapling_v136_%")
        if "origem_v136" in cols:
            where_parts.append("origem_v136 LIKE ?")
            params.append("%scrapling%")
        if "origem" in cols:
            where_parts.append("origem LIKE ?")
            params.append("%scrapling%")
        where = " OR ".join(where_parts) if where_parts else "0"

        before = con.execute(f"SELECT COUNT(*) FROM pautas WHERE {where}", params).fetchone()[0]

        assignments: list[str] = []
        values: list[str | int] = []

        def set_if_exists(col: str, val):
            if col in cols:
                assignments.append(f"{_q(col)} = ?")
                values.append(val)

        def set_if_empty(col: str, val):
            if col in cols:
                assignments.append(f"{_q(col)} = CASE WHEN {_q(col)} IS NULL OR TRIM(CAST({_q(col)} AS TEXT))='' THEN ? ELSE {_q(col)} END")
                values.append(val)

        set_if_exists("status", "captada")
        set_if_exists("situacao", "captada")
        set_if_exists("oculto", 0)
        set_if_exists("oculta", 0)
        set_if_exists("excluida", 0)
        set_if_exists("excluido", 0)
        set_if_exists("descartada", 0)
        set_if_exists("descartado", 0)
        set_if_exists("bloqueada", 0)
        set_if_exists("bloqueado", 0)
        set_if_exists("reprovada", 0)
        set_if_exists("reprovado", 0)
        set_if_exists("mostrar_na_fila", 1)
        set_if_exists("visivel", 1)
        set_if_exists("na_fila", 1)
        set_if_exists("ativo", 1)
        set_if_exists("baixo_score", 0)
        set_if_exists("aprovada_baixo_score", 1)

        set_if_empty("titulo_origem", "Pauta Scrapling v136")
        if "titulo" in cols and "titulo_origem" in cols:
            assignments.append('"titulo" = CASE WHEN "titulo" IS NULL OR TRIM(CAST("titulo" AS TEXT))="" THEN "titulo_origem" ELSE "titulo" END')
        elif "titulo" in cols:
            set_if_empty("titulo", "Pauta Scrapling v136")

        set_if_empty("fonte", "Scrapling v136")
        set_if_empty("fonte_nome", "Scrapling v136")
        set_if_empty("nome_fonte", "Scrapling v136")
        set_if_empty("canal", "Geral")
        set_if_empty("canal_forcado", "Geral")
        set_if_empty("editoria", "Geral")
        set_if_empty("created_at", now)
        set_if_empty("criado_em", now)
        set_if_empty("data_criacao", now)
        set_if_empty("data_pub_fonte", now)
        set_if_empty("data_fonte", now)
        set_if_empty("coleta_lote_label_v123", lote)
        set_if_empty("origem", "scrapling_v136")
        set_if_empty("origem_v136", "scrapling_v136")

        if not assignments:
            return {"ok": True, "alteradas": 0, "total_v136": before, "aviso": "nenhuma coluna de visibilidade encontrada"}

        sql = f"UPDATE pautas SET {', '.join(assignments)} WHERE {where}"
        cur = con.execute(sql, values + params)
        con.commit()
        after = con.execute(f"SELECT COUNT(*) FROM pautas WHERE {where}", params).fetchone()[0]
        return {"ok": True, "alteradas": cur.rowcount, "total_v136": after, "db": str(db_path)}
    finally:
        con.close()


def main() -> int:
    res = executar_backfill_fila_visual_v136()
    print("[V136][FILA_VISUAL][BACKFILL]", res, flush=True)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
