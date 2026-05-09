# Ururau v117 final completo

Projeto completo gerado a partir da base v111.4, com correções integradas:

- Config RSS visual numerado: exibe `1  URL`, `2  URL`, sem `Nome|Canal` para edição diária.
- Ao salvar, o sistema grava internamente `URL|Nome|`, com canal vazio, para não contaminar editoria.
- Links `.xml`/sitemap são separados em `fontes_xml_sitemap_vfinal.txt`.
- Editorias agora são classificadas por contexto da matéria.
- Campo `canal_forcado` vindo de fonte é ignorado nas novas coletas.
- Limite por fonte: `URURAU_RSS_MAX_POR_LINK=5`.
- Motor GPT Spec V2 aplicado: Redigir/Copydesk recebem prompt rígido, auditoria e regeneração.
- Dependências ajustadas para Python 3.14: `tzdata`, `python-dotenv`, `lxml==6.1.0`.

Validação:
```powershell
python -m compileall ururau
python -m pytest ururau/tests/test_motor_gpt_spec_v2.py -q
python -m pytest ururau/tests/test_editoria_contextual_v117.py -q
cmd /c INICIAR.bat
```
