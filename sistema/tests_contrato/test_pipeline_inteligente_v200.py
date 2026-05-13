# -*- coding: utf-8 -*-
"""Testes do pipeline inteligente: bandit aprende por dominio."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from ururau.coleta import pipeline_inteligente_v200 as PI


class TestPipelineInteligente(unittest.TestCase):
    def setUp(self):
        # store em arquivo temporario
        self.tmp = tempfile.mkdtemp()
        self._orig_store = PI._store_path
        PI._store_path = lambda: Path(self.tmp) / "metricas.json"

    def tearDown(self):
        PI._store_path = self._orig_store

    def test_registra_e_le_metrica(self):
        u = "https://exemplo.com/noticia/1"
        PI.registrar_resultado(u, "json_ld", sucesso=True, chars=1000)
        stats = PI.estatisticas_por_dominio(u)
        self.assertEqual(stats["dominio"], "exemplo.com")
        self.assertEqual(stats["estrategias"]["json_ld"]["sucessos"], 1)

    def test_bandit_prioriza_estrategia_que_funciona(self):
        u = "https://teste.com/x"
        # json_ld falha 10x, articlebody acerta 10x
        for _ in range(10):
            PI.registrar_resultado(u, "json_ld", sucesso=False)
            PI.registrar_resultado(u, "articlebody", sucesso=True, chars=1500)
        ordem = PI.ordem_recomendada_para_url(u)
        self.assertEqual(ordem[0], "articlebody",
                         f"esperado articlebody primeiro, veio {ordem[:3]}")

    def test_sem_historico_mantem_ordem_default(self):
        # dominio novo sem historico
        ordem = PI.ordem_recomendada_para_url("https://novosite.com/abc")
        self.assertEqual(ordem[0], "json_ld")

    def test_dominio_diferente_nao_contamina(self):
        u1 = "https://siteA.com/x"
        u2 = "https://siteB.com/y"
        for _ in range(5):
            PI.registrar_resultado(u1, "playwright", sucesso=True, chars=2000)
        ordem_a = PI.ordem_recomendada_para_url(u1)
        ordem_b = PI.ordem_recomendada_para_url(u2)
        self.assertEqual(ordem_a[0], "playwright")
        self.assertEqual(ordem_b[0], "json_ld")  # default

    def test_relatorio_global_conta_dominios(self):
        PI.registrar_resultado("https://a.com/x", "json_ld", sucesso=True, chars=100)
        PI.registrar_resultado("https://b.com/y", "amp", sucesso=True, chars=100)
        rel = PI.relatorio_global()
        self.assertEqual(rel["dominios_aprendidos"], 2)
        self.assertEqual(rel["total_sucessos"], 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
