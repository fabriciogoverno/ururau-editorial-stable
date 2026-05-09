# PURAL/URURAU Editorial v46.8 — Auditoria IA final

## Objetivo

Entregar uma versão corrigida em que o sistema não esconda mais falhas da OpenAI/GPT Mini atrás de fallback local silencioso e em que o padrão editorial fique mais previsível.

## Correções principais

1. Diagnóstico autoritativo da IA

- `modo_geracao=openai_gpt4mini` quando o texto final veio de chamada real OpenAI bem-sucedida.
- `modo_geracao=fallback_sem_ia` quando o texto final veio de fallback local.
- `ia_status` agora preserva o erro raiz da OpenAI quando houver, por exemplo `openai_invalid_api_key`, `openai_quota_or_rate_limit`, `openai_timeout` ou `openai_json_invalid`.
- `ia_texto_final_origem` indica se o texto final veio de `openai` ou `fallback_local`.
- `ia_openai_status` guarda o status específico da chamada OpenAI, mesmo quando o texto final foi refeito por fallback local.

2. Logs dedicados

O sistema grava diagnóstico em:

- `logs/ia_diagnostico.log`
- `logs/ia_diagnostico.jsonl`

3. Painel com aviso claro

Ao redigir, o painel agora informa:

- modo de geração;
- status da IA;
- origem do texto final;
- status da OpenAI quando houver.

4. Inicialização corrigida

`ururau_painel.py` agora valida configuração OpenAI antes de criar o cliente. Criar o cliente não é mais tratado como prova de funcionamento do GPT; a prova real fica registrada somente quando a chamada ao modelo retorna `openai_ok`.

5. Fallback sem mascarar erro

Quando a OpenAI falha e o fallback local gera texto, o sistema não chama isso de IA. O objeto final mantém:

- `modo_geracao=fallback_sem_ia`
- `ia_texto_final_origem=fallback_local`
- `ia_status` com o erro raiz, quando aplicável.

6. Correção de classificação editorial

Foi corrigido falso positivo de classificação que podia jogar matéria policial para Economia. O erro vinha de busca por substring curta: termos como `nis` e `quem` batiam dentro de palavras como `Ministério` e `esquema`.

Agora termos curtos são avaliados com limite de palavra.

7. Retranca de uma palavra

O padrão foi ajustado para retranca com uma palavra, conforme uso editorial solicitado.

8. Validador incluído

Novos arquivos:

- `VALIDAR_AUDITORIA_IA_V46_8.py`
- `VALIDAR_SEM_CHAMAR_OPENAI.bat`
- `TESTAR_IA_DIAGNOSTICO.bat`

## Como testar sem gastar API

Execute:

```bat
VALIDAR_SEM_CHAMAR_OPENAI.bat
```

Esse teste valida sintaxe e prova que o fallback fica marcado como `fallback_sem_ia`.

## Como testar a OpenAI real

Execute:

```bat
TESTAR_IA_DIAGNOSTICO.bat
```

Esse teste faz uma chamada curta ao modelo configurado no `.env` e registra o resultado em `logs/ia_diagnostico.log`.

## Resultado dos testes nesta revisão

- `python -m compileall -q ururau`: OK
- `python VALIDAR_AUDITORIA_IA_V46_8.py`: OK
- Fallback local: `modo_geracao=fallback_sem_ia`
- Origem final: `ia_texto_final_origem=fallback_local`
- Retranca no teste policial: `Polícia`
- Simulação de OpenAI 401: `ia_status=openai_invalid_api_key` e texto final como `fallback_local`

## Arquivos alterados

- `ururau/ia/diagnostico.py`
- `ururau/core/models.py`
- `ururau/editorial/engine.py`
- `ururau/editorial/redacao.py`
- `ururau/editorial/fallback_local.py`
- `ururau/editorial/premium_v97.py`
- `ururau/editorial/copydesk.py`
- `ururau/editorial/copydesk_regenerador_v87.py`
- `ururau/editorial/editorial_policy.py`
- `ururau/editorial/field_limits.py`
- `ururau/editorial/auditoria_v78c.py`
- `ururau/editorial/quality_gates.py`
- `ururau/editorial/motor_gpt_spec_v2.py`
- `ururau/agents/agente_editorial_ururau.py`
- `ururau/publisher/workflow.py`
- `ururau/ui/painel.py`
- `ururau/ui/copydesk_painel.py`
- `ururau_painel.py`
- `VALIDAR_AUDITORIA_IA_V46_8.py`
- `VALIDAR_SEM_CHAMAR_OPENAI.bat`
- `TESTAR_IA_DIAGNOSTICO.bat`
