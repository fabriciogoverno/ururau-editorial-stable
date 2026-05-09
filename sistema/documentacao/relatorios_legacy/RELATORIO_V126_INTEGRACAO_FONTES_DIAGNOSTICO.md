# Ururau v126 — integração definitiva de fontes e diagnóstico pós-coleta

## Implementado

- Registry de fontes por domínio e tipo:
  - `ururau/coleta/fonte_registry_v126.py`
- Auditoria pós-coleta:
  - `ururau/coleta/coleta_auditoria_v126.py`
- Coletor especial Campos 24 Horas:
  - `ururau/coleta/adapters/campos24horas_v126.py`
  - usa `/portal/feed/`, `/portal/rss/` e feeds de categorias antes do sitemap
- Diagnóstico visual abaixo da fila de pautas:
  - lista fontes que não enviaram matéria nova para a fila
  - separa `OK`, `SEM COLETA`, `SEM ENVIO`, `FALHA`
- Nomes fixos por domínio:
  - `https://mancheterj.com/feed/` → Manchete RJ
  - `https://mancheterio.com.br/feed/` → Manchete Rio
  - `https://campos.rj.gov.br/rss` → Prefeitura de Campos
  - Campos 24 Horas não aparece mais apenas como XML/Sitemap quando vem do coletor especial
- Rollback por `.env`:
  - `URURAU_V126_CAMPOS24_ESPECIAL_ATIVO=0` desliga o especial Campos24
  - fluxo RSS/XML/GNews/Kimi legado preservado

## O que aparece no painel

Abaixo da fila, após cada coleta:

```text
Coleta N - HH:MM | Fontes auditadas: X | OK: Y | Sem coleta: Z | Sem envio: W | Falha: K

Portais que NÃO enviaram matéria nova para a fila:
01. SEM COLETA | Fonte X | encontradas=0 | enviadas=0 | sem entradas
02. SEM ENVIO | Fonte Y | encontradas=10 | enviadas=0 | filtro/deduplicação/já na fila
03. FALHA | Fonte Z | encontradas=0 | enviadas=0 | timeout/erro/parser
```

## Validação

```powershell
cd sistema
python validar_v126_integracao_fontes.py
python -m compileall ururau
```
