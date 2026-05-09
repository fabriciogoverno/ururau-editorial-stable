from pathlib import Path
p = Path(__file__).parent / 'ururau' / 'ui' / 'painel.py'
s = p.read_text(encoding='utf-8')
assert 'on_select=self._ao_selecionar' in s, 'on_select ainda não aponta para _ao_selecionar'
assert 'on_abrir=self._acao_preview_direto' in s, 'preview não está separado em on_abrir'
assert 'self._on_abrir_callback' in s, 'callback de abrir separado ausente'
print('[OK] v129.11: clique na pauta seleciona/detalha; preview separado.')
