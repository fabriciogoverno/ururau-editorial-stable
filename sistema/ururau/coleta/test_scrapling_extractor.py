r"""
test_scrapling_extractor.py - Testes de validação da integração Scrapling.

Execute via:
    cd sistema
    python -m pytest ururau/coleta/test_scrapling_extractor.py -v
"""
import os
import sys
import unittest

# Garante que o pacote ururau está no path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ururau.coleta.scrapling_extractor import (
    UrurauScraplingExtractor, ScraplingResult, scrapling_para_dossie, SCRAPLING_DISPONIVEL
)


class TestScraplingExtractor(unittest.TestCase):

    @unittest.skipUnless(SCRAPLING_DISPONIVEL, "Scrapling nao instalado")
    def test_01_extrair_url_valida(self):
        """Testa extração de uma URL real de notícia."""
        ext = UrurauScraplingExtractor()
        url = "https://g1.globo.com/"
        res = ext.extrair(url)
        self.assertIsInstance(res, ScraplingResult)
        self.assertIn(res.metodo, [
            "scrapling_auto_extract",
            "scrapling_selectors",
            "scrapling_page_text",
            "scrapling_html_fallback",
            "scrapling_error",
        ])

    @unittest.skipUnless(SCRAPLING_DISPONIVEL, "Scrapling nao instalado")
    def test_02_extrair_url_vazia(self):
        """Testa comportamento com URL vazia."""
        ext = UrurauScraplingExtractor()
        res = ext.extrair("")
        self.assertFalse(res.ok)
        self.assertEqual(res.erro, "url_vazia")

    @unittest.skipUnless(SCRAPLING_DISPONIVEL, "Scrapling nao instalado")
    def test_03_para_dossie_estrutura(self):
        """Testa conversao para dict do pipeline Ururau."""
        res = ScraplingResult(
            ok=True,
            url_original="https://exemplo.com/noticia",
            url_final="https://exemplo.com/noticia",
            titulo="Titulo Teste",
            texto="Texto da matéria com conteúdo jornalístico.",
            imagem="https://exemplo.com/img.jpg",
            site_name="Exemplo",
            metodo="scrapling_auto_extract",
            status="ok",
            score=95,
            chars=50,
            util_chars=45,
        )
        dossie = scrapling_para_dossie(res, url="https://exemplo.com/noticia")
        self.assertEqual(dossie["extraction_method"], "scrapling_auto_extract")
        self.assertEqual(dossie["extraction_status"], "ok")
        self.assertIn("metadata", dossie)
        self.assertEqual(dossie["metadata"]["titulo"], "Titulo Teste")

    @unittest.skipUnless(SCRAPLING_DISPONIVEL, "Scrapling nao instalado")
    def test_04_extrair_campos24horas(self):
        """Testa extração do site parceiro Campos 24 Horas."""
        ext = UrurauScraplingExtractor()
        url = "https://www.campos24horas.com.br/"
        res = ext.extrair(url)
        self.assertIsInstance(res, ScraplingResult)
        print(f"[TESTE] Campos24Horas: ok={res.ok}, chars={res.util_chars}, metodo={res.metodo}")

    @unittest.skipUnless(SCRAPLING_DISPONIVEL, "Scrapling nao instalado")
    def test_05_extrair_nfnoticias(self):
        """Testa extração do site parceiro NF Notícias."""
        ext = UrurauScraplingExtractor()
        url = "https://nfnoticias.com.br/"
        res = ext.extrair(url)
        self.assertIsInstance(res, ScraplingResult)
        print(f"[TESTE] NFNoticias: ok={res.ok}, chars={res.util_chars}, metodo={res.metodo}")

    def test_06_scrapling_disponivel(self):
        """Verifica se Scrapling está instalado no ambiente."""
        self.assertTrue(SCRAPLING_DISPONIVEL, "Scrapling nao está instalado. Execute: pip install scrapling[fetchers]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
