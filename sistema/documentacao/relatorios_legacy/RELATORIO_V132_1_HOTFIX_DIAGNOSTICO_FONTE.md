# URURAU v132.1 - hotfix do Diagnóstico de Fonte

Correção crítica da aba `Config > Diagnóstico de Fonte`.

## Problema corrigido

Na v132, o botão verde **Diagnosticar, aplicar e testar** chamava `_diagnosticar_aplicar(self)`, mas essa função não existia no arquivo:

`ururau/ui/diagnostico_fontes_tab_v130.py`

Isso gerava erro em Tkinter:

`NameError: name '_diagnosticar_aplicar' is not defined`

## Correção aplicada

Foi criada a função `_diagnosticar_aplicar(self)` com o fluxo único esperado:

1. roda diagnóstico completo;
2. gera relatório técnico;
3. gera perfil operacional;
4. aplica com backup;
5. testa a fonte imediatamente;
6. salva relatórios TXT/JSON;
7. exibe na tela se ficou `APLICADO E FUNCIONAL` ou `NÃO APLICADO`;
8. informa se será usada na próxima coleta geral.

## O que não foi alterado

- motor de coleta RSS;
- AutoFontes v131;
- Regionais;
- Especiais;
- Campos 24 Horas;
- NF Notícias;
- fila de pautas;
- publicação;
- CopyDesk.

