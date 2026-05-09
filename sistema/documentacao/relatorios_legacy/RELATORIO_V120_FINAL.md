# Ururau v120 final organizado

## Alterações principais

- Aba **XML/Sitemap** criada no Config, ao lado de Fontes RSS.
- A aba XML/Sitemap usa a mesma lógica de prioridade por número fixo não editável.
- Fontes RSS continua com numeração fixa e aceita feeds XML reais, como `feed.xml` e `rss.xml`.
- Sitemap deixa de ser misturado com RSS comum.
- `campos24horas.com.br/noticia/sitemap.xml` e `www.campos24horas.com.br/sitemap.xml` já vêm cadastrados.
- `fontes_rss.json` já vem preenchido com 36 feeds revisados.
- `fontes_xml_sitemap_vfinal.txt` já vem preenchido com 2 sitemaps.
- Corrigido o erro grave de Redigir: `'function' object has no attribute 'EM_REDACAO'`.
- `dentro_da_janela(..., janela_horas=...)` corrigido para aceitar o argumento usado pelo Kimi/Google News.
- Configuração mantém `canal_forcado` vazio para a editoria ser definida pelo robô, não pela fonte.

## Validação

```powershell
cd sistema
python -m compileall ururau
python -m pytest ururau/tests/test_config_xml_sitemap_v120.py -q
```
