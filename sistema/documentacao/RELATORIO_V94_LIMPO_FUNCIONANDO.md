# Ururau v94 limpo funcionando

## Correções principais

- Corrigido o erro fatal do Tkinter: `_tkinter.tkapp object has no attribute '_auto_coleta_v92'`.
- A auto coleta agora chama `_auto_coleta_v94()`, método existente e protegido para rodar uma única vez.
- A coleta manual e automática agora têm trava contra execução duplicada simultânea.
- A coleta passou a ser feita em fases: RSS por fonte, fontes oficiais, Google News opcional e Source Hunter opcional.
- A fila é atualizada durante a coleta, a cada lote salvo, sem esperar todo o ciclo terminar.
- Google News permanece desligado por padrão: `URURAU_V92_USAR_GNEWS=0`.
- Source Hunter pesado permanece desligado por padrão: `URURAU_V92_SOURCE_HUNTER_LENTO=0`.
- Mantidos `.env`, `RODAR_TUDO.bat`, painel, monitor, copydesk, preview e CMS.

## Limpeza

Foram removidos arquivos de teste antigos, validadores antigos, relatórios de versões antigas e scripts soltos que não são necessários para rodar o sistema.

## Como rodar

1. Extraia o ZIP.
2. Abra a pasta extraída.
3. Execute `RODAR_TUDO.bat`.
