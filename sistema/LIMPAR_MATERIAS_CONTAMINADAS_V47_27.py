# -*- coding: utf-8 -*-
from ururau.editorial.limpar_contaminadas_v47_27 import limpar_banco
import json
r = limpar_banco('data/ururau.db')
print(json.dumps(r, ensure_ascii=False, indent=2))
