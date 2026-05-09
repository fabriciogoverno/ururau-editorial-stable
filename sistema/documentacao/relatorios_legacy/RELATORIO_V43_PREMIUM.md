# URURAU V43 Premium — saneamento estrutural, fonte única, memória editorial e layout modular

## Objetivo executado

Esta versão consolida a correção estrutural que faltava: o diagnóstico de fonte deixa de ser apenas relatório e passa a alimentar uma fonte única de verdade, status operacional e memória de aplicação. Também cria uma camada visual premium, modular e redimensionável, baseada no layout solicitado.

## Implementações centrais

### 1. Fonte única de verdade

Novo arquivo:

```text
sistema/config/fontes_links.json
```

Ele indexa:

```text
RSS
XML/Sitemap
Especiais
Regionais
AutoFontes
```

O arquivo é gerado a partir dos arquivos legados, sem removê-los, para manter compatibilidade e evitar regressão.

### 2. Status operacional das fontes

Novo arquivo:

```text
sistema/config/status_fontes.json
```

A cada relatório de coleta, o sistema interpreta os blocos OK, SEM COLETA, SEM ENVIO e FALHA, e grava:

```text
status
motivo
encontradas
enviadas
tipo detectado
última coleta
falhas consecutivas
quarentena
```

Estados possíveis:

```text
✅ ok
🟡 sem_envio
⚠️ atencao
❌ erro
❌ sem_coleta
⏸️ quarentena
🧪 aplicada/aguardando primeira coleta
```

### 3. Diagnóstico de Fonte com aplicação operacional registrada

O aplicador do diagnóstico agora também registra a solução em:

```text
sistema/config/fontes_links.json
sistema/config/memoria_diagnosticos_aplicados_v43.json
```

Assim, se o diagnóstico disser que um link funciona, o sistema tem registro auditável de:

```text
URL operacional
grupo/aba
estratégia
parser
fallbacks
WP API
sitemaps
Playwright necessário ou não
```

### 4. Memória editorial operacional ajustável

Novo arquivo:

```text
sistema/config/memoria_editorial_operacional_v43.json
```

A memória registra ações do operador:

```text
redigir
copydesk
preview
publicar
descartar
aprovar
reprovar
```

Ela ajusta pesos internos por:

```text
fonte
termos
editoria
ações
```

Não treina o GPT. É uma camada local e editável que alimenta score e prompts futuros.

### 5. Layout V43 Premium

Novo módulo:

```text
sistema/ururau/ui/patch_v43_premium.py
```

Implementa:

```text
TopHeader com KPIs
Sidebar expandida/recolhida/oculta
ActionToolbar profissional
QueuePanel reaproveitando fila existente
DetailPanel reaproveitando detalhe existente
AnalysisPanel novo, com qualidade, risco, checklist e ações rápidas
Console interno preservado
StatusBar preservada
painéis redimensionáveis via PanedWindow
persistência de layout
```

Preferências salvas em:

```text
sistema/config/layout_v43_premium.json
```

### 6. Configurações > Fontes / Links com saúde de fontes

A aba Fontes / Links ganhou uma área “Saúde das fontes”, com status visual das fontes vindo do último relatório real de coleta.

### 7. Scoring adaptativo

O score editorial passa a receber ajuste leve da memória operacional V43. Limite aplicado para evitar distorção:

```text
mínimo: -20
máximo: +25
```

## Arquivos novos

```text
sistema/ururau/coleta/fontes_links_v43.py
sistema/ururau/editorial/memoria_operacional_v43.py
sistema/ururau/ui/patch_v43_premium.py
sistema/config/fontes_links.json
sistema/config/status_fontes.json
sistema/config/memoria_editorial_operacional_v43.json
sistema/config/layout_v43_premium.json
sistema/validar_v43_premium.py
```

## Arquivos alterados

```text
sistema/ururau/ui/painel.py
sistema/ururau/coleta/aplicador_diagnostico_v130.py
sistema/VERSAO.txt
```

## Critérios atendidos

- Logo preservada.
- Layout mais profissional e modular.
- Sidebar pode ser expandida, recolhida e ocultada.
- Painéis principais são redimensionáveis.
- Console interno permanece no sistema.
- Configurações continuam com Fontes / Links em estrutura única.
- Diagnóstico aplicado registra solução operacional.
- Status das fontes passa a ser atualizado por relatório real.
- Memória editorial operacional foi criada sem treinar o GPT literalmente.
- Motor principal de coleta/publicação foi preservado.

## Pontos que continuam exigindo validação real no Windows

- Redimensionamento e persistência visual em tela real.
- Coleta real com fontes recém-aplicadas, especialmente Expresso Rio e Tribuna NF.
- Interação com CopyDesk e publicação no CMS.
- Comportamento visual em 1366x768, 1920x1080 e telas maiores.

