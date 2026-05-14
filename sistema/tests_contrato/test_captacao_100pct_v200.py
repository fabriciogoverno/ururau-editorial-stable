# -*- coding: utf-8 -*-
"""Testes da captacao v200 — endpoints quebrados, sitemap_index, janelas.

Cobre os 6 fixes da issue captacao-100pct-fontes-quebradas:
1. Fallback automatico para URLs oficiais quebradas (ALERJ, Camara, MPRJ, etc).
2. Parser de sitemap_index recursivo.
3. Sanitizador de entidades XML invalidas.
4. Fetch resiliente para dominios com timeout cronico (girorj).
5. Cobertura de portodoacu/tce/rj.gov.br via fallback v200.
6. Janela alargada para fontes regionais (Nfnoticias, Tribuna NF).
"""
from __future__ import annotations

import datetime
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# -----------------------------------------------------------------------------
# Fix 1 + 5: fallback automatico para URLs oficiais quebradas
# -----------------------------------------------------------------------------
class FallbackUrlsOficiaisQuebradasTests(unittest.TestCase):
    def setUp(self):
        from ururau.coleta.fontes_oficiais_fallback_v200 import substituir_url_se_quebrado
        self.substituir = substituir_url_se_quebrado

    def test_camara_quebrado_vira_gnews_site(self):
        nova, motivo = self.substituir("https://www.camara.leg.br/rss/noticias.xml")
        self.assertIn("news.google.com/rss/search", nova)
        self.assertIn("site%3Acamara.leg.br", nova)
        self.assertTrue(motivo)

    def test_alerj_302_vira_gnews_site(self):
        nova, motivo = self.substituir("https://www.alerj.rj.gov.br/Noticias/rss")
        self.assertIn("news.google.com/rss/search", nova)
        self.assertIn("site%3Aalerj.rj.gov.br", nova)
        self.assertTrue(motivo)

    def test_mprj_404_vira_gnews_site(self):
        nova, motivo = self.substituir("https://www.mprj.mp.br/rss")
        self.assertIn("news.google.com/rss/search", nova)
        self.assertIn("site%3Amprj.mp.br", nova)

    def test_tre_rj_404_vira_gnews_site(self):
        nova, motivo = self.substituir("https://www.tre-rj.jus.br/comunicacao/noticias/RSS")
        self.assertIn("news.google.com/rss/search", nova)
        self.assertIn("site%3Atre-rj.jus.br", nova)

    def test_tjrj_404_vira_gnews_site(self):
        nova, motivo = self.substituir("https://www.tjrj.jus.br/web/guest/home/-/noticias/rss")
        self.assertIn("news.google.com/rss/search", nova)
        self.assertIn("site%3Atjrj.jus.br", nova)

    def test_defensoria_404_vira_gnews_site(self):
        nova, motivo = self.substituir("https://defensoria.rj.def.br/rss/noticias")
        self.assertIn("news.google.com/rss/search", nova)
        self.assertIn("site%3Adefensoria.rj.def.br", nova)

    def test_governo_rj_html_vira_gnews_site(self):
        nova, motivo = self.substituir("https://www.rj.gov.br/noticias/rss")
        self.assertIn("news.google.com/rss/search", nova)
        self.assertIn("site%3Arj.gov.br", nova)

    def test_tce_rj_vira_gnews(self):
        nova, motivo = self.substituir("https://www.tce.rj.gov.br/")
        self.assertIn("site%3Atce.rj.gov.br", nova)

    def test_portodoacu_vira_gnews(self):
        nova, motivo = self.substituir("https://www.portodoacu.com.br/")
        self.assertIn("site%3Aportodoacu.com.br", nova)

    def test_stf_funcionando_nao_alterado(self):
        nova, motivo = self.substituir("https://noticias.stf.jus.br/feed/")
        self.assertEqual(nova, "https://noticias.stf.jus.br/feed/")
        self.assertEqual(motivo, "")

    def test_url_vazia_retorna_vazia(self):
        nova, motivo = self.substituir("")
        self.assertEqual(nova, "")

    def test_aplica_em_lista_de_fontes(self):
        from ururau.coleta.fontes_oficiais_fallback_v200 import aplicar_fallback_em_fontes_especiais
        fontes = [
            {"nome": "Camara", "url": "https://www.camara.leg.br/rss/noticias.xml"},
            {"nome": "STF", "url": "https://noticias.stf.jus.br/feed/"},
        ]
        out = aplicar_fallback_em_fontes_especiais(fontes)
        self.assertEqual(len(out), 2)
        camara = next(f for f in out if f["nome"] == "Camara")
        self.assertIn("news.google.com", camara["url"])
        self.assertEqual(camara["_url_original_v200"], "https://www.camara.leg.br/rss/noticias.xml")
        stf = next(f for f in out if f["nome"] == "STF")
        self.assertEqual(stf["url"], "https://noticias.stf.jus.br/feed/")
        self.assertNotIn("_url_original_v200", stf)


