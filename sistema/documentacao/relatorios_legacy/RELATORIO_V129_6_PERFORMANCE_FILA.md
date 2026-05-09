# v129.6 — Performance da Fila de Pautas

Correção focada em desempenho e estabilidade visual da fila.

## Problema observado

Durante a coleta progressiva, cada nova pauta chamava a renderização da fila. A versão anterior limpava o cache visual, destruía todos os cards, recriava a lista inteira e reposicionava o scroll. Isso causava:

- fila pulando;
- travamentos aparentes;
- separador visual reaparecendo sem estabilidade;
- lentidão conforme a quantidade de pautas crescia.

## Correções

1. Removida limpeza forçada de `_uids_cache` em `_aplicar_filtro`.
2. `FilaPautas.popular()` agora detecta atualização incremental e cria apenas os novos cards.
3. Reconstrução completa preserva posição do scroll.
4. Renderização completa ocorre em lotes pequenos para não bloquear o Tkinter.
5. Busca agora usa debounce de 180 ms, evitando redraw a cada tecla.
6. Mantidas as correções anteriores: Fontes Especiais, Aprovar/Reprovar Baixo Score, selo PRIORIDADE e import de `unicodedata`.

## Resultado esperado

A fila deve continuar listando as pautas enquanto a coleta roda, sem pular para o topo e sem recriar todos os cards a cada nova matéria.
