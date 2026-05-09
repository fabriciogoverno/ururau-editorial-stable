# Ururau Auditor IA

## Objetivo

Criar uma camada local de auditoria tecnica e editorial para o Ururau Editorial. O modulo deve analisar o projeto, ler logs, mapear fluxos criticos, executar testes de contrato e gerar relatorios antes de qualquer correcao.

## Principios

- Nao alterar producao sem teste.
- Nao publicar nem rascunhar materia sem fonte e imagem validas.
- Nao permitir preview de materia que nao pertence a pauta selecionada.
- Nao permitir monitor duplicado.
- Nao deixar Google News/Kimi travar o ciclo do monitor.
- Nao versionar credenciais, banco, logs, imagens ou cache.

## Estrutura

```text
sistema/ururau_ai_auditor/
  scanner_codigo.py
  fluxo_registry.py
  log_reader.py
  regression_tests.py
  report_writer.py
  run_auditoria.py
sistema/tests_contrato/
  test_redacao_integridade.py
  test_preview_integridade.py
  test_monitor_stop.py
  test_cms_sem_imagem.py
30_AUDITORIA_TOTAL.bat
31_TESTES_CONTRATO.bat
32_RELATORIO_REGRESSAO.bat
```

## Fluxos criticos

1. Fila de pautas
2. Fonte e extracao textual
3. Imagem
4. Redacao
5. Preview
6. CMS
7. Monitor 24h
8. Parar/reiniciar monitor
9. Classificacao de canal/editoria
10. Regras editoriais e termos proibidos

## Criterios de aceite

- Todos os arquivos Python alterados compilam.
- Redigir bloqueia fonte contaminada antes da IA.
- Preview bloqueia materia de outra pauta.
- CMS bloqueia envio sem imagem.
- Monitor para de verdade e nao cria thread duplicada.
- Auditoria gera relatorio em `sistema/relatorios_auditoria/`.
