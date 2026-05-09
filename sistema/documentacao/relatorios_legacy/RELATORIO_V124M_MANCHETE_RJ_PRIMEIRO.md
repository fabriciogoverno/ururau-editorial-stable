# Ururau v124m

## Alteração desta emissão

- `https://mancheterj.com/feed/` foi colocado como **primeiro item** em `fontes_rss.json`.
- Mantida a correção v124 do Campos 24 Horas por XML/Sitemap.
- Mantida a exceção de janela para XML/Sitemap.
- Mantido limite de 10 pautas por fonte.

## Validação

```powershell
cd sistema
python validar_v124m_config_feeds.py
python -m compileall ururau
```

## Arquivos principais alterados

- `sistema/fontes_rss.json`
- `sistema/configuracoes/fontes_rss.json`
- `sistema/configuracoes/fontes_rss_v124m_final.txt`
