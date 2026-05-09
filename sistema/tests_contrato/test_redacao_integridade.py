# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestRedacaoIntegridade(unittest.TestCase):
    def test_bloqueia_fonte_contaminada_bolao_ato_futuro(self):
        from ururau.editorial.integridade_fonte_v47_26 import validar_fonte_estrita
        pauta = {"titulo_origem": "Bolao de Sao Fidelis fatura mais de R$ 140 mil na Mega-Sena"}
        texto = "Bolao de Sao Fidelis fatura mais de R$ 140 mil. Projeto Ato Futuro abre oficinas gratuitas de arte e cultura."
        ok, motivo = validar_fonte_estrita(pauta, texto)
        self.assertFalse(ok, motivo)

    def test_aprova_fonte_correta_bolao(self):
        from ururau.editorial.integridade_fonte_v47_26 import validar_fonte_estrita
        pauta = {"titulo_origem": "Bolao de Sao Fidelis fatura mais de R$ 140 mil na Mega-Sena"}
        texto = "Um bolao de Sao Fidelis acertou dezenas da Mega-Sena e ganhou mais de R$ 140 mil. A aposta premiada saiu em concurso da loteria e o valor sera dividido entre participantes do bolao."
        ok, motivo = validar_fonte_estrita(pauta, texto)
        self.assertTrue(ok, motivo)

    def test_materia_de_outra_pauta_e_bloqueada(self):
        from ururau.editorial.integridade_redacao_v47_25 import validar_materia_pertence
        pauta = {"titulo_origem": "Bolao de Sao Fidelis fatura mais de R$ 140 mil na Mega-Sena", "texto_fonte": "Bolao de Sao Fidelis ganhou mais de R$ 140 mil na Mega-Sena."}
        materia = {"titulo": "Projeto Ato Futuro abre oficinas", "conteudo": "Projeto cultural abriu inscricoes para oficinas de arte."}
        ok, motivo = validar_materia_pertence(pauta, materia)
        self.assertFalse(ok, motivo)


if __name__ == "__main__":
    unittest.main()
