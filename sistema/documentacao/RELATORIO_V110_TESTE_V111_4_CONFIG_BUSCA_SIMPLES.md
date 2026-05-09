# Relatório — v110 teste + v111.4 Configuração Saneada e Busca Simples

## Resumo executivo

Esta revisão corrige o problema operacional apontado nos logs: o sistema coletava, mas misturava fontes produtivas com fontes vazias, termos com metadados e tentativas técnicas que já demonstraram erro recorrente. A v111.4 organiza o motor para fazer primeiro o simples e funcional: fontes boas primeiro, termos como termos, Source Hunter Plus ativo no painel e redução de ruído.

## Decisões implementadas

1. Fontes que retornaram 0 entradas nos logs saíram do RSS rápido e foram para quarentena.
2. Folha 1 e Campos 24 Horas foram preservadas como fontes locais estratégicas, mas agora entram por Source Hunter com endpoints alternativos e homepage.
3. Termos de busca foram simplificados: um termo por linha.
4. Google News por termos foi religado (`URURAU_V108_GNEWS_TERMOS=1`), mas usando termos simples.
5. Consultas complexas de grupos não entram mais no motor rápido, salvo se `URURAU_TERMOS_USAR_CONSULTAS_COMPLETAS=1`.
6. Source Hunter Plus foi conectado diretamente ao ciclo do painel.
7. Variantes mobile automáticas foram desligadas para eliminar erros DNS de `m.*`.
8. Imagem com erro 429 agora aciona cooldown por domínio.
9. Fallback de imagem relacionada por Google Images foi adicionado e recebe marca vermelha.

## Fontes saneadas

O novo `fontes_rss.json` mantém 41 fontes ativas. O arquivo `fontes_rss_quarentena_v114.json` guarda 26 fontes retiradas do ciclo rápido, sem apagar definitivamente.

## Validação

- `python -m compileall google_news_scraper ururau`: OK.
- `python -m pytest ... -q`: 27 passed, 3 warnings.

## Próximo teste recomendado

Rodar o painel e observar:

```text
[v100] Coleta rápida em fases
[RSS][v111.4][QUARENTENA]
[v111.4][SOURCE_PLUS]
[v105][FONTE] agendada
[v106][FONTE] OK
[v106][IMG] agendada
[v107][IMG] OK
```

Se Campos 24 Horas continuar sem retornar, a próxima etapa é capturar homepage com Playwright público ou criar adaptador específico do domínio.
