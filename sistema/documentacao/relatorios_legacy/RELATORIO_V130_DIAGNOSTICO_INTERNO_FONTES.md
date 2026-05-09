# Ururau v130 — Diagnóstico interno de fontes

## Objetivo

Integrar ao painel do Ururau o motor de diagnóstico de fontes jornalísticas usado externamente em `diagnostico_jornal_gui.py`, sem alterar a coleta existente e sem aplicar mudanças destrutivas.

## O que foi implementado

- Nova aba em Configurações: **Diagnóstico de Fonte**.
- Campo para URL/domínio e nome opcional da fonte.
- Botões:
  - Diagnóstico rápido;
  - Diagnóstico completo;
  - Aplicar sugestão com backup;
  - Exportar TXT/JSON;
  - Limpar.
- Motor interno em `ururau/coleta/diagnostico_fontes_v130.py`.
- Aplicador seguro em `ururau/coleta/aplicador_diagnostico_v130.py`.
- Patch de UI em `ururau/ui/diagnostico_fontes_tab_v130.py`.

## Estratégias testadas pelo diagnóstico

- RSS/Atom na raiz;
- RSS/Atom em `/portal/`;
- RSS por categoria;
- WordPress REST API;
- sitemaps comuns;
- HTML de listagem;
- JSON-LD e Open Graph;
- necessidade de Playwright.

## Segurança da aplicação

O botão **Aplicar sugestão com backup**:

- cria backup dos arquivos alterados em `backups_v130`;
- nunca remove fontes boas;
- atualiza a fonte do mesmo domínio quando existir;
- adiciona nova fonte quando o domínio ainda não existir;
- grava fallbacks RSS em `fallbacks_v130`;
- adiciona sitemaps sem duplicar linhas;
- não aplica HTML/WP API automaticamente quando isso exigir coletor específico.

## Limites assumidos

A aplicação automática é conservadora. Para fontes cuja única solução seja HTML puro, API específica ou Playwright, o sistema gera relatório e sugestão, mas não força uma configuração insegura em RSS.

## Arquivos principais

- `sistema/ururau/coleta/diagnostico_fontes_v130.py`
- `sistema/ururau/coleta/aplicador_diagnostico_v130.py`
- `sistema/ururau/ui/diagnostico_fontes_tab_v130.py`
- `sistema/ururau/ui/painel.py`
- `sistema/validar_v130_diagnostico_fontes.py`

## Como testar

1. Abrir o painel.
2. Ir em Configurações > Diagnóstico de Fonte.
3. Colar um domínio, por exemplo `https://mancheterj.com`.
4. Rodar Diagnóstico completo.
5. Revisar a recomendação.
6. Aplicar sugestão com backup.
7. Rodar nova coleta e exportar diagnóstico.
