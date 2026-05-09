# Relatório V46.5 Visual Premium dos Botões

## Objetivo
Aplicar ajuste visual direto no painel Pural/Ururau Editorial v46, sem alterar os fluxos operacionais de coleta, redação, copydesk, preview, publicação, descarte, exportação, monitor, console ou configuração.

## Arquivo alterado
- `sistema/ururau/ui/patch_v46_layout_definitivo.py`

## Alterações executadas
1. Substituição do visual dos botões principais do header por botões em Canvas com acabamento mais profissional.
2. Manutenção das mesmas ações e dos mesmos handlers originais.
3. Manutenção das larguras já usadas no header v46 para não quebrar alinhamento.
4. Remoção dos ícones decorativos dos botões principais para reduzir aparência infantil.
5. Aplicação de base escura, borda fina, sombra curta, relevo discreto, trilho lateral de acento e hover/press leve.
6. Remoção da faixa verde de progresso/status abaixo dos botões.
7. Preservação do status operacional na barra inferior e no painel lateral, evitando duplicidade visual com o Monitor.
8. Compatibilidade adicional para o botão Monitor, aceitando chamadas antigas de `.config(text=..., bg=..., fg=...)` mesmo sendo Canvas.

## O que não foi alterado
- Banco de dados.
- Motor de coleta.
- IA.
- Copydesk.
- Preview.
- Publicação no CMS.
- Fila de pautas.
- Painel lateral de inteligência.
- Configurações e credenciais.

## Validação feita
- Compilação Python dos arquivos principais:
  - `ururau/ui/patch_v46_layout_definitivo.py`
  - `ururau/ui/painel.py`
  - `ururau_painel.py`
- Smoke test com interface em Xvfb:
  - painel abriu sem erro;
  - header ficou com altura de 72 px;
  - faixa verde de progresso deixou de existir no topo;
  - botão Monitor aceitou atualização por `.config()` sem quebrar.
