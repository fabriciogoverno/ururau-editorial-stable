# -*- coding: utf-8 -*-
"""
Multi-Armed Bandit (Thompson Sampling) para seleção inteligente de fontes.
Prioriza fontes com maior taxa de conversão para matérias publicadas.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Union


class FonteBandit:
    """Thompson Sampling com prior Beta(1,1)."""

    def __init__(self, root: Union[str, Path] = "."):
        self.root = Path(root)
        self._alphas: Dict[str, float] = {}
        self._betas: Dict[str, float] = {}
        self._path = self.root / "dados_ml" / "bandit_fontes.json"
        self._load()

    def _load(self):
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._alphas = data.get("alphas", {})
            self._betas = data.get("betas", {})

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({
            "alphas": self._alphas,
            "betas": self._betas
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def register_fonte(self, fonte: str):
        if fonte not in self._alphas:
            self._alphas[fonte] = 1.0
            self._betas[fonte] = 1.0
            self._save()

    def update(self, fonte: str, success: bool):
        """Chamar após cada ciclo: success=True se gerou matéria publicada."""
        self.register_fonte(fonte)
        if success:
            self._alphas[fonte] += 1.0
        else:
            self._betas[fonte] += 1.0
        self._save()

    def sample(self, fontes: List[str]) -> str:
        """Retorna a fonte com maior amostra da Beta."""
        for f in fontes:
            self.register_fonte(f)
        scores = {f: random.betavariate(self._alphas[f], self._betas[f]) for f in fontes}
        return max(scores, key=scores.get)

    def rank(self, fontes: List[str]) -> List[Dict[str, float]]:
        """Retorna ranking com score esperado."""
        for f in fontes:
            self.register_fonte(f)
        out = []
        for f in fontes:
            a = self._alphas[f]
            b = self._betas[f]
            expected = a / (a + b)
            out.append({"fonte": f, "expected_reward": expected, "alpha": a, "beta": b})
        out.sort(key=lambda x: x["expected_reward"], reverse=True)
        return out

    def penalizar(self, fonte: str, razao: str = "erro"):
        """Penaliza fonte que deu erro (ex: 403, timeout, texto curto)."""
        self.register_fonte(fonte)
        self._betas[fonte] += 2.0  # penalidade mais forte
        self._save()
