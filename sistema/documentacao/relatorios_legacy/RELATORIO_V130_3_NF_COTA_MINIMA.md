# v130.3 — NF Notícias como Fonte Especial e cota mínima por fonte funcional

## Objetivo

1. Promover NF Notícias para Fontes Especiais, por ser fonte regional factual/policial de Campos e Norte Fluminense.
2. Impedir que matéria factual de interesse caia fora da fila apenas por score baixo.
3. Garantir que toda fonte cadastrada que funcione tente trazer ao menos 2 matérias de interesse, quando houver itens elegíveis.

## Regras aplicadas

- `NF Notícias|https://www.nfnoticias.com.br/rss/` foi incluída em `fontes_especiais_v129.json`.
- Fontes especiais continuam passando por deduplicação, janela de publicação, bloqueio de assets/imagens e validação técnica.
- NF Notícias fica livre do corte de score baixo.
- A rotina v130.3 adiciona uma cota mínima por fonte funcional:
  - padrão: `URURAU_V1303_MIN_POR_FONTE_FUNCIONAL=2`;
  - ativa por padrão: `URURAU_V1303_COTA_MINIMA_INTERESSE=1`;
  - só promove item abaixo do score se houver sinal editorial mínimo.

## O que conta como interesse mínimo

- Fonte regional prioritária: NF Notícias, Campos 24 Horas, Prefeitura de Campos, J3, Portal Viu, O Debate, RJ News, O Parahybano etc.
- Termo ativo da aba Config > Termos.
- Factual policial: polícia, prisão, armas, tiros, drogas, operação, acidente, morte, roubo, furto.
- Política/gestão pública: prefeitura, câmara, vereador, deputado, governo, STF, STJ, TSE, MPRJ, TCE-RJ, licitação, fraude, orçamento, eleição.
- Território estratégico: Campos, Macaé, São João da Barra, São Francisco de Itabapoana, Norte Fluminense, Porto do Açu, Guarus etc.
- Esporte local/RJ: Flamengo, Vasco, Botafogo, Fluminense, Americano, Goytacaz/Goitacaz.

## Segurança

Não altera o motor de publicação, copydesk, WhatsApp, imagem, hidratação, Campos 24 Horas ou Manchete RJ.
