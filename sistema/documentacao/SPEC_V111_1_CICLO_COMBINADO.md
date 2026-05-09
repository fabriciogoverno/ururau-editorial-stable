# SPEC.md — v111.1 Ciclo Combinado de Coleta (Google News Scraper no Ururau)

> **Versão:** 111.1  
> **Data:** 2026-04-30  
> **Status:** Aprovado para implementação  
> **Base:** v110_teste_gnews_v111_integrado (já funcional, 7/7 testes passando)

---

## 1. Objetivo

Aumentar o **volume e a diversidade de captura** do sistema Ururau fazendo o monitor explorar **todos os grupos temáticos** do `consultas_google_news.json` em cada ciclo de coleta, em vez de usar apenas os termos prioritários do `radar_audiencia_config_v88.json`.

**O que muda da v111 base:**
- Antes: monitor coleta apenas via `coletar_por_termos_config()` (termos do radar)
- Depois: monitor coleta via **ciclo combinado** = termos do radar + todos os grupos temáticos configurados

---

## 2. Contexto e Estado Atual (v111 Base)

O sistema v111 base já está funcional:

```
ururau_v110_teste/
├── google_news_scraper/                 ← pacote Kimi (74 testes OK)
│   ├── __init__.py
│   ├── models.py, scraper.py, extractor.py, utils.py, config.py, logger.py
│   ├── cli.py
│   └── google_news_integrado.py         ← GoogleNewsIntegrado
├── ururau/coleta/
│   └── gnews_v111_integrado.py          ← wrapper (importa GoogleNewsIntegrado)
├── ururau/publisher/
│   ├── monitor.py                        ← monitor principal (patch aplicado)
│   └── monitor_v111_patch.py           ← patch de integração v111
├── ururau/tests/
│   └── test_gnews_v111.py              ← 7/7 mock tests passando
├── .env                                  ← flags URURAU_V111_* ativas
└── requirements.txt                      ← aiohttp, tldextract, etc.
```

**Flags ativas no .env:**
```env
URURAU_V111_GNEWS_INTEGRADO=1
URURAU_V111_GNEWS_MAX_TERMOS_POR_CICLO=20
URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO=3
URURAU_V111_GNEWS_JANELA_HORAS=4
URURAU_V111_GNEWS_MIN_CHARS_FONTE=1200
URURAU_V111_USAR_EXTRACAO_COMPLETA=1
URURAU_V111_SCORE_MINIMO_PAUTA=65
```

---

## 3. Especificação da v111.1 — Ciclo Combinado

### 3.1 Novo arquivo: `ururau/publisher/monitor_v111_ciclo_combinado.py`

Este módulo **substitui** `monitor_v111_patch.py` (ou complementa, se preferir manter compatibilidade).

#### Responsabilidades

1. Coletar de **múltiplas fontes em paralelo**:
   - Termos prioritários do radar (`coletar_por_termos_config`)
   - Grupos temáticos do `consultas_google_news.json`
2. **Deduplicar** pautas por URL após a soma
3. **Recalcular score** das pautas combinadas
4. **Ordenar por score** decrescente
5. **Limitar** o total para não sobrecarregar o pipeline
6. **Hidratar** pautas sem texto completo (chamar `extrair_fonte_v111`)
7. **Injetar** na fila do monitor no formato legado + moderno

#### Interface pública

```python
async def coletar_ciclo_combinado_v111(
    max_por_grupo: int = None,
    max_total: int = None,
    janela_horas: int = None,
    grupos_ativos: List[str] = None,
) -> List[Dict[str, Any]]:
    """
    Coleta combinada de termos + grupos temáticos.
    Retorna lista de pautas únicas, ordenadas por score.
    """

async def hidratar_pautas_v111(
    pautas: List[Dict[str, Any]],
    min_chars: int = None,
    max_concorrencia: int = 3,
) -> List[Dict[str, Any]]:
    """
    Extrai texto completo das pautas que não têm texto suficiente.
    Usa GoogleNewsIntegrado.extrair_fonte_completa() com cascata.
    """

def deduplicar_pautas_combinadas(
    pautas: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Remove duplicatas por URL normalizada (sem www, sem query params).
    Preserva a pauta com MAIOR SCORE quando há conflito.
    """

def recalcular_score_combinado(pauta: Dict[str, Any]) -> int:
    """
    Recalcula score considerando:
    - Base: 50
    - Fonte oficial: +20
    - Termo prioritário: +15
    - Texto longo (>2000 chars): +10
    - Recência < 1h: +15
    - Autor presente: +10
    - Imagem presente: +5
    - Canal definido: +5
    - BÔNUS grupo temático oficial (alerj, governo_rj, etc.): +5
    """
```

