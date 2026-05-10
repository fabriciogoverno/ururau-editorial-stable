# -*- coding: utf-8 -*-
"""
Neural Hooks — Facade leve para qualquer modulo chamar a Neural Engine.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from pathlib import Path

_neural = None

def _get():
    global _neural
    if _neural is None:
        try:
            from neural_service import NeuralService
            _neural = NeuralService()
        except Exception:
            _neural = None
    return _neural


def nn_start():
    n = _get()
    if n:
        n.start()


def nn_stop():
    n = _get()
    if n:
        n.stop()


def nn_status():
    n = _get()
    if n:
        return n.status()
    return {"running": False, "erro": "Neural Service nao inicializado"}


def nn_registrar_ciclo(fontes_coletadas, materias_geradas, erros, duracao):
    n = _get()
    if n:
        n.registrar_ciclo(fontes_coletadas, materias_geradas, erros, duracao)


def nn_registrar_pauta(fonte, score, aprovada):
    n = _get()
    if n:
        n.registrar_pauta(fonte, score, aprovada)


def nn_registrar_publicacao(sucesso, tentativas=1):
    n = _get()
    if n:
        n.registrar_publicacao(sucesso, tentativas)


def nn_registrar_erro(texto_erro, severidade="MEDIO"):
    n = _get()
    if n:
        n.registrar_erro(texto_erro, severidade)


def nn_avaliar_fonte(fonte):
    n = _get()
    if n:
        return n.avaliar_fonte(fonte)
    return {"fonte": fonte, "expected_reward": 0.5, "alpha": 1.0, "beta": 1.0}


def nn_get_intervalo():
    n = _get()
    if n:
        return n.get_intervalo_recomendado()
    return 1800


def nn_get_score_threshold():
    n = _get()
    if n:
        return n.get_score_threshold()
    return 65
