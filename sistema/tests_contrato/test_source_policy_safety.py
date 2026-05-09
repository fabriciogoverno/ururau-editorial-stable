# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestSourcePolicySafety(unittest.TestCase):
    def test_fonte_none_nao_quebra(self):
        from ururau.coleta.source_policy_v114 import fonte_nome, status_fonte_por_log, prioridade_fonte
        self.assertEqual(fonte_nome(None), "")
        self.assertEqual(status_fonte_por_log(None), "desconhecida")
        self.assertIsInstance(prioridade_fonte(None), int)

    def test_ordenar_fontes_ignora_itens_invalidos(self):
        from ururau.coleta.source_policy_v114 import ordenar_fontes
        fontes = [None, "x", {"nome": "Clique Diario", "ativo": True}]
        out = ordenar_fontes(fontes, incluir_quarentena=True)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], dict)

    def test_deve_ignorar_pauta_none_safe(self):
        from ururau.coleta.source_policy_v114 import deve_ignorar_pauta
        ignorar, motivo = deve_ignorar_pauta(None, None, None, None)
        self.assertTrue(ignorar)
        self.assertEqual(motivo, "sem_texto")


if __name__ == "__main__":
    unittest.main()
