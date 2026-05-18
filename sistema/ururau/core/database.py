"""
core/database.py — Persistência SQLite com abstração clara.
Substitui o modelo frágil baseado apenas em JSON local.
Mantém compatibilidade com o histórico JSON existente na migração.

v41+ — sistema de bloqueio permanente por link:
  - Tabela links_bloqueados: registro definitivo de links descartados/publicados
  - Cache em memória (_links_bloqueados_cache): O(1) lookup sem bater no banco
  - Migração automática: backfill de pautas rejeitadas/publicadas existentes
  - Arquivo .ururau_bloqueados.txt: persiste cache entre reinicializações
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

TZ_BR = ZoneInfo("America/Sao_Paulo")
_lock = threading.Lock()

# ── Cache em memória de links bloqueados ──────────────────────────────────────
# Carregado do banco na inicialização. Lookup O(1) sem SQL.
_links_bloqueados_cache: set[str] = set()
_cache_lock = threading.Lock()

def _cache_add(link: str):
    """Adiciona link ao cache em memória de forma thread-safe."""
    if link:
        with _cache_lock:
            _links_bloqueados_cache.add(link.strip())

def _cache_has(link: str) -> bool:
    """Verifica se link está no cache em memória."""
    if not link:
        return False
    with _cache_lock:
        return link.strip() in _links_bloqueados_cache


def _hash_titulo_fonte(titulo: str, fonte: str) -> str:
    """V200_37: normaliza titulo+fonte para gerar pseudo-link bloqueavel.

    Mesma materia entrando por feeds diferentes (Google News, RSS direto,
    Burlesco) tem URLs diferentes mas o mesmo titulo+fonte. Esse hash
    permite bloquear a materia em qualquer feed que tente trazer ela.

    Formato: 'tf::<titulo_normalizado>|<fonte_normalizada>'
    Retorna string vazia se nao tem titulo OU nao tem fonte.
    """
    import unicodedata
    import re as _re
    t = (titulo or "").strip()
    f = (fonte or "").strip()
    if not t or not f:
        return ""
    def _norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        s = s.lower()
        s = _re.sub(r"[^a-z0-9 ]+", " ", s)
        s = _re.sub(r"\s+", " ", s).strip()
        # limita pra evitar variantes longas com sufixo
        return s[:120]
    tn = _norm(t)
    fn = _norm(f)
    if not tn or not fn:
        return ""
    return f"tf::{tn}|{fn}"


class Database:
    """Camada de persistência SQLite thread-safe."""

    def __init__(self, caminho_db: str = "ururau.db"):
        self.caminho = Path(caminho_db)
        self._conn: Optional[sqlite3.Connection] = None
        self._inicializar()

    def _conectar(self) -> sqlite3.Connection:
        self.caminho.parent.mkdir(parents=True, exist_ok=True) if self.caminho.parent != Path('.') else None
        conn = sqlite3.connect(str(self.caminho), check_same_thread=False, timeout=60)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=60000")
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            # v47: não derruba painel se outro processo estiver usando o banco.
            pass
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _inicializar(self):
        with _lock:
            ultimo_erro = None
            conn = None
            for tentativa in range(1, 7):
                try:
                    conn = self._conectar()
                    break
                except sqlite3.OperationalError as e:
                    ultimo_erro = e
                    if "locked" not in str(e).lower() or tentativa == 6:
                        raise
                    time.sleep(min(0.5 * tentativa, 3.0))
            if conn is None:
                raise ultimo_erro or RuntimeError("Falha ao conectar ao banco")
            c = conn.cursor()

            # Tabela principal de pautas
            c.execute("""
            CREATE TABLE IF NOT EXISTS pautas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE NOT NULL,
                titulo_origem TEXT NOT NULL,
                link_origem TEXT NOT NULL,
                fonte_nome TEXT,
                resumo_origem TEXT,
                canal TEXT,
                score_editorial INTEGER DEFAULT 0,
                status TEXT DEFAULT 'captada',
                urgente INTEGER DEFAULT 0,
                captada_em TEXT,
                atualizada_em TEXT,
                dados_json TEXT
            )""")

            # Tabela de matérias geradas
            c.execute("""
            CREATE TABLE IF NOT EXISTS materias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pauta_uid TEXT NOT NULL,
                versao INTEGER DEFAULT 1,
                titulo TEXT,
                titulo_capa TEXT,
                slug TEXT,
                meta_description TEXT,
                subtitulo TEXT,
                legenda TEXT,
                retranca TEXT,
                tags TEXT,
                conteudo TEXT,
                resumo_curto TEXT,
                chamada_social TEXT,
                score_risco INTEGER DEFAULT 0,
                termos_ia TEXT,
                status TEXT DEFAULT 'rascunho',
                gerada_em TEXT,
                dados_json TEXT,
                FOREIGN KEY (pauta_uid) REFERENCES pautas(uid)
            )""")

            # Tabela de imagens
            c.execute("""
            CREATE TABLE IF NOT EXISTS imagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pauta_uid TEXT NOT NULL,
                caminho_final TEXT,
                caminho_original TEXT,
                url_origem TEXT,
                dimensoes_origem TEXT,
                estrategia TEXT,
                credito TEXT,
                score_imagem REAL DEFAULT 0,
                aprovada INTEGER DEFAULT 0,
                registrada_em TEXT,
                dados_json TEXT,
                FOREIGN KEY (pauta_uid) REFERENCES pautas(uid)
            )""")

            # Tabela de publicações
            c.execute("""
            CREATE TABLE IF NOT EXISTS publicacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pauta_uid TEXT NOT NULL,
                canal TEXT,
                titulo_publicado TEXT,
                status TEXT DEFAULT 'rascunho',
                tentativa INTEGER DEFAULT 1,
                publicada_em TEXT,
                erro TEXT,
                dados_json TEXT,
                FOREIGN KEY (pauta_uid) REFERENCES pautas(uid)
            )""")

            # Tabela de auditoria
            c.execute("""
            CREATE TABLE IF NOT EXISTS auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pauta_uid TEXT,
                acao TEXT NOT NULL,
                detalhe TEXT,
                usuario TEXT DEFAULT 'sistema',
                timestamp TEXT,
                sucesso INTEGER DEFAULT 1
            )""")

            # Tabela de histórico legado (compatibilidade)
            c.execute("""
            CREATE TABLE IF NOT EXISTS historico_legado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo_origem TEXT,
                titulo_publicado TEXT,
                canal TEXT,
                status TEXT DEFAULT 'rascunho',
                publicado_em TEXT,
                dados_json TEXT
            )""")

            # ── Tabela de bloqueio permanente por link ────────────────────────
            # Garante que links descartados ou publicados NUNCA voltem à fila,
            # mesmo que não tenham passado pelo fluxo completo de salvar_pauta.
            c.execute("""
            CREATE TABLE IF NOT EXISTS links_bloqueados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT UNIQUE NOT NULL,
                uid TEXT,
                titulo TEXT,
                motivo TEXT DEFAULT 'descarte',
                bloqueado_em TEXT
            )""")
            # Índice para busca rápida por link
            c.execute("""
            CREATE INDEX IF NOT EXISTS idx_links_bloqueados_link
            ON links_bloqueados(link)
            """)

            conn.commit()

            # ── Migração automática ───────────────────────────────────────────
            # Garante que bancos existentes recebam as novas tabelas/índices
            # mesmo que já tenham sido criados antes dessa versão.
            self._migrar(conn)

            # ── Carrega cache de links bloqueados em memória ──────────────────
            self._carregar_cache_bloqueados(conn)

            conn.close()

    def _migrar(self, conn):
        """
        Aplica migrações incrementais no banco existente.
        Seguro rodar múltiplas vezes — usa IF NOT EXISTS.
        """
        # Migração 1: tabela links_bloqueados (v41+)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS links_bloqueados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE NOT NULL,
            uid TEXT,
            titulo TEXT,
            motivo TEXT DEFAULT 'descarte',
            bloqueado_em TEXT
        )""")
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_links_bloqueados_link
        ON links_bloqueados(link)
        """)

        # Migração 2: popula links_bloqueados a partir de pautas já rejeitadas/publicadas
        # (backfill para quem já tem banco com histórico)
        conn.execute("""
        INSERT OR IGNORE INTO links_bloqueados (link, uid, titulo, motivo, bloqueado_em)
        SELECT link_origem, uid, titulo_origem,
               CASE WHEN status='publicada' THEN 'publicada'
                    WHEN status='excluida' THEN 'excluida_pelo_editor'
                    ELSE 'descarte' END,
               atualizada_em
        FROM pautas
        WHERE status IN ('rejeitada', 'bloqueada', 'publicada', 'excluida')
          AND link_origem IS NOT NULL
          AND link_origem != ''
        """)

        # Migração 5: Feed Universal v200+.
        # Guarda descoberta, geracao de candidatos, dedupe e logs de extracao
        # fora do cache temporario. A fila continua entrando pela tabela pautas.
        conn.execute("""
        CREATE TABLE IF NOT EXISTS feed_universal_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT UNIQUE NOT NULL,
            domain TEXT,
            created_at TEXT,
            updated_at TEXT,
            dados_json TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS feed_universal_discovered_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            feed_url TEXT NOT NULL,
            tipo TEXT,
            score INTEGER DEFAULT 0,
            status_http INTEGER DEFAULT 0,
            ok INTEGER DEFAULT 0,
            entries INTEGER DEFAULT 0,
            discovered_at TEXT,
            dados_json TEXT,
            UNIQUE(source_url, feed_url)
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS feed_universal_generated_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_url TEXT UNIQUE NOT NULL,
            source_url TEXT,
            title TEXT,
            method TEXT,
            status TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            dados_json TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS feed_universal_seen_urls (
            canonical_url TEXT PRIMARY KEY,
            title_hash TEXT,
            text_hash TEXT,
            source_url TEXT,
            pauta_uid TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            dados_json TEXT
        )""")
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fu_seen_title_hash
        ON feed_universal_seen_urls(title_hash)
        """)
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fu_seen_text_hash
        ON feed_universal_seen_urls(text_hash)
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS feed_universal_blocked_urls (
            canonical_url TEXT PRIMARY KEY,
            motivo TEXT,
            source_url TEXT,
            blocked_at TEXT,
            dados_json TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS feed_universal_source_health (
            domain TEXT PRIMARY KEY,
            score INTEGER DEFAULT 0,
            status TEXT,
            updated_at TEXT,
            dados_json TEXT
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS feed_universal_extraction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_url TEXT,
            source_url TEXT,
            status TEXT,
            motivo TEXT,
            useful_chars INTEGER DEFAULT 0,
            method TEXT,
            logged_at TEXT,
            dados_json TEXT
        )""")
        conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fu_logs_url
        ON feed_universal_extraction_logs(canonical_url)
        """)

        # Migração 4: adiciona coluna revisao_status na tabela materias (v59+)
        try:
            conn.execute("ALTER TABLE materias ADD COLUMN revisao_status TEXT DEFAULT 'pendente'")
        except Exception:
            pass  # já existe
        try:
            conn.execute("ALTER TABLE materias ADD COLUMN approved_by TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE materias ADD COLUMN approved_at TEXT DEFAULT ''")
        except Exception:
            pass

        # Migração 3: corrige data_pub_fonte com fuso errado (+3h) em pautas captadas
        # antes do fix de fuso (v45). Subtrai 3h de qualquer data_pub_fonte que tenha
        # hora >= 03:00, só uma vez (marcador: migração3_fuso_aplicada na tabela meta).
        conn.execute("""
        CREATE TABLE IF NOT EXISTS _meta (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )""")
        ja_migrou = conn.execute(
            "SELECT valor FROM _meta WHERE chave='migr3_fuso_corrigido'"
        ).fetchone()
        if not ja_migrou:
            try:
                import json as _json
                from datetime import datetime as _dt, timedelta as _td
                rows = conn.execute(
                    "SELECT uid, dados_json FROM pautas WHERE dados_json LIKE '%data_pub_fonte%'"
                ).fetchall()
                corrigidos = 0
                for row in rows:
                    try:
                        d = _json.loads(row["dados_json"] or "{}")
                        dpf = (d.get("data_pub_fonte") or "").strip()
                        if not dpf:
                            continue
                        # Formato esperado: "DD/MM/YYYY HH:MM"
                        # Se hora >= 3, provavelmente está em UTC — subtrai 3h
                        dt_obj = _dt.strptime(dpf, "%d/%m/%Y %H:%M")
                        if dt_obj.hour >= 3:
                            dt_corr = dt_obj - _td(hours=3)
                            d["data_pub_fonte"] = dt_corr.strftime("%d/%m/%Y %H:%M")
                            conn.execute(
                                "UPDATE pautas SET dados_json=? WHERE uid=?",
                                (_json.dumps(d, ensure_ascii=False, default=str), row["uid"])
                            )
                            corrigidos += 1
                    except Exception:
                        pass
                conn.execute(
                    "INSERT OR REPLACE INTO _meta (chave, valor) VALUES ('migr3_fuso_corrigido', ?)",
                    (str(corrigidos),)
                )
                if corrigidos:
                    print(f"[DB] Migração 3: corrigidos {corrigidos} data_pub_fonte (fuso UTC→BRT)")
            except Exception as e:
                print(f"[DB] Aviso migração 3: {e}")

        conn.commit()

    def _carregar_cache_bloqueados(self, conn):
        """Carrega todos os links bloqueados do banco para o cache em memória."""
        global _links_bloqueados_cache
        try:
            rows = conn.execute(
                "SELECT link FROM links_bloqueados"
            ).fetchall()
            with _cache_lock:
                for row in rows:
                    if row[0]:
                        _links_bloqueados_cache.add(row[0].strip())
            print(f"[DB] Cache de bloqueio carregado: {len(_links_bloqueados_cache)} links")
        except Exception as e:
            print(f"[DB] Aviso ao carregar cache de bloqueio: {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _agora(self) -> str:
        return datetime.now(TZ_BR).strftime("%Y-%m-%d %H:%M:%S")

    def _uid_para_pauta(self, link: str, titulo: str) -> str:
        import hashlib
        return hashlib.md5(f"{link}{titulo}".encode()).hexdigest()[:16]

    # ── Pautas ────────────────────────────────────────────────────────────────

    def salvar_pauta(self, pauta: dict) -> str:
        uid = pauta.get("_uid") or self._uid_para_pauta(
            pauta.get("link_origem", ""), pauta.get("titulo_origem", "")
        )
        with _lock:
            conn = self._conectar()
            try:
                # ── Proteção de exclusão: nunca sobrescreve pautas excluídas ──
                # Se a pauta já existe com status='excluida', ignora o INSERT.
                existente = conn.execute(
                    "SELECT status FROM pautas WHERE uid=? LIMIT 1", (uid,)
                ).fetchone()
                if existente and existente["status"] == "excluida":
                    conn.close()
                    return uid   # pauta excluída — não reativa nunca

                conn.execute("""
                INSERT OR REPLACE INTO pautas
                    (uid, titulo_origem, link_origem, fonte_nome, resumo_origem,
                     canal, score_editorial, status, urgente, captada_em, atualizada_em, dados_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    uid,
                    pauta.get("titulo_origem", ""),
                    pauta.get("link_origem", ""),
                    pauta.get("fonte_nome", ""),
                    pauta.get("resumo_origem", "")[:500],
                    pauta.get("canal_forcado", ""),
                    pauta.get("score_editorial", 0),
                    pauta.get("status", "captada"),
                    1 if pauta.get("urgente") else 0,
                    pauta.get("captada_em", self._agora()),
                    self._agora(),
                    json.dumps(pauta, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()
        return uid

    def salvar_pautas_batch(self, pautas: list[dict]) -> dict:
        """V200_12: salva varias pautas em UMA transacao (1 commit so).

        Para 200+ pautas isso e ~10-50x mais rapido que chamar
        salvar_pauta em loop (que abria/comitava/fechava por pauta).
        Retorna {"inseridas": N, "erros": M, "uids": [...]}.
        """
        if not pautas:
            return {"inseridas": 0, "erros": 0, "uids": []}
        import time as _t
        inicio = _t.time()
        uids = []
        erros = 0
        with _lock:
            conn = self._conectar()
            try:
                # Em uma transacao unica, sem auto-commit
                conn.execute("BEGIN IMMEDIATE")
                for pauta in pautas:
                    try:
                        uid = pauta.get("_uid") or self._uid_para_pauta(
                            pauta.get("link_origem", ""), pauta.get("titulo_origem", "")
                        )
                        existente = conn.execute(
                            "SELECT status FROM pautas WHERE uid=? LIMIT 1", (uid,)
                        ).fetchone()
                        if existente and existente["status"] == "excluida":
                            uids.append(uid)
                            continue
                        conn.execute("""
                        INSERT OR REPLACE INTO pautas
                            (uid, titulo_origem, link_origem, fonte_nome, resumo_origem,
                             canal, score_editorial, status, urgente, captada_em, atualizada_em, dados_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            uid,
                            pauta.get("titulo_origem", ""),
                            pauta.get("link_origem", ""),
                            pauta.get("fonte_nome", ""),
                            (pauta.get("resumo_origem", "") or "")[:500],
                            pauta.get("canal_forcado", ""),
                            pauta.get("score_editorial", 0),
                            pauta.get("status", "captada"),
                            1 if pauta.get("urgente") else 0,
                            pauta.get("captada_em", self._agora()),
                            self._agora(),
                            json.dumps(pauta, ensure_ascii=False, default=str),
                        ))
                        uids.append(uid)
                    except Exception as e:
                        erros += 1
                        print(f"[DB][batch] falha pauta: {e}")
                conn.commit()
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                print(f"[DB][batch] ROLLBACK: {e}")
                erros += len(pautas) - len(uids)
                uids = []
            finally:
                conn.close()
        dur = _t.time() - inicio
        print(f"[DB][batch] {len(uids)}/{len(pautas)} pautas em {dur:.1f}s ({erros} erros)")
        return {"inseridas": len(uids), "erros": erros, "uids": uids}


    def buscar_pauta(self, uid: str) -> Optional[dict]:
        with _lock:
            conn = self._conectar()
            try:
                row = conn.execute("SELECT * FROM pautas WHERE uid=?", (uid,)).fetchone()
                if row:
                    return dict(row)
                return None
            finally:
                conn.close()

    def atualizar_status_pauta(self, uid: str, status: str):
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("UPDATE pautas SET status=?, atualizada_em=? WHERE uid=?",
                             (status, self._agora(), uid))
                conn.commit()
            finally:
                conn.close()

    def atualizar_pauta(self, uid: str, campos: dict) -> bool:
        """Atualiza campos permitidos da pauta preservando o restante."""
        if not uid or not isinstance(campos, dict) or not campos:
            return False
        permitidos = {
            "titulo_origem",
            "link_origem",
            "fonte_nome",
            "resumo_origem",
            "canal",
            "score_editorial",
            "status",
            "urgente",
            "captada_em",
            "atualizada_em",
            "dados_json",
        }
        sets = []
        valores = []
        for k, v in campos.items():
            if k in permitidos:
                sets.append(f"{k}=?")
                valores.append(v)
        if not sets:
            return False
        if "atualizada_em" not in campos:
            sets.append("atualizada_em=?")
            valores.append(self._agora())
        valores.append(uid)
        with _lock:
            conn = self._conectar()
            try:
                conn.execute(
                    "UPDATE pautas SET " + ", ".join(sets) + " WHERE uid=?",
                    tuple(valores),
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def excluir_pauta(self, uid: str, link: str = "", titulo: str = ""):
        """
        Marca a pauta como 'excluida' e bloqueia o link definitivamente.
        A pauta permanece no banco (auditável), mas fica oculta na fila padrão.
        O link entra na tabela links_bloqueados para não reaparecer em coletas futuras.
        """
        self.atualizar_status_pauta(uid, "excluida")
        if link:
            self.bloquear_link(link, uid, titulo, motivo="excluida_pelo_editor")
        self.log_auditoria(uid, "exclusao", "Excluída manualmente pelo editor", sucesso=True)

    def excluir_pautas_em_lote(self, uids_e_dados: list[tuple[str, str, str]]):
        """
        Exclui várias pautas de uma vez.
        uids_e_dados: lista de (uid, link, titulo)
        """
        for uid, link, titulo in uids_e_dados:
            self.excluir_pauta(uid, link, titulo)

    def reativar_pauta(self, uid: str, link: str = ""):
        """
        Reativa uma pauta excluída: volta para 'captada' e remove o link do bloqueio.
        Útil para recuperar pautas excluídas por engano.
        """
        self.atualizar_status_pauta(uid, "captada")
        if link:
            # Remove da tabela de links bloqueados
            with _lock:
                conn = self._conectar()
                try:
                    conn.execute(
                        "DELETE FROM links_bloqueados WHERE link=? AND motivo='excluida_pelo_editor'",
                        (link,)
                    )
                    conn.commit()
                    # Atualiza cache
                    with _cache_lock:
                        _links_bloqueados_cache.discard(link.strip())
                finally:
                    conn.close()
        self.log_auditoria(uid, "reativacao", "Pauta reativada pelo editor", sucesso=True)

    def link_ja_publicado(self, link: str, janela_horas: int = 48) -> bool:
        from datetime import timedelta
        cutoff = (datetime.now(TZ_BR) - timedelta(hours=janela_horas)).strftime("%Y-%m-%d %H:%M:%S")
        with _lock:
            conn = self._conectar()
            try:
                r = conn.execute(
                    "SELECT 1 FROM pautas WHERE link_origem=? AND status='publicada' AND atualizada_em>=?",
                    (link, cutoff)
                ).fetchone()
                return r is not None
            finally:
                conn.close()

    # ── Checagem anti-repetição ───────────────────────────────────────────────

    def pauta_ja_captada(self, link: str, uid: str = "") -> Optional[dict]:
        """
        Verifica se uma pauta com o mesmo link (ou uid) já foi captada.
        Retorna o registro existente ou None.

        Uso: antes de adicionar nova pauta à fila.
        """
        with _lock:
            conn = self._conectar()
            try:
                # Tenta por link primeiro (mais confiável)
                row = conn.execute(
                    "SELECT uid, status, atualizada_em FROM pautas WHERE link_origem=? LIMIT 1",
                    (link,)
                ).fetchone()
                if row:
                    return dict(row)
                # Fallback por uid (hash md5 do link+titulo)
                if uid:
                    row = conn.execute(
                        "SELECT uid, status, atualizada_em FROM pautas WHERE uid=? LIMIT 1",
                        (uid,)
                    ).fetchone()
                    if row:
                        return dict(row)
                return None
            finally:
                conn.close()

    def pauta_foi_descartada(self, link: str, uid: str = "") -> bool:
        """
        Verifica se a pauta foi explicitamente rejeitada ou descartada.

        Checagens (em ordem):
          1. Tabela links_bloqueados — barreira definitiva por link
          2. Tabela pautas — status rejeitada/bloqueada
        """
        # 1. Barreira definitiva: link na lista de bloqueio
        if link and self.link_esta_bloqueado(link):
            return True

        # 2. Status na tabela de pautas
        with _lock:
            conn = self._conectar()
            try:
                row = conn.execute(
                    "SELECT status FROM pautas WHERE link_origem=? LIMIT 1",
                    (link,)
                ).fetchone()
                if not row and uid:
                    row = conn.execute(
                        "SELECT status FROM pautas WHERE uid=? LIMIT 1",
                        (uid,)
                    ).fetchone()
                if row:
                    # Lista expandida (spec_claudio_reverter_bloqueio §6) para
                    # cobrir TODAS as variantes que indicam pauta sem fila ativa.
                    return str(row["status"] or "").lower() in (
                        "rejeitada", "rejeitado",
                        "bloqueada", "bloqueado",
                        "excluida", "excluido",
                        "descartada", "descartado",
                        "reprovada", "reprovado",
                    )
                return False
            finally:
                conn.close()

    def pauta_ja_publicada(self, link: str, uid: str = "") -> bool:
        """
        Verifica se a pauta já foi publicada no Ururau.
        Checagem sem janela temporal — cobre todo o histórico.

        Checagens:
          1. Tabela links_bloqueados com motivo='publicada'
          2. Tabela pautas — status='publicada'
          3. Tabela publicacoes — registro de saída confirmado
        """
        # 1. Barreira por link (motivo publicada registrado por registrar_publicacao)
        if link and self.link_esta_bloqueado(link):
            return True

        with _lock:
            conn = self._conectar()
            try:
                # 2. Checa na tabela pautas (status publicada)
                row = conn.execute(
                    "SELECT 1 FROM pautas WHERE link_origem=? AND status='publicada' LIMIT 1",
                    (link,)
                ).fetchone()
                if row:
                    return True
                if uid:
                    row = conn.execute(
                        "SELECT 1 FROM pautas WHERE uid=? AND status='publicada' LIMIT 1",
                        (uid,)
                    ).fetchone()
                    if row:
                        return True
                # 3. Checa na tabela publicacoes (registro de saída)
                row = conn.execute(
                    "SELECT 1 FROM publicacoes WHERE dados_json LIKE ? AND status='publicada' LIMIT 1",
                    (f'%"{link}"%',)
                ).fetchone()
                return row is not None
            finally:
                conn.close()

    def classificar_pauta(self, link: str, uid: str = "") -> str:
        """
        Retorna o status atual da pauta ou 'nova' se não existir no banco.

        Possíveis retornos:
          'nova'       — nunca foi captada
          'captada'    — está na fila aguardando processamento
          'em_redacao' — está sendo processada agora
          'pronta'     — matéria gerada, aguardando publicação
          'publicada'  — já foi publicada no Ururau
          'rejeitada'  — foi descartada por critérios editoriais
          'bloqueada'  — bloqueada por risco jurídico

        Uso: ponto único de consulta para decisão de fluxo.
        """
        with _lock:
            conn = self._conectar()
            try:
                row = conn.execute(
                    "SELECT status FROM pautas WHERE link_origem=? LIMIT 1",
                    (link,)
                ).fetchone()
                if not row and uid:
                    row = conn.execute(
                        "SELECT status FROM pautas WHERE uid=? LIMIT 1",
                        (uid,)
                    ).fetchone()
                return row["status"] if row else "nova"
            finally:
                conn.close()

    def titulo_similar_ja_publicado(
        self,
        titulo: str,
        limiar: float = 0.70,
        janela_horas: int = 72,
    ) -> Optional[str]:
        """
        Verifica se um título similar ao informado já foi publicado nas
        últimas `janela_horas` horas.

        Retorna o título publicado similar, ou None se não encontrar.

        Uso: evita publicar duas matérias sobre o mesmo fato com títulos
        diferentes mas conteúdo idêntico.
        """
        from datetime import timedelta
        import re

        cutoff = (datetime.now(TZ_BR) - timedelta(hours=janela_horas)).strftime("%Y-%m-%d %H:%M:%S")

        def _normalizar(t: str) -> set:
            stopwords = {
                "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
                "e", "ou", "a", "o", "as", "os", "um", "uma", "que", "se",
                "com", "por", "para", "ao", "é", "foi", "ser", "ter",
            }
            palavras = set(re.sub(r"[^\w\s]", "", t.lower()).split())
            return palavras - stopwords

        palavras_alvo = _normalizar(titulo)
        if not palavras_alvo:
            return None

        with _lock:
            conn = self._conectar()
            try:
                rows = conn.execute(
                    """SELECT titulo_origem FROM pautas
                       WHERE status='publicada' AND atualizada_em>=?
                       ORDER BY atualizada_em DESC LIMIT 200""",
                    (cutoff,)
                ).fetchall()
            finally:
                conn.close()

        for row in rows:
            palavras_pub = _normalizar(row["titulo_origem"] or "")
            if not palavras_pub:
                continue
            intersecao = palavras_alvo & palavras_pub
            uniao = palavras_alvo | palavras_pub
            if uniao and len(intersecao) / len(uniao) >= limiar:
                return row["titulo_origem"]

        return None

    def listar_publicadas_recentes(self, horas: int = 48) -> list[dict]:
        """Retorna pautas com status publicada das últimas N horas."""
        from datetime import timedelta
        corte = (datetime.now(TZ_BR) - timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            with _lock:
                conn = self._conectar()
                try:
                    rows = conn.execute(
                        """SELECT titulo_origem, link_origem, canal, atualizada_em
                           FROM pautas
                           WHERE status = 'publicada'
                           AND atualizada_em >= ?
                           ORDER BY atualizada_em DESC""",
                        (corte,)
                    ).fetchall()
                finally:
                    conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[DB] listar_publicadas_recentes: {e}")
            return []

    def bloquear_link(self, link: str, uid: str = "", titulo: str = "",
                      motivo: str = "descarte"):
        """
        Registra um link na lista de bloqueio permanente.

        Dupla persistência:
          1. Cache em memória → lookup O(1) sem SQL em toda coleta futura
          2. Tabela links_bloqueados → persiste entre reinicializações

        Chamado por marcar_descartada() e registrar_publicacao().
        """
        if not link or link.strip() == "":
            return
        link = link.strip()
        # Cache em memória imediato
        _cache_add(link)
        # Persistência no banco
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT OR IGNORE INTO links_bloqueados
                    (link, uid, titulo, motivo, bloqueado_em)
                VALUES (?,?,?,?,?)
                """, (link, uid, titulo[:300], motivo, self._agora()))
                conn.commit()
            finally:
                conn.close()

    def link_esta_bloqueado(self, link: str) -> bool:
        """
        Verifica se um link está bloqueado permanentemente.

        Primeiro consulta o cache em memória (O(1)), depois o banco se necessário.
        """
        if not link:
            return False
        # Cache em memória — resposta instantânea sem SQL
        if _cache_has(link):
            return True
        # Fallback: consulta o banco (para links adicionados por outras instâncias)
        with _lock:
            conn = self._conectar()
            try:
                r = conn.execute(
                    "SELECT 1 FROM links_bloqueados WHERE link=? LIMIT 1",
                    (link.strip(),)
                ).fetchone()
                if r:
                    _cache_add(link)  # adiciona ao cache para próximas consultas
                return r is not None
            except Exception:
                return False
            finally:
                conn.close()

    def motivo_link_bloqueado(self, link: str) -> str:
        """Retorna o motivo salvo para um link bloqueado, quando existir."""
        if not link:
            return ""
        with _lock:
            conn = self._conectar()
            try:
                r = conn.execute(
                    "SELECT motivo FROM links_bloqueados WHERE link=? LIMIT 1",
                    (link.strip(),)
                ).fetchone()
                return (r["motivo"] if r and "motivo" in r.keys() else "") or ""
            except Exception:
                return ""
            finally:
                conn.close()

    # ── Feed Universal v200+ ─────────────────────────────────────────────────

    def _fu_hash(self, valor: str) -> str:
        import hashlib
        raw = " ".join(str(valor or "").lower().split())
        return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16] if raw else ""

    def feed_universal_registrar_source(self, source_url: str, dados: dict | None = None):
        """Registra a URL de origem analisada pelo Feed Universal."""
        if not source_url:
            return
        from urllib.parse import urlparse

        source_url = source_url.strip()
        domain = urlparse(source_url).netloc.lower().removeprefix("www.")
        agora = self._agora()
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO feed_universal_sources
                    (source_url, domain, created_at, updated_at, dados_json)
                VALUES (?,?,?,?,?)
                ON CONFLICT(source_url) DO UPDATE SET
                    domain=excluded.domain,
                    updated_at=excluded.updated_at,
                    dados_json=excluded.dados_json
                """, (
                    source_url,
                    domain,
                    agora,
                    agora,
                    json.dumps(dados or {}, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    def feed_universal_registrar_discovered_feed(self, source_url: str, feed: dict):
        """Persiste feed RSS/Atom/JSON descoberto para diagnostico posterior."""
        feed_url = str((feed or {}).get("url") or "").strip()
        if not feed_url:
            return
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO feed_universal_discovered_feeds
                    (source_url, feed_url, tipo, score, status_http, ok, entries, discovered_at, dados_json)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_url, feed_url) DO UPDATE SET
                    tipo=excluded.tipo,
                    score=excluded.score,
                    status_http=excluded.status_http,
                    ok=excluded.ok,
                    entries=excluded.entries,
                    discovered_at=excluded.discovered_at,
                    dados_json=excluded.dados_json
                """, (
                    source_url,
                    feed_url,
                    str(feed.get("tipo") or feed.get("type") or ""),
                    int(feed.get("score") or 0),
                    int(feed.get("status_http") or 0),
                    1 if feed.get("ok") else 0,
                    int(feed.get("entries") or 0),
                    self._agora(),
                    json.dumps(feed, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    def feed_universal_registrar_generated_item(self, source_url: str, item: dict, status: str = "detectado"):
        """Persiste candidato detectado antes/depois da hidratacao."""
        canonical_url = str((item or {}).get("url") or item.get("url_final") or "").strip()
        if not canonical_url:
            return
        agora = self._agora()
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO feed_universal_generated_items
                    (canonical_url, source_url, title, method, status, first_seen_at, last_seen_at, dados_json)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                    source_url=excluded.source_url,
                    title=excluded.title,
                    method=excluded.method,
                    status=excluded.status,
                    last_seen_at=excluded.last_seen_at,
                    dados_json=excluded.dados_json
                """, (
                    canonical_url,
                    source_url,
                    str(item.get("titulo") or item.get("titulo_origem") or "")[:300],
                    str(item.get("metodo") or item.get("extraction_method") or ""),
                    status,
                    agora,
                    agora,
                    json.dumps(item, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    def feed_universal_match_seen(self, link: str = "", titulo: str = "", texto: str = "") -> Optional[dict]:
        """Busca duplicidade por URL canonica, hash de titulo ou hash de texto."""
        canonical = str(link or "").strip()
        title_hash = self._fu_hash(titulo)
        text_hash = self._fu_hash(texto[:2000] if texto else "")
        with _lock:
            conn = self._conectar()
            try:
                if canonical:
                    row = conn.execute(
                        "SELECT * FROM feed_universal_seen_urls WHERE canonical_url=? LIMIT 1",
                        (canonical,),
                    ).fetchone()
                    if row:
                        return dict(row)
                if title_hash:
                    row = conn.execute(
                        "SELECT * FROM feed_universal_seen_urls WHERE title_hash=? LIMIT 1",
                        (title_hash,),
                    ).fetchone()
                    if row:
                        return dict(row)
                if text_hash:
                    row = conn.execute(
                        "SELECT * FROM feed_universal_seen_urls WHERE text_hash=? LIMIT 1",
                        (text_hash,),
                    ).fetchone()
                    if row:
                        return dict(row)
                return None
            finally:
                conn.close()

    def feed_universal_url_seen(self, link: str) -> bool:
        return self.feed_universal_match_seen(link=link) is not None

    def feed_universal_mark_seen(
        self,
        link: str,
        *,
        titulo: str = "",
        texto: str = "",
        source_url: str = "",
        pauta_uid: str = "",
        dados: dict | None = None,
    ):
        """Marca URL como vista fora do cache temporario."""
        canonical = str(link or "").strip()
        if not canonical:
            return
        agora = self._agora()
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO feed_universal_seen_urls
                    (canonical_url, title_hash, text_hash, source_url, pauta_uid,
                     first_seen_at, last_seen_at, dados_json)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                    title_hash=excluded.title_hash,
                    text_hash=excluded.text_hash,
                    source_url=excluded.source_url,
                    pauta_uid=excluded.pauta_uid,
                    last_seen_at=excluded.last_seen_at,
                    dados_json=excluded.dados_json
                """, (
                    canonical,
                    self._fu_hash(titulo),
                    self._fu_hash(texto[:2000] if texto else ""),
                    source_url,
                    pauta_uid,
                    agora,
                    agora,
                    json.dumps(dados or {}, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    def feed_universal_block_url(
        self,
        link: str,
        motivo: str,
        *,
        source_url: str = "",
        dados: dict | None = None,
    ):
        """Registra bloqueio tecnico/editorial especifico do Feed Universal."""
        canonical = str(link or "").strip()
        if not canonical:
            return
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO feed_universal_blocked_urls
                    (canonical_url, motivo, source_url, blocked_at, dados_json)
                VALUES (?,?,?,?,?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                    motivo=excluded.motivo,
                    source_url=excluded.source_url,
                    blocked_at=excluded.blocked_at,
                    dados_json=excluded.dados_json
                """, (
                    canonical,
                    str(motivo or "")[:300],
                    source_url,
                    self._agora(),
                    json.dumps(dados or {}, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    def feed_universal_log_extraction(
        self,
        link: str,
        *,
        source_url: str = "",
        status: str = "",
        motivo: str = "",
        useful_chars: int = 0,
        method: str = "",
        dados: dict | None = None,
    ):
        """Auditoria leve da extracao/hidratacao."""
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO feed_universal_extraction_logs
                    (canonical_url, source_url, status, motivo, useful_chars, method, logged_at, dados_json)
                VALUES (?,?,?,?,?,?,?,?)
                """, (
                    str(link or "").strip(),
                    source_url,
                    str(status or ""),
                    str(motivo or "")[:300],
                    int(useful_chars or 0),
                    str(method or ""),
                    self._agora(),
                    json.dumps(dados or {}, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    def feed_universal_update_source_health(self, domain: str, summary: dict):
        if not domain:
            return
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO feed_universal_source_health
                    (domain, score, status, updated_at, dados_json)
                VALUES (?,?,?,?,?)
                ON CONFLICT(domain) DO UPDATE SET
                    score=excluded.score,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    dados_json=excluded.dados_json
                """, (
                    domain.lower().removeprefix("www."),
                    int(summary.get("score") or 0),
                    str(summary.get("status") or ""),
                    self._agora(),
                    json.dumps(summary or {}, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    def feed_universal_source_health_summary(self, limite: int = 100) -> list[dict]:
        with _lock:
            conn = self._conectar()
            try:
                rows = conn.execute(
                    """SELECT domain, score, status, updated_at, dados_json
                       FROM feed_universal_source_health
                       ORDER BY updated_at DESC LIMIT ?""",
                    (int(limite),),
                ).fetchall()
                out = []
                for row in rows:
                    d = dict(row)
                    try:
                        extra = json.loads(d.get("dados_json") or "{}")
                        if isinstance(extra, dict):
                            d.update(extra)
                    except Exception:
                        pass
                    out.append(d)
                return out
            finally:
                conn.close()

    def marcar_descartada(self, uid: str, motivo: str = "", pauta: dict = None):
        """
        Marca uma pauta como rejeitada de forma PERMANENTE.

        V200_37: bloqueia AGORA todos os links variantes que possam trazer a
        mesma materia de volta (link_origem, link_origem_resolvido, url_final,
        canonical_url) + um hash de titulo+fonte para casos onde a mesma
        noticia entra por feeds diferentes (Google News vs RSS direto).

        Dupla garantia:
          1. Atualiza status='rejeitada' na tabela pautas (se existir)
          2. Garante upsert na tabela pautas (INSERT OR REPLACE) se pauta dict fornecido
          3. Insere todos os links variantes na tabela links_bloqueados
          4. Insere hash 'tf::<titulo_normalizado>|<fonte>' como pseudo-link
             (compartilha tabela/cache com URLs reais).
        """
        # 1. Tenta atualizar status na tabela pautas (pode não existir ainda)
        self.atualizar_status_pauta(uid, "rejeitada")

        # 2. Se temos o dict completo, garante persistência mesmo que nunca foi salvo
        if pauta:
            pauta_copia = dict(pauta)
            pauta_copia["status"] = "rejeitada"
            pauta_copia["_uid"]   = uid
            try:
                self.salvar_pauta(pauta_copia)
            except Exception:
                pass

        # 3. V200_37: bloqueia TODOS os links variantes da pauta
        titulo = (pauta or {}).get("titulo_origem", "") if pauta else ""
        fonte = ""
        if pauta:
            fonte = str(pauta.get("fonte_nome") or pauta.get("fonte") or "")
        motivo_final = motivo or "descarte"
        links_para_bloquear: list[str] = []
        if pauta:
            for k in (
                "link_origem", "link_origem_resolvido", "url_final",
                "canonical_url", "link_origem_original", "link", "url",
                "fonte_url", "origem_url",
            ):
                v = pauta.get(k)
                if isinstance(v, str) and v.strip().startswith(("http://", "https://")):
                    raw = v.strip()
                    if raw not in links_para_bloquear:
                        links_para_bloquear.append(raw)
                    # tambem bloqueia versao normalizada (sem query/fragmento)
                    try:
                        from urllib.parse import urlsplit, urlunsplit
                        s = urlsplit(raw)
                        norm = urlunsplit((s.scheme, s.netloc, s.path, "", ""))
                        if norm and norm != raw and norm not in links_para_bloquear:
                            links_para_bloquear.append(norm)
                    except Exception:
                        pass
        for lnk in links_para_bloquear:
            try:
                self.bloquear_link(lnk, uid, titulo, motivo=motivo_final)
            except Exception:
                pass

        # 4. V200_37: hash titulo+fonte como pseudo-link bloqueado
        try:
            tf_hash = _hash_titulo_fonte(titulo, fonte)
            if tf_hash:
                self.bloquear_link(tf_hash, uid, titulo,
                                   motivo=f"{motivo_final}:titulo_fonte")
        except Exception:
            pass

        if motivo:
            self.log_auditoria(uid, "descarte", motivo, sucesso=False)

    # ── Matérias ──────────────────────────────────────────────────────────────

    def salvar_materia(self, pauta_uid: str, materia: dict) -> int:
        versao = self._proxima_versao_materia(pauta_uid)
        with _lock:
            conn = self._conectar()
            try:
                c = conn.execute("""
                INSERT INTO materias
                    (pauta_uid, versao, titulo, titulo_capa, slug, meta_description,
                     subtitulo, legenda, retranca, tags, conteudo, resumo_curto,
                     chamada_social, score_risco, termos_ia, status, gerada_em, dados_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    pauta_uid, versao,
                    materia.get("titulo", ""),
                    materia.get("titulo_capa", ""),
                    materia.get("slug", ""),
                    materia.get("meta_description", ""),
                    materia.get("subtitulo", ""),
                    materia.get("legenda", ""),
                    materia.get("retranca", ""),
                    materia.get("tags", ""),
                    materia.get("conteudo", ""),
                    materia.get("resumo_curto", ""),
                    materia.get("chamada_social", ""),
                    materia.get("score_risco", 0),
                    json.dumps(materia.get("termos_ia_detectados", []), ensure_ascii=False),
                    materia.get("status", "rascunho"),
                    self._agora(),
                    json.dumps(materia, ensure_ascii=False, default=str),
                ))
                conn.commit()
                return c.lastrowid
            finally:
                conn.close()

    def _proxima_versao_materia(self, pauta_uid: str) -> int:
        with _lock:
            conn = self._conectar()
            try:
                r = conn.execute(
                    "SELECT MAX(versao) FROM materias WHERE pauta_uid=?", (pauta_uid,)
                ).fetchone()
                return (r[0] or 0) + 1
            finally:
                conn.close()

    # ── Imagens ───────────────────────────────────────────────────────────────

    def salvar_imagem(self, pauta_uid: str, img: dict):
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT OR REPLACE INTO imagens
                    (pauta_uid, caminho_final, caminho_original, url_origem,
                     dimensoes_origem, estrategia, credito, score_imagem, aprovada, registrada_em, dados_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    pauta_uid,
                    img.get("caminho_imagem", ""),
                    img.get("caminho_original", ""),
                    img.get("url_imagem", ""),
                    img.get("dimensoes_origem", ""),
                    img.get("estrategia_imagem", ""),
                    img.get("credito_foto", "Reprodução"),
                    img.get("score_imagem", 0),
                    1,
                    self._agora(),
                    json.dumps(img, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    # ── Publicações ───────────────────────────────────────────────────────────

    def registrar_publicacao(self, pauta_uid: str, canal: str,
                              titulo: str, sucesso: bool, erro: str = "",
                              link_origem: str = ""):
        """
        Registra uma publicação e, se bem-sucedida, bloqueia o link permanentemente
        para que não seja recoletado.
        """
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO publicacoes
                    (pauta_uid, canal, titulo_publicado, status, publicada_em, erro, dados_json)
                VALUES (?,?,?,?,?,?,?)
                """, (
                    pauta_uid, canal, titulo,
                    "publicada" if sucesso else "erro",
                    self._agora(), erro, "",
                ))
                conn.commit()
            finally:
                conn.close()

        # Bloqueia link permanentemente se publicação foi bem-sucedida
        if sucesso and link_origem:
            self.bloquear_link(link_origem, pauta_uid, titulo, motivo="publicada")

    # ── Auditoria ─────────────────────────────────────────────────────────────

    def log_auditoria(self, pauta_uid: str, acao: str,
                       detalhe: str = "", sucesso: bool = True, usuario: str = "sistema"):
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO auditoria (pauta_uid, acao, detalhe, usuario, timestamp, sucesso)
                VALUES (?,?,?,?,?,?)
                """, (pauta_uid, acao, detalhe[:500], usuario, self._agora(), 1 if sucesso else 0))
                conn.commit()
            finally:
                conn.close()

    # ── Histórico (compatibilidade JSON ↔ SQLite) ─────────────────────────────

    def carregar_historico(self) -> list[dict]:
        """Carrega histórico do SQLite + JSON legado, unificados."""
        historico = []
        # SQLite (nova persistência)
        with _lock:
            conn = self._conectar()
            try:
                rows = conn.execute(
                    "SELECT dados_json FROM publicacoes ORDER BY publicada_em DESC LIMIT 200"
                ).fetchall()
                for row in rows:
                    try:
                        historico.append(json.loads(row[0] or "{}"))
                    except Exception:
                        pass
            finally:
                conn.close()
        return historico

    def salvar_historico_legado(self, item: dict):
        """Salva item no histórico legado (compatibilidade com JSON antigo)."""
        with _lock:
            conn = self._conectar()
            try:
                conn.execute("""
                INSERT INTO historico_legado
                    (titulo_origem, titulo_publicado, canal, status, publicado_em, dados_json)
                VALUES (?,?,?,?,?,?)
                """, (
                    item.get("titulo_origem", ""),
                    item.get("titulo_publicado", ""),
                    item.get("canal", ""),
                    item.get("status", "rascunho"),
                    item.get("publicado_em", self._agora()),
                    json.dumps(item, ensure_ascii=False, default=str),
                ))
                conn.commit()
            finally:
                conn.close()

    def contagem_publicacoes_canal_hoje(self, canal: str) -> int:
        hoje = datetime.now(TZ_BR).strftime("%Y-%m-%d")
        with _lock:
            conn = self._conectar()
            try:
                r = conn.execute(
                    "SELECT COUNT(*) FROM publicacoes WHERE canal=? AND publicada_em LIKE ? AND status='publicada'",
                    (canal, f"{hoje}%")
                ).fetchone()
                return r[0] if r else 0
            finally:
                conn.close()

    def estatisticas(self) -> dict:
        with _lock:
            conn = self._conectar()
            try:
                total_pautas     = conn.execute("SELECT COUNT(*) FROM pautas").fetchone()[0]
                total_publicadas = conn.execute("SELECT COUNT(*) FROM publicacoes WHERE status='publicada'").fetchone()[0]
                total_materias   = conn.execute("SELECT COUNT(*) FROM materias").fetchone()[0]
                return {
                    "total_pautas": total_pautas,
                    "total_publicadas": total_publicadas,
                    "total_materias": total_materias,
                }
            finally:
                conn.close()

    # ── Fila ativa / contadores oficiais ─────────────────────────────────────
    #
    # Adicionados em fix/auditoria-fila-scrapling-v136 para consolidar o que
    # antes vivia em patches concorrentes (V136 FILA_FORCE, V137 FILA_REAL,
    # V138 FILA_DB). Fonte única da verdade para fila e contadores superiores.

    # status que NAO devem aparecer na fila ativa
    _STATUS_FORA_DA_FILA = (
        "publicada", "publicado", "descartada", "descartado",
        "rejeitada", "rejeitado", "bloqueada", "bloqueado",
        "reprovada", "reprovado", "excluida", "excluido",
    )

    def query_fila_ativa(self, *, incluir_baixo_score: bool = True,
                         limite: int = 500) -> list[dict]:
        """Query oficial da fila ativa (substitui patches de runtime).

        Regras (spec_autorizacao §5 Fase B):

        * Exclui publicadas/descartadas/bloqueadas/reprovadas/excluidas.
        * Nao cria separador falso com horario atual.
        * Nao carrega lote generico de 160 registros como solucao visual.
        * Ordena: pautas validas primeiro (por captacao desc), depois
          baixo score, depois itens que exigem Aprovar/Reprovar.
        * Cada dict retornado ja tem o ``dados_json`` decodificado e
          mesclado (chaves do JSON sobrescrevem colunas conflitantes - assim
          o alias canonico ``cleaned_source_text`` chega ao chamador).

        Nao chama nenhum patch de runtime e nao depende de polling agressivo.
        Resultado deterministico para a mesma snapshot do banco.
        """
        placeholders = ",".join("?" * len(self._STATUS_FORA_DA_FILA))
        rows: list[dict] = []
        with _lock:
            conn = self._conectar()
            try:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(pautas)").fetchall()}
                # SELECT * e intencional: o writer/hidratador v136 pode popular
                # colunas fisicas como cleaned_source_text, imagem_url e
                # data_pub_fonte mesmo quando dados_json ainda esta vazio.
                # A fila canonica precisa enxergar esses campos.
                order_cols = [
                    c for c in ("captada_em", "atualizada_em", "criado_em", "data_pub_fonte", "data_fonte")
                    if c in cols
                ]
                if order_cols:
                    order_expr = "datetime(COALESCE(" + ", ".join(
                        f"NULLIF({c}, '')" for c in order_cols
                    ) + ")) DESC"
                else:
                    order_expr = "rowid DESC"
                sql = (
                    "SELECT * "
                    "FROM pautas "
                    f"WHERE (status IS NULL OR LOWER(status) NOT IN ({placeholders})) "
                    "  AND link_origem IS NOT NULL AND TRIM(link_origem) <> '' "
                    f"ORDER BY {order_expr} "
                    "LIMIT ?"
                )
                cur = conn.execute(
                    sql,
                    tuple(self._STATUS_FORA_DA_FILA) + (int(limite),),
                )
                for r in cur.fetchall():
                    d = dict(r)
                    try:
                        extra = json.loads(d.get("dados_json") or "{}")
                        if isinstance(extra, dict):
                            # JSON vence em chaves repetidas - e a versao mais
                            # rica da pauta (carrega cleaned_source_text etc).
                            d.update(extra)
                    except Exception:
                        pass
                    # garante presenca de _uid (compat com painel)
                    if d.get("uid") and not d.get("_uid"):
                        d["_uid"] = d["uid"]
                    rows.append(d)
            finally:
                conn.close()

        # Agrupamento por COLETA (pedido do usuario 13/05/2026): cada lote
        # de coleta vira um bloco. Mais novo em cima. Dentro de cada bloco,
        # TXT OK primeiro, pendentes depois. baixo_score isolado no fim.
        try:
            from ururau.core.source_text_contract import source_text_is_valid
        except Exception:
            def source_text_is_valid(p):
                t = (p or {}).get("cleaned_source_text") or ""
                return len(str(t).strip()) >= 550

        # 1) separa baixo_score em buffer dedicado
        baixo: list[dict] = []
        ativos: list[dict] = []
        for d in rows:
            st = str(d.get("status") or "").lower()
            if st == "baixo_score":
                baixo.append(d)
            else:
                ativos.append(d)

        # 2) agrupa ativos por coleta_lote_label_v123. Cada grupo ganha como
        #    chave de ordenacao o MAIOR captada_em do grupo (= coleta mais
        #    recente fica no topo, conforme pedido do usuario).
        def _label(p: dict) -> str:
            v = (p.get("coleta_lote_label_v123") or
                 p.get("coleta_lote") or
                 p.get("grupo_coleta") or "")
            v = str(v).strip()
            return v or "Coletas anteriores"

        grupos: dict[str, list[dict]] = {}
        max_captada_por_label: dict[str, str] = {}
        for d in ativos:
            lab = _label(d)
            grupos.setdefault(lab, []).append(d)
            cap = str(d.get("captada_em") or d.get("atualizada_em") or "")
            if cap and cap > max_captada_por_label.get(lab, ""):
                max_captada_por_label[lab] = cap

        # Labels ordenadas: primeiro pelo MAX captada_em do grupo desc;
        # 'Coletas anteriores' (sem label) sempre por ultimo.
        def _peso(lab: str) -> tuple[int, str]:
            antigo = 1 if lab == "Coletas anteriores" else 0
            # inverte string para DESC virar ascendente
            return (antigo, max_captada_por_label.get(lab, ""))

        ordem_labels = sorted(grupos.keys(),
                               key=lambda l: _peso(l), reverse=True)
        # Como reverse=True, 'antigo=1' fica no topo. Corrige:
        ordem_labels = sorted(
            grupos.keys(),
            key=lambda l: (
                0 if l == "Coletas anteriores" else 1,
                max_captada_por_label.get(l, ""),
            ),
            reverse=True,
        )

        # 3) dentro de cada grupo: TXT OK primeiro, pendentes depois.
        def _dt_ordem(p: dict) -> str:
            for key in ("_data_pub_ordem", "data_pub_fonte", "data_pub_fonte_br", "captada_em", "atualizada_em"):
                v = str(p.get(key) or "")
                if v:
                    return v
            return ""

        out: list[dict] = []
        for lab in ordem_labels:
            com_txt = sorted(
                [d for d in grupos[lab] if source_text_is_valid(d)],
                key=_dt_ordem,
                reverse=True,
            )
            sem_txt = sorted(
                [d for d in grupos[lab] if not source_text_is_valid(d)],
                key=_dt_ordem,
                reverse=True,
            )
            out.extend(com_txt)
            out.extend(sem_txt)

        # 4) baixo_score no fim, agrupado tambem (mesma ordem, mas como bloco
        #    unico — nao quebra por coleta porque eles ja foram revisados).
        if incluir_baixo_score:
            out = out + baixo
        return out

    # Status recuperaveis (spec_claudio_reverter_bloqueio_descartada_redigir).
    # NUNCA mudar uma pauta para esses por falha tecnica: descartada, descartado,
    # bloqueada, bloqueado, rejeitada, rejeitado, reprovada, reprovado, excluida.
    # Em vez disso usar: erro_ia, erro_credencial_ia, erro_modelo_ia, erro_rede_ia,
    # fonte_insuficiente, redacao_pendente.
    STATUS_RECUPERAVEIS = (
        "captada", "em_redacao", "pronta_para_redigir", "redacao_pendente",
        "erro_ia", "erro_credencial_ia", "erro_modelo_ia", "erro_rede_ia",
        "fonte_insuficiente", "pendente_fonte", "baixo_score",
    )

    def reativar_pauta_para_redacao(self, uid: str, motivo: str = "",
                                    novo_status: str = "em_redacao") -> dict:
        """Reativa uma pauta marcada como descartada/bloqueada para redigir.

        Pre-condicao: chamador ja validou que ha texto fonte valido OU usuario
        confirmou explicitamente a reativacao (caso baixo_score).

        Acao:
          - Le status atual (anterior)
          - Remove o link de links_bloqueados se estiver la
          - Grava novo_status (default 'em_redacao')
          - Log de auditoria com motivo e status_anterior

        Nao apaga a pauta, nao toca em dados_json (preserva todo o trabalho
        anterior). Devolve dict com status anterior e novo para o chamador
        exibir feedback.
        """
        status_anterior = ""
        link_atual = ""
        with _lock:
            conn = self._conectar()
            try:
                row = conn.execute(
                    "SELECT status, link_origem FROM pautas WHERE uid=? LIMIT 1",
                    (uid,),
                ).fetchone()
                if row:
                    status_anterior = (row["status"] or "").strip()
                    link_atual = (row["link_origem"] or "").strip()
            finally:
                conn.close()

        # Remove bloqueio definitivo por link, se existir.
        try:
            if link_atual:
                with _lock:
                    conn = self._conectar()
                    try:
                        conn.execute(
                            "DELETE FROM links_bloqueados WHERE link=?",
                            (link_atual,),
                        )
                        conn.commit()
                    finally:
                        conn.close()
                with _cache_lock:
                    _links_bloqueados_cache.discard(link_atual)
        except Exception:
            pass

        # Aplica novo status.
        self.atualizar_status_pauta(uid, novo_status)

        # Auditoria.
        try:
            self.log_auditoria(
                uid,
                "pauta_reativada_para_redacao",
                {
                    "motivo": motivo or "texto_fonte_valido",
                    "status_anterior": status_anterior,
                    "novo_status": novo_status,
                    "link_origem": link_atual,
                },
            )
        except Exception:
            pass

        return {
            "uid": uid,
            "status_anterior": status_anterior,
            "novo_status": novo_status,
            "motivo": motivo,
            "link_atual": link_atual,
        }

    def marcar_status_redacao(self, uid: str, status_redacao: str,
                              detalhe: str = "") -> None:
        """Grava status auxiliar de redacao SEM mudar o status principal da pauta.

        Usado para refletir falhas de IA/rede/credencial sem tornar a pauta
        descartada. Vai para o dados_json sob a chave 'status_redacao_v200'.
        """
        try:
            row = self.buscar_pauta(uid)
            if not row:
                return
            p = dict(row)
            try:
                extra = json.loads(p.get("dados_json") or "{}")
                if isinstance(extra, dict):
                    p.update(extra)
            except Exception:
                pass
            p["status_redacao_v200"] = status_redacao
            if detalhe:
                p["status_redacao_detalhe_v200"] = str(detalhe)[:500]
            p["atualizada_em"] = self._agora()
            self.salvar_pauta(p)
            try:
                self.log_auditoria(uid, "status_redacao_atualizado",
                                   {"status_redacao": status_redacao,
                                    "detalhe": detalhe[:200]})
            except Exception:
                pass
        except Exception:
            pass

    def contadores_dashboard(self) -> dict:
        """Contadores oficiais para os indicadores superiores do painel.

        Substitui leituras avulsas espalhadas pelo painel. Sempre consulta
        os campos canonicos de status e ignora itens marcados como
        ``baixo_score`` na contagem de "Pautas ativas".
        """
        with _lock:
            conn = self._conectar()
            try:
                placeholders = ",".join("?" * len(self._STATUS_FORA_DA_FILA))
                ativas = conn.execute(
                    "SELECT COUNT(*) FROM pautas "
                    f"WHERE (status IS NULL OR LOWER(status) NOT IN ({placeholders})) "
                    "  AND (status IS NULL OR LOWER(status) <> 'baixo_score') "
                    "  AND link_origem IS NOT NULL AND TRIM(link_origem) <> ''",
                    tuple(self._STATUS_FORA_DA_FILA),
                ).fetchone()[0]
                baixo = conn.execute(
                    "SELECT COUNT(*) FROM pautas WHERE LOWER(status)='baixo_score'"
                ).fetchone()[0]
                descartadas = conn.execute(
                    "SELECT COUNT(*) FROM pautas WHERE LOWER(status) IN ('descartada','descartado','rejeitada','rejeitado','excluida','excluido')"
                ).fetchone()[0]
                bloqueadas = conn.execute(
                    "SELECT COUNT(*) FROM pautas WHERE LOWER(status) IN ('bloqueada','bloqueado','reprovada','reprovado')"
                ).fetchone()[0]
                publicadas = conn.execute(
                    "SELECT COUNT(*) FROM publicacoes WHERE LOWER(status)='publicada'"
                ).fetchone()[0]
                materias = conn.execute(
                    "SELECT COUNT(*) FROM materias"
                ).fetchone()[0]
                total = conn.execute("SELECT COUNT(*) FROM pautas").fetchone()[0]
                return {
                    "pautas_ativas": int(ativas),
                    "baixo_score":   int(baixo),
                    "publicadas":    int(publicadas),
                    "materias":      int(materias),
                    "descartadas":   int(descartadas),
                    "bloqueadas":    int(bloqueadas),
                    "total":         int(total),
                }
            finally:
                conn.close()


# -- Singleton global ----------------------------------------------------------
_db_instance: Optional[Database] = None

def get_db(caminho: str = "ururau.db") -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(caminho)
    return _db_instance


# ── Compatibilidade JSON legado ────────────────────────────────────────────────
def carregar_historico_json(arquivo: str = "historico_unico.json") -> list[dict]:
    try:
        p = Path(arquivo)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

def salvar_historico_json(lista: list[dict], arquivo: str = "historico_unico.json"):
    try:
        Path(arquivo).write_text(
            json.dumps(lista, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[DB] Erro ao salvar histórico JSON: {e}")
