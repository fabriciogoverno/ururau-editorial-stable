# V43 Premium — Correção visual do painel

## Objetivo
Corrigir os problemas visuais apontados no painel do Ururau Robô Editorial sem alterar a estrutura funcional do sistema.

## Alterações aplicadas

1. **Mensagem/status abaixo da barra de carregamento**
   - Header superior ganhou folga vertical explícita.
   - A linha de status foi reposicionada em uma área própria abaixo da barra de progresso.
   - O texto agora tem mais largura e altura, evitando corte visual durante atualizações.

2. **Círculos de IA, risco e score da fila**
   - Os rings foram redesenhados com renderização anti-aliased via Pillow quando disponível.
   - Mantido fallback com Canvas caso o Pillow não esteja acessível.
   - Os círculos da Fila de Pautas continuam na própria fila, como solicitado.

3. **Console interno**
   - Console interno ampliado para aproximadamente o dobro da área útil anterior.
   - Fonte e espaçamento ajustados para leitura de mensagens completas.
   - Mantido o botão Console e o comportamento de abrir/fechar sob demanda.

4. **Preservação da estrutura**
   - Fila de Pautas permanece à esquerda.
   - Detalhe de Pauta permanece à direita.
   - Não houve mudança no motor de coleta, geração, copydesk, publicação ou regras editoriais.

## Arquivos alterados

- `ururau/ui/patch_v43_premium.py`
- `VERSAO.txt`
- `documentacao/RELATORIO_V43_PREMIUM_LAYOUT_VISUAL_FIX.md`

## Validação executada

- `python -m py_compile ururau/ui/patch_v43_premium.py`
- `python -m py_compile ururau/ui/painel.py`

Ambos os arquivos compilaram sem erro de sintaxe.
