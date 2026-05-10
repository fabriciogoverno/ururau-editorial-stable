# -*- coding: utf-8 -*-
"""
Detector de anomalias nos ciclos do monitor 24h.
Usa IsolationForest do scikit-learn.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Union

import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest


class AnomalyCicloDetector:
    """Detecta ciclos de monitoramento anômalos."""

    FEATURE_COLS = ["fontes_coletadas", "materias_geradas", "erros",
                    "duracao_segundos", "hora_dia", "dia_semana",
                    "taxa_sucesso", "erro_rate"]

    def __init__(self, random_state: int = 42):
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=random_state,
            n_jobs=-1
        )
        self._fitted = False

    def fit(self, df: pd.DataFrame) -> "AnomalyCicloDetector":
        X = self._extract_features(df)
        if X.shape[0] < 10:
            raise ValueError("Mínimo 10 registros para treinar.")
        self.model.fit(X)
        self._fitted = True
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("Modelo não treinado. Rode .fit() primeiro.")
        X = self._extract_features(df)
        preds = self.model.predict(X)
        scores = self.model.score_samples(X)
        df = df.copy()
        df["anomaly"] = preds == -1
        df["anomaly_score"] = scores
        return df

    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        cols = [c for c in self.FEATURE_COLS if c in df.columns]
        X = df[cols].fillna(0).values
        return X

    def save(self, path: Union[str, Path]):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pickle.dumps({"model": self.model, "fitted": self._fitted}))
        meta = {"tipo": "anomaly_ciclo", "features": self.FEATURE_COLS}
        path.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: Union[str, Path]):
        path = Path(path)
        data = pickle.loads(path.read_bytes())
        self.model = data["model"]
        self._fitted = data["fitted"]
