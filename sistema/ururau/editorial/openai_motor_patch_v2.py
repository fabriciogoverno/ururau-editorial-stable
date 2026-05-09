
from __future__ import annotations
import os
from ururau.editorial.motor_gpt_spec_v2 import auditar_pacote_motor,deve_forcar_json,extrair_json,prompt_correcao_motor,reforcar_messages_openai
_PATCHED=False
def _env_bool(k,d=True):
    v=os.getenv(k); return d if v is None else str(v).strip().lower() in {'1','true','yes','sim','on'}
def _extrair_fonte(messages):
    txt='\n\n'.join(str(m.get('content') or '') for m in messages or [])
    for mk in ['TEXTO DA FONTE','FONTE ORIGINAL','FONTE:','Texto da aba Fonte','texto_fonte']:
        i=txt.lower().find(mk.lower())
        if i>=0: return txt[i:][:12000]
    return txt[:12000]
def _conteudo(resp):
    try: return resp.choices[0].message.content or ''
    except Exception: pass
    try: return resp['choices'][0]['message']['content'] or ''
    except Exception: return ''
def aplicar_patch_openai_motor_v2():
    global _PATCHED
    if _PATCHED or not _env_bool('URURAU_MOTOR_PATCH_OPENAI_ATIVO',True): return
    _PATCHED=True
    try: import openai
    except Exception as exc: print(f'[MOTOR_V2][AVISO] openai não importado: {exc}'); return
    patched=0
    try:
        from openai.resources.chat.completions import Completions
        original=Completions.create
        def wrap(self,*args,**kwargs):
            messages=kwargs.get('messages'); fonte=_extrair_fonte(messages) if isinstance(messages,list) else ''
            if isinstance(messages,list): kwargs['messages']=reforcar_messages_openai(messages,fonte); kwargs=deve_forcar_json(kwargs)
            try: resp=original(self,*args,**kwargs)
            except Exception: kwargs.pop('response_format',None); resp=original(self,*args,**kwargs)
            if isinstance(messages,list) and _env_bool('URURAU_MOTOR_AUDITAR_RESPOSTA',True):
                pacote=extrair_json(_conteudo(resp)); aud=auditar_pacote_motor(pacote,fonte=fonte)
                if not aud.ok:
                    print('[MOTOR_V2][REPROVADO]',' | '.join(aud.problemas[:5]))
                    if _env_bool('URURAU_MOTOR_REGERAR_SE_REPROVAR',True):
                        kw=dict(kwargs); kw['messages']=reforcar_messages_openai([{'role':'system','content':'Você corrige matéria reprovada pelo padrão Ururau.'},{'role':'user','content':prompt_correcao_motor(pacote,fonte,aud.problemas)}],fonte)
                        try: return original(self,*args,**deve_forcar_json(kw))
                        except Exception: kw.pop('response_format',None); return original(self,*args,**kw)
            return resp
        Completions.create=wrap; patched+=1
    except Exception as exc: print(f'[MOTOR_V2][AVISO] patch SDK novo falhou: {exc}')
    print(f'[MOTOR_V2] patch OpenAI aplicado; pontos envolvidos: {patched}')
