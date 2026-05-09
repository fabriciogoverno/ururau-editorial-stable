# SPEC.md — Integração Google News Scraper → Ururau
> **Versão:** 1.0 | **Data:** 2026-04-29 | **Status:** Aprovado

---

## 1. Objetivo

Produzir o artefato de integração que permite ao sistema **Ururau** (monitor de notícias do RJ) utilizar o pacote `google_news_scraper` como **fonte de coleta consolidada**, substituindo as camadas legadas v108+v109+v110 por uma única interface operacional.

---

## 2. Contexto do Sistema Ururau

O Ururau é um sistema de monitoramento e publicação automática de notícias focado no estado do Rio de Janeiro (Campos dos Goytacazes, Norte Fluminense). Evoluiu de v81 até v110 com as seguintes camadas de coleta Google News:

| Versão | Componente | Função |
|--------|-----------|--------|
| v108 | `google_news_scraper_v108.py` | Busca Google News por termos + trafilatura fallback |
| v109 | `http_fetch_v109.py` | HTTP resiliente (retry, UA rotation, cooldown 429) |
| v110 | `kimi_bridge_v110.py` | Ponte com projeto Kimi google_news_scraper |
| **v111** | **`google_news_integrado.py`** | **Interface única que consolida tudo** |

### Arquivos de Configuração do Ururau

```
radar_audiencia_config_v88.json      → termos_prioritarios, termos_baixa_prioridade
aliases_editoriais.json              → aliases de nomes, contexto obrigatório
consultas_google_news.json           → grupos temáticos com queries pré-definidas
fontes_oficiais_prioritarias.json    → fontes oficiais (ALERJ, TCE-RJ, MPRJ, etc.)
portais_referencia_cobertura.json    → portais de referência para medir vácuo
fontes_rss.json                      → feeds RSS locais e nacionais
.env                                 → todas as flags v102-v110
```

---

## 3. O que já existe (pacote google_news_scraper)

O pacote já foi desenvolvido e testado (74/74 testes passando). Estrutura:

```
google-news-scraper/
├── src/google_news_scraper/
│   ├── __init__.py              # API pública
│   ├── models.py                # Pydantic v2: Article, SearchParams, ScraperConfig
│   ├── config.py                # 12 UAs, blacklist, URLs Google News
│   ├── scraper.py               # GoogleNewsScraper (RSS + HTML)
│   ├── extractor.py             # ArticleExtractor (5 métodos em cascata)
│   ├── utils.py                 # retry/backoff, DomainCooldown, dedup
│   ├── cli.py                   # CLI Click
│   ├── logger.py                # Logging
│   └── google_news_integrado.py # 🎯 Módulo de integração Ururau
├── tests/                       # 74 testes
├── pyproject.toml
└── README.md
```

### Cascata de Extração (já implementada)

```
URL → _fetch_html()
  → 1. trafilatura (primário)
  → 2. readability-lxml
  → 3. JSON-LD NewsArticle/Article
  → 4. BS4 density-based
  → 5. WordPress REST API
  → _post_process() → resultado
```

### Formatos de Dados

**Entrada: `SearchParams`**
```python
SearchParams(
    query="Porto do Açu",      # termo de busca
    max_results=10,             # 1-100
    from_date="2026-01-01",     # opcional
    to_date="2026-04-29",       # opcional
    country="BR",               # BR, US, IN, GB, etc.
    language="pt",              # pt, en, es, fr, etc.
)
```

**Saída: `Article`**
```python
Article(
    title="Título",
    description="Resumo",
    author="Autor",
    published_date=datetime(2026, 4, 29, 10, 30),
    image="https://...",
    images=["https://..."],
    article_text="Texto completo...",
    url="https://exemplo.com/artigo",
    domain="exemplo.com",
    language="pt",
    source_type="google_news",
)
```

---

## 4. Especificação da Integração

### 4.1 O que deve ser criado no Ururau

Devem ser criados **3 arquivos** dentro da estrutura existente do Ururau:

#### Arquivo 1: `ururau/coleta/gnews_v111_integrado.py`

**Wrapper operacional** que encapsula o `GoogleNewsIntegrado` do pacote.

Responsabilidades:
- Carregar as configurações do Ururau (`.env`, JSONs)
- Chamar o `GoogleNewsIntegrado` com os parâmetros corretos
- Converter as pautas para o formato interno do Ururau (já feito no integrado)
- Logar no formato que o monitor espera (`[V111][GNEWS] ...`)
- Respeitar as flags do `.env` (janela temporal, max resultados, etc.)

Interface pública:
```python
async def coletar_pautas_gnews_v111(
    modo: str = "termos_config",  # "termos_config" | "termo_livre" | "grupo"
    termo: str = "",
    grupo: str = "",
    janela_horas: int = 4,
    max_resultados: int = 10,
) -> List[Dict[str, Any]]:
    """Retorna pautas prontas para o fluxo do Ururau."""

async def extrair_fonte_v111(url: str) -> Dict[str, Any]:
    """Extrai texto completo de uma URL. Retorna dict com texto, metodo, chars."""
```

