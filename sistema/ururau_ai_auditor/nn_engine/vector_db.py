# -*- coding: utf-8 -*-
"""
Banco vetorial para busca semântica de erros e padrões.
Usa ChromaDB (leve) com fallback para JSON em memória.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Tentativa ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    _CHROMA_AVAILABLE = True
except Exception:
    _CHROMA_AVAILABLE = False


class LogVectorDB:
    """Armazena e busca logs/erros por similaridade semântica."""

    def __init__(self, root: Union[str, Path] = ".", collection_name: str = "ururau_logs"):
        self.root = Path(root)
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._fallback: List[Dict[str, Any]] = []
        self._mode = "unknown"

    def _init(self):
        if self._client is not None:
            return
        db_dir = self.root / "dados_ml" / "chroma_db"
        db_dir.mkdir(parents=True, exist_ok=True)
        if _CHROMA_AVAILABLE:
            self._client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(db_dir)
            ))
            self._collection = self._client.get_or_create_collection(self.collection_name)
            self._mode = "chromadb"
        else:
            self._mode = "json"
            fallback_path = db_dir / f"{self.collection_name}.json"
            if fallback_path.exists():
                self._fallback = json.loads(fallback_path.read_text(encoding="utf-8"))

    def add(self, texts: List[str], metadatas: Optional[List[Dict]] = None, ids: Optional[List[str]] = None):
        self._init()
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        if metadatas is None:
            metadatas = [{} for _ in texts]
        if self._mode == "chromadb":
            self._collection.add(documents=texts, metadatas=metadatas, ids=ids)
            self._client.persist()
        else:
            for t, m, i in zip(texts, metadatas, ids):
                self._fallback.append({"id": i, "text": t, "meta": m})
            self._persist_fallback()

    def query(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        self._init()
        if self._mode == "chromadb":
            res = self._collection.query(query_texts=[query_text], n_results=n_results)
            out = []
            for i in range(len(res["ids"][0])):
                out.append({
                    "id": res["ids"][0][i],
                    "text": res["documents"][0][i],
                    "meta": res["metadatas"][0][i],
                    "distance": res.get("distances", [[None]*n_results])[0][i]
                })
            return out
        else:
            # Fallback: busca simples por substring (ordena por comprimento de match)
            ranked = []
            for item in self._fallback:
                score = 0
                if query_text.lower() in item["text"].lower():
                    score = len(query_text) / max(len(item["text"]), 1)
                if score > 0:
                    ranked.append((score, item))
            ranked.sort(key=lambda x: x[0], reverse=True)
            return [x[1] for x in ranked[:n_results]]

    def _persist_fallback(self):
        db_dir = self.root / "dados_ml" / "chroma_db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (db_dir / f"{self.collection_name}.json").write_text(
            json.dumps(self._fallback, ensure_ascii=False, indent=2), encoding="utf-8"
        )
