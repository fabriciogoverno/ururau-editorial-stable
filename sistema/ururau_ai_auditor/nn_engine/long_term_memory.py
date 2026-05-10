# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union
from .vectorizer import LogVectorizer

class LongTermMemory:
    def __init__(self, root="."):
        self.root = Path(root)
        self._path = self.root / "dados_ml" / "long_term_memory.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._memorias = []
        self._vec = LogVectorizer()
        self._load()

    def _load(self):
        if self._path.exists():
            self._memorias = json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self):
        self._path.write_text(json.dumps(self._memorias[-200:], ensure_ascii=False, indent=2), encoding="utf-8")

    def adicionar(self, problema, solucao, resultado, arquivo, patch_id=None):
        mid = patch_id or str(uuid.uuid4())
        embedding = self._vec.encode(problema).tolist()
        self._memorias.append({"id": mid, "problema": problema, "solucao": solucao, "resultado": resultado, "arquivo": arquivo, "embedding": embedding, "utilizada": 0})
        self._save()
        return mid

    def buscar(self, problema_novo, top_k=3):
        if not self._memorias:
            return []
        emb_novo = self._vec.encode(problema_novo)
        scored = []
        for m in self._memorias:
            emb_antigo = self._vec.encode(m["problema"])
            dot = float(emb_novo @ emb_antigo.T)
            norm = float((emb_novo**2).sum()**0.5 * (emb_antigo**2).sum()**0.5)
            sim = dot / norm if norm > 0 else 0
            scored.append((sim, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"similaridade": round(s, 3), **m} for s, m in scored[:top_k]]

    def marcar_utilizada(self, memoria_id):
        for m in self._memorias:
            if m["id"] == memoria_id:
                m["utilizada"] += 1
                self._save()
                break
