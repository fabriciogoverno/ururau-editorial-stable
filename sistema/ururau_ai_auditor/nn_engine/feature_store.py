# -*- coding: utf-8 -*-
"""
Extrai features tabulares do banco SQLite do Ururau para treinamento.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


class FeatureStore:
    """Lê o banco do Ururau e produz DataFrames de features."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)

    def _query(self, sql: str) -> pd.DataFrame:
        with sqlite3.connect(str(self.db_path)) as conn:
            return pd.read_sql_query(sql, conn)

    def extrair_ciclos(self, limit: int = 1000) -> pd.DataFrame:
        """Features por ciclo de monitoramento."""
        # Tabela assumida: monitor_log (adaptar se nome for diferente)
        sql = f"""
        SELECT
            id,
            timestamp,
            COALESCE(fontes_coletadas, 0) as fontes_coletadas,
            COALESCE(materias_geradas, 0) as materias_geradas,
            COALESCE(erros, 0) as erros,
            COALESCE(duracao_segundos, 0) as duracao_segundos,
            COALESCE(modo_cms, 'local') as modo_cms
        FROM monitor_log
        ORDER BY timestamp DESC
        LIMIT {limit}
        """
        try:
            df = self._query(sql)
        except Exception:
            # Se tabela não existe, retorna schema vazio
            df = pd.DataFrame(columns=[
                "id", "timestamp", "fontes_coletadas", "materias_geradas",
                "erros", "duracao_segundos", "modo_cms"
            ])
        # Features derivadas
        if not df.empty:
            df["hora_dia"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.hour
            df["dia_semana"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.dayofweek
            df["taxa_sucesso"] = df["materias_geradas"] / (df["fontes_coletadas"].replace(0, 1))
            df["erro_rate"] = df["erros"] / (df["fontes_coletadas"].replace(0, 1))
        return df

    def extrair_fontes(self, limit: int = 2000) -> pd.DataFrame:
        """Features por fonte (domínio)."""
        sql = f"""
        SELECT
            dominio,
            COUNT(*) as total_coletas,
            AVG(COALESCE(texto_length, 0)) as avg_texto_length,
            SUM(CASE WHEN erro IS NOT NULL THEN 1 ELSE 0 END) as total_erros,
            SUM(CASE WHEN publicado = 1 THEN 1 ELSE 0 END) as total_publicados,
            MAX(timestamp) as ultima_coleta
        FROM fontes_log
        GROUP BY dominio
        ORDER BY total_coletas DESC
        LIMIT {limit}
        """
        try:
            df = self._query(sql)
        except Exception:
            df = pd.DataFrame(columns=[
                "dominio", "total_coletas", "avg_texto_length",
                "total_erros", "total_publicados", "ultima_coleta"
            ])
        if not df.empty:
            df["taxa_publicacao"] = df["total_publicados"] / (df["total_coletas"].replace(0, 1))
            df["taxa_erro"] = df["total_erros"] / (df["total_coletas"].replace(0, 1))
        return df

    def salvar(self, df: pd.DataFrame, nome: str, root: Union[str, Path] = ".") -> Path:
        pasta = Path(root) / "dados_ml"
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"{nome}.parquet"
        df.to_parquet(caminho, index=False)
        return caminho
