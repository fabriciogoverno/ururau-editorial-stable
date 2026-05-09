# RELATÓRIO v129.2 — Correção crítica de RSS e fila de pautas

## Problemas corrigidos

1. A fila coletava pautas, mas não renderizava os cards.
   - Causa técnica: a v129.1 usava `unicodedata` em funções novas de título/termo, mas `unicodedata` não estava importado em `painel.py`.
   - Efeito: o item da fila falhava ao renderizar depois do separador visual.
   - Correção: import explícito de `unicodedata` e reparo preventivo de cache Python.

2. A aba Fontes RSS caiu para o fallback de 4 fontes.
   - Causa técnica: o mesmo erro de `unicodedata` quebrava o carregamento de `fontes_rss.json`.
   - Efeito: a UI exibia apenas G1/CNN/Folha/UOL, como se as fontes funcionais tivessem sido removidas.
   - Correção: restauração da lista RSS completa da v127, removendo apenas as fontes cadastradas exatamente em Fontes Especiais.

3. Remoção ampla demais por domínio/host.
   - Causa técnica: a v129.1 comparava também por domínio, podendo excluir mais do que deveria.
   - Correção: a v129.2 remove do RSS apenas quando o nome ou a URL forem exatamente os mesmos da Fonte Especial.

## Preservado

- Coletor especial do Campos 24 Horas.
- RSS comuns já funcionais.
- XML/Sitemap.
- Busca por Termos.
- Baixo Score com Aprovar/Reprovar.
- Selo PRIORIDADE.
- Hidratação de texto/imagem.
- Publicação/WhatsApp.

## Arquivos principais alterados

- sistema/ururau/ui/painel.py
- sistema/CORRIGIR_V129_2_FILA_RSS.py
- sistema/INICIAR.bat
- sistema/fontes_rss.json
- sistema/configuracoes/fontes_rss.json
- sistema/config/fontes_rss.json

## Resultado esperado

- A aba Fontes RSS volta a listar as fontes comuns funcionais.
- Fontes Especiais não ficam duplicadas no RSS.
- A fila volta a mostrar os cards das matérias coletadas.
- Cards com termos continuam mostrando PRIORIDADE.
