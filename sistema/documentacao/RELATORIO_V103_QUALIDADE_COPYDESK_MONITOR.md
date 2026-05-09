# URURAU v103 — Copydesk com fonte integral e gate final de qualidade

Correções principais:

1. Monitor 24h e fluxo principal agora passam a matéria pelo Copydesk com o texto-fonte integral, não apenas pelo resumo curto.
2. Antes do Copydesk revisar, a v103 tenta reconstruir a matéria com o regenerador de fonte quando existe fonte útil acima de 800 caracteres.
3. Criado `ururau/editorial/quality_gate_v103.py`.
4. Gate final bloqueia publicação direta quando houver:
   - matéria em parágrafo único;
   - corpo curto;
   - corpo desproporcional à fonte longa;
   - repetição excessiva;
   - lixo de página no corpo;
   - título ou subtítulo ausente.
5. O corpo é normalizado para parágrafos antes de ir ao CMS.
6. Matérias geradas pelo robô passam a enviar `nomefonte` como `Redação` no CMS.
7. O link original da fonte continua preservado no campo `linkfonte`.
8. O sistema tenta extrair crédito real de foto por padrões como `Foto: Nome/Fonte`, `Crédito:` e `Copyright`. Se não encontrar, usa `Reprodução`.
9. Criado gate de duplicidade por título e lead contra publicações recentes do banco e títulos capturados do Ururau.
10. O monitor 24h chama o gate v103 antes do risco, persistência e decisão de CMS.
11. Imediatamente antes de enviar ao CMS, há nova barreira `quality_gate_v103_presubmit`, bloqueando publicação ao vivo se a matéria ainda estiver curta ou em bloco único.

Resultado esperado:
- O monitor não deve mais publicar matéria em texto único.
- O monitor não deve mais publicar matéria curta quando há fonte longa.
- O fluxo principal e o monitor usam a mesma régua editorial.
- Duplicatas deixam de ir ao ar automaticamente.
