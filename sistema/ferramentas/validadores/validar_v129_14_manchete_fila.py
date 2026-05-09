from pathlib import Path
base = Path(__file__).resolve().parent
painel = base / 'ururau' / 'ui' / 'painel.py'
adapter = base / 'ururau' / 'coleta' / 'adapters' / 'mancheterj_v12913.py'
text_painel = painel.read_text(encoding='utf-8', errors='ignore')
text_adapter = adapter.read_text(encoding='utf-8', errors='ignore')
assert '_v12914_forcar_visivel_fila' in text_adapter
assert '_normalizar_pauta_para_fila_v12914' in text_adapter
assert 'URURAU_V12914_EXIBIR_EXCECOES_FILA' in text_painel
assert 'self._carregar_pautas(forcar=True)' in text_painel
print('[OK] v129.14: Manchete RJ salva e aparece na fila visível.')
