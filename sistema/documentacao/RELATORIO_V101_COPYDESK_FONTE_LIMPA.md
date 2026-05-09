# URURAU v101 — Copydesk com fonte limpa e sem lixo interno

Correções aplicadas:

- Criado `ururau/coleta/source_clean_v101.py`.
- A leitura da fonte remove menus, política de privacidade, chamadas internas, listas de matérias e cabeçalhos antes de enviar para Redigir/Copydesk.
- Quando o título aparece em lista interna e também no artigo real, a limpeza usa a ocorrência mais próxima do texto real.
- Copydesk escolhe o melhor texto-fonte por pontuação de utilidade, não apenas pelo maior tamanho.
- Corpo final remove intertítulos genéricos como `Contexto`, `Detalhes`, `Efeitos práticos` e `Próximos passos`.
- Prompt premium passa a proibir intertítulos no corpo.
- Fallback local do Copydesk gera apenas parágrafos jornalísticos corridos.

Objetivo: impedir saídas com lixo como `Catecontando Histórias`, `Política de Privacidade` e listas internas misturadas à matéria.
