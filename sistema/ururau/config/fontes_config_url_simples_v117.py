
from __future__ import annotations
import os, re
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from typing import Any

def _env_int(k: str, d: int) -> int:
    try: return int(str(os.getenv(k, d)).strip())
    except Exception: return d

@dataclass
class FonteURLSimplesV117:
    ordem: int
    url: str
    tipo: str
    nome_fonte: str
    canal_config_legado: str = ""
    canal_config_ignorado: bool = True
    max_por_link: int = 5
    ativo: bool = True
    def to_dict(self) -> dict[str, Any]: return asdict(self)

def limpar_prefixo_ordem(linha: str) -> str:
    return re.sub(r"^\s*\d+\s*[\.\-\|\)]\s*", "", (linha or "").strip()).strip()

def detectar_tipo(url: str) -> str:
    u=(url or '').lower().strip()
    return 'sitemap_xml' if 'sitemap' in u else 'rss'

def nome_por_url(url: str) -> str:
    host=urlparse(url).netloc.lower().replace('www.','')
    mapa={
      'j3news.com':'J3 News','portalviu.com.br':'Portal Viu','sfnoticias.com.br':'SF Notícias','odebateon.com.br':'O Debate',
      'cliquediario.com.br':'Clique Diário','parahybano.com.br':'O Parahybano','rjnewsnoticias.com.br':'RJ News Notícias',
      'jornaldesabado.com.br':'Jornal de Sábado','prensadebabel.com.br':'Prensa de Babel','agendadopoder.com.br':'Agenda do Poder',
      'diariodorio.com':'Diário do Rio','girorj.com.br':'Giro RJ','campos24horas.com.br':'Campos 24 Horas',
      'g1.globo.com':'G1','cnnbrasil.com.br':'CNN Brasil','poder360.com.br':'Poder360','odia.ig.com.br':'O Dia',
      'agenciabrasil.ebc.com.br':'Agência Brasil','camara.leg.br':'Câmara','senado.leg.br':'Senado','folha.uol.com.br':'Folha',
      'uol.com.br':'UOL','tse.jus.br':'TSE','stf.jus.br':'STF','stj.jus.br':'STJ','gov.br':'Gov.br','alerj.rj.gov.br':'ALERJ',
      'mprj.mp.br':'MPRJ','tre-rj.jus.br':'TRE-RJ','metropoles.com':'Metrópoles'}
    for k,v in mapa.items():
        if k in host: return v
    base=host.split('.')[0] if host else 'Fonte'
    return base.replace('-',' ').title()

def parse_fontes_url_simples(texto: str, tipo_forcado: str|None=None) -> list[FonteURLSimplesV117]:
    out=[]; seen=set(); ordem=0; max_por_link=_env_int('URURAU_RSS_MAX_POR_LINK',5)
    for raw in (texto or '').splitlines():
        linha=limpar_prefixo_ordem(raw)
        if not linha or linha.startswith('#'): continue
        partes=[p.strip() for p in linha.split('|')]
        url=partes[0] if partes else ''
        if not url.startswith(('http://','https://')): continue
        key=url.rstrip('/')
        if key in seen: continue
        seen.add(key); ordem+=1
        nome_legado=partes[1] if len(partes)>1 and partes[1] else ''
        canal_legado=partes[2] if len(partes)>2 and partes[2] else ''
        out.append(FonteURLSimplesV117(ordem,url,tipo_forcado or detectar_tipo(url),nome_legado or nome_por_url(url),canal_legado,True,max_por_link,True))
    return out

def linha_interna(f: FonteURLSimplesV117) -> str:
    return f"{f.url}|{f.nome_fonte}|"

def normalizar_para_interno(texto: str, tipo_forcado: str|None=None) -> str:
    return '\n'.join(linha_interna(f) for f in parse_fontes_url_simples(texto,tipo_forcado))

def formatar_visual_numerado(texto: str, tipo_forcado: str|None=None) -> str:
    return '\n'.join(f"{f.ordem}  {f.url}" for f in parse_fontes_url_simples(texto,tipo_forcado))

def separar_rss_xml(texto: str) -> tuple[str,str]:
    rss=[]; xml=[]
    for f in parse_fontes_url_simples(texto):
        (xml if f.tipo=='sitemap_xml' else rss).append(f.url)
    return '\n'.join(rss), '\n'.join(xml)

def fontes_para_json(texto: str) -> tuple[list[dict], list[str]]:
    rss=[]; xml=[]
    for f in parse_fontes_url_simples(texto):
        if f.tipo=='sitemap_xml': xml.append(f.url)
        else: rss.append({'url': f.url, 'nome': f.nome_fonte, 'canal_forcado': ''})
    return rss, xml
