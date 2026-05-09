# Ururau v128 — diagnóstico técnico expandido

## Objetivo

Implementar diagnóstico técnico mais completo sem alterar a coleta que funcionou na v127.

## O que foi preservado

- RSS fonte por fonte.
- Coletor especial Campos 24 Horas.
- XML/Sitemap.
- Busca por Termos via Google News RSS.
- Source Hunter Plus.
- Fila progressiva e hidratação.

## O que foi adicionado

1. Funil objetivo por fonte:
   - brutas;
   - deduplicadas no lote;
   - já na fila;
   - publicadas no banco;
   - similares no Ururau;
   - fora da janela;
   - ruído editorial;
   - score baixo;
   - limite por fonte;
   - enviadas para fila;
   - primeira matéria encontrada;
   - primeira matéria enviada.

2. Diagnóstico HTTP por URL de fonte:
   - status HTTP;
   - content-type;
   - tipo detectado: RSS/Atom, Sitemap, HTML, JSON ou erro;
   - erro HTTP quando houver.

3. Campos 24 Horas detalhado:
   - cada feed testado;
   - quantidade de entradas por endpoint;
   - HTML fallback quando usado;
   - total final do coletor especial.

4. XML/Sitemap detalhado:
   - arquivo de configuração usado;
   - cada sitemap processado;
   - quantidade de itens por sitemap;
   - erro por sitemap.

5. Busca por Termos detalhada:
   - termo buscado;
   - URL do Google News RSS gerada;
   - janela em horas;
   - resultados brutos;
   - candidatos gerados;
   - descartes por termo: sem título/link, sem data, fora da janela, duplicado no ciclo, erro RSS.

## Arquivos alterados

- `ururau/coleta/coleta_auditoria_v126.py`
- `ururau/ui/painel.py`
- `ururau/coleta/termos_busca_v127.py`
- `ururau/coleta/adapters/campos24horas_v126.py`
- `ururau/coleta/sitemap_xml_coletor_v123.py`
- `VERSAO.txt`

## Observação operacional

A classe manteve o nome `AuditoriaColetaV126` para compatibilidade com o painel, mas agora gera diagnóstico `v128-expandido`.

## Como usar

Execute a coleta normalmente. Depois abra:

`Config > Diagnóstico > Atualizar diagnóstico`

ou exporte o TXT pela própria aba.

O relatório passa a explicar objetivamente por que uma fonte ficou em `SEM COLETA` ou `SEM ENVIO`.
