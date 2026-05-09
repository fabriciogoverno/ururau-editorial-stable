
from ururau.config.fontes_config_url_simples_v117 import parse_fontes_url_simples, separar_rss_xml, normalizar_para_interno, formatar_visual_numerado
from ururau.editorial.classificador_editorial_contextual_v117 import classificar_editoria_contextual

def test_config_limpa_ordem_e_ignora_canal():
    fs=parse_fontes_url_simples('1 - https://j3news.com/feed/|J3 News|Estado RJ\n2. https://g1.globo.com/rss/g1/politica/')
    assert fs[0].url=='https://j3news.com/feed/' and fs[0].canal_config_legado=='Estado RJ' and fs[0].canal_config_ignorado is True and fs[1].ordem==2

def test_normaliza_interno_sem_canal():
    assert normalizar_para_interno('1 - https://j3news.com/feed/|J3 News|Estado RJ')=='https://j3news.com/feed/|J3 News|'

def test_visual_numerado_so_url():
    assert formatar_visual_numerado('https://j3news.com/feed/|J3 News|Estado RJ')=='1  https://j3news.com/feed/'

def test_separa_xml_de_rss():
    rss,xml=separar_rss_xml('https://a.com/feed/\nhttps://b.com/sitemap.xml')
    assert 'feed' in rss and 'sitemap' in xml

def test_classifica_policia_mesmo_com_estado_rj():
    assert classificar_editoria_contextual({'titulo':'Homem é preso com drogas em Guarus','canal':'Estado RJ'})['canal_sugerido']=='Polícia'

def test_classifica_economia():
    assert classificar_editoria_contextual({'titulo':'Porto do Açu anuncia investimento em nova área industrial'})['canal_sugerido']=='Economia'

def test_respeita_manual():
    assert classificar_editoria_contextual({'titulo':'Homem é preso','canal_sugerido':'Cidades','canal_manual':True})['canal_sugerido']=='Cidades'
