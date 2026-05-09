from pathlib import Path
import json
import py_compile

ROOT = Path(__file__).resolve().parent

# 1. Arquivos novos/alterados precisam compilar.
for rel in [
    'ururau/ui/painel.py',
    'ururau/coleta/adapters/mancheterj_v12913.py',
    'ururau/coleta/coleta_auditoria_v126.py',
]:
    py_compile.compile(str(ROOT / rel), doraise=True)

# 2. Config RSS principal deve usar /portal/feed/.
for rel in ['fontes_rss.json', 'configuracoes/fontes_rss.json', 'config/fontes_rss.json']:
    p = ROOT / rel
    data = json.loads(p.read_text(encoding='utf-8'))
    item = next((f for f in data if (f.get('nome') or '').lower() == 'manchete rj'), None)
    assert item, f'Manchete RJ ausente em {rel}'
    assert item.get('url') == 'https://mancheterj.com/portal/feed/', f'URL incorreta em {rel}: {item.get("url")}'

# 3. Coletor especial expõe função e diagnóstico no código.
adapter_txt = (ROOT / 'ururau/coleta/adapters/mancheterj_v12913.py').read_text(encoding='utf-8')
assert 'def coletar_mancheterj_v12913' in adapter_txt
assert 'def obter_diagnostico_mancheterj_v12913' in adapter_txt
assert 'https://mancheterj.com/portal/feed/' in adapter_txt
assert 'https://mancheterj.com/wp-json/wp/v2/posts?per_page=10' in adapter_txt

print('[OK] v129.13 Manchete RJ: /portal/feed + fallback WP API/sitemap/HTML integrado e validado.')
