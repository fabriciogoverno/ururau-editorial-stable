# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestPreviewIntegridade(unittest.TestCase):
    def test_detector_de_materia_contaminada(self):
        from ururau.editorial.limpar_contaminadas_v47_27 import esta_contaminada
        titulo = "Bolao de Sao Fidelis fatura mais de R$ 140 mil na Mega-Sena"
        materia = {
            "titulo": "Projeto Ato Futuro abre oficinas",
            "conteudo": "Projeto cultural oferece oficinas gratuitas de arte para jovens.",
        }
        ok, motivo = esta_contaminada(titulo, materia)
        self.assertTrue(ok, motivo)

    def test_detector_nao_bloqueia_materia_correta(self):
        from ururau.editorial.limpar_contaminadas_v47_27 import esta_contaminada
        titulo = "Bolao de Sao Fidelis fatura mais de R$ 140 mil na Mega-Sena"
        materia = {
            "titulo": "Bolao de Sao Fidelis fatura mais de R$ 140 mil na Mega-Sena",
            "conteudo": "Aposta feita em Sao Fidelis acertou dezenas da Mega-Sena e recebeu premio superior a R$ 140 mil.",
        }
        ok, motivo = esta_contaminada(titulo, materia)
        self.assertFalse(ok, motivo)


if __name__ == "__main__":
    unittest.main()
