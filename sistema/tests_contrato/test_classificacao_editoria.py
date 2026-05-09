# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestClassificacaoEditoria(unittest.TestCase):
    def test_pf_suriname_nao_vira_saude(self):
        from ururau.editorial.canal_final_v47_23 import corrigir_canal_materia
        pauta = {"titulo_origem": "PF resgata brasileira mantida em carcere no Suriname"}
        materia = {"titulo": "PF resgata brasileira mantida em carcere no Suriname", "conteudo": "A Policia Federal resgatou uma brasileira mantida em carcere no Suriname apos promessa falsa de emprego.", "canal": "Saude"}
        canal = corrigir_canal_materia(materia, pauta)
        self.assertNotEqual(canal, "Saúde")
        self.assertNotEqual(canal, "Saude")
        self.assertIn(canal, {"Brasil e Mundo", "Polícia", "Policia"})

    def test_hantavirus_pode_ser_saude(self):
        from ururau.editorial.canal_final_v47_23 import corrigir_canal_materia
        pauta = {"titulo_origem": "Hantavirus: OMS alerta para novos casos em cruzeiro"}
        materia = {"titulo": "OMS alerta para novos casos de hantavirus", "conteudo": "A Organizacao Mundial da Saude monitora novos casos de hantavirus.", "canal": "Polícia"}
        canal = corrigir_canal_materia(materia, pauta)
        self.assertIn(canal, {"Saúde", "Saude"})


if __name__ == "__main__":
    unittest.main()
