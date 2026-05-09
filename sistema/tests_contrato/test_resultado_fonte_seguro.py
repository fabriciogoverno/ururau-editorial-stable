# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestResultadoFonteSeguro(unittest.TestCase):
    def test_none_vira_resultado_seguro_failed(self):
        from ururau.coleta.resultado_fonte_seguro_v47_31 import normalizar_resultado_fonte
        r = normalizar_resultado_fonte(None, url="https://example.com/a", titulo="Teste")
        self.assertFalse(r.ok)
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.url_original, "https://example.com/a")

    def test_dict_incompleto_nao_quebra(self):
        from ururau.coleta.resultado_fonte_seguro_v47_31 import normalizar_resultado_fonte
        r = normalizar_resultado_fonte({"texto": "Texto de teste"}, url="https://example.com/a")
        self.assertFalse(r.ok)
        self.assertEqual(r.texto, "Texto de teste")

    def test_erro_nonetype_get_e_sanitizado(self):
        from ururau.coleta.resultado_fonte_seguro_v47_31 import normalizar_resultado_fonte
        r = normalizar_resultado_fonte({"erro": "AttributeError: 'NoneType' object has no attribute 'get'"})
        self.assertIn("normalizada", r.erro)


if __name__ == "__main__":
    unittest.main()
