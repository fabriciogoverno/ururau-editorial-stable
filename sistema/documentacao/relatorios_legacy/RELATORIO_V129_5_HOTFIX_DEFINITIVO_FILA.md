# v129.5 - Hotfix definitivo da Fila de Pautas

Correções aplicadas:

1. Importação global de `unicodedata` adicionada em `sistema/ururau/ui/painel.py`.
2. Funções de título visual agora são tolerantes a erro e não derrubam a renderização.
3. A renderização da fila agora trata exceção card a card. Um item problemático vira card de erro, mas a fila continua aparecendo.
4. A lista continua usando o separador visual de coleta, mas as matérias são empacotadas abaixo dele.
5. A contagem no topo é atualizada a partir do cache da fila, para não ficar em zero enquanto as pautas estão coletadas em memória.
6. As correções de Fontes Especiais, Baixo Score com Aprovar/Reprovar e selo PRIORIDADE foram preservadas.

Motivo do erro anterior:

O log apontava `NameError: name 'unicodedata' is not defined` em `_norm_titulo_v129_1`. Esse erro acontecia dentro de `_criar_item`, logo após o separador visual. Por isso a coleta salvava as pautas, mas a UI parava de desenhar os cards.
