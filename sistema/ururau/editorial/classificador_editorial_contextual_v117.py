
from __future__ import annotations
import os
from typing import Any
CANAIS_VALIDOS=['Política','Estado RJ','Cidades','Polícia','Economia','Saúde','Educação','Esportes','Tecnologia','Rural','Entretenimento','Curiosidades','Brasil e Mundo','Opinião']
REGRAS={
 'Polícia':['preso','prisão','apreensão','drogas','arma','homicídio','roubo','furto','tráfico','pm','polícia civil','delegacia','operação policial','mandado','suspeito','vítima','flagrante','foragido'],
 'Política':['alerj','deputado','governador','prefeito','câmara','senado','stf','tse','tre','partido','eleição','veto','projeto de lei','mandato','campanha','bacellar','wladimir','claudio castro','cláudio castro','eduardo paes','ricardo couto'],
 'Saúde':['hospital','ubs','upa','vacinação','dengue','atendimento médico','cirurgia','secretaria de saúde','paciente','medicamento','emergência médica'],
 'Educação':['escola','aluno','professor','universidade','matrícula','enem','creche','educação','aula','campus'],
 'Economia':['porto do açu','petrobras','petróleo','royalties','emprego','investimento','indústria','comércio','inflação','pib','dólar','arrecadação','fazenda','imposto','mercado','energia'],
 'Esportes':['futebol','brasileirão','flamengo','vasco','fluminense','botafogo','jogo','partida','técnico','atleta','campeonato','gol'],
 'Cidades':['prefeitura','bairro','obra','trânsito','chuva','serviço público','moradores','rua','iluminação','coleta','transporte municipal','campos dos goytacazes'],
 'Estado RJ':['governo do estado','palácio guanabara','secretaria estadual','estado do rio','tce-rj','tjrj','rio de janeiro','baixada','região metropolitana'],
 'Brasil e Mundo':['governo federal','presidente da república','congresso nacional','internacional','guerra','exterior','estados unidos','argentina','china','europa'],
 'Tecnologia':['tecnologia','inteligência artificial','aplicativo','internet','software','celular'],
 'Rural':['rural','agro','agricultura','pecuária','produtor rural','safra'],
 'Entretenimento':['show','cantor','atriz','ator','festival','cinema','música'],
 'Curiosidades':['curioso','inusitado','viral','ranking']}
def _env_bool(k,d=True):
    v=os.getenv(k); return d if v is None else str(v).strip().lower() in {'1','true','yes','sim','on'}
def texto_pauta(pauta:dict[str,Any])->str:
    campos=['titulo','titulo_origem','subtitulo','descricao','resumo','resumo_origem','texto_fonte','corpo_materia','conteudo','tags']
    return ' '.join(str(pauta.get(c) or '') for c in campos).lower()
def classificar_editoria_contextual(pauta:dict[str,Any])->dict[str,Any]:
    if not _env_bool('URURAU_EDITORIA_CONTEXTUAL_ATIVA',True):
        return {'canal_sugerido':pauta.get('canal_sugerido') or pauta.get('canal') or 'Cidades','confianca':0,'motivos':['desligado'],'canal_anterior':pauta.get('canal') or ''}
    if _env_bool('URURAU_RESPEITAR_CANAL_MANUAL',True) and pauta.get('canal_manual'):
        return {'canal_sugerido':pauta.get('canal_sugerido') or pauta.get('canal') or 'Cidades','confianca':1.0,'motivos':['canal manual respeitado'],'canal_anterior':pauta.get('canal') or ''}
    txt=texto_pauta(pauta); scores={c:0 for c in CANAIS_VALIDOS}; motivos={c:[] for c in CANAIS_VALIDOS}
    for canal,termos in REGRAS.items():
        for termo in termos:
            if termo in txt:
                scores[canal]+=4 if ' ' in termo else 2
                if len(motivos[canal])<5: motivos[canal].append('termo: '+termo)
    for c,b in [('Polícia',5),('Política',4),('Saúde',4),('Economia',4)]:
        if scores[c]>=4: scores[c]+=b
    canal=max(scores,key=scores.get); score=scores[canal]
    if score<=0: canal='Cidades'; conf=0.35; mot=['fallback contextual sem sinal forte']
    else: conf=min(0.98,0.45+score/20); mot=motivos[canal]
    return {'canal_sugerido':canal,'confianca':round(conf,2),'motivos':mot,'canal_anterior':pauta.get('canal_sugerido') or pauta.get('canal') or pauta.get('canal_config_legado') or '','fonte_usada_apenas_como_sinal_fraco':True,'canais_scores':scores}
def aplicar_editoria_contextual(pauta:dict[str,Any])->dict[str,Any]:
    res=classificar_editoria_contextual(pauta)
    pauta['editoria_contextual_v117']=res
    if pauta.get('canal_manual') and _env_bool('URURAU_RESPEITAR_CANAL_MANUAL',True): return pauta
    pauta['canal_sugerido']=res['canal_sugerido']; pauta['canal']=res['canal_sugerido']; pauta['canal_forcado']=''
    return pauta
