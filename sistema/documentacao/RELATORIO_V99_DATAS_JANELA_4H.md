# Ururau v99 — Datas em Brasília e fila por últimas 4 horas

## Correções aplicadas

- Corrigida a interpretação de datas de RSS/Google News em UTC/GMT.
- Toda data de publicação da fonte agora é normalizada para `America/Sao_Paulo` antes de ser exibida ou salva.
- A fila passa a aceitar somente pautas publicadas nas últimas 4 horas.
- Pautas sem data confiável, com data futura ou fora da janela são ignoradas.
- A fila é ordenada pela data de publicação na fonte, das mais recentes para as mais antigas.
- O card da fila passa a exibir `Publicado: DD/MM/AAAA HH:MM`, para deixar claro que não é horário de captura.
- A aba Info passa a indicar que a data da fonte está em horário de Brasília.

## Flags principais

```env
URURAU_V99_JANELA_PUBLICACAO_HORAS=4
URURAU_V99_FILA_APENAS_ULTIMAS_HORAS=1
URURAU_V99_TOLERANCIA_FUTURO_MIN=10
URURAU_V99_REJEITAR_SEM_DATA_PUBLICACAO=1
```

## Observação

A hora de captura continua existindo separadamente em `captada_em`. A fila usa `data_pub_fonte`, que agora é a data de publicação da fonte convertida para Brasília.
