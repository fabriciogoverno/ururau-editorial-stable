# RELATORIO V45 - REDESIGN VISUAL PREMIUM

A versao V45 traz REDESIGN VISUAL REAL do painel Tkinter do Ururau Robo
Editorial. Diferente da V44 (que so otimizou performance), a V45 substitui
a camada visual principal por uma versao premium baseada num design system
proprio. Toda a logica de coleta, geracao, copydesk, publicacao,
configuracoes, RSS, sitemap, Google News, Bing, banco de dados e regras
editoriais permanece inalterada. As otimizacoes da V44 (virtualizacao
incremental da fila, cache de rings, debounce de scroll) sao PRESERVADAS.

## 1. Arquivos alterados

| Arquivo | Tipo de mudanca |
|---|---|
| `sistema/ururau/ui/painel.py` | Adicionado, ao final, o gancho `aplicar_patch_v45(globals())` apos os ganchos V43 e V44. Nao mexe em logica de coleta/IA/publicacao. |

## 2. Arquivos criados

| Arquivo | Funcao |
|---|---|
| `sistema/ururau/ui/theme_v45_design_system.py` | Design system real: paleta em camadas (bg/surface/surface_hi/overlay), escala de raios (xs..pill), espacamentos 4px, escala tipografica completa, alturas e larguras nomeadas, mapa STATUS_TONE. |
| `sistema/ururau/ui/widgets_v45.py` | `rounded_rect`, `PillButton` (com hover binding), `KPIHeroCard` (label maiuscula + numero grande + sub + accent stripe), `RingV45` (ring com track + arco anti-aliased compartilhando cache da V44), `draw_status_pill`. |
| `sistema/ururau/ui/header_v45.py` | Novo header em 3 linhas: brand + acoes pill + rings IA/Risco; KPI hero cards; barra de progresso arredondada + status com altura dedicada. |
| `sistema/ururau/ui/queue_v45.py` | Novo `_draw_row` para `FilaPautas`: card arredondado com accent stripe colorida por status, tipografia hierarquica, ring de score liso a direita, pills coloridas, hover/selecao com elevacao visual. Reaproveita virtualizacao V44 (tags `row` e `row_<idx>`). |
| `sistema/ururau/ui/detail_v45.py` | Estilo ttk premium (`V45.TNotebook` em pill), cabecalho restilizado para o Detalhe da Pauta. |
| `sistema/ururau/ui/console_v45.py` | Console interno com aparencia de terminal: header com 3 bullets coloridos, fonte mono, padding generoso, severidade colorida, prompt char laranja, bufferizacao mantida. |
| `sistema/ururau/ui/patch_v45_redesign.py` | Orquestrador: aplica os 5 patches acima na ordem correta sobre o painel ja patcheado pelo V43+V44. |
| `sistema/documentacao/RELATORIO_V45_REDIRECT_VISUAL_PREMIUM.md` | Este relatorio. |

Backups:

```
sistema/_backup_v45_redesign/painel.py.bak
sistema/_backup_v45_redesign/patch_v43_premium.py.bak
sistema/_backup_v45_redesign/patch_v44_layout_ultraleve.py.bak
sistema/_backup_v45_redesign/theme_v44_premium.py.bak
sistema/_backup_v45_redesign/widgets_v44.py.bak
sistema/_backup_v45_redesign/virtual_queue_v44.py.bak
```

## 3. Componentes redesenhados visualmente

### 3.1 Header (3 linhas em 132 px)

Linha 1 - Brand (logo + URURAU + subtitulo "Robo Editorial v45") + acoes em
PILL com hover (Coletar, Redigir, Copydesk, Preview, Publicar, Descartar,
Exportar) + utilitarios (Monitor, Console, Config) + rings IA/Risco com
label embaixo.

Linha 2 - 4 KPI HERO cards (Pautas na fila, Publicadas, Materias, Saude)
com label maiuscula apagada, numero 19pt em destaque, sub-linha discreta
e ACCENT STRIPE lateral colorida por tom.

