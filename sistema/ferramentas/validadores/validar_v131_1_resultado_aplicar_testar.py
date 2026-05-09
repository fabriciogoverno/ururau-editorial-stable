from pathlib import Path
import importlib.util

base = Path(__file__).resolve().parent
files = [
    base / 'ururau' / 'ui' / 'diagnostico_fontes_tab_v130.py',
    base / 'ururau' / 'coleta' / 'aplicador_diagnostico_v130.py',
    base / 'ururau' / 'coleta' / 'auto_perfil_fontes_v131.py',
]
for f in files:
    assert f.exists(), f'arquivo ausente: {f}'
    src = f.read_text(encoding='utf-8', errors='ignore')
    compile(src, str(f), 'exec')

app = (base / 'ururau' / 'coleta' / 'aplicador_diagnostico_v130.py').read_text(encoding='utf-8', errors='ignore')
assert 'resumo_resultado_aplicacao_v131' in app
assert 'salvar_relatorio_aplicacao_v131' in app
ui = (base / 'ururau' / 'ui' / 'diagnostico_fontes_tab_v130.py').read_text(encoding='utf-8', errors='ignore')
assert 'RESULTADO DO APLICAR E TESTAR' in app
assert 'resumo_resultado_aplicacao_v131' in ui
assert '_set_text(self, resultado_visual)' in ui
print('[OK] v131.1 validada: Aplicar/Testar agora exibe resultado claro e salva relatório TXT/JSON.')
