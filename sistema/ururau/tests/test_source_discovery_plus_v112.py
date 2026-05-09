import textwrap

from ururau.coleta import source_discovery_plus_v112 as plus


def test_clean_url_remove_tracking_params():
    url = "https://exemplo.com/noticias/campos-materia?utm_source=x&fbclid=abc&id=10"
    cleaned = plus.clean_url(url)
    assert "utm_source" not in cleaned
    assert "fbclid" not in cleaned
    assert "id=10" in cleaned


def test_looks_like_article_url_aceita_slug_jornalistico():
    assert plus.looks_like_article_url(
        "https://site.com.br/noticias/campos-tem-operacao-policial-no-centro"
    )


def test_looks_like_article_url_recusa_assets_e_paginas_institucionais():
    assert not plus.looks_like_article_url("https://site.com.br/wp-content/uploads/foto.jpg")
    assert not plus.looks_like_article_url("https://site.com.br/contato")


def test_common_feed_candidates_inclui_feed_e_rss():
    candidatos = plus.common_feed_candidates("https://site.com.br/")
    assert "https://site.com.br/feed/" in candidatos
    assert "https://site.com.br/rss" in candidatos


def test_discover_article_links_from_html_prioriza_links_de_noticia():
    html = """
    <html><body>
      <nav><a href="/contato">Contato</a></nav>
      <main>
        <a href="/noticias/campos-tem-nova-operacao-da-policia-no-centro">
          Campos tem nova operação da polícia no Centro
        </a>
        <a href="/tag/campos">Tag Campos</a>
      </main>
    </body></html>
    """
    links = plus.discover_article_links_from_html(html, "https://site.com.br/", 5)
    assert links
    assert links[0][0].endswith("/noticias/campos-tem-nova-operacao-da-policia-no-centro")


def test_parse_feed_items_normaliza_pauta():
    xml = textwrap.dedent("""
    <rss version="2.0">
      <channel>
        <title>Fonte Teste</title>
        <item>
          <title>Campos registra nova pauta relevante</title>
          <link>https://site.com.br/noticias/campos-registra-nova-pauta-relevante?utm_source=rss</link>
          <description>Resumo da pauta regional</description>
          <pubDate>Wed, 29 Apr 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """)
    fonte = {"nome": "Fonte Teste", "canal_forcado": "Cidades", "peso": 10, "regiao": "campos_norte_fluminense"}
    pautas = plus.parse_feed_items(xml, fonte, max_items=3)
    assert len(pautas) == 1
    pauta = pautas[0]
    assert pauta["fonte_tipo"] == "source_discovery_plus"
    assert pauta["canal_sugerido"] == "Cidades"
    assert "utm_source" not in pauta["url"]
    assert 0 <= pauta["score"] <= 100


def test_deduplicar_pautas_source_plus_mantem_maior_score():
    pautas = [
        {"url": "https://site.com.br/noticias/a?utm_source=x", "score": 60, "titulo": "A"},
        {"url": "https://site.com.br/noticias/a", "score": 90, "titulo": "A melhor"},
    ]
    dedup = plus.deduplicar_pautas_source_plus(pautas)
    assert len(dedup) == 1
    assert dedup[0]["score"] == 90
