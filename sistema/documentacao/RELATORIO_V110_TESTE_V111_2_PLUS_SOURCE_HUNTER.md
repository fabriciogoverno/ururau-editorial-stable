# RELATÓRIO — Ururau v110 teste + v111.2 Plus Source Hunter

## Resumo

Foi aplicada uma nova camada de captura baseada na análise técnica dos projetos `newspaper`, `newspaper4k` e `meridian`. A solução foi incorporada diretamente ao motor já existente, sem substituir o fluxo v111.1 que havia passado nos testes.

## O que foi aproveitado do newspaper

- Heurística de URL jornalística:
  - datas no caminho;
  - caminhos como `news`, `article`, `noticia`, `materia`;
  - rejeição de assets, páginas institucionais e páginas de tag/autores.
- Descoberta de feeds comuns:
  - `/feed/`;
  - `/rss`;
  - `/rss.xml`;
  - `/atom.xml`;
  - `?feed=rss2`.
- Modelo de separação entre fonte, feed e artigo.

## O que foi aproveitado do newspaper4k

- Extração modular de metadados:
  - título;
  - autor;
  - data;
  - canonical;
  - descrição;
  - imagem principal.
- Score textual mais forte:
  - densidade textual;
  - link density;
  - stopwords;
  - classes/ids positivas e negativas;
  - complementação por blocos irmãos.
- Captura de imagens por:
  - OpenGraph;
  - Twitter Card;
  - JSON-LD;
  - `srcset`;
  - `data-src`.

## O que foi aproveitado do Meridian

- Cooldown por domínio para reduzir erro e bloqueio.
- Deduplicação por URL limpa, removendo rastreadores.
- Pauta com status e `fail_reason`.
- Ideia de pipeline em camadas: ingestão → hidratação → deduplicação → score → fila.

## O que foi implementado

### Arquivos novos

- `ururau/coleta/source_discovery_plus_v112.py`;
- `ururau/tests/test_source_discovery_plus_v112.py`;
- `ururau/tests/test_extractor_newspaper_plus_v112.py`;
- `.env.v111_2_plus_adicional`;
- `SPEC_URURAU_V111_2_PLUS_SOURCE_HUNTER.md`.

### Arquivos alterados

- `google_news_scraper/extractor.py`;
- `ururau/publisher/monitor_v111_ciclo_combinado.py`;
- `.env`;
- `.env.exemplo`;
- `requirements.txt`;
- `VERSAO.txt`;
- `SPEC.md`.

## Como a coleta fica agora

O ciclo combinado passa a somar três entradas:

1. Google News por termos prioritários;
2. Google News por grupos temáticos;
3. Source Hunter Plus:
   - RSS conhecido;
   - RSS descoberto;
   - links de homepage/categorias públicas;
   - hidratação por cascata de extração.

## Validação realizada neste ambiente

- `py_compile` dos arquivos novos e alterados: OK.
- Teste manual direto dos helpers de URL e do fallback `newspaper_plus`: OK.
- Não foi feito teste real com internet externa dentro deste ambiente.
- O `pytest` completo deve ser rodado no Windows do usuário, como foi feito na etapa anterior.

## Comando de teste

```powershell
cd "CAMINHO_DA_PASTA_EXTRAIDA\ururau_v110_teste"

python -m compileall google_news_scraper ururau

python -m pytest ururau/tests/test_gnews_v111.py ururau/tests/test_v111_1_ciclo_combinado.py ururau/tests/test_source_discovery_plus_v112.py ururau/tests/test_extractor_newspaper_plus_v112.py -q
```

## Rollback rápido

```env
URURAU_PLUS_SOURCE_HUNTER=0
```

Isso desliga apenas a camada nova e preserva a v111.1.
