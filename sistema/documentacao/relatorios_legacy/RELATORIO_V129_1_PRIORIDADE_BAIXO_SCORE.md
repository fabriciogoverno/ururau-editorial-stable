# Ururau v129.1 — prioridade visual, baixo score aprovável/reprovável e RSS sem duplicidade especial

Alterações aplicadas:

1. Fontes Especiais vencem Fontes RSS.
   - Qualquer fonte cujo nome, domínio ou URL esteja em `fontes_especiais_v129.json` é removida/ignorada do RSS comum.
   - Removidas agora dos arquivos RSS: 24 entrada(s).

2. Baixo Score ficou operacional para decisão editorial.
   - Card passa a mostrar título visual robusto.
   - Evita rótulos genéricos como `A HORA`, `Home`, `Últimas`, `Notícias` como título principal.
   - Tenta usar título real, OG/meta/headline, resumo/lead ou slug do link.
   - Botões: `✓ Aprovar` e `✕ Reprovar`.
   - Reprovar marca como `reprovada` e bloqueia o link para não voltar.

3. Prioridade por termo ganhou sinalização visual.
   - Cards com termos da linha editorial mostram selo `PRIORIDADE: termo`.
   - Fundo/borda discretos para leitura rápida.

4. Termos esportivos adicionados.
   - Flamengo, Vasco, Vasco da Gama, Botafogo, Fluminense.
   - Americano de Campos, Americano Futebol Clube, Americano FC.
   - Goytacaz e variações com Goitacaz.

5. Preservado:
   - Coleta RSS funcional.
   - Coletor especial Campos 24 Horas.
   - XML/Sitemap.
   - Busca por Termos.
   - Diagnóstico v128.
   - Fontes Especiais v129.
