# Ururau v107 — imagem no painel Fonte e texto capturado formatado

Correções aplicadas:

- A aba **Fonte** agora usa a mesma imagem local já encontrada para a miniatura da fila de pautas.
- Quando a imagem chega depois do texto, a aba **Fonte** é atualizada automaticamente se a pauta estiver selecionada.
- A mensagem `[imagem já encontrada]` deixa de ser o comportamento final quando há arquivo local disponível; o preview real é renderizado.
- A resolução de imagem passa a buscar em `imagem_caminho`, `caminho_imagem`, `caminho_final`, `thumb_path`, `thumb_local`, `imagem_path`, `foto_local`, `foto_path` e também na tabela `imagens` do banco.
- O texto capturado na aba **Fonte** passa a ser exibido com título e parágrafos separados por linha em branco.
- Quando a extração vem em bloco corrido, a v107 recompõe parágrafos por sentenças, sem alterar fatos.
- Mantida a lógica v106: texto é prioridade; imagem roda depois em fila separada.

Comportamento esperado:

```txt
[v107][IMG] OK via URL prévia (...)
[v107][IMG] OK via pipeline (...)
```

Na interface:

1. pauta entra na fila;
2. texto é hidratado automaticamente;
3. imagem é buscada depois;
4. a miniatura aparece na fila;
5. a mesma imagem aparece no painel **Fonte**;
6. o texto da fonte aparece como título + parágrafos, não como bloco único.
