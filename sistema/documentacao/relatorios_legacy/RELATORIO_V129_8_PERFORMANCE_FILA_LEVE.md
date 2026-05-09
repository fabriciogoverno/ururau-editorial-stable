# v129.8 - Performance da Fila de Pautas

Correções focadas em performance visual sem alterar coleta, RSS, termos, fontes especiais, imagem, copydesk ou publicação.

## Alterações

- Reativada a virtualização real da fila: só os cards visíveis existem como widgets Tkinter.
- Coalescência visual: múltiplas chamadas de atualização são consolidadas em uma atualização curta.
- Thumbnails da fila desativados por padrão para reduzir travamento; imagem completa permanece na aba Fonte/Preview.
- Recarregamento do banco/fila durante coleta agora é limitado por janela de tempo.
- Clique na pauta mantém destaque imediato, mas hidratação/aba lateral é debounced para evitar pulos.
- Refresh final forçado ao término da coleta.

## Variáveis novas

- URURAU_V1298_FILA_REFRESH_MS=900
- URURAU_V1298_DB_REFRESH_MS=2500
- URURAU_V1298_FILA_THUMBS=0

## Objetivo

Evitar a reconstrução massiva da fila enquanto coleta, texto e imagem atualizam em paralelo.
