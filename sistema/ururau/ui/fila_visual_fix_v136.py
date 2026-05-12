# -*- coding: utf-8 -*-
from __future__ import annotations

import builtins
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

_INSTALLED = False
_ORIG_IMPORT = None
_ORIG_POPULAR = None


def _db_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "ururau.db"


def _cols(con: sqlite3.Connection) -> list[str]:
    return [r[1] for r in con.execute("PRAGMA table_info(pautas)").fetchall()]


def _slug(url: str) -> str:
    try:
        path = unquote(urlparse(str(url or "")).path or "")
        s = path.strip("/").split("/")[-1]
        s = re.sub(r"\.(html?|ghtml|shtml|php)$", "", s, flags=re.I)
        s = re.sub(r"[-_]+", " ", s).strip()
        return s[:1].upper() + s[1:] if len(s) >= 8 else "Sem título identificado"
    except Exception:
        return "Sem título identificado"


def _host(url: str) -> str:
    try:
        h = urlparse(str(url or "")).netloc.lower().replace("www.", "")
        return h.split(":")[0] if h else "Scrapling v136"
    except Exception:
        return "Scrapling v136"


def _texto(p: dict) -> str:
    return str(p.get("cleaned_source_text") or p.get("texto_fonte") or p.get("texto_fonte_v134") or p.get("texto_fonte_v105") or p.get("raw_source_text") or p.get("dossie") or "").strip()


def _img(p: dict) -> str:
    return str(p.get("imagem_url") or p.get("imagem_url_v134") or p.get("imagem") or p.get("image") or p.get("foto_url") or p.get("thumb") or p.get("thumbnail") or p.get("og_image") or "").strip()


def _bad(p: dict) -> bool:
    t = str(p.get("titulo_origem") or p.get("titulo") or "").lower().strip()
    if not t and not str(p.get("link_origem") or "").strip():
        return True
    return any(x in t for x in ("powershell", "select-string", "set-content", "get-content", "traceback", "syntaxerror", "patch_"))


def _enrich(p: dict, lote: str) -> dict:
    try:
        link = str(p.get("link_origem") or p.get("url") or p.get("url_original") or p.get("url_final") or "").strip()
        title = str(p.get("titulo_origem") or p.get("titulo") or p.get("headline") or "").strip()
        if not title or title.startswith("http") or ("/" in title and len(title) > 120):
            title = _slug(link)
        text = _texto(p)
        image = _img(p)
        fonte = str(p.get("fonte") or p.get("fonte_nome") or p.get("nome_fonte") or p.get("dominio_v136") or "").strip()
        if not fonte or fonte.lower() in {"fonte", "geral", "scrapling v136"}:
            fonte = _host(link)
        data = str(p.get("data_pub_fonte") or p.get("data_fonte") or p.get("captada_em") or p.get("criado_em") or p.get("created_at") or "").strip() or time.strftime("%Y-%m-%d %H:%M:%S")
        chars = len(text)
        score = 100 if chars >= 550 and image else 90 if chars >= 550 else 80 if chars > 0 and image else 70 if chars > 0 else 60 if image else 35
        p.update({
            "titulo_origem": title,
            "titulo": title,
            "headline": title,
            "link_origem": link,
            "url": p.get("url") or link,
            "fonte": fonte,
            "fonte_nome": fonte,
            "nome_fonte": fonte,
            "data_pub_fonte": data,
            "data_fonte": data,
            "data": data,
            "criado_em": p.get("criado_em") or data,
            "created_at": p.get("created_at") or data,
            "coleta_lote_label_v123": p.get("coleta_lote_label_v123") or lote,
            "coleta_lote": p.get("coleta_lote") or lote,
            "grupo_coleta": p.get("grupo_coleta") or lote,
            "cleaned_source_text": text,
            "texto_fonte": text,
            "texto_fonte_v105": text,
            "texto_fonte_v134": p.get("texto_fonte_v134") or text,
            "raw_source_text": p.get("raw_source_text") or text,
            "dossie": p.get("dossie") or text,
            "status_fonte_v105": "ok" if chars >= 550 else "curta_ok" if chars > 0 else p.get("status_fonte_v105") or "pendente",
            "fonte_validada": chars >= 550,
            "fonte_ok": chars >= 550,
            "tem_texto_fonte": chars > 0,
        })
        for k in ("chars", "texto_chars", "texto_fonte_chars", "chars_texto_fonte", "fonte_chars", "tamanho_fonte", "source_chars", "source_text_chars"):
            p[k] = chars
        if image:
            for k in ("imagem_url", "imagem_url_v134", "imagem", "image", "foto_url", "thumb", "thumbnail", "og_image", "preview_image"):
                p[k] = image
            p["imagem_status"] = p["imagem_status_v106"] = p["status_imagem"] = "aprovada"
            p["imagem_pronta"] = p["tem_imagem"] = True
        else:
            p["imagem_status"] = p.get("imagem_status") or "pendente"
            p["imagem_status_v106"] = p.get("imagem_status_v106") or "pendente"
            p["status_imagem"] = p.get("status_imagem") or "pendente"
            p["imagem_pronta"] = p["tem_imagem"] = False
        for k in ("score", "score_total", "score_qualidade", "score_editorial", "seo_score", "qualidade", "nota", "nota_final", "score_visual", "score_visual_v136", "score_circular", "score_fila", "fonte_score", "source_sufficiency_score", "source_sufficiency_score_v105", "percentual", "percentual_fonte", "pct", "pct_fonte", "progresso", "progresso_fonte"):
            p[k] = score
        return p
    except Exception:
        return p


