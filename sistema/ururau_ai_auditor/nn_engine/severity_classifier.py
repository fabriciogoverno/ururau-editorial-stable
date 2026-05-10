# -*- coding: utf-8 -*-
"""
Classificador neural de severidade de logs/erros.
MLP (Multi-Layer Perceptron) com scikit-learn.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import List, Union

import numpy as np
from sklearn.neural_network import MLPClassifier

from .vectorizer import LogVectorizer


class SeverityClassifier:
    """Classifica severidade: CRITICO / MEDIO / BAIXO / FALSO_POSITIVO."""

    LABELS = ["BAIXO", "MEDIO", "CRITICO", "FALSO_POSITIVO"]

    def __init__(self, hidden_layers: tuple = (128, 64), max_iter: int = 500):
        self.vectorizer = LogVectorizer()
        self.model = MLPClassifier(
            hidden_layer_sizes=hidden_layers,
            max_iter=max_iter,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=10
        )
        self._fitted = False

    def fit(self, texts: List[str], labels: List[str]):
        self.vectorizer.fit(texts)
        X = self.vectorizer.encode(texts)
        y = np.array([self.LABELS.index(l) if l in self.LABELS else 0 for l in labels])
        self.model.fit(X, y)
        self._fitted = True

    def predict(self, texts: List[str]) -> List[Dict[str, Any]]:
        if not self._fitted:
            raise RuntimeError("Modelo não treinado.")
        X = self.vectorizer.encode(texts)
        probs = self.model.predict_proba(X)
        preds = self.model.predict(X)
        out = []
        for pred, prob in zip(preds, probs):
            out.append({
                "classe": self.LABELS[pred],
                "confianca": float(np.max(prob)),
                "probabilidades": {self.LABELS[i]: float(v) for i, v in enumerate(prob)}
            })
        return out

    def save(self, path: Union[str, Path]):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        base = path.with_suffix("")
        base.with_suffix(".mlp.pkl").write_bytes(pickle.dumps({"model": self.model, "fitted": self._fitted}))
        self.vectorizer.save(base.with_suffix(".vec"))
        meta = {"tipo": "severity_mlp", "labels": self.LABELS}
        base.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: Union[str, Path]):
        path = Path(path)
        base = path.with_suffix("")
        data = pickle.loads(base.with_suffix(".mlp.pkl").read_bytes())
        self.model = data["model"]
        self._fitted = data["fitted"]
        self.vectorizer.load(base.with_suffix(".vec"))
