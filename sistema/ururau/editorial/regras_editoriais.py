from __future__ import annotations
import json, re, unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any
BASE_DIR=Path(__file__).resolve().parents[2]
REGRAS_PATH=BASE_DIR/'config'/'regras_editoriais.json'
_FALLBACK={'versao':'fallback-v47.2','briefing_editorial':'Produza texto jornalístico profissional, factual, direto e sem linguagem de IA.','limites_campos':{'titulo_seo_min':40,'titulo_seo_max':89,'titulo_capa_min':20,'titulo_capa_max':60,'subtitulo_curto_max':200,'legenda_curta_max':100,'tags_min':5,'tags_max':12,'meta_description_min':120,'meta_description_max':160,'retranca_max_words':3,'nome_fonte_max_words':4,'creditos_foto_max_words':6,'corpo_min_chars':500,'corpo_paragrafos_min':3,'coverage_panel_min':0.85,'coverage_monitor_min':0.90,'score_qualidade_panel_min':90,'score_qualidade_monitor_min':92,'score_risco_max':10},'termos_ia_proibidos':['reforça','acende o alerta','vale lembrar','cabe ressaltar','nesse contexto'],'expressoes_proibidas':{},'frases_genericas_proibidas':[],'status_validos':['publicar_direto','salvar_rascunho','bloquear','bloqueio_total']}
_CACHE=None
def _merge(a,b):
    out=deepcopy(a)
    for k,v in (b or {}).items(): out[k]=_merge(out[k],v) if isinstance(v,dict) and isinstance(out.get(k),dict) else v
    return out
def obter_matriz_editorial():
    global _CACHE
    if _CACHE is not None: return deepcopy(_CACHE)
    try: data=json.loads(REGRAS_PATH.read_text(encoding='utf-8')) if REGRAS_PATH.exists() else {}
    except Exception: data={}
    _CACHE=_merge(_FALLBACK,data); return deepcopy(_CACHE)
def recarregar_regras_editoriais():
    global _CACHE; _CACHE=None; return obter_matriz_editorial()
def salvar_matriz_editorial(matriz:dict[str,Any])->None:
    REGRAS_PATH.parent.mkdir(parents=True,exist_ok=True); novo=_merge(obter_matriz_editorial(),matriz or {}); REGRAS_PATH.write_text(json.dumps(novo,ensure_ascii=False,indent=2),encoding='utf-8'); recarregar_regras_editoriais()
def atualizar_briefing_e_termos(briefing:str, termos:list[str])->None:
    limpos=[]; seen=set()
    for x in termos or []:
        t=re.sub(r'\s+',' ',str(x or '')).strip(); k=normalizar_texto(t)
        if t and k not in seen: limpos.append(t); seen.add(k)
    exp=dict(obter_matriz_editorial().get('expressoes_proibidas') or {})
    for t in limpos: exp.setdefault(t,None)
    salvar_matriz_editorial({'briefing_editorial':'\n'+(briefing or '').strip()+'\n','termos_ia_proibidos':limpos,'expressoes_proibidas':exp})
def limites(): return dict(obter_matriz_editorial().get('limites_campos') or {})
def obter_briefing_editorial(): return str(obter_matriz_editorial().get('briefing_editorial') or _FALLBACK['briefing_editorial'])
def obter_termos_ia_proibidos(): return [str(x).strip() for x in (obter_matriz_editorial().get('termos_ia_proibidos') or []) if str(x).strip()]
def obter_expressoes_proibidas():
    out={}
    for k,v in (obter_matriz_editorial().get('expressoes_proibidas') or {}).items(): out[str(k).strip()]=str(v).strip() if isinstance(v,str) and v.strip() else None
    return out
def obter_frases_genericas_proibidas(): return [str(x).strip() for x in (obter_matriz_editorial().get('frases_genericas_proibidas') or []) if str(x).strip()]
def normalizar_texto(texto:str)->str:
    texto=unicodedata.normalize('NFD',str(texto or '')); texto=''.join(c for c in texto if unicodedata.category(c)!='Mn'); return re.sub(r'\s+',' ',texto.lower()).strip()
def detectar_termos_ia(texto:str)->list[str]:
    alvo=normalizar_texto(texto); ach=[]; seen=set()
    for termo in sorted(obter_termos_ia_proibidos(),key=len,reverse=True):
        k=normalizar_texto(termo)
        if not k or k in seen: continue
        ok=(k in alvo) if ' ' in k else (re.search(rf'(?<!\w){re.escape(k)}(?!\w)',alvo) is not None)
        if ok: ach.append(termo); seen.add(k)
    return ach
def validar_termos_ia_em_artigo(article:Any, modo:str='panel')->dict[str,Any]:
    campos=obter_matriz_editorial().get('auditoria_saida',{}).get('campos_verificados_termos_ia') or ['titulo','titulo_seo','titulo_capa','subtitulo','subtitulo_curto','conteudo','corpo_materia','texto_final','legenda','legenda_curta','meta_description','tags','chamada_social','legenda_instagram']
    ach=[]
    for campo in campos:
        valor=article.get(campo,'') if isinstance(article,dict) else getattr(article,campo,'')
        if isinstance(valor,(list,tuple,set)): valor=', '.join(map(str,valor))
        for termo in detectar_termos_ia(str(valor or '')): ach.append({'campo':campo,'termo':termo})
    erros=[{'categoria':'EDITORIAL_BLOCKER','codigo':'termo_ia_proibido','mensagem':f"Termo de IA proibido encontrado em {i['campo']}: {i['termo']!r}",'campo':i['campo'],'termo':i['termo'],'bloqueia_publicacao':True,'corrigivel_automaticamente':True,'acao_recomendada':'reescrever_campo_antes_de_publicar','modo':modo} for i in ach]
    return {'passou':not ach,'achados':ach,'erros':erros,'total':len(ach),'modo':modo}
def montar_bloco_prompt_editorial()->str:
    m=obter_matriz_editorial(); l=m.get('limites_campos') or {}; termos=', '.join(obter_termos_ia_proibidos()[:160])
    return f"""== MATRIZ EDITORIAL ÚNICA URURAU {m.get('versao','')} ==
Fonte oficial das regras: sistema/config/regras_editoriais.json.
Use somente fatos presentes na fonte limpa, título, subtítulo, fatos obrigatórios ou relações factuais fornecidas.
Nunca invente nomes, cargos, datas, números, valores, falas, documentos, decisões, órgãos, reações ou desdobramentos.
Limites obrigatórios: título SEO até {l.get('titulo_seo_max',89)} caracteres; título de capa até {l.get('titulo_capa_max',60)}; subtítulo curto até {l.get('subtitulo_curto_max',200)}; legenda curta até {l.get('legenda_curta_max',100)}; retranca até {l.get('retranca_max_words',3)} palavra(s); tags entre {l.get('tags_min',5)} e {l.get('tags_max',12)}.
Bloqueio de linguagem de IA: não use nenhuma expressão da blocklist. Exemplos proibidos: {termos}.
Se uma expressão proibida aparecer na primeira versão, reescreva antes de devolver o JSON. No monitor 24h, qualquer termo de IA encontrado impede publicação direta.""".strip()
