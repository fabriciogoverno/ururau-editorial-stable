from ururau.coleta import auto_perfil_fontes_v131 as m

assert m._parse_date('02/05/2026 17:54').strftime('%d/%m/%Y %H:%M') == '02/05/2026 17:54'
assert m._parse_date('Publicado em 2/5/2026 às 17h54').strftime('%d/%m/%Y %H:%M') == '02/05/2026 17:54'
html = '''<html><head><meta property="og:title" content="Americano perde para o São Gonçalo no Aryzão pela Série A2 do Carioca"><meta property="og:description" content="Teste"><meta property="og:image" content="https://www.folha1.com.br/img.jpg"></head><body>02/05/2026 17:54 - Atualizado em 02/05/2026 17:53</body></html>'''
# Simula extração direta de data brasileira usada pelo fallback de artigo.
d = m._parse_data_br_texto(html)
assert d and d.strftime('%d/%m/%Y %H:%M') == '02/05/2026 17:54'
print('[OK] v131.2 Folha HTML com data real validado')
