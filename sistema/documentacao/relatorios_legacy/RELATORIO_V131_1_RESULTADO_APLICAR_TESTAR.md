# v131.1 — Resultado claro no Aplicar e Testar

## Objetivo
Corrigir a falha de usabilidade da ferramenta de Diagnóstico de Fonte: depois de clicar em **Aplicar e testar perfil com backup**, o operador precisava descobrir manualmente se a fonte realmente foi aplicada, se o perfil foi salvo e se seria usada na próxima coleta.

## Implementação

A partir desta versão, o botão **Aplicar e testar perfil com backup** sempre retorna um relatório executivo no topo da tela com:

- Fonte e domínio
- Aba/grupo escolhido: RSS, Especiais ou Regionais
- Estratégia aplicada
- Parser operacional usado
- Status final: aplicado e funcional SIM/NÃO
- Se será usada na próxima coleta geral
- Quantidade de pautas geradas no teste
- Itens brutos lidos
- Itens com título/link
- Itens aceitos
- Tentativas técnicas executadas
- Arquivo `perfis_fontes_v131.json` salvo ou não
- Arquivos de aba sincronizados
- Relatório TXT/JSON salvo em `relatorios_diagnostico_fontes/aplicacoes_v131/`

## Regra operacional

A fonte só é marcada como **APLICADO E FUNCIONAL** se o teste imediato gerar pauta real. Se não gerar, o sistema exibe **NÃO APLICADO** e informa o motivo.

## Arquivos alterados

- `sistema/ururau/ui/diagnostico_fontes_tab_v130.py`
- `sistema/ururau/coleta/aplicador_diagnostico_v130.py`

## Preservado

Não houve alteração no motor de coleta geral, fila, publicação, WhatsApp, Campos 24 Horas, Manchete RJ, NF Notícias ou demais adaptadores.
