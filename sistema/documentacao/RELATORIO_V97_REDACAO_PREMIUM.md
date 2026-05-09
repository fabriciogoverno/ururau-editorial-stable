# Ururau v97 — Redação premium, SEO e GPT-4.1-mini

Correções aplicadas:

1. O prompt mestre agora deixa claro que o modelo não deve resumir a fonte, mas produzir matéria jornalística completa.
2. O engine detecta saída rasa quando há fonte longa: 1 parágrafo, poucos caracteres ou corpo equivalente a subtítulo.
3. Se o GPT-4.1-mini devolver texto curto, o sistema tenta uma segunda geração premium com fonte integral.
4. Se a segunda geração ainda vier fraca, entra fallback local premium baseado somente nas frases da fonte.
5. O Copydesk/Reescrever pela Fonte ganhou a mesma exigência: mínimo proporcional de parágrafos e caracteres.
6. SEO reforçado: título SEO até 89 caracteres, título de capa até 60, meta entre 120 e 160, retranca curta e 8 a 12 tags.
7. A aba Fonte continua sendo prioridade para Redigir e Copydesk quando existir texto longo capturado.
8. Mantidos .env, RODAR_TUDO.bat, painel, monitor, copydesk, preview e CMS.
