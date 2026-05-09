# v131.2 — Correção Folha da Manhã / HTML com data real

Correção aplicada após diagnóstico em que a Folha da Manhã foi coletada por AutoFontes v131, mas as matérias recentes foram classificadas como fora da janela.

## Causa

O perfil correto da Folha era `html_listagem`, mas os itens extraídos da listagem não carregavam a data real do artigo. O funil posterior tratava esses itens como fora da janela, embora a página do artigo mostrasse publicação recente, por exemplo 02/05/2026 17:54.

## Correção

- O parser `html_listagem` agora abre de forma leve a página do artigo e extrai metadados.
- Foram adicionados extratores para `og:title`, `og:description`, `og:image`, `article:published_time`, `article:modified_time`, JSON-LD e datas brasileiras no texto.
- Datas no formato `02/05/2026 17:54` ou `02/05/2026 às 17h54` agora são normalizadas.
- A pauta HTML passa a receber `data_pub_fonte`, `_data_pub_ordem` e imagem quando disponível.
- A entrada antiga da Folha em Regionais usando RSS 403 foi removida do padrão, mantendo a coleta correta pelo perfil AutoFontes v131.
- O nome exibido é normalizado para `Folha da Manhã`.

## Resultado esperado

Na próxima coleta, a Folha não deve mais aparecer como `fora_janela` para matéria publicada dentro da janela real. O diagnóstico deve mostrar a fonte como `auto_v131_regionais`, estratégia `html_listagem`, com itens aceitos e envio se não houver duplicidade.