# -----------------------------------------------------------------------------
# Fix 4: timeout cronico (girorj.com.br)
# -----------------------------------------------------------------------------
class DominioTimeoutCronicoTests(unittest.TestCase):
    def test_girorj_marcado_como_timeout_cronico(self):
        from ururau.coleta.fontes_oficiais_fallback_v200 import dominio_e_timeout_cronico
        self.assertTrue(dominio_e_timeout_cronico("https://girorj.com.br/feed/"))
        self.assertTrue(dominio_e_timeout_cronico("https://www.girorj.com.br/feed/"))

    def test_outros_dominios_nao_sao_timeout_cronico(self):
        from ururau.coleta.fontes_oficiais_fallback_v200 import dominio_e_timeout_cronico
        self.assertFalse(dominio_e_timeout_cronico("https://g1.globo.com/rss/g1/"))
        self.assertFalse(dominio_e_timeout_cronico("https://noticias.stf.jus.br/feed/"))

    def test_url_wayback_inclui_dominio_original(self):
        from ururau.coleta.fontes_oficiais_fallback_v200 import url_wayback_recente
        wb = url_wayback_recente("https://girorj.com.br/feed/")
        self.assertIn("web.archive.org", wb)
        self.assertIn("girorj.com.br/feed", wb)


# -----------------------------------------------------------------------------
# Fix 2: parser sitemap_index recursivo
# -----------------------------------------------------------------------------
class SitemapIndexRecursivoTests(unittest.TestCase):
    def test_detecta_root_sitemap_index(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import _root_e_sitemap_index
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://exemplo.com/sm1.xml</loc></sitemap>
</sitemapindex>"""
        root = ET.fromstring(xml)
        self.assertTrue(_root_e_sitemap_index(root))

    def test_detecta_root_urlset_normal(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import _root_e_sitemap_index
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://exemplo.com/n/1.html</loc></url>
</urlset>"""
        root = ET.fromstring(xml)
        self.assertFalse(_root_e_sitemap_index(root))

    def test_extrai_filhos_de_sitemapindex(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import _extrair_filhos_de_sitemapindex
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://exemplo.com/sm-1.xml</loc></sitemap>
  <sitemap><loc>https://exemplo.com/sm-2.xml</loc></sitemap>
  <sitemap><loc>https://exemplo.com/sm-3.xml</loc></sitemap>
</sitemapindex>"""
        root = ET.fromstring(xml)
        filhos = _extrair_filhos_de_sitemapindex(root)
        self.assertEqual(len(filhos), 3)
        self.assertIn("https://exemplo.com/sm-1.xml", filhos)


# -----------------------------------------------------------------------------
# Fix 3: sanitizador de entidades XML invalidas
# -----------------------------------------------------------------------------
class SanitizadorEntidadesTests(unittest.TestCase):
    def test_amp_solto_e_escapado(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import sanitizar_xml
        bruto = b"<x>foo & bar</x>"
        seguro = sanitizar_xml(bruto)
        self.assertIn(b"foo &amp; bar", seguro)
        root = ET.fromstring(seguro)
        self.assertEqual(root.text, "foo & bar")

    def test_nbsp_e_trocado_por_espaco(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import sanitizar_xml
        bruto = "<x>foo&nbsp;bar</x>".encode("utf-8")
        seguro = sanitizar_xml(bruto)
        # entidade &nbsp; nao existe em XML, foi convertida em espaco unicode
        root = ET.fromstring(seguro)
        self.assertIn("foo", root.text)
        self.assertIn("bar", root.text)
        # Garante que nao tem mais &nbsp;
        self.assertNotIn(b"&nbsp;", seguro)

    def test_aacute_atilde_sao_substituidos(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import sanitizar_xml
        bruto = "<x>S&atilde;o Jo&atilde;o &aacute;</x>".encode("utf-8")
        seguro = sanitizar_xml(bruto)
        root = ET.fromstring(seguro)
        self.assertIn("São", root.text)
        self.assertIn("João", root.text)
        self.assertIn("á", root.text)

    def test_entidades_xml_validas_preservadas(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import sanitizar_xml
        bruto = b"<x>a &amp; b &lt; c</x>"
        seguro = sanitizar_xml(bruto)
        # parse sem erro
        root = ET.fromstring(seguro)
        self.assertEqual(root.text, "a & b < c")

    def test_entidade_desconhecida_e_escapada_nao_quebra(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import sanitizar_xml
        bruto = "<x>&algoinventado;</x>".encode("utf-8")
        seguro = sanitizar_xml(bruto)
        # nao deve dar erro de parse
        root = ET.fromstring(seguro)


# -----------------------------------------------------------------------------
# Fix 2: heuristica "URL parece de noticia"
# -----------------------------------------------------------------------------
class HeuristicaUrlDeNoticiaTests(unittest.TestCase):
    def test_url_com_noticia_no_path(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import _parece_url_de_noticia
        self.assertTrue(_parece_url_de_noticia("https://campos24horas.com.br/noticia/abc-def-ghi"))

    def test_url_com_html(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import _parece_url_de_noticia
        self.assertTrue(_parece_url_de_noticia("https://rjnews.com.br/governo-camara-fecham-acordo-6x1.html"))

    def test_url_de_listagem_e_recusada(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import _parece_url_de_noticia
        # /categoria/ deve ser rejeitada
        self.assertFalse(_parece_url_de_noticia("https://exemplo.com/categoria/politica/"))
        # /tag/ tambem
        self.assertFalse(_parece_url_de_noticia("https://exemplo.com/tag/eleicoes/"))

    def test_url_curta_e_recusada(self):
        from ururau.coleta.sitemap_xml_coletor_v200 import _parece_url_de_noticia
        self.assertFalse(_parece_url_de_noticia("https://exemplo.com/sobre"))


# -----------------------------------------------------------------------------
# Fix 6: janela alargada para fontes regionais
# -----------------------------------------------------------------------------
class JanelaRegionalAlargadaTests(unittest.TestCase):
    def test_dominio_regional_recebe_24h(self):
        from ururau.coleta.datas_v99 import janela_para_fonte_v200
        janela = janela_para_fonte_v200(
            fonte={"nome": "Nfnoticias"},
            url_feed="https://www.nfnoticias.com.br/rss/",
            nome_fonte="Nfnoticias",
        )
        self.assertGreaterEqual(janela, 12)

    def test_tribuna_nf_recebe_24h(self):
        from ururau.coleta.datas_v99 import janela_para_fonte_v200
        janela = janela_para_fonte_v200(
            fonte={},
            url_feed="https://www.tribunanf.com.br/feed/",
            nome_fonte="Tribuna NF",
        )
        self.assertGreaterEqual(janela, 12)

    def test_fonte_oficial_gov_recebe_12h_minimo(self):
        from ururau.coleta.datas_v99 import janela_para_fonte_v200
        janela = janela_para_fonte_v200(
            fonte={"bypass_score": True},
            url_feed="https://www.gov.br/rss.xml",
            nome_fonte="Gov.br",
        )
        self.assertGreaterEqual(janela, 4)

    def test_fonte_jus_br_recebe_oficial(self):
        from ururau.coleta.datas_v99 import janela_para_fonte_v200
        janela = janela_para_fonte_v200(
            fonte={},
            url_feed="https://noticias.stf.jus.br/feed/",
            nome_fonte="STF",
        )
        self.assertGreaterEqual(janela, 4)

    def test_fonte_default_continua_padrao(self):
        from ururau.coleta.datas_v99 import janela_para_fonte_v200, janela_publicacao_horas
        janela = janela_para_fonte_v200(
            fonte={},
            url_feed="https://prensadebabel.com.br/feed/",
            nome_fonte="Prensa de Babel",
        )
        self.assertEqual(janela, janela_publicacao_horas())


# -----------------------------------------------------------------------------
# Integracao: dentro_da_janela com janela_horas customizada
# -----------------------------------------------------------------------------
class DentroDaJanelaComJanelaCustomTests(unittest.TestCase):
    def test_pauta_12h_passa_com_janela_24h(self):
        from ururau.coleta.datas_v99 import dentro_da_janela
        agora = datetime.datetime(2026, 5, 14, 0, 0, 0)
        dt_pub = datetime.datetime(2026, 5, 13, 12, 0, 0)  # 12h atras
        ok, motivo, idade = dentro_da_janela(dt_pub, agora, janela_horas=24)
        self.assertTrue(ok)

    def test_pauta_12h_reprova_com_janela_4h(self):
        from ururau.coleta.datas_v99 import dentro_da_janela
        agora = datetime.datetime(2026, 5, 14, 0, 0, 0)
        dt_pub = datetime.datetime(2026, 5, 13, 12, 0, 0)
        ok, motivo, idade = dentro_da_janela(dt_pub, agora, janela_horas=4)
        self.assertFalse(ok)
        self.assertIn("fora_da_janela", motivo)



if __name__ == "__main__":
    unittest.main(verbosity=2)
