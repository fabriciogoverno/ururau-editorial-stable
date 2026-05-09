# v129.11 — Clique da Fila restaurado

## Correção principal

Na v129.10, a fila leve em Canvas ainda estava chamando Preview ao clicar no corpo da pauta. Isso ocorria porque o callback `on_select` foi configurado como `_acao_preview_direto`, quando deveria chamar `_ao_selecionar`.

## Ajuste aplicado

- Clique no corpo da pauta agora chama somente `_ao_selecionar`.
- `_ao_selecionar` volta a carregar Detalhe da Pauta > Fonte.
- Preview ficou em callback separado: `on_abrir`.
- Botão `Ver Matéria` chama Preview somente quando a ação específica for clicada.
- Botão `Gerar` continua chamando geração, mas também sincroniza a pauta selecionada antes.

## Escopo preservado

Não foram alterados:

- motor de coleta;
- RSS;
- XML/Sitemap;
- Fontes Especiais;
- Termos;
- publicação;
- copydesk;
- WhatsApp;
- pipeline de imagem.
