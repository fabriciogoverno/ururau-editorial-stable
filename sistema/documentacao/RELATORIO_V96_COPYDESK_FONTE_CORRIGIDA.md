# URURAU v96 — Copydesk e Redação usando a aba Fonte

Correções aplicadas:

1. O texto exibido na aba **Fonte** agora é gravado na pauta e na matéria quando for mais longo que o resumo/RSS.
2. O botão **Redigir** injeta o texto longo da aba Fonte antes de gerar a matéria.
3. O workflow de redação tenta hidratar a fonte com `ler_fonte_pauta()` quando o scraper principal retorna texto curto.
4. Se a IA gerar matéria com 1 parágrafo apesar de fonte longa, o workflow reprocessa a matéria com o regenerador do Copydesk.
5. O Copydesk agora procura a fonte nos campos `_fonte_aba_texto`, `fonte_aba_texto` e `leitura_fonte_texto`.
6. O botão **Reescrever pela Fonte** tenta hidratar a URL automaticamente quando a fonte salva estiver curta.
7. A resposta curta da IA no Copydesk é barrada: se vier com menos de 3 parágrafos ou corpo curto, entra fallback local baseado somente na fonte.

Resultado esperado:

- Fonte com 3.000+ caracteres não deve mais virar matéria de 1 parágrafo.
- Copydesk deve usar o mesmo texto que aparece em **Detalhe da Pauta > Fonte**.
- Preview deve receber corpo maior, com vários parágrafos, depois de Redigir ou Reescrever pela Fonte.
