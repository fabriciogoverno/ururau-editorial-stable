from pathlib import Path
import importlib.util

REQ = [
    'ururau/coleta/diagnostico_fontes_v130.py',
    'ururau/coleta/aplicador_diagnostico_v130.py',
    'ururau/ui/diagnostico_fontes_tab_v130.py',
    'ururau/ui/painel.py',
]
for rel in REQ:
    p = Path(rel)
    assert p.exists(), f'arquivo ausente: {rel}'
    compile(p.read_text(encoding='utf-8'), rel, 'exec')

painel = Path('ururau/ui/painel.py').read_text(encoding='utf-8')
assert 'Diagnóstico interno de fontes integrado' in painel
assert 'diagnostico_fontes_tab_v130' in painel
mod = Path('ururau/coleta/diagnostico_fontes_v130.py').read_text(encoding='utf-8')
for token in ['diagnostico_completo', 'avaliar_feed_util', 'format_report', 'salvar_relatorio']:
    assert token in mod, f'token ausente: {token}'
app = Path('ururau/coleta/aplicador_diagnostico_v130.py').read_text(encoding='utf-8')
for token in ['aplicar_sugestao_diagnostico_v130', 'backups_v130', 'fallbacks_v130']:
    assert token in app, f'token ausente: {token}'
print('[OK] v130 validado: Diagnóstico interno de fontes integrado em modo seguro.')
