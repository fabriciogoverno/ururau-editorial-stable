# Ururau v95 - instalação corrigida

Correções aplicadas sobre a v94:

- Reincluído `VALIDAR_ENV.py`, removido por engano na limpeza anterior.
- Reincluído `VALIDAR_ENV.bat`.
- Reincluído `CORRIGIR_FILA_SEM_TEXTO_V84.py`, chamado pelo `INICIAR.bat`.
- Atualizados `INSTALAR.bat`, `INICIAR.bat` e `RODAR_TUDO.bat` para v95.
- Mantidas as correções de auto coleta segura e fila progressiva.

Execução recomendada:

1. Extrair o ZIP em uma pasta nova.
2. Rodar `RODAR_TUDO.bat`.
3. Se existir `.venv` antigo copiado de outra versão, apagar `.venv` antes de rodar.
