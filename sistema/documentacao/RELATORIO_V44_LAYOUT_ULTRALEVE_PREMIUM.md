# RELATORIO V44 - LAYOUT ULTRALEVE PREMIUM

Refatoracao visual e de performance do painel Tkinter do Ururau Robo Editorial,
sem alterar coleta, IA, copydesk, publicacao, banco, configuracoes, RSS,
sitemap, Google News, Bing, watchlists ou regras editoriais. O patch v44
roda DEPOIS do v43 Premium, somando refinamentos sem reescreve-lo.

## 1. Arquivos criados

| Arquivo | Funcao |
|---|---|
| `sistema/ururau/ui/theme_v44_premium.py` | Tokens de design centralizados (paleta, fontes, alturas, espacamentos). |
| `sistema/ururau/ui/widgets_v44.py` | `ScoreRingCache` global + helpers `create_metric_ring` / `update_metric_ring` / `draw_queue_ring`. Cache de PhotoImage por (valor, inverse, tamanho, espessura, cor). |
| `sistema/ururau/ui/virtual_queue_v44.py` | Virtualizacao incremental por janela: monkey-patch seguro de `FilaPautas` que so apaga linhas que SAEM da viewport e desenha as que ENTRAM. |
| `sistema/ururau/ui/patch_v44_layout_ultraleve.py` | Patch principal v44: instala virtualizacao incremental, amplia o console interno (buffer + limite de linhas), corrige altura do status sob a barra de progresso, integra rings cacheados. |
| `sistema/documentacao/RELATORIO_V44_LAYOUT_ULTRALEVE_PREMIUM.md` | Este relatorio. |

## 2. Arquivos alterados

| Arquivo | Tipo de mudanca |
|---|---|
| `sistema/ururau/ui/painel.py` | Adicionado, ao final, o gancho `aplicar_patch_v44(globals())` apos o gancho do v43. Sem mexer em logica de coleta, deduplicacao, score, regras editoriais ou regras de janela. |

Backups:

```
sistema/_backup_v44_layout/painel.py.bak
sistema/_backup_v44_layout/patch_v43_premium.py.bak
```

## 3. Resumo do funcionamento anterior

- A `FilaPautas` ja era um Canvas virtualizado (so renderizava linhas
  visiveis), porem a cada `_request_redraw` chamava `c.delete("row")` e
  redesenhava TODAS as linhas visiveis no Canvas. Em scroll continuo isso
  fazia centenas de `create_*` por segundo, gerando travamento perceptivel
  com 500+ pautas.
- O `patch_v43_premium.py` ja redesenhava cards com badges e ring de score
  cacheado via Pillow, mas o cache ficava preso ao Canvas/owner local — em
  sessoes longas crescia ou era regerado.
- O console interno tinha apenas 14 linhas de altura e fazia `see("end")` a
  cada linha de stdout, somando muitas chamadas de UI por segundo durante
  coleta.
- O texto de status sob a barra de progresso podia ser cortado na inferior
  por nao ter altura minima reservada.

## 4. Nova arquitetura visual

A camada visual do v43 Premium permanece intacta. O v44 adiciona, por cima:

1. **Tokens de design** centralizados em `theme_v44_premium.THEME` (paleta
   compativel com a do v43). Substituicao de literais espalhados por
   referencia unica.
2. **Cache global de rings** (`ScoreRingCache`) compartilhado entre header
   (IA / Risco) e fila de pautas. Limite defensivo de 320 entradas com
   eviction LIFO.
3. **Virtualizacao incremental por janela**: a Fila so apaga as linhas que
   SAEM da viewport (tag `row_<idx>`) e desenha as que ENTRAM. Linhas que
   continuam visiveis nao sao tocadas.
4. **Console expandido**: altura de 380px (configuravel via
   `HEIGHTS["console"]`), fonte Consolas 10pt, buffer com `deque(maxlen=4000)`
   e flush em lote a cada 80ms. Limite duro de 1000 linhas no widget.
5. **Status sem corte**: a faixa de status do header tem altura minima
   garantida (`HEIGHTS["status_strip"] = 28`) e `pack_propagate(False)`.

## 5. Onde foi implementada a virtualizacao

`sistema/ururau/ui/virtual_queue_v44.py`, funcao
`install_window_virtualization(FilaPautas_cls)`. Operacoes:

- `_v44_visible_indices`: calcula faixa visivel a partir de `canvasy(0)` e
  `winfo_height()`.
- `_v44_full_repaint`: apaga tudo e redesenha apenas a janela visivel
  (chamado em `popular`, resize, mudanca de dados).
