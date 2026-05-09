# SPEC.md — Ururau v110 teste + v111.4 Configuração Saneada e Coleta Operacional

## 1. Objetivo

Corrigir a camada operacional de coleta do Ururau a partir dos logs reais enviados, simplificando a configuração de termos, saneando fontes RSS, ativando a coleta complementar Source Hunter Plus no painel e reduzindo erros recorrentes de extração e imagem.

A v111.4 mantém o projeto no mesmo local e preserva os fallbacks v108, v109, v110, v111.1, v111.2 e v111.3. A implementação é aditiva e reversível por `.env`.

## 2. Problemas observados nos logs

1. Fontes RSS com 0 entradas em ciclos reais, incluindo Folha 1, Campos 24 Horas, Manchete RJ, G1 Norte Fluminense, VNotícia, NF Notícias, Portal OZK, Macaé News, Jornal O Diário, Portal da Cidade Campos, Portal da Cidade Macaé e outras.
2. Fontes produtivas misturadas com fontes improdutivas, fazendo o painel gastar tempo antes de chegar nos sites que realmente entregam notícia.
3. Termos de busca configurados com formato longo `Termo|Peso|Canal|Buscar|Observação`, gerando confusão com fontes RSS e regras editoriais.
4. Tentativas de variantes mobile inexistentes, como `m.j3news.com`, `m.girorj.com.br` e `m.www.portalviu.com.br`.
5. Repetição de download de imagem em domínios com 429, especialmente Agenda do Poder.
6. Source Hunter Plus existia, mas não estava conectado ao ciclo rápido do painel; o painel ainda exibia “Source Hunter pesado desligado por padrão”.
7. Ruído editorial entrando na fila, como BBB, novela, celebridades e chamadas sensacionalistas sem ligação regional/política.

## 3. Escopo implementado

### 3.1 Fontes RSS

- `fontes_rss.json` foi saneado para manter no ciclo rápido apenas fontes produtivas ou estratégicas.
- Fontes que retornaram 0 entradas foram movidas para `fontes_rss_quarentena_v114.json`.
- Fontes locais estratégicas que não devem ser descartadas, como Folha 1 e Campos 24 Horas, foram movidas para `fontes_source_hunter_especiais_v114.json`, com fallback por feeds alternativos e homepage.

### 3.2 Termos simples

- `termos_watchlist_v98.json` passou a conter lista simples de termos.
- A aba Config > Termos passa a exibir e salvar um termo por linha.
- O formato antigo com pipe continua aceito, mas só o primeiro campo é usado como termo.
- Linhas que começam por `http://` ou `https://` são ignoradas na aba de termos para evitar misturar fonte com busca.

### 3.3 Source Hunter Plus no painel

- O painel agora chama `coletar_source_hunter_plus_v112_sync()` quando `URURAU_PLUS_SOURCE_HUNTER=1`.
- O Source Hunter Plus testa RSS direto, endpoints alternativos, homepage e links jornalísticos.
- Campos 24 Horas e Folha 1 entram como fontes especiais, não como RSS rápido.

### 3.4 Extração de texto

- O gerador automático de variantes `m.*` foi desativado por padrão em `fonte_extractor_v86.py`.
- Mobile só será tentado se `URURAU_V86_TENTAR_MOBILE_AUTOMATICO=1` e o domínio estiver em whitelist.
- A cascata antiga continua preservada: RSS fulltext, WordPress REST, Kimi extractor, newspaper_plus, trafilatura, readability, JSON-LD e BS4 density.

### 3.5 Imagem

- Foi adicionado cooldown de 429 por domínio em `ururau/imaging/processamento.py`.
- Se uma URL de imagem ou domínio entra em 429, o sistema evita repetir a tentativa imediatamente.
- Foi adicionado fallback de imagem relacionada por Google Images público, quando `URURAU_PLUS_GOOGLE_IMAGES_FALLBACK=1`.
- Imagens relacionadas recebem marca vermelha no canto superior direito, se `URURAU_PLUS_MARCAR_IMAGEM_RELACIONADA=1`.

### 3.6 Ruído editorial