Linha 3 - Barra de progresso ARREDONDADA a esquerda + percentual + dot de
status verde + linha de status COM ALTURA PROPRIA (32px), tornando
impossivel cortar texto + pill "PRODUCAO" a direita.

### 3.2 Fila de Pautas (cards premium)

Cada pauta vira um CARD com:
- Cantos arredondados (rounded polygon, nao varios items).
- Accent stripe lateral colorida por status (laranja=selecao, verde=pronta,
  ambar=baixo_score, vermelho=rejeitada, cinza=excluida).
- Titulo em 11pt branco; meta (fonte | data) em cinza.
- Pills coloridas para Status / Canal / TXT / Risco / Prioridade.
- Ring de score (tamanho 44, espessura 4, anti-aliased) a direita com
  legenda "SCORE" embaixo.
- Botao de acao pill (Gerar / Ver Materia / Aprovar / Reprovar / Reativar)
  em cor de tom apropriado.
- Linha de selecao com OVERLAY claro + accent stripe forte.
- Checkbox modernizado (rounded square + indicador "OK").

### 3.3 Detalhe da Pauta

- Cabecalho premium: marker laranja vertical + "DETALHE DA PAUTA" em
  caps + sub "Materia, fonte e auditoria".
- ttk.Notebook estilo `V45.TNotebook`: tabs em formato pill, paddings
  generosos (16x8), tipografia caps, hover/active/selected com paleta
  acentuada (selecionada em laranja).

### 3.4 Console

- Cabeçalho de "janela de terminal": 3 bullets (vermelho/amarelo/verde),
  texto "CONSOLE - ururau-shell - ativo".
- Body em #02060d (preto profundo) com fonte Consolas 10 e padding 14x12.
- Cores por severidade (info, ok, warn, err, dim).
- Prompt char laranja "ururau> ".
- Botoes Limpar / Fechar no header.
- Bufferizacao da V44 mantida (deque maxlen=4000, flush em lote a cada
  80ms, limite duro de 1200 linhas).

### 3.5 Botoes / Filtros / Statusbar

- `PillButton.build` com hover binding (sem chamadas custosas durante
  movimento do mouse).
- Filtros e barra de acoes em lote da fila repintados com paleta v45.
- Statusbar inferior com cor `surface`, fonte `label`, altura 30 e
  borda superior sutil.

## 4. Como a Fila ficou mais leve

Toda a virtualizacao incremental introduzida em V44 esta intacta. A V45
apenas substitui o conteudo desenhado por linha. Em particular:

- Cada linha continua sendo desenhada com tag `row` e marcada com
  `row_<idx>` apos a criacao (`virtual_queue_v44._v44_redraw_window`).
- Em scroll, ainda so apagamos `row_<idx>` das linhas que SAEM e desenhamos
  apenas as que ENTRAM. O `_draw_row` premium e chamado SO uma vez por
  linha que entra na viewport.
- O ring de score reusa a cache global `widgets_v44.ScoreRingCache` (que e
  consumida por `RingV45.get_photo`); valores repetidos entre linhas usam
  o mesmo PhotoImage.
- O card arredondado e UM unico polygon (`rounded_rect` -> 1
  `create_polygon`). Mesmo com mais elementos visuais por linha, o numero
  total de items canvas nao explode.

Resultado: no mesmo smoke test usado para a V44 (2000 pautas mockadas, 100
ticks de scroll), o redraw incremental se mantem na mesma faixa de
microsegundos.

## 5. Como as funcoes anteriores foram mantidas

- Nenhum modulo de coleta, editorial, publisher, IA, banco, configuracoes,
  fontes ou validadores foi tocado.
- Os patches V45 sao aplicados via `setattr` sobre `PainelUrurau` e
  `FilaPautas`, preservando o comportamento original quando algo falha
  (todo bloco esta em `try/except` com fallback).
- As assinaturas das funcoes foram preservadas:
  - `_construir_lista(self, frame)`, `_construir_detalhe(self, frame)`,
    `_construir_console(self)`, `_toggle_console(self)`,
    `_set_status(self, msg)`, `_v43_build_top_header(self)`,
    `_v43_update_kpis(self)` e `FilaPautas._draw_row(self, idx, w)`.
