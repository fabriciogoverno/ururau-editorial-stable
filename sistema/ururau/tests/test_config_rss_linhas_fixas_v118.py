from ururau.ui.config_rss_linhas_fixas_v118 import _internal_save_text, _visual_text, _urls_from_text

def test_salva_interno_sem_canal():
    raw = "1 - https://j3news.com/feed/|J3 News|Estado RJ\n2  https://portalviu.com.br/feed/"
    out = _internal_save_text(raw)
    assert "Estado RJ" not in out
    assert "https://j3news.com/feed/" in out
    assert out.splitlines()[0].endswith("|")

def test_visual_so_url():
    raw = "1 - https://j3news.com/feed/|J3 News|Estado RJ"
    assert _visual_text(raw) == "https://j3news.com/feed/"

def test_urls_remove_xml():
    raw = "https://a.com/feed/\nhttps://b.com/sitemap.xml"
    assert _urls_from_text(raw) == ["https://a.com/feed/"]
