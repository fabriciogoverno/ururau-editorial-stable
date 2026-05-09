# v129.9 — Fila ultraleve em Canvas puro

## Objetivo

Corrigir definitivamente a lentidão, os pulos e os apagões visuais da Fila de Pautas durante coleta, hidratação de texto e busca de imagens.

## Diagnóstico

As versões anteriores ainda criavam muitos widgets Tkinter por pauta: Frame, Label, Button, checkbox, badge e estruturas internas. Com 100+ pautas, cada atualização de coleta, texto ou imagem podia destruir e recriar dezenas/centenas de widgets. Isso fazia a lista pular, ficar em branco e travar.

## Correção técnica

A classe `FilaPautas` foi substituída por uma implementação de Canvas puro:

- não cria mais Frame/Label/Button por card;
- desenha somente as linhas visíveis;
- usa retângulos e textos do Canvas;
- preserva a pauta no topo como âncora visual quando novas pautas chegam;
- mantém checkbox, seleção, Aprovar, Reprovar, Gerar, Ver Matéria e Reativar por regiões clicáveis no Canvas;
- não carrega miniaturas dentro da fila;
- mantém a imagem e o texto completo nas abas Fonte/Preview;
- preserva os callbacks existentes do painel;
- não altera coleta, RSS, XML/Sitemap, Fontes Especiais, Termos, publicação, copydesk, imagem ou WhatsApp.

## Resultado esperado

Durante a coleta:

- a fila não deve ficar branca;
- a fila não deve reconstruir todos os cards;
- a rolagem deve ficar mais leve;
- clicar em uma pauta não deve redesenhar a lista inteira;
- novas pautas podem chegar sem deslocar violentamente o ponto de leitura.

## Validação estática

Executado:

```bash
python -m py_compile sistema/ururau/ui/painel.py
```

Sem erros de compilação.
