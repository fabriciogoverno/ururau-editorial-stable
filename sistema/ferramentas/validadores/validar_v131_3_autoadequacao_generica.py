from pathlib import Path
import ast

BASE = Path(__file__).resolve().parent
alvos = [
    BASE / 'ururau' / 'coleta' / 'auto_perfil_fontes_v131.py',
    BASE / 'ururau' / 'coleta' / 'aplicador_diagnostico_v130.py',
    BASE / 'ururau' / 'ui' / 'diagnostico_fontes_tab_v130.py',
    BASE / 'ururau' / 'ui' / 'painel.py',
]
for arq in alvos:
    ast.parse(arq.read_text(encoding='utf-8'))

src = (BASE / 'ururau' / 'coleta' / 'auto_perfil_fontes_v131.py').read_text(encoding='utf-8')
assert '_parse_sitemap_locs_xml' in src
assert '_extrair_metadados_artigo_html_v131' in src
assert 'sitemap_html_meta' in src
assert 'html_listagem' in src
assert 'aplicar_so_com_teste_ok' in src
print('[OK] v131.3: autoadequação genérica validada.')
