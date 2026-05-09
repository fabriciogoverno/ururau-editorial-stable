# Ururau v123.1 - Coleta ampliada

## Correções integradas

1. `https://mancheterj.com/feed/` deve ser mantido. O log mostrou `Manchete Rio: 12 entradas`; não entrou novidade porque o filtro achou 4 já na fila e 1 descartada.
2. RSS por fonte aumentado de 5 para 10:
   - `URURAU_RSS_MAX_POR_LINK=10`
   - `URURAU_V92_MAX_POR_FONTE=10`
3. Exceção de janela:
   - se uma fonte respondeu, mas todas as entradas estão fora da janela de 8h, o sistema salva 1 pauta mais recente como exceção.
   - log esperado: `[RSS][v123][EXCECAO_JANELA] Fonte: entrou 1 mais recente fora da janela`.
4. O filtro final da fila também respeita a exceção:
   - log esperado: `[v123][JANELA][EXCECAO] mantendo pauta fora da janela`.
5. XML/Sitemap permanece integrado para Campos 24 Horas:
   - `fontes_xml_sitemap_vfinal.txt`
   - `https://campos24horas.com.br/noticia/sitemap.xml`

## Validação

```powershell
cd sistema
python validar_v123_1_coleta_ampliada.py
python -m compileall ururau
cmd /c ..\RODAR_TUDO.bat
```
