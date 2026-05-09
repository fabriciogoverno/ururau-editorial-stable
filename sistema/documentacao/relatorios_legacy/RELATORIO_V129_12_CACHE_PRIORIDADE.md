# v129.12 — Cache e prioridade limpa

Correções:

- Config > Termos passa a ser a fonte oficial do selo PRIORIDADE.
- Termos removidos não voltam por TERMOS_BASE_V129.
- Salvar e Aplicar invalida caches editoriais e de watchlist.
- A fila filtra selos antigos contra a lista ativa de termos antes de desenhar.
- Limpeza automática segura de cache temporário ao iniciar, no máximo uma vez a cada 6 horas.
- A limpeza preserva configurações, banco, credenciais, histórico, matérias geradas e imagens finais.

Retenção automática:

- cache/html/tmp: mais de 24h;
- miniaturas/preview: mais de 3 dias;
- logs/diagnósticos antigos: mais de 7 dias;
- originais de imagem `*_original.*`: mais de 3 dias;
- imagens finais `*_final.*`: preservadas.
