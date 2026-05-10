# -*- coding: utf-8 -*-
"""
Otimizador dinâmico do intervalo entre ciclos do monitor.
Aumenta quando não acha pautas; diminui quando acha muitas.
Respeita sempre max/hora e limites de segurança.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Union


class IntervaloOptimizer:
    """Ajusta intervalo baseado em histórico recente."""

    MIN_INTERVALO = 300      # 5 minutos (mínimo seguro)
    MAX_INTERVALO = 3600     # 60 minutos (máximo)
    DEFAULT = 1800           # 30 minutos

    def __init__(self, root: Union[str, Path] = "."):
        self.root = Path(root)
        self._path = self.root / "dados_ml" / "intervalo_state.json"
        self._historico: list = []
        self._intervalo_atual = self.DEFAULT
        self._load()

    def _load(self):
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._historico = data.get("historico", [])
            self._intervalo_atual = data.get("intervalo", self.DEFAULT)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({
            "intervalo": self._intervalo_atual,
            "historico": self._historico[-50:]  # mantém últimos 50
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def registrar_ciclo(self, achou_pauta: bool, materias_geradas: int = 0):
        self._historico.append({"achou": achou_pauta, "materias": materias_geradas})
        self._historico = self._historico[-10:]  # janela de 10 ciclos

        # Lógica de ajuste
        ultimos = self._historico
        if len(ultimos) >= 3:
            ultimos_3 = [x["achou"] for x in ultimos[-3:]]
            if not any(ultimos_3):
                # 3 ciclos sem nada → aumenta 20%
                self._intervalo_atual = min(int(self._intervalo_atual * 1.2), self.MAX_INTERVALO)
            elif sum(ultimos_3) >= 2:
                # 2+ com pauta → diminui 15%
                self._intervalo_atual = max(int(self._intervalo_atual * 0.85), self.MIN_INTERVALO)

        self._save()

    def get_intervalo(self) -> int:
        return self._intervalo_atual

    def reset(self):
        self._intervalo_atual = self.DEFAULT
        self._historico = []
        self._save()
