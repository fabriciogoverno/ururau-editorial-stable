# Relatório de auditoria — Integração IA / fallback editorial v46.7

## Diagnóstico objetivo

O problema central não era apenas prompt editorial. O projeto tinha uma arquitetura de fallback silencioso: quando a chamada ao GPT falhava, retornava vazia, produzia JSON inválido ou gerava texto curto, outras camadas reconstruíam a matéria localmente e o painel continuava tratando o fluxo como se a redação tivesse sido concluída normalmente.

Resultado prático: o padrão editorial podia ser ignorado sem que o operador soubesse se o texto saiu do GPT-4.1-mini, do engine local, do fallback v78/v87/v97 ou de uma camada emergencial.

## Causas encontradas

1. `ururau/editorial/engine.py`
   - `_call_gpt_with_brief()` capturava erro da OpenAI e devolvia `{}`.
   - O fluxo seguinte gerava rascunho local sem diagnóstico claro.
   - Falhas de API, timeout, cota, modelo inválido ou JSON inválido ficavam mascaradas.

2. `ururau/editorial/redacao.py`
   - O wrapper final podia classificar a geração como `ia_ou_engine`, rótulo ambíguo que não prova chamada real ao GPT.
   - Camadas antigas podiam devolver matéria sem telemetria de IA.

3. `ururau/editorial/fallback_local.py`
   - Gerava matéria local segura, mas sem sinalizar de forma forte no objeto final e no JSON da matéria.

4. `ururau/editorial/copydesk.py`
   - Quando o copydesk IA falhava, o sistema apenas mantinha os dados anteriores.
   - O painel não recebia um status estruturado de falha da IA.

5. `ururau/editorial/copydesk_regenerador_v87.py` e `premium_v97.py`
   - Tinham chamadas próprias à OpenAI e fallbacks próprios.
   - Quando a IA retornava texto curto, o corpo era substituído por fallback local sem marcação suficiente.

6. `ururau/publisher/workflow.py`
   - O log operacional registrava redação/copydesk, mas não registrava explicitamente se a OpenAI respondeu.

7. `ururau/ui/painel.py`
   - Sem cliente OpenAI, o painel apenas imprimia aviso no console técnico.
   - Havia erro intermitente de interface: `_tkinter.tkapp object has no attribute _lbl_stats`.

## Correções aplicadas

### 1. Novo módulo de diagnóstico

Arquivo criado:

- `ururau/ia/diagnostico.py`

Funções principais:

- `trace_openai_ok()`
- `trace_openai_erro()`
- `trace_fallback()`
- `aplicar_trace_em_dados()`
- `aplicar_trace_em_materia()`

Logs criados automaticamente:

- `logs/ia_diagnostico.log`
- `logs/ia_diagnostico.jsonl`

Esses arquivos informam etapa, provedor, modelo, status, sucesso, UID e motivo da falha/fallback.

### 2. Novos campos em `Materia`

Arquivo alterado:

- `ururau/core/models.py`

Campos adicionados:

- `modo_geracao`
- `ia_provider`
- `ia_modelo`
- `ia_status`
- `ia_etapa`
- `ia_chamada_ok`
- `ia_fallback_motivo`
- `ia_erros`

### 3. Estados agora são explícitos

Quando o GPT-4.1-mini funciona:

- `modo_geracao = openai_gpt4mini`
- `ia_provider = openai`
- `ia_modelo = gpt-4.1-mini`
- `ia_status = openai_ok`
- `ia_chamada_ok = True`

Quando a OpenAI falha ou o texto final sai de fallback:

- `modo_geracao = fallback_sem_ia`
- `ia_provider = local`
- `ia_chamada_ok = False` ou `True` quando a OpenAI respondeu, mas o corpo foi substituído por fallback por estar curto/inválido
- `ia_status` passa a indicar o motivo, como:
  - `openai_invalid_api_key`
  - `openai_quota_or_rate_limit`
  - `openai_timeout`
  - `openai_model_error`
  - `openai_json_invalid`
  - `openai_call_failed`
  - `fallback_local`
  - `fallback_local_copydesk_v87`
  - `fallback_local_premium_v97`
  - `openai_ok_resposta_curta_fallback_local`