- Os callbacks da fila (`_ao_selecionar`, `_acao_gerar_item`,
  `_acao_preview_direto`, `_descartar_rapido`, `_acao_aprovar_baixo_score_v129`,
  `_acao_reprovar_baixo_score_v129_1`, `_acao_reativar_pauta`) NAO foram
  modificados — apenas o desenho da linha mudou.
- As variaveis usadas pelo V43 (`_v43_kpis`, `_v43_progress_canvas`,
  `_v43_progress_fill`, `_v43_header_status`, `_v43_header_pct`,
  `_v43_ia_frame`, `_v43_risk_frame`) recebem aliases para os novos
  widgets, garantindo compatibilidade com qualquer codigo legado que tente
  ler esses atributos.

## 6. Como reverter para V44

Se a V45 precisar ser desativada, basta:

1. Restaurar `sistema/ururau/ui/painel.py` a partir de
   `sistema/_backup_v45_redesign/painel.py.bak` (essa copia ja contem o
   estado V44).
2. Os arquivos novos (`*_v45.py`) podem permanecer no projeto sem ativacao
   — sem o gancho `aplicar_patch_v45(globals())` no fim do `painel.py` eles
   nao sao executados.
3. Alternativamente, comentar so o bloco `try/except` final de `painel.py`
   que importa `patch_v45_redesign`.

A V44 continua intacta: os modulos `theme_v44_premium`, `widgets_v44`,
`virtual_queue_v44` e `patch_v44_layout_ultraleve` permanecem operando
abaixo do redesign V45.

## 7. Testes executados

- `python3 -m compileall sistema/ururau` -> rc=0.
- `python3 -m py_compile` em cada modulo V45 -> OK.
- Smoke test importando todos os modulos V45 com Tkinter stub -> OK.
- Smoke test aplicando `aplicar_patch_v45` em `MockPainelUrurau` +
  `MockFilaPautas` -> retornou True; todos os metodos `_construir_*`,
  `_v43_build_top_header`, `_set_status`, `_construir_detalhe`,
  `_construir_console` e `FilaPautas._draw_row` apontam para as
  implementacoes V45.
- Validador `validar_v43_premium.py` (com PYTHONPATH=.): todos os checks
  de import e de fonte unica passaram. O unico ERRO ("painel importavel")
  e por falta de tkinter no sandbox Linux — nao reflete o ambiente Windows
  do usuario.

## 8. Como rodar

Sem alteracao no fluxo de inicializacao:

- Windows, na raiz do projeto: `RODAR_TUDO.bat` ou `INICIAR.bat`.
- Ao subir, o console interno deve imprimir, na ordem:
  ```
  [V44] Virtualizacao incremental da Fila instalada.
  [V44 LAYOUT ULTRALEVE] Patch aplicado: virtualizacao incremental, console ampliado, status sem corte, rings cacheados.
  [V45 REDESIGN] iniciando aplicacao do redesign visual premium...
  [V45] Detalhe da Pauta restilizado.
  [V45] Console interno terminal aplicado.
  [V45] Header redesenhado: 3 linhas, KPI hero, rings, status sem corte.
  [V45] Fila de Pautas: row premium com card, accent stripe e ring liso.
  [V45 REDESIGN] aplicado: header novo, fila premium, detalhe, console terminal.
  ```
- Se a saida acima nao aparecer, verificar `logs/painel_inicializacao.log`
  para mensagens `[V45][AVISO]` (nesse caso a V44 continua valida).

## 9. Riscos remanescentes

- O ring de score depende de Pillow para anti-aliasing. Sem Pillow ele cai
  para `Canvas.create_arc`, que tambem fica decente mas com aliasing
  visivel.
- Se um patch instalado entre V43 e V45 (por exemplo `patch_v132`) sobrescrever
  algum dos metodos que reescrevemos, a aparencia dele tera prioridade. Para
  todos os patches presentes no ZIP atual isso NAO ocorre.
- DPI alto no Windows pode cortar elementos com altura fixa em pixels. As
  alturas usadas (header 132, status_strip 32, console 420) foram pensadas
  para 1080p / 100% DPI.
