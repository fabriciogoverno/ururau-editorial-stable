from pathlib import Path
import json
base=Path(__file__).resolve().parent
assert (base/'regionais_v1305.json').exists(), 'regionais_v1305.json ausente'
regs=json.loads((base/'regionais_v1305.json').read_text(encoding='utf-8'))
assert any((r.get('nome') or '').lower().startswith('nf') for r in regs), 'NF Noticias nao esta em Regionais'
assert not any('rj news' in (r.get('nome') or '').lower() for r in regs), 'RJ News nao deve estar em Regionais por padrao'
painel=(base/'ururau/ui/painel.py').read_text(encoding='utf-8')
for token in ['text="RSS"','text="Especiais"','text="Regionais"','_carregar_regionais_v1305','_filtrar_fontes_rss_sem_regionais_v1305']:
    assert token in painel, f'token ausente: {token}'
print('[OK] v130.5 validada: abas RSS, Especiais e Regionais integradas.')
