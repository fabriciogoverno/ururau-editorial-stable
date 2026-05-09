# RELATÓRIO — v110 teste com Google News Scraper integrado

## Objetivo

Aplicar no projeto Ururau a especificação recebida para ampliar a coleta e captura de matérias com texto e foto completos, usando o pacote `google_news_scraper` como camada consolidada, sem remover os fallbacks v108, v109 e v110.

A versão final foi nomeada como **v110 teste**, mas os módulos internos seguem a nomenclatura **v111** quando isso era exigido pela especificação técnica. Isso permite ativar/desativar a integração por `.env` sem quebrar o histórico do projeto.

## Arquivos adicionados

- `google_news_scraper/`: pacote completo do Kimi copiado para a raiz do projeto.
- `ururau/coleta/gnews_v111_integrado.py`: wrapper operacional do coletor integrado.
- `ururau/publisher/monitor_v111_patch.py`: adaptador para injetar pautas no ciclo do monitor.
- `ururau/ui/painel_v111_tab.py`: aba opcional para busca manual/teste no painel.
- `ururau/tests/test_gnews_v111.py`: testes com mock, sem acesso à internet.
- `PROMPT_CHATGPT_V110_TESTE.md`: prompt técnico original anexado.
- `SPEC_INTEGRACAO_V110_TESTE.md`: especificação técnica original anexada.

## Arquivos alterados

- `ururau/publisher/monitor.py`
  - O bloco antigo que chamava diretamente a ponte Kimi v110 foi substituído por `injetar_gnews_v111_no_raw()`.
  - Se `URURAU_V111_GNEWS_INTEGRADO=1`, o monitor usa a integração nova.
  - Se a v111 estiver desligada e `URURAU_V110_MONITOR_GNEWS_LEGADO=1`, o fallback v110 pode ser usado.
  - O RSS legado do Google News só entra se `URURAU_V108_GNEWS_TERMOS=1`.

- `.env` e `.env.exemplo`
  - Flags v111/v110 teste adicionadas.
  - Integração nova ativada por padrão.
  - Fallbacks legados desativados por padrão para evitar duplicidade e ruído.

- `requirements.txt`
  - Adicionados `aiohttp` e `tldextract`, além das dependências já existentes.

- `google_news_scraper/google_news_integrado.py`
  - Corrigido erro de sintaxe no carregador de JSON.
  - Ajustados nomes de editorias para a taxonomia em português usada pelo Ururau.
  - Adicionados campos `id`, `coletado_em` e `status` ao schema consolidado.

## Como o fluxo ficou

1. O monitor coleta RSS normalmente.
2. O monitor monta os termos Google News como antes.
3. O adaptador v111 verifica `.env`.
4. Se ativo, chama `coletar_pautas_gnews_v111()`.
5. O pacote busca Google News por RSS + HTML.
6. Links são deduplicados e convertidos para pauta Ururau.
7. Se `URURAU_V111_USAR_EXTRACAO_COMPLETA=1`, a pauta é hidratada com texto completo.
8. A pauta entra no `raw` do monitor com campos novos e campos legados:
   - novos: `titulo`, `descricao`, `url`, `texto_fonte`, `score`, `cidade`, `regiao`;
   - legados: `titulo_origem`, `link_origem`, `resumo_origem`, `fonte_nome`, `canal_forcado`, `_uid`.
9. O workflow existente continua responsável por scoring, fail-closed, imagem, redação, copydesk e CMS.

## Flags principais

```env
URURAU_V111_GNEWS_INTEGRADO=1
URURAU_V111_GNEWS_MAX_TERMOS_POR_CICLO=20
URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO=3
URURAU_V111_GNEWS_JANELA_HORAS=4
URURAU_V111_GNEWS_MIN_CHARS_FONTE=1200
URURAU_V111_USAR_EXTRACAO_COMPLETA=1
URURAU_V111_SCORE_MINIMO_PAUTA=65
URURAU_V110_MONITOR_GNEWS_LEGADO=0
URURAU_V108_GNEWS_TERMOS=0
URURAU_V105_USAR_BING_NEWS=0
```

## Rollback seguro

Para desligar a integração nova e testar apenas fallback v110:

```env
URURAU_V111_GNEWS_INTEGRADO=0
URURAU_V110_MONITOR_GNEWS_LEGADO=1
```

Para desligar Google News completamente no monitor:

```env
URURAU_V111_GNEWS_INTEGRADO=0
URURAU_V110_MONITOR_GNEWS_LEGADO=0
URURAU_V108_GNEWS_TERMOS=0
```

## Comandos de teste

```powershell
cd "PASTA_DO_PROJETO"
pip install -r requirements.txt
python -m pytest ururau/tests/test_gnews_v111.py -q
python ururau_monitor.py --ciclo-unico
```

## Observação

Não foi executado teste real de coleta externa neste ambiente porque o acesso livre à internet não está disponível. Foram feitas validações locais de sintaxe, empacotamento e integração estrutural.
