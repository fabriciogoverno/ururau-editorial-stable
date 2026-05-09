# v129.10 — Integração restaurada da fila ultraleve

## Objetivo
Corrigir as regressões introduzidas na troca da fila tradicional por Canvas ultraleve, preservando a performance obtida na v129.9 e restaurando o comportamento antigo de clique/detalhe.

## Problemas corrigidos

1. Clique no corpo da pauta não podia abrir Preview nem modal de "Sem matéria gerada".
2. Clique na pauta precisava voltar a carregar a aba Fonte/Detalhe como na v127.
3. Botão Gerar precisava continuar separado da seleção da pauta.
4. Botão Ver Matéria/Preview precisava deixar de abrir alerta modal quando a matéria ainda não estivesse válida.
5. Preview de imagem na aba Fonte precisava usar miniatura leve/cache, sem carregar a imagem final pesada a cada clique.

## Arquivos alterados

- `sistema/ururau/ui/painel.py`
- `sistema/ururau/ui/fonte_preview_v107.py`
- `VERSAO.txt`
- `sistema/VERSAO.txt`

## O que não foi alterado

- Motor RSS
- Campos 24 Horas
- XML/Sitemap
- Fontes Especiais
- Termos
- Scoring editorial
- Copydesk
- Publicação
- WhatsApp

## Comportamento esperado

- Clique no corpo da pauta: seleciona a pauta e carrega Detalhe > Fonte.
- Botão Gerar: gera/redige a matéria.
- Botão Ver Matéria: abre preview somente se houver matéria gerada válida; caso contrário, apenas seleciona a pauta sem modal.
- Aba Fonte usa imagem leve de interface em `_preview_cache_v12910`, preservando o arquivo final de publicação.
