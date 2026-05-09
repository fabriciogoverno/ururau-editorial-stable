from pathlib import Path
import json
base = Path(__file__).resolve().parent
assert (base/'ururau/ui/painel.py').exists(), 'painel.py não encontrado'
text = (base/'ururau/ui/painel.py').read_text(encoding='utf-8', errors='ignore')
assert '_v1303_pauta_tem_interesse_minimo' in text, 'helper v130.3 ausente'
assert 'URURAU_V1303_MIN_POR_FONTE_FUNCIONAL' in text, 'env de cota mínima ausente'
assert '_v1303_promovida_cota_minima' in text, 'marcação de cota mínima ausente'
for rel in ['fontes_especiais_v129.json', 'configuracoes/fontes_especiais_v129.json']:
    p = base / rel
    assert p.exists(), f'{rel} ausente'
    data = json.loads(p.read_text(encoding='utf-8'))
    fontes = data.get('fontes', [])
    assert any('nfnoticias.com.br' in (f.get('url','').lower()) and f.get('bypass_score') for f in fontes), f'NF Notícias não está como fonte especial em {rel}'
print('[OK] v130.3 validada: NF Notícias especial + cota mínima por fonte funcional/interesse.')
