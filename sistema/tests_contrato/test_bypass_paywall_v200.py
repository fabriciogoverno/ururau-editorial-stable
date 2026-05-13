# -*- coding: utf-8 -*-
"""Testes do bypass de paywall — sem rede, com mocks."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve()
SISTEMA = HERE.parents[1]
if str(SISTEMA) not in sys.path:
    sys.path.insert(0, str(SISTEMA))

from ururau.coleta import bypass_paywall_v200 as BP


HTML_LIMPO = """
<html><head><title>Materia teste</title></head><body>
<article>
<p>Bruno Moretti, ministro do Planejamento, anunciou na quarta-feira o novo subsidio para gasolina. O custo do programa chega a tres bilhoes de reais nos proximos seis meses, segundo balanco apresentado em coletiva no Palacio do Planalto.</p>
<p>Segundo o ministro, as medidas foram coordenadas com o Ministerio de Minas e Energia e o Ministerio da Fazenda. A desoneracao do diesel custara um bilhao e setecentos milhoes por mes no orcamento federal.</p>
<p>O subsidio para gasolina, anunciado nesta quarta, tera valor de ate noventa centavos por litro. O governo trabalha inicialmente com valor entre quarenta e quarenta e cinco centavos. O Ministerio de Minas estima despesa mensal de duzentos e setenta milhoes para cada dez centavos de subvencao.</p>
<p>A medida sera custeada por receitas extraordinarias da Uniao oriundas do aumento do preco internacional do petroleo. A votacao no Congresso esta prevista para o segundo semestre, conforme acordo entre governo e Camara dos Deputados.</p>
</article>
</body></html>
"""


def _fake_get(url, ua=BP.DESKTOP_UA, referer="", allow_redirects=True):
    # Simula resposta 200 para qualquer URL
    return 200, url, HTML_LIMPO


def _fake_get_falha(url, **kw):
    return 0, "", ""


class TestBypassPaywall(unittest.TestCase):

    def test_bypass_disponivel(self):
        self.assertTrue(BP.BYPASS_DISPONIVEL,
                        "requests precisa estar instalado para o bypass")

    def test_googlebot_extrai_quando_html_tem_texto(self):
        with mock.patch.object(BP, "_http_get", _fake_get):
            r = BP._tent_googlebot("https://x.com/y", "titulo qualquer")
        self.assertTrue(r["ok"], r)
        self.assertGreater(r["chars"], 100)

    def test_amp_gera_candidatos_alternativos(self):
        chamadas = []
        def _g(url, **kw):
            chamadas.append(url)
            return _fake_get(url, **kw)
        with mock.patch.object(BP, "_http_get", _g):
            r = BP._tent_amp("https://exemplo.com.br/noticia", "t")
        self.assertTrue(r["ok"])
        # Deve ter tentado pelo menos uma URL diferente da original
        self.assertGreater(len(chamadas), 0)

    def test_referer_google_passa_titulo_url_encoded(self):
        chamado = {}
        def _g(url, ua=BP.DESKTOP_UA, referer="", **kw):
            chamado["referer"] = referer
            return _fake_get(url, ua=ua, referer=referer)
        with mock.patch.object(BP, "_http_get", _g):
            r = BP._tent_referer_google("https://x.com/y", "titulo com espacos")
        self.assertTrue(r["ok"])
        self.assertIn("google.com/search", chamado.get("referer", ""))

    def test_pipeline_completo_para_no_primeiro_sucesso(self):
        # Apenas a 1a estrategia retorna texto valido
        contador = {"n": 0}
        def _g(url, **kw):
            contador["n"] += 1
            if contador["n"] <= 2:  # 1 chamada para a primeira tentativa
                return 200, url, HTML_LIMPO
            return 0, "", ""
        with mock.patch.object(BP, "_http_get", _g):
            r = BP.tentar_bypass_paywall("https://x.com/y", "t")
        self.assertTrue(r["ok"])
        # estrategia vencedora deve ser a primeira (_tent_amp)
        self.assertIn("amp", r["estrategia"])

    def test_pipeline_falha_grava_todas_tentativas(self):
        with mock.patch.object(BP, "_http_get", _fake_get_falha):
            r = BP.tentar_bypass_paywall("https://x.com/y", "t")
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["tentativas"]), len(BP.ESTRATEGIAS))
        for t in r["tentativas"]:
            self.assertFalse(t.get("ok"))


class TestIntegracaoExtractPipeline(unittest.TestCase):
    def test_extract_pipeline_chama_bypass_no_final(self):
        # Verificacao estatica: extract_pipeline_v90 importa bypass_paywall
        src = (SISTEMA / "ururau" / "coleta" / "extract_pipeline_v90.py").read_text(
            encoding="utf-8", errors="ignore"
        )
        self.assertIn("bypass_paywall_v200", src)
        self.assertIn("tentar_bypass_paywall", src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main(verbosity=2)
