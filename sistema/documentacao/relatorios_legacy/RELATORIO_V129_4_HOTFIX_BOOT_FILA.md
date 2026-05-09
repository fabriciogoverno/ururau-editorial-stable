# RELATÓRIO v129.4 — hotfix boot e fila

## Correções

- Corrigido erro Python `NameError: name 'true' is not defined` no arquivo `sistema/CORRIGIR_V129_2_FILA_RSS.py`.
- Convertidos booleanos JSON (`true`/`false`) para booleanos Python (`True`/`False`) dentro da lista embutida de fontes RSS.
- Pacote reorganizado para não sair com pasta raiz `ururau_v129_2_correcao_critica_rss_fila` dentro da v129.3.
- Mantidas as correções de fila/restauração de cards da v129.3.

## Observação

Este hotfix não altera coletores RSS, Campos 24 Horas, XML/Sitemap, Termos, WhatsApp ou publicação. A finalidade é impedir a quebra na inicialização causada pelo script corretivo.
