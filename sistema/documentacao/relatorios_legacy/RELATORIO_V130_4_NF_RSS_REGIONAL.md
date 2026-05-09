# v130.4 — NF Notícias RSS regional prioritário

## Objetivo

Corrigir o comportamento da v130.3 em que o NF Notícias foi movido para Fontes Especiais genéricas e passou a retornar 0 itens úteis.

## Correção

- NF Notícias saiu de Fontes Especiais genéricas.
- NF Notícias voltou para Fontes RSS como `rss_regional_prioritario_v1304`.
- A fonte usa o parser RSS normal, que já havia lido o feed corretamente.
- A fonte continua livre do corte de score baixo.
- A cota mínima de 2 matérias por fonte funcional continua ativa quando houver itens úteis.
- Se o usuário mantiver NF Notícias por engano na aba Fontes Especiais, o painel redireciona essa entrada para o parser RSS regional prioritário.

## Arquivos alterados

- `fontes_rss.json`
- `configuracoes/fontes_rss.json`
- `config/fontes_rss.json`
- `fontes_especiais_v129.json`
- `configuracoes/fontes_especiais_v129.json`
- `ururau/coleta/rss.py`
- `ururau/coleta/linha_editorial_v129.py`
- `ururau/ui/painel.py`

## Resultado esperado

No próximo diagnóstico, NF Notícias deve aparecer como:

```text
OK | NF Notícias | tipo=rss_regional_prioritario_v1304
```

ou, se não houver matéria nova, pelo menos com funil real do RSS comum, não mais como Fonte Especial genérica com 0 itens úteis.
