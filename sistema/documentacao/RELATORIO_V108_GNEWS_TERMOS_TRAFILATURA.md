# Ururau v108 — Google News por Termos + fallback de extração

## Objetivo
Implementar tudo que foi acordado para transformar a aba **Termos** em fonte ativa de busca editorial e reforçar a captação de texto completo.

## Implementações

1. **Google News por Termos do Config**
   - Usa `termos_watchlist_v98.json`.
   - Respeita `Termo|Peso|Canal|Buscar(1/0)|Observação`.
   - Só pesquisa termos ativos com `Buscar=1` e peso mínimo configurado.
   - Busca limitada à janela editorial de 4 horas.
   - Limita quantidade de termos por ciclo e resultados por termo.
   - Resolve, quando possível, o link real da fonte a partir do Google News.

2. **Fallback trafilatura/readability**
   - Copiado o pacote `google_news_scraper` para `ururau/vendor/google_news_scraper`.
   - Criado fallback próprio `ururau/coleta/trafilatura_fallback_v108.py`.
   - Integrado ao extrator `fonte_extractor_v104.py` como etapa adicional.
   - Preserva parágrafos e evita texto em bloco único.

3. **Config do painel**
   - Adicionados parâmetros v108 para Google News por Termos e extração por trafilatura/readability.

4. **Segurança editorial**
   - Mantido bloqueio contra fonte curta.
   - Fonte OK padrão: mínimo de 1.200 caracteres úteis.
   - Matéria não deve ser gerada por snippet/RSS curto.

## Flags principais

```env
URURAU_V108_GNEWS_TERMOS=1
URURAU_V108_GNEWS_JANELA_HORAS=4
URURAU_V108_GNEWS_MAX_TERMOS_POR_CICLO=20
URURAU_V108_GNEWS_MAX_RESULTADOS_POR_TERMO=3
URURAU_V108_GNEWS_MIN_PESO_TERMO=18
URURAU_V108_USAR_TRAFILATURA_FALLBACK=1
URURAU_V108_MIN_TEXTO_FONTE_OK=1200
```

## Logs esperados

```text
[GNEWS v108] buscando 20 termo(s), janela=4h, máx=3/termo
[GNEWS v108] Alerj: 8 entrada(s)
[v100][FILA] entrou (GNews Termos v108): ...
[V108][FONTE] OK 3200 chars via v108_trafilatura: ...
```
