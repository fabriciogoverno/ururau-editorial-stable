# Ururau v122/v123 - Correções de coleta

## Corrigido

- Busca por termos: o erro `dentro_da_janela() got an unexpected keyword argument 'janela'` foi corrigido com compatibilidade para `janela` e `janela_horas`.
- XML/Sitemap: `fontes_xml_sitemap_vfinal.txt` passa a ser lido no botão Coletar.
- Campos 24 Horas: `https://campos24horas.com.br/noticia/sitemap.xml` integrado ao ciclo de coleta.
- Fila de pautas: cada clique em Coletar cria lote visual `Coleta N - HH:MM`.
- Separadores: a fila mostra uma barra entre os ciclos, com número de pautas do lote.
- Limite total: default aumentado para 250 por coleta.
- Limite por fonte: default ajustado para 5.

## Como validar

```powershell
cd sistema
python validar_v122_coleta_sitemap_termos.py
python -m ururau.coleta.sitemap_xml_coletor_v123
python -m compileall ururau
```