- Foi criado `ururau/coleta/source_policy_v114.py` com termos positivos, negativos, fontes produtivas, fontes em quarentena e domínios mobile inválidos.
- O motor bloqueia ruído evidente somente quando não há sinal positivo de interesse editorial.

## 4. Arquivos criados

- `ururau/coleta/source_policy_v114.py`
- `fontes_rss_quarentena_v114.json`
- `fontes_source_hunter_especiais_v114.json`
- `termos_busca_simples_v114.json`
- `RELATORIO_V110_TESTE_V111_4_CONFIG_BUSCA_SIMPLES.md`

## 5. Arquivos alterados

- `fontes_rss.json`
- `termos_watchlist_v98.json`
- `.env`
- `.env.exemplo`
- `ururau/coleta/rss.py`
- `ururau/coleta/termos_config_v98.py`
- `ururau/coleta/source_discovery_plus_v112.py`
- `ururau/coleta/fonte_extractor_v86.py`
- `ururau/ui/painel.py`
- `ururau/imaging/busca.py`
- `ururau/imaging/processamento.py`
- `ururau/publisher/monitor_v111_ciclo_combinado.py`

## 6. Variáveis principais

```env
URURAU_V92_MAX_SALVAR_RAPIDO=100
URURAU_V92_MAX_POR_FONTE=12
URURAU_V100_JANELA_PUBLICACAO_HORAS=8
URURAU_V108_GNEWS_TERMOS=1
URURAU_TERMOS_USAR_CONSULTAS_COMPLETAS=0
URURAU_PLUS_SOURCE_HUNTER=1
URURAU_PLUS_MAX_FONTES=100
URURAU_PLUS_MAX_POR_FONTE=8
URURAU_PLUS_MAX_TOTAL=100
URURAU_PLUS_HIDRATAR_FONTES=1
URURAU_PLUS_MAX_HIDRATAR=60
URURAU_FONTES_INCLUIR_QUARENTENA=0
URURAU_V86_TENTAR_MOBILE_AUTOMATICO=0
URURAU_IMG_COOLDOWN_429_SEG=1800
URURAU_PLUS_GOOGLE_IMAGES_FALLBACK=1
URURAU_PLUS_MARCAR_IMAGEM_RELACIONADA=1
```

## 7. Critérios de aceitação

1. `python -m compileall google_news_scraper ururau` deve terminar sem erro.
2. `python -m pytest ... -q` deve retornar 27 testes aprovados.
3. A aba Config > Termos deve mostrar somente termos, um por linha.
4. O painel não deve tentar `m.j3news.com`, `m.girorj.com.br` ou `m.www.portalviu.com.br` por padrão.
5. Fontes em quarentena não devem aparecer no ciclo RSS rápido.
6. Folha 1 e Campos 24 Horas devem ser tentadas no Source Hunter Plus, com feeds alternativos e homepage.
7. Agenda do Poder não deve gerar tentativas repetidas de imagem durante cooldown de 429.
8. O painel deve exibir logs `[v111.4][SOURCE_PLUS]` ou `Source Hunter Plus v111.4` quando a camada Plus rodar.

## 8. Testes

```powershell
cd "C:\Users\fabri\Downloads\ururau_v110_teste_v111_4_config_busca_simples\ururau_v110_teste"
python -m compileall google_news_scraper ururau
python -m pytest ururau/tests/test_gnews_v111.py ururau/tests/test_v111_1_ciclo_combinado.py ururau/tests/test_source_discovery_plus_v112.py ururau/tests/test_extractor_newspaper_plus_v112.py -q
```

Resultado validado nesta revisão:

```text
27 passed, 3 warnings
```

## 9. Rollback

Para desligar apenas a camada Plus:

```env
URURAU_PLUS_SOURCE_HUNTER=0
```

Para voltar a usar fontes em quarentena no RSS rápido:

```env
URURAU_FONTES_INCLUIR_QUARENTENA=1
```

Para voltar ao formato antigo dos termos, ainda é possível colar `Termo|Peso|Canal|Buscar|Observação`; o parser aceitará, mas usará somente o primeiro campo como termo no motor de busca.

Para reativar tentativa mobile automática:

```env
URURAU_V86_TENTAR_MOBILE_AUTOMATICO=1
```

Não recomendado sem whitelist de domínio.