Quando uma camada antiga devolver texto sem telemetria:

- `modo_geracao = sem_telemetria_ia`
- `ia_status = sem_telemetria_ia`

Isso substitui o rótulo ambíguo `ia_ou_engine`.

### 4. Workflow agora registra diagnóstico

Arquivo alterado:

- `ururau/publisher/workflow.py`

Novos logs de auditoria:

- `ia_diagnostico`
- `copydesk_ia_diagnostico`

Exemplo de log esperado:

```text
ia_diagnostico: modo=openai_gpt4mini | status=openai_ok | modelo=gpt-4.1-mini
```

Ou, em falha:

```text
ia_diagnostico: modo=fallback_sem_ia | status=openai_invalid_api_key | modelo=gpt-4.1-mini | motivo=Chave OpenAI inválida ou sem permissão.
```

### 5. Painel passa a avisar quando não há IA

Arquivo alterado:

- `ururau/ui/painel.py`

Mudanças:

- Se `client OpenAI` estiver ausente, o painel mostra status visível: `IA OpenAI indisponível: redigindo por fallback local e marcando diagnóstico.`
- Após concluir redação, o status informa: `Redação concluída | IA: <modo>/<status>`.
- Corrigido erro `_lbl_stats` com verificação segura antes de atualizar o label.

### 6. Copydesk e regeneradores deixam de mascarar falha

Arquivos alterados:

- `ururau/editorial/copydesk.py`
- `ururau/editorial/copydesk_regenerador_v87.py`
- `ururau/editorial/premium_v97.py`

Agora, quando o copydesk/regenerador usar fallback local, o JSON da matéria recebe campos de diagnóstico. Quando a OpenAI responder, mas entregar corpo curto demais e o sistema substituir por fallback, isso fica registrado como `openai_ok_resposta_curta_fallback_local`.

## Arquivos alterados

- `ururau/ia/diagnostico.py`
- `ururau/core/models.py`
- `ururau/editorial/engine.py`
- `ururau/editorial/fallback_local.py`
- `ururau/editorial/redacao.py`
- `ururau/editorial/premium_v97.py`
- `ururau/editorial/copydesk.py`
- `ururau/editorial/copydesk_regenerador_v87.py`
- `ururau/publisher/workflow.py`
- `ururau/ui/painel.py`

## Testes realizados

1. Compilação Python de todo o pacote:

```bash
python -m compileall -q ururau
```

Resultado: sem erro de sintaxe.

2. Teste de redação com `client=None`:

Resultado esperado e confirmado:

```text
modo=fallback_sem_ia
status=fallback_local
ok=False
gj_modo=fallback_sem_ia
```

3. Geração de log em:

```text
logs/ia_diagnostico.log
logs/ia_diagnostico.jsonl
```

## Observação importante

Não foi feita chamada real à OpenAI neste ambiente porque não há execução externa garantida aqui. A correção foi validada por compilação e por teste local do caminho de fallback, que era justamente o ponto que estava sendo mascarado.

## Como aplicar o patch

1. Feche o painel.
2. Faça backup da pasta atual.
3. Extraia o ZIP do patch sobre a raiz do projeto, preservando as pastas.
4. Não substitua seu `.env` por nenhum arquivo externo.
5. Inicie o painel normalmente.
6. Redija uma pauta de teste.
7. Verifique:
   - status no painel;
   - log do workflow;
   - `logs/ia_diagnostico.log`;
   - `logs/ia_diagnostico.jsonl`.

## Critério de aceite

A correção está correta se, para cada matéria gerada, for possível responder claramente:

1. O GPT-4.1-mini respondeu?
2. Qual modelo foi usado?
3. Se falhou, qual foi o erro?
4. Se houve fallback, qual camada usou fallback?
5. O corpo final veio da OpenAI ou de fallback local?

