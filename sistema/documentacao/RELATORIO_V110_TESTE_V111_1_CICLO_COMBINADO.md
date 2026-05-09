# Relatório — v110 teste com v111.1 Ciclo Combinado

## Objetivo

Aplicar sobre a última v110 teste a melhoria sugerida pelo Kimi: ciclo combinado de coleta do Google News, usando termos prioritários e grupos temáticos do `consultas_google_news.json`.

## Arquivos adicionados

- `ururau/publisher/monitor_v111_ciclo_combinado.py`
- `ururau/tests/test_v111_1_ciclo_combinado.py`
- `SPEC.md`
- `SPEC_V111_1_CICLO_COMBINADO.md`
- `.env.v111_1_adicional`

## Arquivos alterados

- `.env`
- `.env.exemplo`
- `ururau/publisher/monitor_v111_patch.py`

## Comportamento novo

Quando `URURAU_V111_GNEWS_INTEGRADO=1` e `URURAU_V111_USAR_CICLO_COMBINADO=1`, o monitor usa o ciclo combinado v111.1:

1. coleta por termos do radar;
2. coleta por grupos temáticos;
3. deduplica URLs, mantendo maior score;
4. filtra pela janela temporal;
5. aplica score mínimo;
6. hidrata texto/imagem quando necessário;
7. entrega campos modernos e legados para o pipeline.

## Rollback

Voltar ao v111 base:

```env
URURAU_V111_USAR_CICLO_COMBINADO=0
```

Voltar ao v110 legado:

```env
URURAU_V111_GNEWS_INTEGRADO=0
URURAU_V110_MONITOR_GNEWS_LEGADO=1
```

## Validação local esperada

```powershell
python -m compileall google_news_scraper ururau
pytest ururau/tests/test_gnews_v111.py ururau/tests/test_v111_1_ciclo_combinado.py -q
```

