
# -*- coding: utf-8 -*-
from __future__ import annotations
import re, unicodedata

def _txt(v): return str(v or '').strip()
def _words(t): return re.findall(r'\w+', _txt(t), flags=re.UNICODE)
def _norm(t):
    t=unicodedata.normalize('NFKD', _txt(t)).encode('ascii','ignore').decode().lower()
    return re.sub(r'\s+',' ',t).strip()

TERMOS_IA = ['reforça','acende o alerta','vale lembrar','cabe ressaltar','é importante destacar','nesse contexto','ganha destaque','chama atenção']

def avaliar_seo_premium(materia: dict) -> dict:
    titulo=_txt(materia.get('titulo') or materia.get('titulo_seo'))
    capa=_txt(materia.get('titulo_capa'))
    sub=_txt(materia.get('subtitulo') or materia.get('descricao'))
    meta=_txt(materia.get('meta_description') or materia.get('meta'))
    corpo=_txt(materia.get('corpo') or materia.get('texto') or materia.get('conteudo'))
    tags=materia.get('tags') or []
    if isinstance(tags,str): tags=[x.strip() for x in tags.split(',') if x.strip()]
    score=0; checks=[]
    def add(ok, pts, msg):
        nonlocal score
        if ok: score += pts
        checks.append({'ok':bool(ok),'pts':pts,'msg':msg})
    add(35 <= len(titulo) <= 89, 14, f'título SEO com {len(titulo)} caracteres')
    add(not capa or len(capa) <= 60, 6, f'título de capa com {len(capa)} caracteres')
    add(35 <= len(sub) <= 180, 10, f'subtítulo com {len(sub)} caracteres')
    add(110 <= len(meta) <= 165, 10, f'meta description com {len(meta)} caracteres')
    add(len(_words(corpo)) >= 220, 14, f'corpo com {len(_words(corpo))} palavras')
    add(len(re.findall(r'\n\s*\n|\n', corpo)) >= 2, 8, 'estrutura em parágrafos')
    add(5 <= len(tags) <= 12, 8, f'{len(tags)} tags')
    add(bool(re.search(r'\b(quando|onde|quem|segundo|nesta|neste|após|durante)\b', corpo.lower())), 8, 'contexto factual')
    add(not any(t in _norm(titulo+' '+sub+' '+corpo) for t in TERMOS_IA), 12, 'sem termos de IA bloqueantes')
    add(bool(titulo and corpo and sub), 10, 'campos essenciais preenchidos')
    return {'seo_score': min(100, score), 'score': min(100,score), 'checks': checks, 'aprovado_publicacao_direta': score >= 90}

def otimizar_metadados_basico(materia: dict) -> dict:
    m=dict(materia or {})
    titulo=_txt(m.get('titulo') or m.get('titulo_seo'))
    if len(titulo)>89: m['titulo']=titulo[:86].rstrip()+'...'
    if not _txt(m.get('titulo_capa')) and titulo: m['titulo_capa']=titulo[:60].rstrip()
    corpo=_txt(m.get('corpo') or m.get('texto') or m.get('conteudo'))
    if not _txt(m.get('meta_description')):
        frase=re.split(r'(?<=[.!?])\s+', corpo)[0] if corpo else _txt(m.get('subtitulo'))
        m['meta_description']=frase[:160].rstrip()
    return m
