from __future__ import annotations
import json
import os
import py_compile
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

# Carrega env igual ao sistema.
try:
    from dotenv import load_dotenv
    for p, over in ((BASE/'credenciais'/'.env.exemplo', False), (BASE/'credenciais'/'env_principal.env', True), (BASE/'.env', True)):
        if p.exists():
            load_dotenv(p, override=over)
except Exception:
    pass

ERROS=[]
AVISOS=[]

def ok(msg): print('[OK]', msg)
def warn(msg):
    AVISOS.append(msg); print('[AVISO]', msg)
def err(msg):
    ERROS.append(msg); print('[ERRO]', msg)

for rel in [
    'ururau_monitor.py',
    'ururau/publisher/monitor.py',
    'ururau/publisher/workflow.py',
    'ururau/editorial/decision_v82.py',
    'ururau/editorial/quality_gates.py',
    'ururau/editorial/regras_editoriais.py',
]:
    try:
        py_compile.compile(str(BASE/rel), doraise=True)
        ok(f'compilou: {rel}')
    except Exception as e:
        err(f'falha de sintaxe em {rel}: {e}')

cfg_path=BASE/'config'/'monitor_24h.json'
try:
    cfg=json.loads(cfg_path.read_text(encoding='utf-8'))
    modo=cfg.get('modo_cms_padrao')
    if modo not in {'local','rascunho','direto'}:
        err(f'modo_cms_padrao inválido: {modo}')
    else:
        ok(f'modo_cms_padrao={modo}')
except Exception as e:
    err(f'não leu config/monitor_24h.json: {e}')

try:
    from ururau.editorial.decision_v82 import decidir_destino_publicacao_v82
    artigo={
        'titulo':'Prefeitura anuncia nova etapa de obra em Campos',
        'titulo_seo':'Prefeitura anuncia nova etapa de obra em Campos',
        'conteudo':'A Prefeitura de Campos informou nesta segunda-feira que iniciou uma nova etapa da obra. O serviço ocorre na área central e tem prazo informado em nota oficial. A intervenção será acompanhada pela secretaria responsável.',
        'link_origem':'https://exemplo.com/noticia',
        'fonte_nome':'Fonte Teste',
        'status_validacao':'aprovado',
        'auditoria_bloqueada':False,
        'score_qualidade':95,
        'score_risco':0,
    }
    aud={'status':'aprovado','pode_publicar':True,'score':95}
    old1=os.environ.get('URURAU_PUBLICAR_DIRETO')
    old2=os.environ.get('URURAU_CMS_PUBLICACAO_DIRETA')
    os.environ['URURAU_PUBLICAR_DIRETO']='1'
    os.environ['URURAU_CMS_PUBLICACAO_DIRETA']='1'
    d=decidir_destino_publicacao_v82(artigo,aud,{'chars_fonte':900,'permitir_publicacao_direta':False,'modo_cms':'rascunho'})
    if d.get('destino')!='salvar_rascunho':
        err('modo rascunho não bloqueou publicação direta: '+str(d))
    else:
        ok('modo rascunho força salvar_rascunho mesmo com env direta ligado')
    artigo_bad=dict(artigo)
    artigo_bad['conteudo']=artigo_bad['conteudo']+' Vale lembrar que a situação exige atenção.'
    d2=decidir_destino_publicacao_v82(artigo_bad,aud,{'chars_fonte':900,'permitir_publicacao_direta':True,'modo_cms':'direto'})
    if d2.get('destino')=='publicar_direto':
        err('termo de IA não bloqueou publicação direta: '+str(d2))
    else:
        ok('termo de IA impede publicação direta no monitor')
    if old1 is None: os.environ.pop('URURAU_PUBLICAR_DIRETO',None)
    else: os.environ['URURAU_PUBLICAR_DIRETO']=old1
    if old2 is None: os.environ.pop('URURAU_CMS_PUBLICACAO_DIRETA',None)
    else: os.environ['URURAU_CMS_PUBLICACAO_DIRETA']=old2
except Exception as e:
    err(f'teste decision_v82 falhou: {e}')

try:
    from ururau.publisher.workflow import can_publish
    artigo={
        'titulo':'Prefeitura anuncia nova etapa de obra em Campos',
        'conteudo':'Texto factual com informações suficientes. Vale lembrar que a obra segue conforme cronograma informado.',
        'status_validacao':'aprovado',
        'auditoria_bloqueada':False,
        'coverage_score':0.95,
        'score_qualidade':95,
        'score_risco':0,
    }
    pode,motivo=can_publish(artigo,modo='monitor')
    if pode:
        err('can_publish liberou matéria com termo de IA proibido')
    else:
        ok('can_publish bloqueia termo de IA proibido no monitor')
except Exception as e:
    err(f'teste can_publish falhou: {e}')

print('\nResumo:')
print(f'  Erros : {len(ERROS)}')
print(f'  Avisos: {len(AVISOS)}')
if ERROS:
    sys.exit(1)
