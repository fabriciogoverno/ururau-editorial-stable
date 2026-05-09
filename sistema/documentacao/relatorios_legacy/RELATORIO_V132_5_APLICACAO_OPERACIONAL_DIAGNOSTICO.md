# v132.5 — aplicação operacional correta do diagnóstico de fonte

Correção focada no problema identificado com Tribuna NF.

## Problema confirmado

O diagnóstico completo apontava que o site era coletável por RSS, WP API, sitemap e HTML, mas a aplicação no sistema gravava a fonte visualmente como Regional e a coleta real caía no parser regional genérico (`regional_v1305`). Resultado: a fonte aparecia no relatório como `SEM COLETA`, mesmo com RSS válido.

## Correções

1. O relatório completo passa a valer como prova técnica de funcionalidade quando contém RSS válido, WP API com posts, HTML com artigos ou feed com título/link/data.
2. A aplicação salva o perfil operacional mesmo quando o teste imediato interno falha, se o diagnóstico completo já comprovou caminho funcional.
3. A ordem dos feeds agora segue o guia original do diagnóstico jornalístico: `/portal/feed/`, `/portal/rss/`, `/feed/`, `/rss/`.
4. Fontes regionais aplicadas pelo diagnóstico passam a usar o coletor universal AutoFontes v132.5, não o `regional_v1305` genérico.
5. Se uma fonte aparecer na aba Regionais mas o perfil persistido não for encontrado, a coleta cria um perfil temporário seguro com RSS, WP API, sitemap e HTML fallback.
6. Tribuna NF e Expresso Rio ficam cobertos por essa lógica sem adaptador específico por site.

## Resultado esperado para Tribuna NF

A próxima coleta deve mostrar algo do tipo:

```text
OK | Tribuna NF
Tipo detectado/configurado: auto_v1325_regionais
observacao: AutoFontes v132.5 aplicado a Regional
parser=rss_cascata
brutas>0
titulo_link>0
aceitas>=1, se houver matéria dentro da janela
```

Não deve mais aparecer como:

```text
SEM COLETA | Tribuna NF | tipo=regional_v1305 | brutas=0
```

## Validação feita

- `python -m py_compile ururau/coleta/auto_perfil_fontes_v131.py ururau/ui/painel.py`
- `python -m compileall -q ururau`
- Teste local de geração de perfil com o JSON do Tribuna NF: ordem correta de feeds e grupo Regionais.