#### Constantes e mapeamentos

```python
# Grupos temáticos padrão (de consultas_google_news.json)
GRUPOS_PADRAO = [
    "campos_local",
    "norte_fluminense",
    "porto_do_acu",
    "rj_politica",
    "rj_policia",
    "governo_rj",
    "alerj",
    "deputados_rj",
    "pre_candidatos_governo_rj",
    "transparencia_e_investigacao",
    "utilidade_publica_rj",
    "servico_brasil",
    "alto_trafego_brasil",
    "alertas_globais",
]

# Grupos que recebem bônus de score (oficiais/prioritários)
GRUPOS_BONUS = [
    "alerj",
    "governo_rj",
    "transparencia_e_investigacao",
    "porto_do_acu",
    "rj_politica",
]

# Semáforo de concorrência (máximo de buscas simultâneas no Google News)
MAX_CONCORRENCIA_GNEWS = 3
```

#### Fluxo de execução (diagrama)

```
CICLO DO MONITOR (cada 30 min)
│
├─► [1] COLETA POR TERMOS (radar de audiência)
│   └─► coletar_por_termos_config(max_termos=20, max_resultados=3)
│   └─► retorna: pautas_termos (List[Dict])
│
├─► [2] COLETA POR GRUPOS TEMÁTICOS (em paralelo, max 3 concorrentes)
│   ├─► grupo "campos_local"      → 3 pautas
│   ├─► grupo "norte_fluminense"  → 3 pautas
│   ├─► grupo "porto_do_acu"      → 3 pautas
│   ├─► grupo "rj_politica"       → 3 pautas
│   ├─► grupo "rj_policia"        → 3 pautas
│   ├─► grupo "alerj"             → 3 pautas
│   ├─► grupo "governo_rj"        → 3 pautas
│   ├─► grupo "transparencia..."  → 3 pautas
│   └─► ... demais grupos
│   └─► retorna: pautas_grupos (List[Dict])
│
├─► [3] COMBINAÇÃO
│   └─► todas_pautas = pautas_termos + pautas_grupos
│
├─► [4] DEDUPLICAÇÃO POR URL
│   └─► mantém a de MAIOR SCORE quando há conflito
│   └─► retorna: pautas_unicas
│
├─► [5] FILTRO TEMPORAL
│   └─► descarta pautas fora da janela (padrão 4h)
│
├─► [6] SCORE MÍNIMO
│   └─► descarta pautas com score < URURAU_V111_SCORE_MINIMO_PAUTA (65)
│
├─► [7] ORDENAÇÃO
│   └─► sort by score desc, depois by data desc
│
├─► [8] HIDRATAÇÃO (texto + imagem)
│   └─► para pautas sem texto suficiente:
│       └─► extrair_fonte_v111(url, min_chars=1200)
│       └─► captura imagem via OpenGraph / Twitter Card / JSON-LD
│
├─► [9] INJEÇÃO NA FILA DO MONITOR
│   └─► converte para formato legado + moderno
│   └─► adiciona à fila interna do monitor
│
└─► [10] LOGS
    └─► [V111.1][CICLO] 12 pautas de termos + 24 de grupos = 36 brutas
    └─► [V111.1][DEDUP] 36 → 31 únicas
    └─► [V111.1][SCORE] 31 → 28 acima do mínimo
    └─► [V111.1][HIDRATA] 28 → 22 com texto suficiente
    └─► [V111.1][FILA] 22 pautas adicionadas
```

#### Formato da pauta (saída do ciclo combinado)

A pauta deve ter **todos** estes campos (modernos + legados):

