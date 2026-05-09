# Ururau v131 — Autoadequação operacional de fontes

Esta versão muda a ferramenta de diagnóstico de fontes de um relatório passivo para um fluxo operacional.

## Regra nova

Diagnóstico completo → gera perfil técnico → testa imediatamente → só salva se a fonte produzir pauta real.

O sistema não deve mais considerar uma fonte “resolvida” apenas porque o RSS respondeu HTTP 200. O perfil só é aplicado se o coletor v131 transformar o resultado em pauta válida.

## Perfis suportados

- `rss_cascata`: tenta `feedparser` e, se necessário, parser XML direto por `<item>`, `<title>`, `<link>`, `<description>`, `<pubDate>` e `<enclosure>`.
- `wp_api`: coleta posts da WordPress REST API quando o diagnóstico indicar esse caminho.
- `html_listagem`: fallback leve para páginas de listagem, com filtro contra assets/imagens.
- `sitemap`: reservado como apoio de descoberta.

## Abas

A classificação automática usa três grupos:

- `RSS`: fontes jornalísticas comuns.
- `Especiais`: órgãos oficiais/institucionais.
- `Regionais`: sites locais relevantes para Campos/Norte Fluminense.

## Proteção

A sugestão só vira operacional quando o teste imediato retorna pelo menos uma pauta. Caso contrário, o relatório permanece, mas o perfil não é salvo como ativo.

## Arquivo criado

- `sistema/perfis_fontes_v131.json`

A coleta geral lê este arquivo na fase AutoFontes v131 e insere as pautas com o mesmo funil de deduplicação, janela, publicação e fila.