def _score(p: dict) -> tuple:
    text = _texto(p)
    image = _img(p)
    title = str(p.get("titulo_origem") or p.get("titulo") or "").lower()
    s = 5000 if len(text) >= 550 else 1000 if text else 0
    if image:
        s += 1000
    if any(x in title for x in ("melhores gols", "melhores defesas", "gol –", "mls:", "spl:", "charge", "frase do dia")):
        s -= 3000
    if title.startswith("coleta ") or " pauta(s)" in title:
        s -= 8000
    return (s, str(p.get("data_pub_fonte") or p.get("criado_em") or ""))


def _rows(limit: int = 250) -> list[dict]:
    db = _db_path()
    if not db.exists():
        return []
    con = sqlite3.connect(db, timeout=20)
    con.row_factory = sqlite3.Row
    try:
        c = _cols(con)
        where = []
        if "link_origem" in c:
            where.append("(link_origem IS NOT NULL AND TRIM(CAST(link_origem AS TEXT)) <> '')")
        if "status" in c:
            where.append("(status IS NULL OR LOWER(CAST(status AS TEXT)) NOT IN ('publicada','descartada','rejeitada','bloqueada','reprovada'))")
        for col in ("oculto", "oculta", "excluido", "excluida", "descartado", "descartada", "bloqueado", "bloqueada", "reprovado", "reprovada"):
            if col in c:
                where.append(f"({col} IS NULL OR CAST({col} AS TEXT) NOT IN ('1','true','True','sim','SIM'))")
        order = "id" if "id" in c else "criado_em" if "criado_em" in c else "rowid"
        sql = "SELECT * FROM pautas" + ((" WHERE " + " AND ".join(where)) if where else "") + f' ORDER BY "{order}" DESC LIMIT {int(limit)}'
        raw = [dict(r) for r in con.execute(sql).fetchall()]
        lote = f"Coleta Scrapling v136 - {time.strftime('%H:%M')} — {len(raw)} pauta(s)"
        enriched = sorted([_enrich(r, lote) for r in raw if not _bad(r)], key=_score, reverse=True)
        sep = {"uid": "sep_v136_" + str(abs(hash(lote))), "_uid": "sep_v136_" + str(abs(hash(lote))), "_separador_coleta_v123": True, "_subtitulo_separador_v123": "Separador visual. A numeração não interfere nas pautas nem na publicação.", "titulo": lote, "titulo_origem": lote, "status": "_separador", "score": 0, "score_total": 0, "score_qualidade": 0, "coleta_lote_label_v123": lote, "coleta_lote": lote, "grupo_coleta": lote}
        print(f"[V136][FILA_VISUAL] DB fallback pronto: {len(enriched)} pauta(s).", flush=True)
        return [sep] + enriched
    finally:
        con.close()


def _patch(mod) -> None:
    global _ORIG_POPULAR
    try:
        F = getattr(mod, "FilaPautas", None)
        if F is None or getattr(F, "_v136_force_db_ok", False):
            return
        _ORIG_POPULAR = getattr(F, "popular")
        def popular_force(self, itens):
            try:
                n = len(itens or [])
            except Exception:
                n = 0
            force = str(os.getenv("URURAU_FORCAR_FILA_DB_V136", "1")).lower() in {"1", "true", "sim", "yes", "on"}
            if force or n <= 20:
                r = _rows(int(os.getenv("URURAU_FILA_DB_V136_LIMIT", "250") or "250"))
                if r:
                    print(f"[V136][FILA_VISUAL] popular recebeu {n}; exibindo {len(r)} itens do DB.", flush=True)
                    itens = r
            res = _ORIG_POPULAR(self, itens)
            def redraw():
                try:
                    self._canvas.update_idletasks()
                    self._canvas.configure(scrollregion=(0, 0, max(1, self._canvas.winfo_width()), self._total_h()))
                    self._canvas.yview_moveto(0.0)
                    self._redraw_visible()
                except Exception as e:
                    print(f"[V136][FILA_VISUAL][AVISO] redraw falhou: {e}", flush=True)
            try:
                self.after(20, redraw)
                self.after(250, redraw)
                self.after(700, redraw)
            except Exception:
                redraw()
            return res
        F.popular = popular_force
        F._v136_force_db_ok = True
        print("[V136][FILA_VISUAL] patch consolidado instalado em FilaPautas.popular.", flush=True)
    except Exception as e:
        print(f"[V136][FILA_VISUAL][ERRO] patch falhou: {e}", flush=True)


def instalar_fila_visual_fix_v136() -> bool:
    global _INSTALLED, _ORIG_IMPORT
    # fix/auditoria-fila-scrapling-v136: gate oficial.
    # Default = desligado. Para reativar: URURAU_DISABLE_FILA_RUNTIME_PATCHES=0.
    _flag = str(os.getenv("URURAU_DISABLE_FILA_RUNTIME_PATCHES", "1")).strip().lower()
    if _flag in {"1", "true", "sim", "yes", "s", "on"}:
        print("[V136][FILA_VISUAL] patch ignorado por URURAU_DISABLE_FILA_RUNTIME_PATCHES=1.", flush=True)
        return False
    if _INSTALLED:
        return True
    if "ururau.ui.painel" in sys.modules:
        _patch(sys.modules["ururau.ui.painel"])
    _ORIG_IMPORT = builtins.__import__
    def wrapper(name, globals=None, locals=None, fromlist=(), level=0):
        mod = _ORIG_IMPORT(name, globals, locals, fromlist, level)
        if name == "ururau.ui.painel" or name.endswith(".painel"):
            _patch(sys.modules.get("ururau.ui.painel") or mod)
        return mod
    builtins.__import__ = wrapper
    _INSTALLED = True
    print("[V136][FILA_VISUAL] import hook instalado.", flush=True)
    return True

__all__ = ["instalar_fila_visual_fix_v136"]
