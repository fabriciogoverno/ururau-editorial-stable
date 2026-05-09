# URURAU v131.3 — Autoadequação genérica de fontes

Esta versão consolida a ferramenta de Diagnóstico de Fonte como uma etapa operacional real do sistema.

## Regra principal

O diagnóstico não deve apenas sugerir um link. Ele gera um perfil operacional de coleta e o sistema só salva esse perfil quando o teste imediato produz pauta real.

Fluxo:

1. Diagnóstico completo do domínio ou URL.
2. Geração de perfil operacional.
3. Teste imediato do perfil.
4. Se o teste gerar pauta real, o perfil é salvo em `perfis_fontes_v131.json`.
5. A próxima coleta geral usa a fonte pela fase AutoFontes v131.3.
6. Se o teste não gerar pauta, a fonte não é marcada como resolvida.

## Cascata operacional

A coleta por perfil tenta:

1. RSS com `feedparser`.
2. RSS XML direto por `<item>`, `<title>`, `<link>`, `<description>`, `<pubDate>` e `<enclosure>`.
3. WordPress REST API.
4. Sitemap XML com validação por metadados da página.
5. HTML de listagem, abrindo cada artigo para extrair título, descrição, imagem e data real.

## Correção aplicada ao problema da Folha

O problema da Folha da Manhã não era só uma exceção do domínio. Era uma falha genérica do modo `html_listagem`: o sistema encontrava links, mas não extraía a data real do artigo e podia derrubar pautas recentes como fora da janela.

Agora o parser de HTML de listagem abre a página do artigo e tenta extrair data por:

- `article:published_time`
- `article:modified_time`
- `datePublished`
- `dateModified`
- JSON-LD
- texto visível no padrão brasileiro, como `02/05/2026 17:54`

Essa correção vale para qualquer fonte que o diagnóstico classifique como `html_listagem`, não apenas para a Folha.

## Resultado esperado no painel

Depois de aplicar/testar, a ferramenta mostra:

- fonte;
- domínio;
- grupo/aba;
- estratégia;
- parser operacional;
- se foi aplicada e funcional;
- se será usada na próxima coleta geral;
- quantidade de pautas de teste;
- itens brutos;
- itens aceitos;
- tentativas técnicas;
- arquivo onde o perfil foi salvo.

