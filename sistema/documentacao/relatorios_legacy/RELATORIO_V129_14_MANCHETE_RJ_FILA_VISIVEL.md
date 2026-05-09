# v129.14 — Manchete RJ com integração completa na Fila de Pautas

## Problema corrigido

Na v129.13, o coletor especial da Manchete RJ passou a encontrar e salvar pauta, mas a matéria podia não aparecer na Fila de Pautas porque o fallback fora da janela era aceito no salvamento, porém o carregador visual da fila continuava aplicando o filtro rígido de publicação recente.

O comportamento era parecido com o problema antigo do Campos 24 Horas: a coleta achava material, a auditoria marcava como enviado, mas a pauta não ficava visível para o operador.

## Correção aplicada

1. O adaptador da Manchete RJ agora normaliza a pauta no mesmo contrato usado pelo coletor especial do Campos 24 Horas:
   - titulo_origem e titulo
   - link_origem, url e link
   - fonte_nome, fonte e nome_fonte
   - data_pub_fonte, data_pub_fonte_br, data_publicacao e publicado_em
   - uid e _uid
   - tipo_fonte, origem_feed, origem
   - _v94_listagem_rapida
   - _v94_precisa_hidratar
   - precisa_hidratar_fonte

2. Quando a Manchete RJ usa fallback operacional fora da janela, a pauta recebe:
   - _v12914_forcar_visivel_fila=True
   - _v12914_motivo_visivel_fila=mancheterj_fallback_operacional

3. O carregador da fila agora respeita essa exceção específica, desde que a variável abaixo esteja ativa:
   - URURAU_V12914_EXIBIR_EXCECOES_FILA=1

4. Após inserir pauta da Manchete RJ, o painel força um refresh da fila.

## O que não foi alterado

- Motor geral de RSS
- Campos 24 Horas
- XML/Sitemap
- Busca por Termos
- Fontes Especiais
- Copydesk
- Publicação
- WhatsApp

## Resultado esperado

Se o diagnóstico disser:

OK | Manchete RJ | encontradas=1 | enviadas=1

então a pauta também deve aparecer na Fila de Pautas visível.
