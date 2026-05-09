# SPEC.md — Ururau v110 teste + v111.2 Plus Source Hunter

## 1. Objetivo

Aplicar diretamente no projeto Ururau as soluções técnicas reais identificadas nos projetos `newspaper`, `newspaper4k` e `meridian`, para aumentar a capacidade de coleta, captura, hidratação de texto e recuperação de imagens de matérias públicas.

A entrega mantém a base já aprovada da **v110 teste + v111.1 Ciclo Combinado** e adiciona uma camada **v111.2 Plus**, sem remover o fluxo legado.

## 2. Escopo

### Incluído

1. Reforço do `google_news_scraper/extractor.py`:
   - novo fallback `newspaper_plus`;
   - score textual por densidade, stopwords, link density e classes positivas/negativas;
   - complementação por parágrafos irmãos;
   - extração ampliada de imagem por OpenGraph, Twitter Card, JSON-LD, `srcset`, `data-src` e `link image_src`;
   - enriquecimento de metadados em todos os métodos da cascata.

2. Novo coletor complementar:
   - `ururau/coleta/source_discovery_plus_v112.py`;
   - leitura de `fontes_rss.json`, `fontes_oficiais_prioritarias.json` e, opcionalmente, `portais_referencia_cobertura.json`;
   - descoberta de feeds comuns: `/feed/`, `/rss`, `/rss.xml`, `/atom.xml`, `/noticias/rss`, `?feed=rss2`;
   - fallback por homepage/categorias públicas;
   - filtragem de URLs com heurística jornalística inspirada em `newspaper.urls.valid_url`;
   - cooldown por domínio inspirado no `DomainRateLimiter` do Meridian;
   - deduplicação por URL limpa, removendo `utm_*`, `fbclid`, `gclid` etc.;
   - hidratação usando `ArticleExtractor`.

3. Integração no ciclo combinado:
   - `ururau/publisher/monitor_v111_ciclo_combinado.py` agora soma:
     - termos prioritários;
     - grupos temáticos do Google News;
     - RSS/fontes públicas/homepages pelo Source Hunter Plus.

4. Novos testes:
   - `ururau/tests/test_source_discovery_plus_v112.py`;
   - `ururau/tests/test_extractor_newspaper_plus_v112.py`.

5. Variáveis `.env` novas:
   - `URURAU_PLUS_SOURCE_HUNTER`;
   - limites de fonte, concorrência, timeout, hidratação e uso opcional de portais de referência.

## 3. Fora do escopo

- Não faz login em sites.
- Não quebra paywall.
- Não usa proxy pago.
- Não usa APIs pagas.
- Não substitui v108/v109/v110/v111.1.
- Não publica automaticamente por causa dessa camada; ela apenas fornece pautas ao fluxo existente.

## 4. Arquivos alterados

### `google_news_scraper/extractor.py`

Implementa o fallback `newspaper_plus` e a fusão de metadados/imagens.

Ordem final da cascata:

1. `trafilatura`;
2. `readability`;
3. `jsonld`;
4. `bs4_density`;
5. `newspaper_plus`;
6. `wordpress_rest`.

### `ururau/publisher/monitor_v111_ciclo_combinado.py`

Inclui etapa Source Hunter Plus quando:

```env
URURAU_PLUS_SOURCE_HUNTER=1
```

### `.env` e `.env.exemplo`

Incluem variáveis da v111.2 Plus.

### `VERSAO.txt`

Atualizado para identificar a revisão.

## 5. Arquivos novos

### `ururau/coleta/source_discovery_plus_v112.py`

Módulo de descoberta complementar por fontes públicas.

Funções principais:

```python
async def coletar_source_hunter_plus_v112(...)
async def hidratar_pautas_source_plus(...)
def clean_url(url)
def normalized_url_key(url)
def looks_like_article_url(url)
def common_feed_candidates(base_url)
def parse_feed_items(feed_xml, fonte, max_items)
def discover_article_links_from_html(html, base_url, max_items)
def deduplicar_pautas_source_plus(pautas)
```

