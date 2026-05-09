# RELATÓRIO V129 — Linha editorial ampliada, Fontes Especiais e Baixo Score auditável

## Objetivo

Implementar a organização sugerida:

1. Manter **Fontes RSS** como configuração normal.
2. Manter **XML/Sitemap** como configuração normal.
3. Criar a aba **Fontes Especiais** para fontes oficiais/políticas que não devem ser bloqueadas por score baixo.
4. Fazer os termos de **Config > Termos** também alimentarem o filtro editorial positivo.
5. Pré-preencher a lista de termos com deputados estaduais da Alerj, políticos relevantes do RJ e municípios estratégicos.
6. Criar a seção **Baixo score para avaliação** no fim da fila.

## O que mudou

### 1. Nova aba Fontes Especiais

Arquivo principal:

```text
sistema/fontes_especiais_v129.json
```

Formato aceito no painel:

```text
Nome da Fonte|https://url-do-feed-ou-rss
```

Essas fontes entram em fase própria de coleta e passam por bypass de score, mas continuam respeitando:

- deduplicação;
- já está na fila;
- já publicada;
- janela de publicação;
- link inválido;
- asset/imagem;
- erro técnico de RSS/parser.

### 2. Termos viram linha editorial positiva

Os termos em:

```text
Config > Termos
```

agora são usados para:

- busca por termos;
- filtro editorial positivo;
- boost no score;
- diagnóstico de motivo editorial;
- sugestão de canal quando aplicável.

### 3. Lista pré-preenchida

O arquivo `termos_watchlist_v98.json` foi ampliado com:

- deputados estaduais da Alerj;
- políticos relevantes do RJ;
- municípios do Norte Fluminense;
- municípios da Grande Rio/Baixada/Região Metropolitana;
- órgãos oficiais e termos políticos.

### 4. Baixo score para avaliação

Quando uma fonte encontra matéria, mas nenhuma entra por score baixo, o sistema salva até 5 exemplos com status:

```text
baixo_score
```

Eles aparecem no fim da fila, separados por:

```text
Baixo score para avaliação
```

A ação **✓ Aprovar** muda a pauta para `captada`.

### 5. Diagnóstico

O funil agora mostra também:

```text
bypass_score
baixo_score_review
```

## Arquivos alterados

```text
sistema/ururau/coleta/linha_editorial_v129.py
sistema/ururau/coleta/termos_config_v98.py
sistema/ururau/coleta/source_policy_v114.py
sistema/ururau/coleta/scoring.py
sistema/ururau/coleta/coleta_auditoria_v126.py
sistema/ururau/ui/painel.py
sistema/termos_watchlist_v98.json
sistema/configuracoes/termos_watchlist_v98.json
sistema/fontes_especiais_v129.json
sistema/configuracoes/fontes_especiais_v129.json
sistema/.env
sistema/credenciais/env_principal.env
```

## Preservado

Não foi removido nem substituído:

- coletor especial Campos 24 Horas;
- RSS normal;
- XML/Sitemap;
- Busca por Termos;
- diagnóstico v128;
- hidratação de texto;
- hidratação de imagem;
- fila principal;
- envio WhatsApp.