#### Arquivo 2: `ururau/publisher/monitor_v111_patch.py`

**Monkey-patch / adaptador** que conecta o novo coletor ao `monitor.py` existente sem quebrar o fluxo legado.

Responsabilidades:
- Se `URURAU_V111_GNEWS_INTEGRADO=1`, usar o novo coletor
- Se `URURAU_V110_MONITOR_GNEWS_LEGADO=1`, manter comportamento v110
- Chamar `coletar_pautas_gnews_v111()` e injetar as pautas na fila do monitor
- Garantir que o formato da pauta seja compatível com as etapas seguintes (Copydesk, quality gate, CMS)

#### Arquivo 3: `ururau/ui/painel_v111_tab.py`

**Aba no painel web** (se houver) que permite:
- Selecionar grupo temático para coleta manual
- Buscar por termo livre
- Ver resultados com score e preview
- Adicionar pauta à fila com um clique

### 4.2 Formato da Pauta (saída da integração)

A pauta que entra na fila do Ururau deve ter **exatamente** estes campos:

```python
{
    "id": str,                          # gerado pelo Ururau
    "titulo": str,                      # Article.title
    "descricao": str,                   # Article.description
    "url": str,                         # URL real (não news.google.com)
    "dominio": str,                     # Article.domain
    "autor": str,                       # Article.author
    "data_publicacao": str,             # ISO 8601
    "imagem": str,                      # URL da imagem principal
    "imagens": List[str],               # todas as imagens
    "texto_fonte": str,                 # Article.article_text
    "canal_sugerido": str,              # mapeado do grupo
    "score": int,                       # 0-100 (calculado)
    "fonte_tipo": "google_news",        # identificador
    "termo_busca": str,                 # qual termo gerou
    "metodo_extracao": str,             # trafilatura|readability|jsonld|bs4|wordpress
    "chars_fonte": int,                 # len(texto_fonte)
    "cidade": str,                      # mapeada do grupo
    "regiao": str,                      # mapeada do grupo
    "coletado_em": str,                 # ISO 8601
    "status": "pendente",               # pendente|hidratação|ok|erro
}
```

### 4.3 Mapeamento de Grupos → Canal/Região/Cidade

| Grupo | Canal Sugerido | Região | Cidade |
|-------|---------------|--------|--------|
| `alerj` | Política | Rio de Janeiro | Rio de Janeiro |
| `campos_local` | Cidades | Norte Fluminense | Campos dos Goytacazes |
| `norte_fluminense` | Cidades | Norte Fluminense | Campos dos Goytacazes |
| `porto_do_acu` | Economia | Norte Fluminense | São João da Barra |
| `rj_politica` | Política | Rio de Janeiro | Rio de Janeiro |
| `rj_policia` | Polícia | Rio de Janeiro | Rio de Janeiro |
| `governo_rj` | Estado RJ | Rio de Janeiro | Rio de Janeiro |
| `deputados_rj` | Política | Rio de Janeiro | Rio de Janeiro |
| `pre_candidatos_governo_rj` | Política | Rio de Janeiro | Rio de Janeiro |
| `servico_brasil` | Serviço | Nacional | — |
| `alto_trafego_brasil` | Brasil | Nacional | — |
| `alertas_globais` | Brasil e Mundo | Internacional | — |
| `utilidade_publica_rj` | Estado RJ | Rio de Janeiro | Rio de Janeiro |
| `transparencia_e_investigacao` | Política | Rio de Janeiro | Rio de Janeiro |

### 4.4 Cálculo de Score Editorial (0-100)

```python
score = 50  # base

# +20 se domínio está em fontes_oficiais_prioritarias
# +15 se termo está em termos_prioritarios
# +10 se chars_fonte > 2000 (+5 se > 1200)
# +15 se publicado há < 1h (+8 se < 2h)
# +10 se tem autor identificado
# +5 se tem imagem
# +5 se canal está definido

score = min(100, score)
```

### 4.5 Variáveis de Ambiente (.env)

```env
# ===== v111 — Integração Google News Scraper =====
URURAU_V111_GNEWS_INTEGRADO=1
URURAU_V111_GNEWS_MAX_TERMOS_POR_CICLO=20
URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO=3
URURAU_V111_GNEWS_JANELA_HORAS=4
URURAU_V111_GNEWS_MIN_CHARS_FONTE=1200
URURAU_V111_USAR_EXTRACAO_COMPLETA=1
URURAU_V111_SCORE_MINIMO_PAUTA=65

# Flags de compatibilidade (mantém fallback legado)
URURAU_V110_MONITOR_GNEWS_LEGADO=0
URURAU_V108_GNEWS_TERMOS=0
URURAU_V105_USAR_BING_NEWS=0
```

### 4.6 Fluxo de Dados (Diagrama)

