from pathlib import Path
base=Path(__file__).resolve().parent
assert (base/'ururau/coleta/adapters/nfnoticias_v1306.py').exists(), 'adapter NF v130.6 ausente'
painel=(base/'ururau/ui/painel.py').read_text(encoding='utf-8')
for token in ['coletar_nfnoticias_v1306', 'regional_nfnoticias_v1306', 'rss_items', 'NF Notícias v130.6']:
    assert token in painel, f'token ausente no painel: {token}'
print('[OK] v130.6 validada: NF Notícias usa parser RSS direto na aba Regionais.')