- `_v44_redraw_window`: diff por linha. Usa `find_overlapping` para marcar
  cada item recem-criado com a tag `row_<idx>`, depois apaga apenas as
  linhas que sairam (`c.delete(f"row_{idx}")`) e adiciona apenas as que
  entraram. Para 100 ticks de scroll com 2000 pautas o smoke test mediu
  **0,12ms por tick** em ambiente headless.
- `_v44_request_redraw`: debouncing real, ignora reagendamentos enquanto
  ja existe um pendente.

## 6. Como os circulos de score foram otimizados

`widgets_v44.ScoreRingCache.get_photo(valor, inverse, size, thickness)`:

- Cor automatica por faixa (verde/ambar/vermelho), inverte para metricas de
  risco.
- Renderizacao em escala 4x com `Image.LANCZOS` para downsample anti-aliased.
- Cache global compartilhado com chave determinista; reuso instantaneo entre
  header e fila.
- Limite de 320 entradas com remocao em bloco (1/4 do cache) para evitar
  crescimento ilimitado em sessoes longas.
- Fallback nativo: se Pillow nao estiver disponivel, usa
  `Canvas.create_arc/create_oval` com `width=3` (ainda aceitavel).

## 7. Como o console foi ampliado e otimizado

`patch_v44_layout_ultraleve.py`, secao "Console interno":

- Altura aumentada para 380px (mais que 2x o anterior de ~14 linhas).
- Insercao em lote via `deque` + `after(80, flush)`. Cada tick consome todo
  o buffer e faz UM `see("end")`, em vez de um por linha.
- Limite duro de 1000 linhas: ao ultrapassar 1200 o widget e podado para
  1000 (delete `1.0` ate `excess+1.0`).
- Tags `ok`, `err`, `warn`, `info`, `dim` aplicadas conforme palavras-chave
  do conteudo.
- Botao "Limpar" do v43 e preservado.
- A funcao `_redirecionar_stdout` original continua valida (ela chama
  `_append_console`, que agora bufferiza).

## 8. Validacoes executadas

- `python3 -m compileall -q sistema/ururau` -> codigo 0 (sem erros).
- `python3 -m py_compile` em cada modulo novo -> OK.
- `PYTHONPATH=. python3 ferramentas/validadores/validar_v43_premium.py`
  -> todos os checks sob nosso controle passaram. O unico aviso ("painel
  importavel") falha em ambiente sem `tkinter` (sandbox Linux); no Windows
  do usuario o tkinter ja vem com o Python.
- Smoke test de virtualizacao com 2000 pautas mockadas:
  - Full repaint inicial: ~1ms.
  - Scroll incremental: ~0,12ms por tick (100 ticks).

## 9. Riscos remanescentes

- **Sessao com Pillow ausente**: o painel cai para o ring nativo
  (`Canvas.create_arc`) — visualmente correto, sem suavizacao 4x. Como
  Pillow ja era requisito para o v43 Premium, isso nao deve ocorrer.
- **Themes Tk customizados** instalados pelo usuario podem sobrescrever
  cores. O patch usa cores explicitas em todos os widgets criticos para
  reduzir esse risco.
- **Mudanca de DPI no Windows**: alturas em pixels (`HEIGHTS`) sao
  absolutas. Se o usuario rodar em monitor com escala >150% o console
  pode parecer pequeno. Solucao prevista: tornar `HEIGHTS` lido de
  `config/layout_v43_premium.json` em uma proxima iteracao.

## 10. Rollback

Para reverter ao estado anterior basta:

1. Restaurar `sistema/ururau/ui/painel.py` a partir de
   `sistema/_backup_v44_layout/painel.py.bak`.
2. Apagar (ou ignorar) os arquivos criados:
   - `sistema/ururau/ui/theme_v44_premium.py`
   - `sistema/ururau/ui/widgets_v44.py`
   - `sistema/ururau/ui/virtual_queue_v44.py`
   - `sistema/ururau/ui/patch_v44_layout_ultraleve.py`

Como o gancho v44 esta protegido por `try/except`, mesmo que o patch nao
seja removido a falha de import nao impede o painel de subir — ele apenas
loga `[V44][AVISO] patch layout ultraleve nao aplicado`.

## 11. Como rodar

Sem alteracoes no fluxo de inicializacao:

- Windows (raiz do projeto):
  - `RODAR_TUDO.bat` ou `INICIAR.bat` (mesmo comportamento de antes).
- A aplicacao do patch v44 e silenciosa; ao subir, o console interno
  imprime:
  ```
  [V44] Virtualizacao incremental da Fila instalada.
  [V44 LAYOUT ULTRALEVE] Patch aplicado: virtualizacao incremental, console ampliado, status sem corte, rings cacheados.
  ```
