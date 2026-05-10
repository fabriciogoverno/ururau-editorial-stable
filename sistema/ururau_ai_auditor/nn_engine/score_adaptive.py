# -*- coding: utf-8 -*-
"""
Ajusta automaticamente o score mínimo de pauta (threshold)
baseado na taxa de aprovação das últimas N pautas.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union


class ScoreAdaptive:
    """Threshold inteligente para aprovação de pautas."""

    MIN_SCORE = 40
    MAX_SCORE = 90
    DEFAULT = 65
    JANELA = 50

    def __init__(self, root: Union[str, Path] = "."):
        self.root = Path(root)
        self._path = self.root / "dados_ml" / "score_adaptive.json"
        self._historico: list = []
        self._threshold = self.DEFAULT
        self._load()

    def _load(self):
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._historico = data.get("historico", [])
            self._threshold = data.get("threshold", self.DEFAULT)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({
            "threshold": self._threshold,
            "historico": self._historico[-self.JANELA:]
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def registrar_pauta(self, score: float, aprovada: bool):
        """Registrar resultado de uma pauta avaliada."""
        self._historico.append({"score": score, "aprovada": aprovada})
        self._historico = self._historico[-self.JANELA:]

        if len(self._historico) >= 10:
            taxa_aprovacao = sum(1 for x in self._historico if x["aprovada"]) / len(self._historico)
            if taxa_aprovacao < 0.10:
                # Muito restritivo → abaixa threshold
                self._threshold = max(self._threshold - 5, self.MIN_SCORE)
            elif taxa_aprovacao > 0.60:
                # Muito permissivo → sobe threshold
                self._threshold = min(self._threshold + 5, self.MAX_SCORE)

        self._save()

    def get_threshold(self) -> int:
        return int(self._threshold)

    def reset(self):
        self._threshold = self.DEFAULT
        self._historico = []
        self._save()
