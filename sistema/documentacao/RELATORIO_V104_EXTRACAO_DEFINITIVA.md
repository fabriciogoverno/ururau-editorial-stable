# URURAU v104 — Extração definitiva de texto completo

## Problema corrigido

O painel e o monitor estavam aceitando snippet/RSS curto como se fosse texto completo da fonte. Em alguns casos, a aba Fonte devolvia 127 caracteres e o workflow marcava a extração como `ok`, permitindo que a IA redigisse matéria com um parágrafo ou conteúdo insuficiente.

## Causa principal localizada

1. `leitura_fonte.py` aceitava qualquer `texto_preextraido` com 120 caracteres ou mais e retornava sem abrir a URL real.
2. `workflow.py` promovia a leitura da aba Fonte para `status=ok` mesmo quando ela retornava texto curto.
3. O guard do monitor v83 exigia método literal `url_scraping`, mas os extratores novos retornavam métodos como `requests:html_density`, `v104_requests:jsonld_articleBody` ou `v104_wordpress_rest`.
4. O extrator antigo não tentava WordPress REST API, que resolve muitos sites locais/parceiros.

## Solução aplicada

Criado `ururau/coleta/fonte_extractor_v104.py` com cascata de captura:

1. resolução de URL final/canonical;
2. HTML direto com headers de navegador;
3. JSON-LD `NewsArticle`/`Article`;
4. JSONs embutidos, incluindo `__NEXT_DATA__`;
5. WordPress REST API por slug e por busca de título;
6. seleção por densidade textual em containers de artigo;
7. Playwright público como fallback;
8. texto pré-extraído só é aceito quando já é corpo longo.

## Regras novas

- Snippet/RSS curto não vira fonte completa.
- Texto com menos de 900 caracteres úteis não deve gerar matéria automática.
- Monitor 24h exige fonte mais robusta: mínimo de 1.200 caracteres úteis quando possível.
- Se a extração falhar, o robô bloqueia a publicação/redação automática em vez de gerar matéria fraca.

## Arquivos alterados

- `ururau/coleta/fonte_extractor_v104.py`
- `ururau/coleta/scraping.py`
- `ururau/coleta/leitura_fonte.py`
- `ururau/coleta/fail_closed_v83.py`
- `ururau/coleta/fail_closed_v84.py`
- `ururau/publisher/workflow.py`
- `.env`

## Logs esperados

- `[V104][FONTE] OK ... chars via v104_wordpress_rest`
- `[V104][FONTE] OK ... chars via v104_requests:html_density`
- `[LEITURA_FONTE][v104] OK ... chars`
- `v104 recusou fonte curta (... chars); não gera matéria por snippet`

