# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestCmsSemImagem(unittest.TestCase):
    def test_preflight_bloqueia_sem_imagem(self):
        from ururau.publisher.preflight_publicacao_v47_23 import preflight_publicacao
        ok, msg = preflight_publicacao({}, {"titulo": "Teste", "conteudo": "Texto suficiente"}, None, rascunho=True)
        self.assertFalse(ok)
        self.assertIn("imagem", msg.lower())

    def test_preflight_aceita_imagem_url(self):
        from ururau.publisher.preflight_publicacao_v47_23 import preflight_publicacao
        imagem = {"url_imagem": "https://example.com/foto.jpg"}
        ok, msg = preflight_publicacao({}, {"titulo": "Teste", "conteudo": "Texto suficiente"}, imagem, rascunho=True)
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
