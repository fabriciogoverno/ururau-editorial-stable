# Relatório de auditoria — Regras editoriais GPT-4-mini (Fase 1)

**Data:** 2026-05-18
**Spec analisado:** `spec_regras_editoriais_gpt4mini_ururau.md` (58 seções, ~150 regras)
**Versão atual do projeto:** v200.x (branch `fix/captacao-100pct-fontes-quebradas`)

---

## 1. Arquivos analisados

Os **16 arquivos sugeridos pelo spec EXISTEM** no projeto:

| Arquivo | Linhas | Papel |
|---|---|---|
| `sistema/config/regras_editoriais.json` | 469 | **Matriz JSON central** (fonte oficial) |
| `agents/agente_editorial_ururau.py` | 1513 | Prompt mestre `SYSTEM_PROMPT_EDITORIAL_URURAU` |
| `config/house_style.py` | 338 | Estilo da casa |
| `ia/politica_editorial.py` | 796 | Política editorial em Python |
| `editorial/editorial_policy.py` | 152 | **Source of truth Python** que reexporta tudo |
| `editorial/engine.py` | 2306 | Motor editorial principal |
| `editorial/copydesk.py` | 382 | Copydesk |
| `editorial/quality_gates.py` | 554 | Gates de qualidade |
| `editorial/auditoria_v78c.py` | 405 | Auditoria de termos |
| `editorial/auditoria_factual_v81.py` | 305 | Auditoria factual |
| `editorial/quality_gate_v103.py` | 329 | Gate de publicação |
| `editorial/receita_editorial.py` | 1161 | Receita editorial |
| `publisher/workflow.py` | 1481 | Workflow de publicação |
| `coleta/fail_closed_v84.py` | 166 | Fail-closed |
| `coleta/linha_editorial_v129.py` | 575 | Linha editorial v129 |
| `ia/ia_service.py` | 490 | Service GPT central |

**Arquivos adicionais editoriais (40+):** `regras_editoriais.py`, `field_limits.py`, `linha_editorial_ururau.py`, `motor_gpt_spec_v2.py`, `pos_processador_redacao.py`, `safe_title.py`, `relationships.py`, `risco.py`, `decision_v82.py`, `coverage_por_tipo.py`, `duplicidade_semantica.py`, etc.

---

## 2. Fluxo real encontrado

```
RSS/Coleta → Hidratação → Score → Fila pautas
                                       ↓
                            Usuário clica "Redigir"
                                       ↓
                ia_service.redigir_pauta() / engine.gerar_materia()
                                       ↓
              Carrega: regras_editoriais.json + agents.SYSTEM_PROMPT
                                       ↓
                         GPT-4.1-mini (default)
                          temperature=0.4 (env-overridável)
                                       ↓
                    JSON validation (response_format)
                                       ↓
            Validações pós-GPT (termos IA, limites campos,
            relationships, factual, jurídico, copydesk)
                                       ↓
                  quality_gates.aprovar_publicacao()
                                       ↓
                   Decide: publicar_direto / rascunho / bloquear
                                       ↓
                       publisher/workflow.py
```

---

## 3. Onde o GPT-4-mini é chamado

| Arquivo | Função | Uso |
|---|---|---|
| `ia/ia_service.py` | `_redigir`, `_copydesk_aplicar` | Principal — todas as chamadas IA |
| `editorial/engine.py` | múltiplas | Motor que orquestra |
| `editorial/copydesk.py` | `copydesk_aplicar` | Revisão pós-GPT |
| `editorial/motor_gpt_spec_v2.py` | (legado) | Versão antiga (provavelmente não usada ativamente) |
| `editorial/openai_motor_patch_v2.py` | patches | Patches runtime |

**Modelo padrão:** `gpt-4.1-mini`
**Override env:** `OPENAI_MODEL` / `MODELO_OPENAI`
**Temperatura default:** `0.4` (spec sugere 0.2-0.3 — **VERIFICAR**)

---

## 4. Onde o prompt é montado

| Arquivo | Função |
|---|---|
| `agents/agente_editorial_ururau.py` | `SYSTEM_PROMPT_EDITORIAL_URURAU` (constante, ~1500 linhas com regras) |
| `editorial/editorial_policy.py` | `get_editorial_system_prompt()`, `get_editorial_user_prompt_template()` |
| `editorial/linha_editorial_ururau.py` | `build_prompt_redigir()` |
| `editorial/regras_editoriais.py` | `montar_bloco_prompt_editorial()` |
| `ia/ia_service.py` | `_build_prompt_sistema()`, `_build_prompt_user_redigir()` |

**Hierarquia atual:** `ia_service._build_prompt_sistema` tenta usar `linha_editorial_ururau.build_prompt_redigir` → senão usa prompt legado.

