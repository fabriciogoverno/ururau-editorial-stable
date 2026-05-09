from ururau.ui.rss_url_grid_v119 import _extract_urls, _extract_xmls

def test_extract_limpa_numero_nome_canal():
    raw = "1 - https://j3news.com/feed/|J3 News|Estado RJ\n2  https://portalviu.com.br/feed/"
    assert _extract_urls(raw) == ["https://j3news.com/feed/", "https://portalviu.com.br/feed/"]

def test_extract_xml_separado():
    raw = "https://a.com/feed/\nhttps://b.com/sitemap.xml"
    assert _extract_urls(raw) == ["https://a.com/feed/"]
    assert _extract_xmls(raw) == ["https://b.com/sitemap.xml"]

def test_nao_entrega_numero_no_get_logico():
    raw = "10. https://g1.globo.com/rss/g1/politica/|G1 Política|Política"
    assert _extract_urls(raw)[0] == "https://g1.globo.com/rss/g1/politica/"
