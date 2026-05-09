# v129.7 — Fila sem pulos no clique e atualização estável

Correção focada na interface da Fila de Pautas.

## Problema corrigido

Ao clicar em uma matéria, a seleção chamava reconstrução completa da fila (`_renderizar_todos_v129_3`). Isso destruía e recriava todos os cards, causando:

- tela pulando;
- área da fila ficando em branco por instantes;
- perda visual de posição;
- travamento perceptível durante coleta, hidratação de texto e imagem.

## Solução

- `_selecionar()` não redesenha mais a fila inteira.
- O clique atualiza apenas o destaque visual do card anterior e do card selecionado.
- A posição do scroll é preservada após o clique.
- A fila continua recebendo novas pautas por append incremental.
- Não houve alteração nos coletores, RSS, Fontes Especiais, Termos, XML/Sitemap, WhatsApp ou publicação.

## Validação

Executar:

```bash
python -m py_compile sistema/ururau/ui/painel.py
```
