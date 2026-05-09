# RELATÓRIO v102 - Monitor 24h com Copydesk IA antes da publicação

## Objetivo

Ajustar o robô de monitoramento 24h para que a matéria gerada automaticamente seja enviada também automaticamente ao Copydesk IA antes de qualquer publicação direta no CMS.

## Fluxo v102

1. Coleta da pauta.
2. Extração e limpeza da fonte.
3. Redação automática da matéria.
4. Pacote editorial: título, subtítulo, legenda, tags, meta description e campos SEO.
5. **Copydesk IA automático v102.**
6. Reaplicação de auditoria factual após o Copydesk, porque o texto pode ter mudado.
7. Verificação de risco.
8. Persistência local.
9. Decisão: publicar direto, salvar como rascunho ou bloquear.
10. Envio ao CMS.

## Arquivos alterados

- `ururau/publisher/workflow.py`
- `ururau/publisher/monitor.py`
- `.env`
- `VERSAO.txt`

## Implementação

Criado o método:

```python
WorkflowPublicacao.etapa_copydesk_automatico_v102(...)
```

Esse método:

- chama `pipeline_copydesk()`;
- passa a matéria recém-gerada para a IA do Copydesk;
- sincroniza os campos revisados de volta na matéria;
- mantém aliases compatíveis (`titulo_seo` -> `titulo`, `corpo_materia` -> `conteudo` etc.);
- registra histórico de correção em `historico_correcoes`;
- detecta se o Copydesk devolveu corpo curto mesmo com fonte longa;
- tenta regenerar pela fonte quando o corpo revisado fica insuficiente;
- reaplica `auditoria_factual_v81` depois da revisão;
- se o Copydesk falhar, bloqueia publicação direta e força rascunho/revisão.

## Segurança editorial

A v102 não publica direto se o Copydesk automático falhar. Nessa situação, a matéria pode ser salva como rascunho, mas não deve ir ao ar automaticamente.

## Logs esperados

Durante o monitor 24h, devem aparecer linhas como:

```txt
copydesk_v102: Enviando matéria automática ao Copydesk IA antes da publicação.
copydesk_v102: Copydesk IA concluído sem problemas residuais.
```

Se houver problema:

```txt
copydesk_v102: Falha no Copydesk automático: ... Direta bloqueada; rascunho permitido.
```
