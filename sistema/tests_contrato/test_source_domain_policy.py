# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


class TestSourceDomainPolicy(unittest.TestCase):
    def test_campos24_exige_integridade(self):
        from ururau.coleta.source_domain_policy_v47_30 import politica_para_url
        pol = politica_para_url("https://campos24horas.com.br/portal/noticia")
        self.assertFalse(pol.aceita_rss_fallback_sem_integridade)
        self.assertTrue(pol.exige_fonte_validada)
        self.assertGreaterEqual(pol.min_chars_redacao, 900)

    def test_cnn_prioriza_wordpress(self):
        from ururau.coleta.source_domain_policy_v47_30 import politica_para_url
        pol = politica_para_url("https://www.cnnbrasil.com.br/politica/teste")
        self.assertEqual(pol.prioridade_extracao[0], "wordpress_rest")

    def test_dominio_desconhecido_tem_padrao_seguro(self):
        from ururau.coleta.source_domain_policy_v47_30 import politica_para_url
        pol = politica_para_url("https://exemplo.com/noticia")
        self.assertFalse(pol.aceita_rss_fallback_sem_integridade)
        self.assertTrue(pol.exige_fonte_validada)


if __name__ == "__main__":
    unittest.main()
