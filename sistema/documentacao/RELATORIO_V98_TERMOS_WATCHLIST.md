# Ururau v98 — Termos/Watchlist integrados

Correções implementadas:

- Confirmado que `fontes_rss.json` é lido pela coleta progressiva do painel e pelo monitor.
- Corrigido `obter_termos_google_news()` para aceitar grupos em formato de lista no `consultas_google_news.json`. Antes, esses grupos eram ignorados porque o código só lia objetos com chave `termos`.
- Criado `termos_watchlist_v98.json` como fonte única dos termos configuráveis.
- Criado módulo `ururau/coleta/termos_config_v98.py`.
- Adicionada aba **Termos** ao Config do painel.
- Ao salvar, os termos são aplicados em:
  - busca/Google News leve, quando habilitado;
  - watchlist/inteligência editorial;
  - score extra da fila;
  - destaque na leitura da fonte.
- `watchlists_editoriais.json` continua preservado, mas a aba Termos passa a alimentar uma camada dinâmica sem exigir edição manual de JSON.

Formato da aba Termos:

```txt
Termo|Peso|Canal|Buscar(1/0)|Observação
Campos dos Goytacazes|35|Cidades|1|Prioridade local máxima
Alerj|26|Política|1|Política estadual
```

Observação operacional: o Google News continua desligado por padrão se `URURAU_V92_USAR_GNEWS=0`, mas os termos ficam prontos e entram assim que essa opção for ligada. No RSS e no score, os termos já atuam independentemente do Google News.
