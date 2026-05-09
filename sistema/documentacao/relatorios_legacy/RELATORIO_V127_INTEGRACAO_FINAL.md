# Ururau v127 — ajustes finais de coleta, busca e diagnóstico

## Implementado

1. Campo Busca da Fila de Pautas
   - Continua no mesmo lugar.
   - Agora pesquisa também o texto exibido abaixo do título:
     fonte/portal, data de publicação, origem, link, canal e termo de busca.
   - Ex.: `diário`, `diário do rio`, `sf notícias`, `manchete rio`, `campos 24`.

2. Diagnóstico da Coleta
   - Removido de baixo da fila de pautas.
   - Criada aba `Config > Diagnóstico`.
   - Guarda diagnóstico somente na sessão.
   - Botões:
     - Atualizar diagnóstico
     - Exportar TXT
     - Limpar diagnóstico da sessão

3. Campos 24 Horas
   - Corrigida conversão de data do coletor especial.
   - Preenche `data_pub_fonte`, `data_pub_fonte_br`, `data_publicacao`, `publicado_em`, `_data_pub_ordem`.
   - Mantida exceção operacional se o feed vier sem data.

4. Busca por Termos
   - Nova etapa explícita `Busca por Termos v127`.
   - Usa termos cadastrados em `Config > Termos`.
   - Janela padrão: 24 horas.
   - Usa Google News RSS oficial.
   - Insere resultados encontrados na fila como pauta normal.
   - Entra também no diagnóstico da coleta.

## Validação

```powershell
cd sistema
python validar_v127_integracao_final.py
python -m compileall ururau
```
