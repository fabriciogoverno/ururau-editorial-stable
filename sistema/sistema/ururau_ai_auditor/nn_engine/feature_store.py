# -*- coding: utf-8 -*-
"""
Extrai features tabulares do banco SQLite REAL do Ururau (data/ururau.db).
Tabelas: pautas, materias, imagens, publicacoes, auditoria, historico_legado, links_bloqueados, _meta
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

import pandas as pd


class FeatureStore:
    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)

    def _query(self, sql: str) -> pd.DataFrame:
        with sqlite3.connect(str(self.db_path)) as conn:
            return pd.read_sql_query(sql, conn)

    def extrair_ciclos(self, limit: int = 1000) -> pd.DataFrame:
        """Cria ciclos sintéticos a partir de janelas de 1h de pautas capturadas."""
        sql = f"""
        SELECT
            id,
            captada_em as timestamp,
            COALESCE(score_editorial, 0) as score_editorial,
            status,
            urgente,
            fonte_nome,
            CASE WHEN status IN ('publicada','aprovada','processada') THEN 1 ELSE 0 END as materias_geradas,
            CASE WHEN status IN ('rejeitada','erro','bloqueada') THEN 1 ELSE 0 END as erros
        FROM pautas
        WHERE captada_em IS NOT NULL
        ORDER BY captada_em DESC
        LIMIT {limit}
        """
        try:
            df = self._query(sql)
        except Exception:
            df = pd.DataFrame(columns=["id","timestamp","score_editorial","status","urgente","fonte_nome","materias_geradas","erros"])

        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["hora_dia"] = df["timestamp"].dt.hour
        df["dia_semana"] = df["timestamp"].dt.dayofweek
        df["fontes_coletadas"] = 1

        # Agrupa por janela de 1 hora para simular "ciclos"
        df["janela"] = df["timestamp"].dt.floor("1H")
        ciclos = df.groupby("janela").agg({
            "fontes_coletadas": "sum",
            "materias_geradas": "sum",
            "erros": "sum",
            "score_editorial": "mean",
            "urgente": "sum"
        }).reset_index()
        ciclos.rename(columns={"janela": "timestamp"}, inplace=True)
        ciclos["duracao_segundos"] = 1800  # estimado
        ciclos["taxa_sucesso"] = ciclos["materias_geradas"] / ciclos["fontes_coletadas"].replace(0, 1)
        ciclos["erro_rate"] = ciclos["erros"] / ciclos["fontes_coletadas"].replace(0, 1)
        return ciclos

    def extrair_fontes(self, limit: int = 2000) -> pd.DataFrame:
        """Features por fonte (domínio/fonte_nome)."""
        sql = f"""
        SELECT
            COALESCE(fonte_nome, 'desconhecida') as dominio,
            COUNT(*) as total_coletas,
            AVG(COALESCE(score_editorial, 0)) as avg_score,
            SUM(CASE WHEN status IN ('rejeitada','erro','bloqueada') THEN 1 ELSE 0 END) as total_erros,
            SUM(CASE WHEN status IN ('publicada','aprovada','processada') THEN 1 ELSE 0 END) as total_publicados,
            MAX(captada_em) as ultima_coleta
        FROM pautas
        WHERE fonte_nome IS NOT NULL
        GROUP BY fonte_nome
        ORDER BY total_coletas DESC
        LIMIT {limit}
        """
        try:
            df = self._query(sql)
        except Exception:
            df = pd.DataFrame(columns=["dominio","total_coletas","avg_score","total_erros","total_publicados","ultima_coleta"])

        if not df.empty:
            df["taxa_publicacao"] = df["total_publicados"] / df["total_coletas"].replace(0, 1)
            df["taxa_erro"] = df["total_erros"] / df["total_coletas"].replace(0, 1)
        return df

    def extrair_publicacoes(self, limit: int = 1000) -> pd.DataFrame:
        """Features de publicação (CMS/WhatsApp)."""
        sql = f"""
        SELECT
            pauta_uid,
            canal,
            status,
            tentativa,
            publicada_em,
            erro
        FROM publicacoes
        ORDER BY publicada_em DESC
        LIMIT {limit}
        """
        try:
            df = self._query(sql)
        except Exception:
            df = pd.DataFrame(columns=["pauta_uid","canal","status","tentativa","publicada_em","erro"])
        return df

    def extrair_auditoria(self, limit: int = 1000) -> pd.DataFrame:
        """Log de auditoria para análise de padrões de erro."""
        sql = f"""
        SELECT
            timestamp,
            acao,
            detalhe,
            sucesso
        FROM auditoria
        ORDER BY timestamp DESC
        LIMIT {limit}
        """
        try:
            df = self._query(sql)
        except Exception:
            df = pd.DataFrame(columns=["timestamp","acao","detalhe","sucesso"])
        return df

    def salvar(self, df: pd.DataFrame, nome: str, root: Union[str, Path] = ".") -> Path:
        pasta = Path(root) / "dados_ml"
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"{nome}.parquet"
        df.to_parquet(caminho, index=False)
        return caminho
