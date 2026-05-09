# v129.13 — Correção específica para Manchete RJ

## Objetivo

Corrigir apenas a fonte **Manchete RJ**, usando o diagnóstico completo enviado pelo usuário. A coleta geral, RSS das demais fontes, Campos 24 Horas, XML/Sitemap, Fontes Especiais, Termos, painel, publicação e WhatsApp não foram alterados.

## Problema identificado

A entrada anterior usava:

```text
https://mancheterj.com/feed/
```

No diagnóstico de coleta, essa entrada aparecia com `encontradas=0`. O relatório técnico do site mostrou que a estratégia correta é priorizar:

```text
https://mancheterj.com/portal/feed/
https://mancheterj.com/portal/rss/
```

E usar WP REST API como alternativa leve:

```text
https://mancheterj.com/wp-json/wp/v2/posts?per_page=10
```

## Alterações feitas

1. Atualizada a URL principal de Manchete RJ em:

```text
sistema/fontes_rss.json
sistema/configuracoes/fontes_rss.json
sistema/config/fontes_rss.json
```

De:

```text
https://mancheterj.com/feed/
```

Para:

```text
https://mancheterj.com/portal/feed/
```

2. Criado coletor específico:

```text
sistema/ururau/coleta/adapters/mancheterj_v12913.py
```

Ordem de coleta:

```text
1. https://mancheterj.com/portal/feed/
2. https://mancheterj.com/portal/rss/
3. https://mancheterj.com/feed/
4. https://mancheterj.com/rss/
5. https://mancheterj.com/wp-json/wp/v2/posts?per_page=10
6. https://mancheterj.com/sitemap.xml
7. https://mancheterj.com/wp-sitemap.xml
8. HTML de listagens, filtrando uploads/imagens/assets
```

3. Integrado ao painel apenas quando a fonte é Manchete RJ:

```text
sistema/ururau/ui/painel.py
```

4. Diagnóstico expandido para Manchete RJ:

```text
sistema/ururau/coleta/coleta_auditoria_v126.py
```

Agora o relatório deve mostrar:

```text
Manchete RJ detalhado v129.13
estratégia usada
entradas por feed
aceitas na janela
fallback fora da janela
WP API
sitemaps
HTML fallback
```

## O que não foi alterado

- Coleta RSS das outras fontes.
- Campos 24 Horas especial.
- XML/Sitemap geral.
- Busca por Termos.
- Fontes Especiais.
- Linha editorial.
- Fila visual.
- Publicação.
- Copydesk.
- WhatsApp.

## Validação estática

Executado:

```text
PYTHONPATH=sistema python sistema/validar_v129_13_mancheterj.py
```

Resultado:

```text
[OK] v129.13 Manchete RJ: /portal/feed + fallback WP API/sitemap/HTML integrado e validado.
```

## Teste operacional esperado

Na próxima coleta, o relatório deve deixar de mostrar apenas:

```text
SEM COLETA | Manchete RJ | encontradas=0
```

E deve registrar qual etapa funcionou:

```text
Manchete RJ detalhado v129.13:
RSS: https://mancheterj.com/portal/feed/ | entradas=X | aceitas_janela=Y
```

Se os posts do site estiverem fora da janela de publicação, o diagnóstico deve explicar isso, em vez de parecer que a fonte morreu.