```python
pauta = {
    # === Campos modernos v111 ===
    "titulo": "ALERJ aprova projeto...",
    "descricao": "Resumo...",
    "url": "https://folha1.com.br/artigo",
    "dominio": "folha1.com.br",
    "autor": "João Silva",
    "data_publicacao": "2026-04-30T10:30:00+00:00",
    "imagem": "https://folha1.com.br/img.jpg",
    "imagens": ["https://folha1.com.br/img.jpg"],
    "texto_fonte": "Texto completo...",
    "canal_sugerido": "Política",
    "score": 85,
    "fonte_tipo": "google_news",
    "termo_busca": "ALERJ",
    "grupo_tematico": "alerj",
    "metodo_extracao": "trafilatura",
    "chars_fonte": 3200,
    "cidade": "Rio de Janeiro",
    "regiao": "Rio de Janeiro",
    "coletado_em": "2026-04-30T11:00:00+00:00",
    "status": "pendente",

    # === Campos legados (obrigatórios para compatibilidade) ===
    "titulo_origem": "ALERJ aprova projeto...",      # alias de titulo
    "link_origem": "https://folha1.com.br/artigo",   # alias de url
    "resumo_origem": "Resumo...",                    # alias de descricao
    "fonte_nome": "Google News",                     # identificador
    "fonte_id": "gnews_v111",                        # id da fonte
    "canal_forcado": "Política",                     # alias de canal_sugerido
    "cleaned_source_text": "Texto completo...",      # alias de texto_fonte
    "raw_source_text": "Texto completo...",          # alias de texto_fonte
    "dossie": {},                                     # metadados internos
}
```

---

### 3.2 Alteração no `monitor.py`

O `monitor.py` principal deve chamar o ciclo combinado **em vez de** (ou **antes de**) chamar o v111 base.

#### Onde inserir

Localizar no `monitor.py` a seção onde o monitor verifica `URURAU_V111_GNEWS_INTEGRADO`.

**ANTES (v111 base):**
```python
if os.environ.get("URURAU_V111_GNEWS_INTEGRADO") == "1":
    from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111
    pautas_gnews = await coletar_pautas_gnews_v111(modo="termos_config")
    # adiciona à fila...
```

**DEPOIS (v111.1 ciclo combinado):**
```python
if os.environ.get("URURAU_V111_GNEWS_INTEGRADO") == "1":
    if os.environ.get("URURAU_V111_USAR_CICLO_COMBINADO") == "1":
        # NOVO: ciclo combinado (termos + grupos)
        from ururau.publisher.monitor_v111_ciclo_combinado import coletar_ciclo_combinado_v111
        pautas_gnews = await coletar_ciclo_combinado_v111()
    else:
        # LEGADO: apenas termos (v111 base)
        from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111
        pautas_gnews = await coletar_pautas_gnews_v111(modo="termos_config")

    # adiciona à fila...
```

---

### 3.3 Variáveis `.env` adicionais

Adicionar estas linhas ao `.env` (mantendo as anteriores):

```env
# ===== v111.1 — Ciclo Combinado =====
URURAU_V111_USAR_CICLO_COMBINADO=1
URURAU_V111_MAX_POR_GRUPO=3
URURAU_V111_MAX_TOTAL_PAUTAS=30
URURAU_V111_GRUPOS_ATIVOS=campos_local,norte_fluminense,porto_do_acu,rj_politica,rj_policia,alerj,governo_rj,transparencia_e_investigacao

# Configuração de hidratação
URURAU_V111_HIDRATAR_SEM_TEXTO=1
URURAU_V111_MAX_CONCORRENCIA_HIDRATA=3
URURAU_V111_BUSCAR_IMAGEM_OG=1
URURAU_V111_BUSCAR_IMAGEM_TWITTER=1
URURAU_V111_BUSCAR_IMAGEM_JSONLD=1
```

---

### 3.4 Logs esperados

```
[V111.1][INIT] Ciclo combinado iniciado (termos + 8 grupos)
[V111.1][TERMOS] Coletando termos prioritarios...
[V111.1][TERMOS] 12 pautas de termos
[V111.1][GRUPO][campos_local] 3 pautas
[V111.1][GRUPO][norte_fluminense] 3 pautas
[V111.1][GRUPO][porto_do_acu] 2 pautas
[V111.1][GRUPO][rj_politica] 3 pautas
[V111.1][GRUPO][rj_policia] 2 pautas
[V111.1][GRUPO][alerj] 3 pautas
[V111.1][GRUPO][governo_rj] 2 pautas
[V111.1][GRUPO][transparencia_e_investigacao] 3 pautas
[V111.1][COMBINADO] 12 termos + 21 grupos = 33 brutas
[V111.1][DEDUP] 33 → 27 unicas (6 duplicatas removidas)
[V111.1][FILTRO] 27 → 25 dentro da janela
[V111.1][SCORE] 25 → 22 acima do minimo (65)
[V111.1][ORDENADO] 22 pautas por score decrescente
[V111.1][HIDRATA] 22 pautas, 8 sem texto suficiente
[V111.1][HIDRATA][OK] 5 pautas hidratadas via trafilatura
[V111.1][HIDRATA][OK] 2 pautas hidratadas via readability
[V111.1][HIDRATA][FALHA] 1 pauta sem texto suficiente (descartada)
[V111.1][IMAGEM][OG] 15 imagens via OpenGraph
[V111.1][IMAGEM][TW] 3 imagens via Twitter Card
[V111.1][IMAGEM][JSONLD] 2 imagens via JSON-LD
[V111.1][IMAGEM][FALHA] 2 pautas sem imagem
[V111.1][FILA] 21 pautas adicionadas ao pipeline
```

