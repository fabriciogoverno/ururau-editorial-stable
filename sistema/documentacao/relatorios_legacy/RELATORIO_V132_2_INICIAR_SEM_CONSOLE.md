# URURAU v132.2 — Inicialização sem console externo persistente

Correção solicitada: ao clicar para iniciar o painel visual, a janela CMD/PowerShell não deve ficar aberta, porque o console operacional já existe dentro do painel.

## Alterações

- `INICIAR.bat` da raiz agora chama `sistema/INICIAR_OCULTO.bat` em modo oculto e fecha imediatamente.
- `sistema/INICIAR.bat` também virou um delegador oculto, para o caso de ser aberto diretamente.
- `sistema/INICIAR_OCULTO.bat` prepara ambiente, valida `.env`, executa reparos leves e abre o painel com `pythonw.exe`.
- `sistema/INICIAR_PAINEL_GUI.pyw` abre o painel sem console e redireciona logs para `sistema/logs/painel_gui.log`.
- `sistema/INICIAR_CONSOLE.bat` preserva o modo antigo visível para diagnóstico técnico, se algum dia for necessário.
- `sistema/INICIAR_SILENCIOSO.vbs` foi incluído como opção de inicialização 100% sem console, caso seja criado atalho direto para ele.

## Resultado esperado

Ao usar `INICIAR.bat`, a janela preta não fica aberta, não aparece “Pressione qualquer tecla para continuar” e o usuário vê apenas o painel visual do Ururau.

## Onde ver erros agora

Como o console externo fica oculto, erros de inicialização ficam em:

- `sistema/logs/iniciar_oculto.log`
- `sistema/logs/painel_gui.log`

## Observação

Se for necessário depurar com console visível, use `sistema/INICIAR_CONSOLE.bat`.
