# -*- coding: utf-8 -*-
"""
Vetorização de logs, erros e textos de fonte.
Usa sentence-transformers se disponível; fallback para TF-IDF.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import List, Union

import numpy as np

# Tentativa de importar sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except Exception:
    _ST_AVAILABLE = False

# Fallback TF-IDF
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    _SKLEARN_AVAILABLE = True
except Exception:
    _SKLEARN_AVAILABLE = False


class LogVectorizer:
    """Converte textos (logs, erros, snippets) em vetores numéricos."""

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self._model = None
        self._tfidf = None
        self._mode = "unknown"

    def _load_model(self):
        if self._model is not None:
            return
        if _ST_AVAILABLE:
            self._model = SentenceTransformer(self.model_name)
            self._mode = "sentence-transformers"
        elif _SKLEARN_AVAILABLE:
            self._tfidf = TfidfVectorizer(max_features=384)
            self._mode = "tfidf"
        else:
            raise RuntimeError("Nenhum vetorizador disponível. Instale: pip install sentence-transformers scikit-learn")

    def fit(self, texts: List[str]):
        self._load_model()
        if self._mode == "tfidf":
            self._tfidf.fit(texts)

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        self._load_model()
        if isinstance(texts, str):
            texts = [texts]
        if self._mode == "sentence-transformers":
            return self._model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        elif self._mode == "tfidf":
            return self._tfidf.transform(texts).toarray()
        else:
            raise RuntimeError("Vetorizador não inicializado.")

    def save(self, path: Union[str, Path]):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        meta = {"mode": self._mode, "model_name": self.model_name}
        path.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        if self._mode == "tfidf" and self._tfidf is not None:
            path.with_suffix(".tfidf.pkl").write_bytes(pickle.dumps(self._tfidf))

    def load(self, path: Union[str, Path]):
        path = Path(path)
        meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
        self._mode = meta["mode"]
        self.model_name = meta.get("model_name", "")
        if self._mode == "sentence-transformers":
            self._model = SentenceTransformer(self.model_name)
        elif self._mode == "tfidf":
            self._tfidf = pickle.loads(path.with_suffix(".tfidf.pkl").read_bytes())
