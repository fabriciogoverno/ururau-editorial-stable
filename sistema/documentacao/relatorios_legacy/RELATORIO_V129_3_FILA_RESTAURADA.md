# v129.3 — Fila de Pautas restaurada

Correção crítica aplicada:

1. A coleta estava gravando pautas, mas a Fila de Pautas exibia apenas o separador visual.
2. A causa foi a renderização virtualizada com `Canvas + Frame + place()`, que em algumas instalações recortava os cards posicionados abaixo do separador.
3. A lista agora volta a renderizar todos os cards com `pack()`, preservando o comportamento visual antigo: uma pauta abaixo da outra.
4. O separador visual continua existindo, mas não impede a exibição das pautas.
5. A regra de Fontes Especiais permanece: fonte especial não deve duplicar no RSS comum, mas fontes RSS normais não devem ser removidas.

Validação estática: arquivo `painel.py` parseado com sucesso via `compile()`.
