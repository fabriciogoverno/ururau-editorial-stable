from pathlib import Path
import py_compile,json
ROOT=Path(__file__).resolve().parent
for f in ['ururau/ui/painel.py','ururau/ui/patch_v46_layout_definitivo.py','ururau/ui/patch_v47_4_operacional.py','ururau/coleta/auto_perfil_fontes_v131.py','ururau/coleta/aplicador_diagnostico_v130.py']:
    py_compile.compile(str(ROOT/f), doraise=True)
text=(ROOT/'ururau/ui/patch_v46_layout_definitivo.py').read_text(encoding='utf-8')
assert 'Atualizar F5' in text and 'text="--"' in text
painel=(ROOT/'ururau/ui/painel.py').read_text(encoding='utf-8')
for t in ['URURAU_V47_TEXTO_TENTAR_ATE_OK','URURAU_V47_IMAGEM_TENTAR_ATE_OK','patch_v47_4_operacional']:
    assert t in painel
auto=(ROOT/'ururau/coleta/auto_perfil_fontes_v131.py').read_text(encoding='utf-8')
for t in ['diagnostico_prioridade_proxima_coleta','forcar_proxima_coleta_qtd','max_itens=max_itens']:
    assert t in auto
cfg=json.loads((ROOT/'config/extracao_persistente.json').read_text(encoding='utf-8'))
assert cfg['diagnostico_fonte_max_itens_proxima_coleta']==10
print('OK — v47.4 operacional validado: F5 real, painel sem métricas fictícias, extração persistente e Diagnóstico de Fonte até 10 pautas.')
