# URURAU v132.3 — Rodar automático sem ENTER

Correção aplicada para o problema em que `RODAR_TUDO.bat`/`INICIAR.bat` não abria o painel porque algum fluxo de instalação/validação ainda podia ficar preso em `pause` ou exigir tecla.

## Alterações

- `INICIAR.bat` da raiz agora chama `sistema\INICIAR_SILENCIOSO.vbs` e fecha imediatamente.
- `RODAR_TUDO.bat` da raiz agora faz a mesma coisa.
- `sistema\INICIAR.bat` e `sistema\RODAR_TUDO.bat` também usam o launcher silencioso.
- `sistema\INICIAR_OCULTO.bat` executa instalação/validação/reparo sem `pause` e abre o painel com `pythonw.exe`.
- `sistema\INSTALAR.bat` não usa mais `pause`; em caso de erro, registra no log e encerra com código de erro.
- Logs ficam em:
  - `sistema\logs\iniciar_oculto.log`
  - `sistema\logs\painel_gui.log`

## Uso normal

Abrir apenas:

```bat
RODAR_TUDO.bat
```

ou:

```bat
INICIAR.bat
```

O terminal pode piscar e fechar. O que deve permanecer aberto é somente o painel visual.
