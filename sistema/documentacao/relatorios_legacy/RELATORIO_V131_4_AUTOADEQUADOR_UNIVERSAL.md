# URURAU v131.4 — Autoadequador Universal de Fontes

Esta versão reforça a ferramenta de Diagnóstico de Fonte para que ela deixe de ser apenas um relatório e passe a funcionar como um autoadequador operacional.

## Objetivo

Permitir que o operador cole um domínio ou link jornalístico, rode o diagnóstico e aplique uma configuração funcional ao sistema, sem criar um adaptador Python específico para cada site.

## Fluxo implementado

1. Diagnóstico completo detecta RSS, Atom, WP API, sitemap, HTML de listagem, metadados OG/JSON-LD e necessidade de Playwright.
2. O sistema enriquece a solução usando os testes brutos do diagnóstico, não apenas a recomendação textual.
3. É gerado um perfil operacional em `perfis_fontes_v131.json`.
4. O perfil é testado imediatamente.
5. Se gerar pauta dentro da janela, fica `funcional_com_pauta_na_janela`.
6. Se provar extração técnica, mas sem pauta atual na janela, fica `funcional_sem_pauta_na_janela` e será monitorado nas próximas coletas.
7. Se não gerar pauta nem provar extração técnica, não é salvo como operacional.

## Cascata operacional

A coleta por perfil tenta, em ordem:

1. RSS com feedparser.
2. RSS/XML direto por `<item>`, `<title>`, `<link>`, `<description>`, `<pubDate>` e `<enclosure>`.
3. WordPress REST API.
4. Sitemap XML, abrindo artigos para metadados.
5. HTML de listagem, abrindo artigos para data real, título, descrição e imagem.

## Resultado esperado

O botão Aplicar/Testar passa a mostrar se a fonte:

- foi aplicada;
- será usada na próxima coleta geral;
- entrou em RSS, Especiais ou Regionais;
- qual estratégia foi usada;
- quantos itens foram lidos;
- quantos tinham título/link;
- quantos entraram na janela;
- qual foi a primeira pauta encontrada.

## Observação

Esta versão não promete superar bloqueios técnicos absolutos de sites externos, como 403 permanente com proteção ativa. Ela evita, porém, que a cada site seja necessário criar uma correção manual quando o diagnóstico já consegue descobrir uma estratégia viável.
