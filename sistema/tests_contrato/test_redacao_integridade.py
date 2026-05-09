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
        texto = """
        Um bolao registrado em Sao Fidelis, no Norte Fluminense, acertou cinco dezenas
        da Mega-Sena e garantiu premio superior a R$ 140 mil. A aposta foi feita em
        loterica do municipio e saiu premiada no concurso da loteria federal. Segundo
        informacoes do resultado oficial, o grupo acertou parte das dezenas sorteadas
        e agora deve dividir o valor entre os participantes do bolao. A noticia trata
        do premio, da cidade de Sao Fidelis, do concurso da Mega-Sena e da aposta
        coletiva feita por moradores da regiao. O caso gerou repercussao local por
        envolver uma premiacao expressiva para apostadores do municipio.
        """
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