---

## 4. Checklist de Implementação

### Fase 1: Arquivos
- [ ] Criar `ururau/publisher/monitor_v111_ciclo_combinado.py`
- [ ] Adicionar variáveis v111.1 ao `.env`
- [ ] Atualizar `monitor.py` para chamar ciclo combinado quando `URURAU_V111_USAR_CICLO_COMBINADO=1`

### Fase 2: Testes
- [ ] Criar `ururau/tests/test_v111_1_ciclo_combinado.py`
- [ ] Mock de `GoogleNewsIntegrado.coletar_por_termos_config()`
- [ ] Mock de `GoogleNewsIntegrado.coletar_grupo_tematico()` para 3 grupos
- [ ] Testar deduplicação (2 pautas com mesma URL → manter maior score)
- [ ] Testar ordenação por score
- [ ] Testar filtro temporal
- [ ] Testar hidratação mockada
- [ ] Verificar que todos os campos legados estão presentes

### Fase 3: Validação
- [ ] Rodar `pytest ururau/tests/test_v111_1_ciclo_combinado.py -v`
- [ ] Verificar que monitor não quebra com `URURAU_V111_USAR_CICLO_COMBINADO=0` (modo legado)
- [ ] Verificar logs com prefixo `[V111.1]`
- [ ] Rodar ciclo de monitor sem publicar (dry-run)

### Fase 4: Go-live
- [ ] Ativar `URURAU_V111_USAR_CICLO_COMBINADO=1`
- [ ] Monitorar por 24h
- [ ] Comparar volume: pautas/ciclo antes vs. depois

---

## 5. Rollback

```env
# Para voltar ao v111 base (apenas termos):
URURAU_V111_USAR_CICLO_COMBINADO=0

# Para voltar ao v110 legado:
URURAU_V111_GNEWS_INTEGRADO=0
URURAU_V110_MONITOR_GNEWS_LEGADO=1
```

---

## 6. Métricas de Sucesso

| Métrica | v111 Base | v111.1 Alvo | Como medir |
|---------|-----------|-------------|------------|
| Pautas brutas/ciclo | ~12 (termos) | ~30 (termos+grupos) | Logs `[V111.1][COMBINADO]` |
| Pautas únicas/ciclo | ~10 | ~25 | Logs `[V111.1][DEDUP]` |
| Pautas com texto OK | ~8 | ~20 | Logs `[V111.1][HIDRATA]` |
| Pautas com imagem | ~6 | ~18 | Logs `[V111.1][IMAGEM]` |
| Score médio | ~70 | ~75 | Média no log |
| Tempo de ciclo | ~2 min | ~4 min | Timestamps |

---

## 7. Notas para Implementador (ChatGPT)

### Regras críticas:
1. **NUNCA** remova `monitor_v111_patch.py` — o ciclo combinado pode coexistir
2. **SEMPRE** mantenha campos legados (`titulo_origem`, `link_origem`, etc.)
3. **SEMPRE** use `asyncio.Semaphore(3)` para limitar concorrência no Google News
4. **SEMPRE** deduplique mantendo a pauta de MAIOR SCORE
5. **SEMPRE** logue com prefixo `[V111.1]`
6. **NUNCA** bloqueie o monitor se o Google News falhar — retorne lista vazia

### Estrutura do arquivo a criar:

```python
# ururau/publisher/monitor_v111_ciclo_combinado.py
"""
v111.1 — Ciclo Combinado de Coleta Google News
Termos prioritários + grupos temáticos + dedup + score + hidratação
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections import OrderedDict

from ururau.coleta.gnews_v111_integrado import (
    coletar_pautas_gnews_v111,
    extrair_fonte_v111,
)

# ... (implementar conforme especificação acima)
```

### Dependências:
- `google_news_scraper` (já instalado)
- `aiohttp` (já instalado)
- `beautifulsoup4` (já instalado)
- `lxml` (já instalado)
- Nenhuma dependência nova é necessária
