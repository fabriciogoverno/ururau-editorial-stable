# Ururau v124 - Campos 24 Horas e cobertura por fonte

## Diagnóstico do log

- `https://mancheterio.com.br/feed/` funciona. No log aparece como `Manchete Rio`, retornou 12 entradas e colocou 10 pautas na fila.
- `https://campos24horas.com.br/noticia/sitemap.xml` também funciona. O coletor XML/Sitemap retornou 30 pautas para o sitemap sem www e 30 para o com www.
- O problema do Campos 24 Horas era o filtro final de janela: as pautas do sitemap tinham cerca de 40h e foram ignoradas pelo corte de 8h antes de entrar na fila.

## Correção aplicada

- Pautas vindas de XML/Sitemap local agora carregam:
  - `_excecao_fora_janela_v123=True`
  - `_sitemap_excecao_janela_v124=True`
- O filtro final respeita essa exceção e mantém Campos 24 Horas na fila.
- Os dois sitemaps do Campos 24 Horas são deduplicados por URL normalizada, removendo diferença entre `www` e sem `www`.
- O console agora deve mostrar:
  - `[XML/SITEMAP v123] https://campos24horas.com.br/noticia/sitemap.xml: 30 pauta(s)`
  - `[XML/SITEMAP v124] lote integrado ao botão Coletar: X pauta(s) bruta(s)`
  - `[v123][JANELA][EXCECAO] mantendo pauta fora da janela ... Campos 24 Horas`

## Validação

```powershell
cd sistema
python validar_v124_campos_sitemap.py
python -m compileall ururau
```
