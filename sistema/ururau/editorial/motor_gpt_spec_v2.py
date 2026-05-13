
from __future__ import annotations
import difflib,json,os,re
from dataclasses import dataclass
from typing import Any
PROMPT_MOTOR_URURAU_V2="""
Você é o motor editorial do Ururau. Produza matéria jornalística autêntica a partir dos fatos da fonte.
REGRA CENTRAL: a matéria final NÃO PODE ser paráfrase linha a linha da fonte. Reorganize os fatos em estrutura própria, com abertura direta, hierarquia jornalística, contexto, desenvolvimento e fechamento concreto.
SAÍDA OBRIGATÓRIA EM JSON VÁLIDO: titulo_seo, subtitulo_curto, titulo_capa, legenda_curta, retranca, tags, fonte, credito_foto, corpo_materia.
ESTRUTURA: mínimo de 4 parágrafos reais quando houver informação suficiente; proibido parágrafo único; cada parágrafo até 650 caracteres; primeiro parágrafo direto no fato; fechamento concreto.
AUTENTICIDADE: não copie ordem dos parágrafos da fonte; não copie frases longas; não faça resumo; não invente fato, cargo, valor, data, órgão, acusação ou declaração; não transforme investigação em condenação.
PROIBIDO: acende o alerta; chama atenção; ganha destaque; reforça a importância; vale destacar; vale ressaltar; diante desse cenário; em meio a; traz à tona; reacende o debate; joga luz sobre; autoridades seguem acompanhando; medidas cabíveis; até o fechamento desta matéria. Também é proibido usar travessão no corpo.
"""
# spec_auditoria_global §9: delegar para fonte canonica unica.
try:
    from .regras_editoriais_ururau import TERMOS_PROIBIDOS_UNIFICADOS as _TPU
    TERMOS_PROIBIDOS = list(_TPU)
except Exception:
    TERMOS_PROIBIDOS=['acende o alerta','acendeu o alerta','sinal de alerta','chama atenção','chamou atenção','ganha destaque','ganhou destaque','é destaque','reforça a importância','reforça o compromisso','reforça a necessidade','destaca a importância','evidencia a importância','mostra a importância','vale destacar','vale ressaltar','é importante destacar','cabe destacar','nesse sentido','desta forma','dessa forma','diante desse cenário','em meio a','o caso evidencia','o caso mostra','o caso reforça','traz à tona','reacende o debate','joga luz sobre','coloca em xeque','no centro das atenções','segue dando o que falar','movimenta os bastidores','promete movimentar','população fica em alerta','autoridades seguem acompanhando','medidas cabíveis','providências cabíveis','até o fechamento desta matéria','até a publicação desta reportagem']
def env_bool(k,d=True):
    v=os.getenv(k); return d if v is None else str(v).strip().lower() in {'1','true','yes','sim','on'}
def normalizar_texto(t):
    t=(t or '').lower(); t=re.sub(r'\s+',' ',t); t=re.sub(r'[^\wÀ-ÿ\s]','',t,flags=re.UNICODE); return t.strip()
def paragrafos_reais(corpo):
    corpo=(corpo or '').replace('\r','\n').strip()
    if not corpo: return []
    ps=[p.strip() for p in re.split(r'\n\s*\n+',corpo) if p.strip()]
    return ps or [corpo]
def maior_similaridade(fonte,gerado):
    f=normalizar_texto(fonte); g=normalizar_texto(gerado)
    if not f or not g: return 0.0
    return difflib.SequenceMatcher(None,f[:9000],g[:9000]).ratio()
def extrair_json(texto):
    if isinstance(texto,dict): return texto
    raw=(texto or '').strip()
    try: return json.loads(raw)
    except Exception: pass
    m=re.search(r'\{.*\}',raw,flags=re.S)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    return {'corpo_materia':raw}
def corpo_de(p): return str(p.get('corpo_materia') or p.get('conteudo') or p.get('texto') or p.get('texto_final') or '')
@dataclass
class AuditoriaMotor:
    ok:bool; problemas:list[str]; similaridade:float; paragrafos:int
def auditar_pacote_motor(pacote:dict[str,Any], fonte:str='')->AuditoriaMotor:
    problemas=[]; corpo=corpo_de(pacote); ps=paragrafos_reais(corpo)
    if len(ps)==1 and len(corpo)>350: problemas.append('Corpo em parágrafo único')
    if len(ps)<4 and len(corpo)>900: problemas.append(f'Corpo com poucos parágrafos ({len(ps)}); mínimo esperado: 4')
    for i,p in enumerate(ps,1):
        if len(p)>650: problemas.append(f'Parágrafo {i} longo demais ({len(p)} caracteres)')
    lower=corpo.lower()
    for t in TERMOS_PROIBIDOS:
        if t in lower: problemas.append('Termo proibido: '+t)
    if '—' in corpo or '–' in corpo: problemas.append('Travessão encontrado no corpo')
    titulo=str(pacote.get('titulo_seo') or pacote.get('titulo') or ''); capa=str(pacote.get('titulo_capa') or ''); retranca=str(pacote.get('retranca') or ''); credito=str(pacote.get('credito_foto') or pacote.get('imagem_credito') or ''); fonte_nome=str(pacote.get('fonte') or pacote.get('nome_da_fonte') or '')
    if titulo and len(titulo)>89: problemas.append(f'Título SEO acima de 89 caracteres ({len(titulo)})')
    if capa and len(capa)>60: problemas.append(f'Título de capa acima de 60 caracteres ({len(capa)})')
    if retranca and len(retranca.split())>1: problemas.append('Retranca acima de uma palavra')
    if credito and len(credito.replace('Foto:','').split())>6: problemas.append('Crédito de foto acima de 6 palavras')
    if fonte_nome and len(fonte_nome.split())>4: problemas.append('Nome da fonte acima de 4 palavras')
    sim=maior_similaridade(fonte,corpo) if fonte else 0.0
    if fonte and sim>=float(os.getenv('URURAU_MOTOR_SIMILARIDADE_MAX','0.72')): problemas.append(f'Texto gerado muito similar à fonte ({sim:.2f})')
    return AuditoriaMotor(not problemas,problemas,sim,len(ps))
def prompt_correcao_motor(pacote_anterior,fonte,problemas):
    return 'O texto anterior foi REPROVADO.\nPROBLEMAS:\n'+'\n'.join('- '+p for p in problemas)+'\n\nReescreva do zero em JSON válido, sem parágrafo único e sem copiar a fonte.\n\nFONTE:\n'+fonte[:12000]+'\n\nTEXTO REPROVADO:\n'+json.dumps(pacote_anterior,ensure_ascii=False)
def reforcar_messages_openai(messages,fonte=''):
    if not env_bool('URURAU_MOTOR_SPEC_V2_ATIVO',True): return messages
    msgs=list(messages or []); spec=PROMPT_MOTOR_URURAU_V2+(('\n\nFONTE PARA RECONSTRUÇÃO:\n'+fonte[:12000]) if fonte else '')
    if msgs and msgs[0].get('role')=='system': msgs[0]=dict(msgs[0]); msgs[0]['content']=str(msgs[0].get('content') or '')+'\n\n'+spec
    else: msgs.insert(0,{'role':'system','content':spec})
    return msgs
def deve_forcar_json(kwargs):
    if not env_bool('URURAU_MOTOR_FORCAR_JSON',True): return kwargs
    out=dict(kwargs); out.setdefault('response_format',{'type':'json_object'}); return out
