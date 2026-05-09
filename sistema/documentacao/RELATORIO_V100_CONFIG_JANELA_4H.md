# Ururau v100 — Config persistente, janela 4h e logs claros

Correções aplicadas:

- Mantida a leitura efetiva de `fontes_rss.json` pela coleta progressiva.
- Aba **Termos** continua gravando `termos_watchlist_v98.json` e atualizando arquivos auxiliares de busca/watchlist.
- Adicionados parâmetros visíveis no Config para janela de publicação, score mínimo, máximo por fonte e máximo total.
- Filtro temporal agora usa `URURAU_V100_JANELA_PUBLICACAO_HORAS=4`, com compatibilidade para flags v99.
- Datas de RSS/Google News seguem normalizadas para `America/Sao_Paulo`.
- Pautas sem data, futuras ou fora da janela são bloqueadas antes de entrar na fila.
- Fila segue ordenada pela data de publicação da fonte, com mais recentes primeiro.
- Logs de descarte por data mostram motivo, idade e limite.
- Logs de link bloqueado mostram motivo salvo, quando existir.
- Corrigido erro Tkinter de thumbnail em label destruído (`invalid command name ... label`).
- Atualizados títulos dos BATs e janela para v100.

Como validar:

1. Abrir `RODAR_TUDO.bat`.
2. Conferir no console: `[v100] Coleta rápida em fases: N fonte(s) RSS configurada(s).`
3. Conferir no console descartes como: `[RSS][v100] ... janela de 4h`.
4. Editar Fontes RSS/Termos, clicar **Salvar e Aplicar**, fechar e reabrir. A lista deve permanecer.
