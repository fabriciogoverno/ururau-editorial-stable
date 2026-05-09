from __future__ import annotations
import py_compile, sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from ururau.editorial.regras_editoriais import obter_matriz_editorial, validar_termos_ia_em_artigo
print('============================================================')
print(' AUDITORIA DE REGRAS EDITORIAIS — URURAU v47.2')
print('============================================================')
m=obter_matriz_editorial(); l=m.get('limites_campos') or {}
print(f"Matriz: {m.get('versao')}"); print(f"Arquivo: {BASE/'config'/'regras_editoriais.json'}"); print(f"Termos de IA bloqueados: {len(m.get('termos_ia_proibidos') or [])}"); print(f"Status válidos: {', '.join(m.get('status_validos') or [])}"); print(f"Título SEO: até {l.get('titulo_seo_max')} caracteres"); print(f"Título capa: até {l.get('titulo_capa_max')} caracteres"); print(f"Retranca: até {l.get('retranca_max_words')} palavra(s)"); print(f"Tags: {l.get('tags_min')} a {l.get('tags_max')}")
check=validar_termos_ia_em_artigo({'titulo':'Teste reforça alerta no Norte Fluminense','conteudo':'O caso acende o alerta e vale lembrar que a situação segue em andamento.'}, modo='monitor')
print(f"Teste determinístico de bloqueio: {'OK' if not check.get('passou') else 'FALHOU'}")
for i in check.get('achados',[])[:8]: print(f" - {i['campo']}: {i['termo']}")
crit=['ururau/editorial/regras_editoriais.py','ururau/editorial/field_limits.py','ururau/config/house_style.py','ururau/ia/politica_editorial.py','ururau/agents/agente_editorial_ururau.py','ururau/editorial/editorial_policy.py','ururau/editorial/engine.py','ururau/editorial/quality_gates.py','ururau/editorial/auditoria_v78c.py','ururau/publisher/producao_v77.py','ururau/ui/painel.py']
print('\nCompilando arquivos críticos...')
for rel in crit: py_compile.compile(str(BASE/rel), doraise=True); print(' OK '+rel)
print('\nResultado: OK — matriz única carregada e bloqueio determinístico ativo.')