### `ururau/tests/test_source_discovery_plus_v112.py`

Testes unitários sem rede para URL, feed, deduplicação e descoberta por HTML.

### `ururau/tests/test_extractor_newspaper_plus_v112.py`

Teste unitário do fallback `newspaper_plus`.

### `.env.v111_2_plus_adicional`

Bloco pronto para colar em `.env`.

## 6. Variáveis de ambiente

```env
# ===== v111.2 / Ururau Plus — Source Hunter público =====
URURAU_PLUS_SOURCE_HUNTER=1
URURAU_PLUS_MAX_FONTES=18
URURAU_PLUS_MAX_POR_FONTE=3
URURAU_PLUS_MAX_TOTAL=20
URURAU_PLUS_MAX_CONCORRENCIA=3
URURAU_PLUS_DOMAIN_COOLDOWN_MS=1800
URURAU_PLUS_FETCH_TIMEOUT=15
URURAU_PLUS_HIDRATAR_FONTES=1
URURAU_PLUS_MAX_HIDRATAR=12
URURAU_PLUS_HIDRATACAO_CONCORRENCIA=3
URURAU_PLUS_USAR_PORTAIS_REFERENCIA=0
```

## 7. Critérios de aceitação

1. `python -m compileall google_news_scraper ururau` não deve mostrar erro.
2. Os testes devem passar:
   ```powershell
   python -m pytest ururau/tests/test_gnews_v111.py ururau/tests/test_v111_1_ciclo_combinado.py ururau/tests/test_source_discovery_plus_v112.py ururau/tests/test_extractor_newspaper_plus_v112.py -q
   ```
3. O monitor deve mostrar logs:
   ```text
   [V111.1][INIT]
   [V111.2][SOURCE_PLUS]
   [V111.2][TOTAL]
   [V111][FONTE]
   ```
4. As pautas Source Plus devem sair com os campos:
   - `titulo`;
   - `url`;
   - `dominio`;
   - `texto_fonte`;
   - `imagem`;
   - `imagens`;
   - `score`;
   - `canal_sugerido`;
   - `fonte_tipo=source_discovery_plus`.

## 8. Teste local recomendado no Windows

```powershell
cd "C:\Users\fabri\Downloads\ururau_v110_teste_plus_source_hunter\ururau_v110_teste"

python -m pip install -r requirements.txt

python -m compileall google_news_scraper ururau

python -m pytest ururau/tests/test_gnews_v111.py ururau/tests/test_v111_1_ciclo_combinado.py ururau/tests/test_source_discovery_plus_v112.py ururau/tests/test_extractor_newspaper_plus_v112.py -q
```

## 9. Teste real de coleta sem publicação

No `.env`, mantenha:

```env
URURAU_V111_GNEWS_INTEGRADO=1
URURAU_V111_USAR_CICLO_COMBINADO=1
URURAU_PLUS_SOURCE_HUNTER=1
URURAU_PLUS_HIDRATAR_FONTES=1
```

Abra o painel/monitor e confira se as pautas chegam à fila com texto e imagem.

## 10. Rollback

### Voltar para v111.1 sem Source Hunter Plus

```env
URURAU_PLUS_SOURCE_HUNTER=0
```

### Voltar para v111 base sem ciclo combinado

```env
URURAU_V111_USAR_CICLO_COMBINADO=0
URURAU_PLUS_SOURCE_HUNTER=0
```

### Voltar para v110 legado

```env
URURAU_V111_GNEWS_INTEGRADO=0
URURAU_V110_MONITOR_GNEWS_LEGADO=1
```

## 11. Observações técnicas

- A v111.2 usa apenas páginas públicas, RSS e homepages.
- A camada não depende de `newspaper` ou `newspaper4k` instalados; as heurísticas foram incorporadas em código próprio.
- `feedparser` é usado se disponível, mas há fallback BS4/XML para RSS simples.
- A deduplicação por URL limpa foi aplicada para reduzir repetição causada por parâmetros de rastreamento.
- A hidratação é limitada por variáveis de ambiente para não sobrecarregar fontes nem deixar o ciclo lento.
