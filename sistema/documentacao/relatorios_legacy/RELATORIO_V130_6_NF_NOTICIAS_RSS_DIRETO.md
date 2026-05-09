# v130.6 — NF Notícias com parser RSS direto

## Problema corrigido

O diagnóstico do próprio NF Notícias mostrou que `https://www.nfnoticias.com.br/rss/` é RSS válido, com 16 itens, 16 com título/link e 9 dentro da janela. Mesmo assim, a coleta regional v130.5 registrava `brutas=0` e `enviadas=0`.

## Correção

Foi criado o adaptador:

`ururau/coleta/adapters/nfnoticias_v1306.py`

Ele lê o XML do RSS diretamente, extrai `<item>`, `<title>`, `<link>`, `<description>`, `<pubDate>` e `<enclosure>`, aceita links com e sem `www`, normaliza data em Brasília e retorna pautas no formato esperado pela fila.

## Integração

A aba **Regionais** continua existindo. Quando a fonte for NF Notícias, o painel usa o adaptador v130.6. As demais fontes regionais continuam no fluxo v130.5.

## Resultado esperado no diagnóstico

O NF Notícias deve aparecer como:

`tipo=regional_nfnoticias_v1306`

E a observação deve mostrar:

`rss_items=... | titulo_link=... | fora_janela=... | aceitas=...`

