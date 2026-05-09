# -*- coding: utf-8 -*-
from __future__ import annotations

def _get(o, k, d=''):
    if isinstance(o, dict): return o.get(k, d)
    return getattr(o, k, d)

def _set(o, k, v):
    if isinstance(o, dict): o[k] = v
    else:
        try: setattr(o, k, v)
        except Exception: pass

def corrigir_canal_materia(materia, pauta=None):
    pauta = pauta or {}
    campos = ['titulo','titulo_origem','subtitulo','descricao','conteudo','corpo','texto','texto_fonte','cleaned_source_text','canal']
    texto = ' '.join(str(_get(materia,k,'')) for k in campos) + ' ' + ' '.join(str(_get(pauta,k,'')) for k in campos)
    t = texto.lower()
    atual = _get(materia, 'canal', _get(pauta, 'canal', 'Brasil e Mundo')) or 'Brasil e Mundo'

    exterior = ['suriname','paraguai','argentina','chile','uruguai','eua','estados unidos','europa','espanha','oriente medio','irã','ira','israel','internacional','exterior']
    crime = ['policia federal','polícia federal',' pf ','prisao','prisão','preso','mandado','operacao','operação','trafico','tráfico','carcere','cárcere','sequestro','homicidio','homicídio','morte','tiros','drogas','facção']
    politica = ['alerj','stf','governo','prefeitura','deputado','governador','ministro','camara','câmara','senado','tce','mprj','detran']
    saude = ['anvisa','fiocruz','vacina','hospital','saude','saúde','doenca','doença','sindrome','síndrome','virus','vírus','hantavirus','hantavírus','malaria','malária']
    esporte = ['flamengo','vasco','fluminense','botafogo','libertadores','brasileirao','brasileirão','futebol']
    economia = ['dolar','dólar','ibge','renda','economia','emprego','petroleo','petróleo','mercado','inflacao','inflação']

    if any(x in t for x in exterior):
        novo = 'Brasil e Mundo'
    elif any(x in t for x in crime):
        novo = 'Polícia'
    elif any(x in t for x in politica):
        novo = 'Política'
    elif any(x in t for x in saude):
        novo = 'Saúde'
    elif any(x in t for x in esporte):
        novo = 'Esportes'
    elif any(x in t for x in economia):
        novo = 'Economia'
    else:
        novo = atual

    # Saude falso positivo: crime/exterior vence.
    if novo == 'Saúde' and any(x in t for x in crime + exterior):
        novo = 'Brasil e Mundo' if any(x in t for x in exterior) else 'Polícia'

    _set(materia, 'canal', novo)
    _set(materia, 'editoria', novo)
    _set(pauta, 'canal', novo)
    _set(pauta, 'editoria', novo)
    _set(pauta, 'canal_final_v47_23', novo)
    return novo
