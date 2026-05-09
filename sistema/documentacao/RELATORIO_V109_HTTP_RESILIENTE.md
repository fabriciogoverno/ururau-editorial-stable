# RELATÓRIO v109 — HTTP resiliente integrado

## Objetivo

Conectar de forma real ao fluxo do Ururau os recursos que estavam disponíveis no vendor `google_news_scraper`, mas ainda não estavam plenamente usados pelo adaptador principal: rotação de User-Agent, retry com backoff e cooldown de domínio em respostas 429.

## Arquivos criados

- `ururau/coleta/http_fetch_v109.py`

## Arquivos alterados

- `ururau/coleta/google_news_scraper_v108.py`
- `ururau/coleta/trafilatura_fallback_v108.py`
- `ururau/ui/painel.py`
- `.env`
- `.env.exemplo`
- `VERSAO.txt`

## O que mudou

1. Google News por Termos agora busca o RSS usando `fetch_rss_v109()`, em vez de deixar o `feedparser` abrir a URL sem headers, sem retry e sem backoff.
2. O resolvedor de links do Google News agora usa `fetch_text_v109()` com User-Agent rotativo, retry e backoff.
3. O fallback `trafilatura/readability` agora usa `fetch_html_v109()` para acessar as páginas públicas das matérias.
4. Em resposta HTTP 429, o domínio entra em cooldown para evitar múltiplas requisições repetidas em sequência.
5. Há delay mínimo por domínio para reduzir rajadas de acesso.
6. Logs foram ajustados para `[GNEWS v109]` na etapa de busca por termos.

## Flags adicionadas

```env
URURAU_V109_HTTP_FETCH=1
URURAU_V109_HTTP_ROTATE_UA=1
URURAU_V109_HTTP_MAX_RETRIES=3
URURAU_V109_HTTP_BACKOFF=1.7
URURAU_V109_HTTP_MAX_SLEEP=12
URURAU_V109_HTTP_TIMEOUT=14
URURAU_V109_HTTP_DELAY_DOMINIO=0.35
URURAU_V109_HTTP_COOLDOWN_429_SEG=180
URURAU_V109_HTTP_RESPEITAR_COOLDOWN=1
URURAU_V109_HTTP_LOG=0
URURAU_V109_GNEWS_RSS_TIMEOUT=12
URURAU_V109_GNEWS_RSS_RETRIES=3
URURAU_V109_GNEWS_RESOLVE_RETRIES=3
```

## Observação operacional

A v109 não quebra paywall, não faz login e não tenta acessar conteúdo restrito. A correção melhora a robustez das requisições públicas e reduz falhas por timeout, 5xx e rajadas que provocam 429.
