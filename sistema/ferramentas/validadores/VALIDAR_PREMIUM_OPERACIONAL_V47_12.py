from __future__ import annotations
import json, os, sys, py_compile
from pathlib import Path
ROOT=Path(__file__).resolve().parent; os.chdir(ROOT); sys.path.insert(0,str(ROOT)); ok=True
def ck(c,m):
 global ok
 print(('[OK] ' if c else '[ERRO] ')+m); ok=ok and bool(c)
try:
 from ururau.editorial.seo_premium_v47_12 import otimizar_seo_materia
 m={'titulo':'Alerj realiza audiência sobre regulação da cannabis medicinal nesta sexta-feira','subtitulo':'Debate reúne representantes de movimentos sociais, órgãos públicos e associações de pacientes no Centro do Rio.','conteudo':('A Assembleia Legislativa do Estado do Rio de Janeiro realiza audiência pública nesta sexta-feira para discutir a regulação do acesso a medicamentos à base de cannabis.\n\nO debate terá representantes de movimentos sociais e entidades de pesquisa.\n\nA reunião ocorre no Edifício Lúcio Costa, no Centro do Rio, e trata dos efeitos práticos da decisão do Supremo Tribunal Federal.\n\nO encontro tem relevância para pacientes e para a discussão de políticas públicas no estado.'),'canal':'Política','tags':'Alerj, cannabis medicinal, Rio de Janeiro, saúde, STF, política'}
 rep=otimizar_seo_materia(m,{'cleaned_source_text':m['conteudo']*5,'link_origem':'https://exemplo.com/materia','data_pub_fonte':'2026-05-08'}); ck(rep.score>=80,f'SEO module operacional ({rep.score}/100)')
except Exception as e: ck(False,f'SEO module falhou: {e}')
try:
 cfg=json.loads((ROOT/'config'/'monitor_24h.json').read_text(encoding='utf-8')); ck(cfg.get('seo',{}).get('score_minimo_publicavel')==90,'monitor config SEO 90'); ck(cfg.get('coleta',{}).get('usar_fila_painel_no_monitor') is True,'monitor usa fila do painel'); ck(cfg.get('extracao_texto',{}).get('varredura_persistente_fila') is True,'varredura persistente configurada')
except Exception as e: ck(False,f'config monitor falhou: {e}')
try:
 for rel in ['ururau/ui/painel.py','ururau/ui/patch_v47_12_premium_operacional.py','ururau/publisher/monitor.py','ururau/editorial/quality_gate_v103.py','ururau/editorial/seo_premium_v47_12.py']: py_compile.compile(str(ROOT/rel),doraise=True)
 ck(True,'arquivos críticos compilam')
except Exception as e: ck(False,f'compilação crítica falhou: {e}')
if not ok: raise SystemExit(1)
print('[OK] V47.12 Premium operacional validado.')
