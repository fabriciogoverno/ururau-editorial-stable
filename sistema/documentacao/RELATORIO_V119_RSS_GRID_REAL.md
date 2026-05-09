# RELATÓRIO V119 FINAL ORGANIZADO

Correção principal desta versão:

- A aba Config > Fontes RSS usa uma grade real:
  - coluna esquerda fixa com números de prioridade;
  - campo direito editável só com URLs;
  - os números não são texto e não podem ser apagados;
  - ao colar lista antiga com `1 - URL|Nome|Canal`, o sistema mantém só a URL;
  - ao salvar, grava internamente `URL|Nome|`, com canal/editoria vazio.

O problema do `ps://` foi eliminado. Ele ocorria porque a versão anterior desenhava uma faixa por cima dos primeiros caracteres de `https://`.

Validação:

```powershell
cd sistema
python -m compileall ururau
python -m pytest ururau/tests/test_rss_url_grid_v119.py -q
cmd /c INICIAR.bat
```
