# Ururau v118 final organizado

- Raiz limpa com INICIAR, INSTALAR, RODAR_TUDO, VALIDAR e ícones.
- Sistema completo em `sistema/`.
- `.env` copiado também para `sistema/credenciais/env_principal.env`.
- Config RSS com numeração fixa lateral, não editável.
- Campo de RSS aceita somente URL; canal/editoria é ignorado e definido pelo robô.
- XML/Sitemap separado em `fontes_xml_sitemap_vfinal.txt`.

Validação dentro de `sistema/`:

```powershell
python -m compileall ururau
python -m pytest ururau/tests/test_config_rss_linhas_fixas_v118.py -q
```