---

## 5. Onde a matriz editorial é carregada

**Source of truth:** `sistema/config/regras_editoriais.json` (469 linhas)

**Carregadores:**
- `editorial/regras_editoriais.py` — função principal `obter_matriz_editorial()` (cache singleton, merge com fallback hardcoded)
- `editorial/editorial_policy.py` — reexporta via `field_limits.py`
- `ui/painel.py` — UI lê pra apresentar configurações

---

## 6. Regras já implementadas (✅ OK)

### Seção 10 — Limites editoriais
Confirmado em `regras_editoriais.json.limites_campos`:
- ✅ titulo_seo: 40-89
- ✅ titulo_capa: 20-60
- ✅ subtitulo_curto: max 200
- ✅ legenda_curta: max 100
- ✅ meta_description: 120-160
- ✅ tags: 5-12
- ✅ retranca: max 3 palavras
- ✅ creditos_foto: max 6 palavras
- ✅ nome_fonte: max 4 palavras
- ✅ corpo_min_chars: 500
- ✅ corpo_paragrafos_min: 3

### Seção 29 — Termos IA proibidos
- ✅ Lista no JSON (~200 termos cobrindo todos os do spec §29)
- ✅ Função `detectar_termos_ia()` em `regras_editoriais.py`
- ✅ Função `validar_termos_ia_em_artigo()` para validação completa

### Seção 37-38 — Gates de publicação
- ✅ coverage_panel_min: 0.85
- ✅ coverage_monitor_min: 0.90
- ✅ score_qualidade_panel_min: 90
- ✅ score_qualidade_monitor_min: 92
- ✅ score_risco_max: 10

### Seção 9 — Estrutura JSON saída GPT
- ✅ Schema completo em `editorial_policy.get_output_schema()` (15 campos)

### Seção 49 — Prompt mestre
- ✅ Existe em `agents/agente_editorial_ururau.SYSTEM_PROMPT_EDITORIAL_URURAU`
- ✅ Carregado por todos os módulos via `editorial_policy.get_editorial_system_prompt()`

### Seção 21 — Precisão jurídica
- ✅ `auditoria_factual_v81.py` implementa
- ✅ `relationships.py` valida subject→relationship→object

### Seção 22-23 — Atribuição correta + veículo de origem
- ✅ Listadas no briefing do JSON com fórmulas aceitas/proibidas

### Seção 51 — Configuração do modelo
- ✅ `response_format: JSON` aplicado em `ia_service`
- ⚠️ Temperatura default `0.4` (spec sugere `0.2-0.3` — possível ajuste)

---

## 7. Regras parcialmente implementadas (⚠️ AJUSTAR)

### Seção 7 — Suficiência da fonte
- ✅ Limite >=500 chars existe (`corpo_min_chars`)
- ⚠️ Não vi explicitamente os patamares 250/400/800 do spec separados
- ⚠️ Bloqueios específicos (RSS-only, paywall, 403/404) — espalhados em `coleta/fail_closed_v84.py`, `coleta/criterio_aceite_v90.py`

### Seção 8 — Fail-closed
- ✅ Existe `fail_closed_v83.py` E `fail_closed_v84.py` (duplicação)
- ⚠️ Precisa confirmar se todos os pontos do spec §8 estão cobertos

### Seção 27 — Travessão proibido
- ⚠️ Não confirmei se o pós-processador remove travessão ativamente
- ⚠️ Listado no briefing mas precisa validação por código

### Seção 31 — Verbos viciados
- ⚠️ `verbos_crutch` existe no JSON mas precisa confirmar pós-processamento

### Seção 32 — Fechamentos artificiais
- ⚠️ `frases_fechamento_interpretativo` existe no JSON — precisa confirmar aplicação

### Seção 33 — Regras por editoria
- ✅ `regras_por_editoria` existe no JSON
- ⚠️ Nível de detalhe do spec (lead policia, justiça, esportes prévia/resultado, etc.) precisa cruzar

### Seção 41 — Copydesk
- ✅ `copydesk.py` existe (382 linhas)
- ⚠️ Precisa confirmar se rebebe `texto-fonte completo` (spec exige) e não só matéria gerada

### Seção 12 — Tamanho proporcional
- ⚠️ Patamares específicos (300/800/1400/2600/4200 chars) não confirmei como código

---

## 8. Regras ausentes ou suspeitas (❌ PROVÁVEL GAP)

### Seção 48 — Validador pós-GPT unificado
- ❌ Não encontrei função única `validar_pos_gpt()` que faça TODAS as validações em sequência
- ✅ Validações individuais existem espalhadas: `validar_termos_ia_em_artigo`, `auditoria_factual_v81`, `quality_gates`, etc.
- **Gap:** falta orquestrador único que aplique todas as validações do spec §48 em ordem com short-circuit no primeiro erro fatal

