# Operacao - Promocao da branch auditor-ia para main

## Estado atual

A branch `auditor-ia` contem a linha validada do Ururau Auditor IA.

Validacoes locais registradas:

- Python sem falhas de compilacao.
- Testes de contrato passando.
- Sandbox Auditor passando.
- Gate de promocao apontando `apto_promocao_main: true`.
- Pull Request criado: https://github.com/fabriciogoverno/ururau-editorial-stable/pull/1

## Acao manual necessaria

O PR esta em modo draft. O GitHub nao permite merge enquanto o PR estiver como draft.

Passos:

1. Abrir o PR no GitHub.
2. Clicar em `Ready for review`.
3. Depois disso, permitir o merge via `Squash and merge`.

## Regra de seguranca

Nao fazer merge se algum destes pontos falhar:

- auditoria com `python_falhas > 0`;
- testes de contrato falhando;
- sandbox falhando;
- logs novos sem analise;
- arquivo sensivel no diff;
- credenciais, `.env`, banco, logs ou imagens de cache no commit.

## Depois do merge

Apos merge em `main`, a maquina local deve ser atualizada com:

```powershell
git checkout main
git pull origin main
```

A branch `auditor-ia` continua sendo a branch de desenvolvimento do Auditor IA.
