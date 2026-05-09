# Ururau v121 final organizado

Correções integradas:

- Mantida a estrutura organizada com pasta `sistema/`.
- Aba `XML/Sitemap` no Config preservada.
- Lista RSS final preserva feeds XML reais (`feed.xml`, `rss.xml`).
- Sitemaps ficam em `fontes_xml_sitemap_vfinal.txt`.
- Correção definitiva do erro de Redigir: `function object has no attribute REVISADA/EM_REDACAO`.
- Acesso operacional a `StatusPauta.REVISADA`, `StatusPauta.PUBLICADA`, etc. foi substituído por valores literais seguros.
- Runtime guard `ururau/fixes/v121_status_guard.py` protege importações dinâmicas restantes.
- Corrigido `janela_horas=` para `janela=`.

Validação:

```powershell
cd sistema
python validar_v121_redacao_status.py
python -m compileall ururau
```

Rodar:

```powershell
RODAR_TUDO.bat
```
