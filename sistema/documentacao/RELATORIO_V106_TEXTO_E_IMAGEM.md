# Ururau v106 — texto primeiro, imagem depois, RSS pretexto restaurado

## Diagnóstico
A v105 corrigiu um problema real: o sistema não podia aceitar snippet curto de RSS como texto completo. Porém a regra ficou rígida demais em dois pontos:

1. A aba Fonte e o hidratador passaram a colocar a imagem apenas como “segundo plano”, mas não havia uma fila automática de imagem depois que o texto ficava OK.
2. Alguns RSS entregam texto completo em `content:encoded`, `content.value`, `summary_detail.value` ou campos equivalentes. A v105 não promovia esses casos para `cleaned_source_text`, então todas as pautas pareciam chegar sem texto e precisavam hidratar depois.

## Correções
- Criada fila automática de imagem v106, separada da fila de texto.
- Texto continua prioridade absoluta.
- Quando o texto fica OK, a imagem é automaticamente agendada em baixa prioridade.
- Se o RSS trouxer URL de imagem, o sistema tenta baixar/processar essa imagem antes do pipeline normal.
- Se o RSS trouxer texto integral confiável, a pauta já entra na fila com `TXT OK`.
- Snippet curto continua recusado como texto completo.
- O painel preserva comportamento: ao clicar, abre Fonte e prioriza o texto.

## Logs esperados
```txt
[v106][IMG] Worker automático iniciado; imagem roda depois do texto.
[v106][FONTE] OK 3248 chars (...)
[v106][IMG] agendada (texto_ok:...)
[v106][IMG] OK via URL prévia (...)
[v106][IMG] OK via pipeline (...)
```
