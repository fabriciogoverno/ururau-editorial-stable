# V43 Premium — ajuste final de leveza e layout

## Alterações implementadas

1. Removida a faixa extra de análise compacta que ocupava área útil.
2. Qualidade IA e Risco foram movidos para o TopHeader, no espaço onde aparecia o marcador AD.
3. A coluna lateral de Análise e Ações permanece removida.
4. O layout central fica focado em dois painéis: Fila de Pautas e Detalhe da Pauta.
5. O botão Gerar foi removido dos cards da fila.
6. Títulos da fila agora aceitam quebra em até duas linhas.
7. Fonte visual ajustada para Segoe UI, com leitura mais confortável.
8. A fila mantém Canvas virtualizado e agora usa buffer menor para desenhar menos linhas por vez.
9. O refresh da fila durante coleta foi desacelerado para reduzir pulos e travamentos.
10. O limite de pautas consultadas na fila foi reduzido de 1000 para 500 por refresh.
11. A hidratação automática por refresh foi reduzida de 60 para 24 pautas.
12. A barra inferior mostra carregamento quando o console está oculto.
13. O console continua interno e só aparece quando o botão Console é acionado.
14. INICIAR.bat segue como modo normal sem janela preta persistente.
15. RODAR_TUDO.bat permanece visível para instalação/diagnóstico.

## Objetivo técnico

Reduzir custo de renderização da fila, evitar redesenho excessivo, eliminar botões duplicados e liberar área visual para leitura editorial.

## Observação

Alguns arquivos permanecem na raiz da pasta sistema porque o motor legado ainda pode buscá-los por caminho fixo. Mover esses arquivos sem refatorar todos os pontos de leitura poderia quebrar coleta, configuração ou inicialização.
