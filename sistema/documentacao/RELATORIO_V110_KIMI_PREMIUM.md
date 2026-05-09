# RELATÓRIO v110 — Integração Kimi Premium no motor de coleta

## Objetivo
A v110 mantém a base estável da v109 e integra, de forma operacional, os recursos úteis do projeto Kimi `google_news_scraper` diretamente no motor do Ururau.

## O que foi implementado

1. **Ponte operacional Kimi v110**
   - Novo arquivo: `ururau/coleta/kimi_bridge_v110.py`.
   - Conecta o pacote `ururau/vendor/google_news_scraper` ao formato real de pauta do Ururau.
   - Usa busca Google News por HTML + RSS, deduplicação e resolução de link público.
   - Usa `ArticleExtractor` do Kimi como fallback avançado de leitura de matéria.

2. **Google News mais forte no painel**
   - `ururau/coleta/google_news_scraper_v108.py` agora mantém a coleta RSS da v109 e acrescenta a camada Kimi v110.
   - A coleta por termos passa a usar duas camadas: RSS resiliente e HTML+RSS do Kimi.
   - Links duplicados são consolidados antes de entrar na fila.

3. **Google News mais seguro no monitor 24h**
   - `ururau/publisher/monitor.py` agora usa primeiro o motor Kimi v110.
   - O Google News legado no monitor fica opcional por `URURAU_V110_MONITOR_GNEWS_LEGADO=1`, evitando ruído e links `news.google.com` não resolvidos.

4. **HTTP resiliente aplicado no extrator principal**
   - `ururau/coleta/fonte_extractor_v104.py` passou a usar `http_fetch_v109` também no `_fetch()` principal.
   - Com isso, o motor de extração usa rotação de User-Agent, retry/backoff, pacing por domínio e cooldown para 429.

5. **Extração premium por ArticleExtractor**
   - `fonte_extractor_v104.py` ganhou a etapa `_extrair_kimi_v110()` antes do fallback v108 e antes do WordPress REST.
   - O fluxo agora tenta: v86 legado, HTML direto resiliente, Kimi ArticleExtractor, trafilatura/readability v108, WordPress REST, Playwright e pré-extraído longo.

6. **RSS Google News legado reforçado**
   - `ururau/coleta/rss.py` usa `fetch_rss_v109()` ao consultar Google News.
   - O link de pauta passa a ser resolvido para a fonte pública real quando possível.

7. **Dependências e variáveis**
   - `requirements.txt` recebeu `pydantic>=2.0.0`, necessário para os modelos do pacote Kimi.
   - `.env` e `.env.exemplo` receberam as chaves v110.

## Principais variáveis novas

```env
URURAU_V110_KIMI_GNEWS_HTML=1
URURAU_V110_KIMI_MAX_RESULTADOS_POR_TERMO=3
URURAU_V110_KIMI_PERMITIR_SEM_DATA=0
URURAU_V110_USAR_KIMI_EXTRACTOR=1
URURAU_V110_KIMI_MIN_CHARS=900
URURAU_V110_KIMI_TIMEOUT=14
URURAU_V110_KIMI_RETRIES=3
URURAU_V110_KIMI_BACKOFF=1.7
URURAU_V110_KIMI_CONCURRENCY=4
URURAU_V110_KIMI_DELAY=0.4
URURAU_V110_MONITOR_GNEWS_LEGADO=0
URURAU_V110_HTTP_FALLBACK_LEGADO=1
URURAU_V110_KIMI_PROXY=
```

## Segurança operacional

- Não remove recursos existentes.
- Não quebra paywall.
- Não faz login externo.
- Não burla bloqueios de autenticação.
- Mantém fallback legado se a camada HTTP resiliente falhar.
- Mantém filtro de janela temporal e deduplicação antes de salvar na fila.

## Resultado esperado

A v110 deve capturar mais pautas úteis sem aumentar ruído de links inválidos, porque combina:

- RSS tradicional;
- Google News por termos;
- Google News HTML+RSS do pacote Kimi;
- resolução de link real;
- extração estruturada com trafilatura/readability;
- HTTP resiliente aplicado no motor principal.
