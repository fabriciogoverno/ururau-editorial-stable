from ururau.config.fontes_config_url_simples_v120 import fontes_para_json, sitemap_para_lista
from ururau.ui.url_priority_grid_v120 import _extract_urls

def test_feed_xml_continua_rss():
    fontes, xmls = fontes_para_json("https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml\nhttps://www12.senado.leg.br/noticias/rss.xml")
    assert len(fontes) == 2
    assert xmls == []

def test_sitemap_vai_para_xml():
    fontes, xmls = fontes_para_json("https://campos24horas.com.br/noticia/sitemap.xml")
    assert fontes == []
    assert xmls == ["https://campos24horas.com.br/noticia/sitemap.xml"]

def test_grid_limpa_nome_canal():
    raw = "1 - https://j3news.com/feed/|J3 News|Estado RJ"
    assert _extract_urls(raw, mode="rss") == ["https://j3news.com/feed/"]

def test_grid_sitemap_mode():
    raw = "https://j3news.com/feed/\nhttps://campos24horas.com.br/noticia/sitemap.xml"
    assert _extract_urls(raw, mode="sitemap") == ["https://campos24horas.com.br/noticia/sitemap.xml"]
