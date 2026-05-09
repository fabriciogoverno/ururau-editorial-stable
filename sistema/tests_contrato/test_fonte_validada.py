# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestFonteValidada(unittest.TestCase):
    def test_bloqueia_snippet_sem_validacao(self):
        from ururau.coleta.fonte_validada import construir_fonte_validada
        pauta = {"uid": "abc", "titulo_origem": "Teste", "link_origem": "https://example.com/a"}
        texto = "Texto longo suficiente. " * 80
        fonte = construir_fonte_validada(pauta, texto, metodo="rss_fallback", status="pendente", score=80)
        self.assertFalse(fonte.validada)
        self.assertIn("validacao", fonte.motivo.lower())

    def test_aprova_snippet_com_validacao_estrita(self):
        from ururau.coleta.fonte_validada import construir_fonte_validada
        pauta = {"uid": "abc", "titulo_origem": "Teste", "link_origem": "https://example.com/a"}
        texto = "Texto longo suficiente. " * 80
        fonte = construir_fonte_validada(pauta, texto, metodo="v104_v86:rss_fallback", status="ok_integridade_v47_26", score=80)
        self.assertTrue(fonte.validada, fonte.motivo)

    def test_bloqueia_texto_curto(self):
        from ururau.coleta.fonte_validada import construir_fonte_validada
        pauta = {"uid": "abc", "titulo_origem": "Teste", "link_origem": "https://example.com/a"}
        fonte = construir_fonte_validada(pauta, "curto", metodo="v108_readability", status="ok", score=80)
        self.assertFalse(fonte.validada)
        self.assertIn("insuficiente", fonte.motivo)


if __name__ == "__main__":
    unittest.main()
