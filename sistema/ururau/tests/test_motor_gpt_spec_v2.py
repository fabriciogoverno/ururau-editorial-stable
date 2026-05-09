
from ururau.editorial.motor_gpt_spec_v2 import auditar_pacote_motor, reforcar_messages_openai, extrair_json

def test_audita_paragrafo_unico():
    aud=auditar_pacote_motor({'titulo_seo':'Teste','corpo_materia':'Frase. '*300},fonte='')
    assert not aud.ok and any('parágrafo' in p.lower() for p in aud.problemas)

def test_audita_termo_proibido():
    aud=auditar_pacote_motor({'titulo_seo':'Teste','corpo_materia':'O caso chamou atenção na cidade.\n\nOutro parágrafo.\n\nTerceiro.\n\nQuarto.'},fonte='')
    assert not aud.ok

def test_reforca_messages():
    out=reforcar_messages_openai([{'role':'user','content':'gere matéria'}],fonte='fonte')
    assert out[0]['role']=='system' and 'REGRA CENTRAL' in out[0]['content']

def test_extrair_json():
    assert extrair_json('{"titulo_seo":"A","corpo_materia":"B"}')['titulo_seo']=='A'