```
┌─────────────────────────────────────────────────────────────┐
│                     CICLO DO MONITOR                         │
│                         (a cada 30 min)                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. CARREGA CONFIGS                                          │
│     • consultas_google_news.json                            │
│     • aliases_editoriais.json                               │
│     • radar_audiencia_config_v88.json                       │
│     • fontes_oficiais_prioritarias.json                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. EXPANDE ALIASES                                          │
│     "porto do açu" → ["porto do açu", "porto do acu",       │
│                       "porto açu", "prumo"]                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. BUSCA GOOGLE NEWS (async, max 3 concorrentes)            │
│     • RSS primeiro → HTML fallback                           │
│     • Resolve news.google.com → URL real                   │
│     • Deduplica por URL                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. EXTRAI TEXTO COMPLETO (se URURAU_V111_USAR_EXTRACAO=1)   │
│     Cascata: trafilatura → readability → jsonld → bs4 → wp  │
│     Mínimo: URURAU_V111_GNEWS_MIN_CHARS_FONTE chars          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. FILTRA & SCORE                                           │
│     • Janela temporal (4h)                                  │
│     • Score editorial (0-100)                               │
│     • Mínimo score: URURAU_V111_SCORE_MINIMO_PAUTA           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  6. ADICIONA À FILA DO URURAU                                │
│     • Formato: dict padrão (ver seção 4.2)                  │
│     • Status: "pendente" → "hidratação" → "ok"              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  7. FLUXO EXISTENTE DO URURAU                                │
│     • Copydesk IA (v102)                                    │
│     • Quality Gate (v103)                                   │
│     • Auditoria factual (v81)                               │
│     • Decisão: publicar / rascunho / bloquear               │
│     • Envio ao CMS                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Checklist de Implementação

### Fase 1: Preparação
- [ ] Copiar pasta `src/google_news_scraper/` para dentro do projeto Ururau
- [ ] Instalar dependências: `pip install pydantic aiohttp beautifulsoup4 lxml click`
- [ ] (Opcional) `pip install trafilatura readability-lxml` para extração premium
- [ ] Adicionar variáveis v111 ao `.env`

### Fase 2: Wrapper
- [ ] Criar `ururau/coleta/gnews_v111_integrado.py`
- [ ] Implementar `coletar_pautas_gnews_v111()`
- [ ] Implementar `extrair_fonte_v111()`
- [ ] Testar carregamento dos JSONs de config

### Fase 3: Integração com Monitor
- [ ] Criar/adaptar `ururau/publisher/monitor_v111_patch.py`
- [ ] No início do ciclo do monitor, verificar `URURAU_V111_GNEWS_INTEGRADO`
- [ ] Se ativo, chamar o novo coletor e adicionar pautas à fila
- [ ] Manter fallback para v110 se `URURAU_V110_MONITOR_GNEWS_LEGADO=1`

### Fase 4: Validação
- [ ] Rodar ciclo de monitor com `URURAU_V111_GNEWS_INTEGRADO=1` (sem publicar)
- [ ] Verificar logs: `[V111][GNEWS]` presentes
- [ ] Verificar que pautas têm `texto_fonte` com > 1200 chars
- [ ] Verificar que score está sendo calculado
- [ ] Verificar que canal/região/cidade estão mapeados

### Fase 5: Go-live
- [ ] Desativar flags legadas: `URURAU_V108_GNEWS_TERMOS=0`, `URURAU_V110_KIMI_GNEWS_HTML=0`
- [ ] Ativar publicação automática
- [ ] Monitorar por 24h

---

## 6. Logs Esperados

```
[V111][GNEWS] Iniciando coleta por termos da watchlist
[V111][GNEWS] Termos ativos: ['anvisa', 'fgts', 'eduardo paes', ...]
[V111][GNEWS] Termo 'ALERJ': 3 entrada(s)
[V111][GNEWS] Termo 'Porto do Açu': 2 entrada(s)
[V111][GNEWS] Total bruto: 15 pautas
[V111][GNEWS] Após dedup: 12 pautas
[V111][GNEWS] Após filtro temporal: 8 pautas
[V111][FONTE] OK 3248 chars via trafilatura: https://folha1.com.br/...
[V111][FONTE] OK 1890 chars via jsonld: https://g1.globo.com/...
[V111][FONTE] CURTO 450 chars via bs4: https://exemplo.com/...
[V111][SCORE] ALERJ aprova... → 92 pts [Política]
[V111][FILA] Adicionada: ALERJ aprova... (score: 92)
```

---

## 7. Rollback

Se necessário voltar para v110:

```env
URURAU_V111_GNEWS_INTEGRADO=0
URURAU_V110_KIMI_GNEWS_HTML=1
URURAU_V110_MONITOR_GNEWS_LEGADO=1
```

---

## 8. Métricas de Sucesso

| Métrica | Alvo | Como medir |
|---------|------|-----------|
| Pautas coletadas / ciclo | > 5 | Logs do monitor |
| Texto fonte médio (chars) | > 1200 | Métrica no `chars_fonte` |
| Taxa de extração OK | > 70% | `% de pautas com chars > 1200` |
| Score médio | > 65 | Métrica no `score` |
| Falsos positivos | < 10% | Revisão manual amostral |
| Tempo de ciclo | < 5 min | Logs de timestamps |
