import pytest

from google_news_scraper.extractor import ArticleExtractor
from google_news_scraper.models import ScraperConfig


@pytest.mark.asyncio
async def test_newspaper_plus_extrai_texto_imagem_autor_data():
    html = """
    <html>
      <head>
        <title>Título de teste - Site</title>
        <meta property="og:title" content="Título de teste">
        <meta property="og:image" content="/imagens/foto-principal.jpg">
        <meta name="author" content="Redação Teste">
        <meta property="article:published_time" content="2026-04-29T12:00:00Z">
      </head>
      <body>
        <nav>Menu inútil</nav>
        <div class="materia principal">
          <p>A Prefeitura de Campos informou nesta quarta-feira que uma nova operação será realizada no Centro da cidade.</p>
          <p>Segundo a administração municipal, a medida envolve equipes de fiscalização, trânsito e segurança pública.</p>
          <p>O objetivo é organizar o fluxo de veículos e ampliar a presença dos agentes nos pontos de maior movimento.</p>
          <p>A ação também terá acompanhamento de órgãos estaduais e deve continuar durante o fim de semana.</p>
        </div>
        <aside>Publicidade</aside>
      </body>
    </html>
    """
    extractor = ArticleExtractor(ScraperConfig(min_article_chars=180))
    result = await extractor._extract_newspaper_plus(html, "https://site.com.br/noticias/teste")
    result = extractor._merge_html_metadata(result, html, "https://site.com.br/noticias/teste")
    assert result["article_text"]
    assert result["author"] == "Redação Teste"
    assert result["images"][0] == "https://site.com.br/imagens/foto-principal.jpg"
    assert result["title"] == "Título de teste"