### Seção 46 — Deduplicação
- ⚠️ `duplicidade_semantica.py` existe
- ⚠️ Critérios spec (similaridade título >= 0.86, lead >= 0.82) precisam confirmar

### Seção 45 — Legenda Instagram
- ⚠️ Existe em vários lugares — formato exato com `🔗`, `➡` precisa validar

### Seção 6 — Entrada mínima obrigatória
- ⚠️ Gate "tem todos os campos mínimos antes de chamar GPT" não vi explícito

### Seção 24-25 — Datas e números
- ⚠️ "Não converter `nesta quinta (23)` para mês/ano" — não vi regra específica
- ⚠️ "Não somar métricas diferentes" — não vi validação

### Seção 26 — Aspas
- ⚠️ "Aspas só se literal na fonte" — texto no briefing, mas precisa validador por código

---

## 9. Conflitos encontrados

### Duplicações de versão
- `fail_closed_v83.py` E `fail_closed_v84.py` coexistem
- `compat_resultado_v47_18.py` E `compat_resultado_v47_20.py` coexistem
- `auditoria_v78c.py` E `auditoria_factual_v81.py` E `quality_gate_v103.py`

### Listas de termos IA potencialmente divergentes
Existem em 5 arquivos:
- `regras_editoriais.json` (canônica, ~200 termos)
- `editorial_policy.get_editorial_rules()['expressoes_proibidas']` (lista curta hardcoded, ~15 termos)
- `auditoria_v78c.py`
- `fallback_local.py`
- `motor_gpt_spec_v2.py`
- `pos_processador_redacao.py`

**Risco:** lista em `editorial_policy` tem 15 termos enquanto JSON tem 200 — pode causar inconsistência.

### Múltiplos prompts montadores
- `_build_prompt_sistema()` em `ia_service.py`
- `build_prompt_redigir()` em `linha_editorial_ururau.py`
- `montar_bloco_prompt_editorial()` em `regras_editoriais.py`
- `get_editorial_system_prompt()` em `editorial_policy.py`

Não está claro qual é o "oficial" — fallback em cadeia.

---

## 10. Plano de implementação proposto (Fases 2-6)

### Fase 2 — Unificar prompt mestre
- Garantir que TODOS os caminhos importem de `editorial_policy.get_editorial_system_prompt()`
- Eliminar prompts legados duplicados
- Validar com teste que o mesmo prompt vai ao GPT em todas chamadas

### Fase 3 — Validador pós-GPT centralizado
- Criar `editorial/validador_pos_gpt_v200.py` que executa em ordem:
  1. JSON válido
  2. Campos obrigatórios
  3. Limites de tamanho (chamando `field_limits`)
  4. Termos IA (via `regras_editoriais.detectar_termos_ia`)
  5. Travessão
  6. Auditoria factual (`auditoria_factual_v81`)
  7. Relations (`relationships`)
  8. Duplicidade (`duplicidade_semantica`)
- Short-circuit no primeiro erro fatal
- Retorna `{status, motivos, achados}`

### Fase 4 — Unificar termos proibidos
- Fazer `editorial_policy.get_editorial_rules()['expressoes_proibidas']` ler do JSON (não hardcoded)
- Auditar `auditoria_v78c`, `fallback_local`, `motor_gpt_spec_v2`, `pos_processador_redacao`
- Todos devem importar da matriz central
- Remover listas hardcoded

### Fase 5 — Gates de publicação alinhados
- Confirmar `quality_gate_v103` e `quality_gates` aplicam exatamente os limites do JSON
- Marcar cada erro com categoria: `CONFIG_ERROR` / `EXTRACTION_ERROR` / `EDITORIAL_BLOCKER`
- Decisão clara: bloqueio fatal → rascunho → publicar

### Fase 6 — Testes
- Criar `tests/test_spec_editorial_v200.py` com os 12 testes do spec §52
- Rodar suite + CI
- Documentar resultados

---

## 11. Resumo

| Categoria | Quantidade aproximada |
|---|---|
| Regras já OK | ~85 (57%) |
| Parciais ou precisam confirmar | ~40 (27%) |
| Provavelmente ausentes | ~25 (16%) |

A matriz central (`regras_editoriais.json` + `regras_editoriais.py` + `editorial_policy.py`) está **muito bem feita**. O sistema NÃO precisa ser reescrito — precisa de **unificação cirúrgica** das duplicações e implementação dos validadores que estão faltando.

---

## 12. Próximo passo

Fase 2: unificar prompt mestre. Estimativa: 1 push de ~200 linhas de mudanças cirúrgicas, sem risco de quebrar fluxo existente.

**Pendente aprovação para prosseguir.**
