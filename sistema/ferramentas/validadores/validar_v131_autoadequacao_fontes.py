from pathlib import Path
import json
import sys

base = Path(__file__).resolve().parent
sys.path.insert(0, str(base))

from ururau.coleta.auto_perfil_fontes_v131 import gerar_perfil_v131, testar_perfil_v131, formatar_relatorio_v131

fake = {
    "name": "exemplo.com.br",
    "root": "https://exemplo.com.br/",
    "summary": {"RSS/Atom raiz": "1 válido(s)"},
    "solucao": {
        "estrategia_principal": "rss",
        "feeds": ["https://exemplo.com.br/rss/"],
        "sitemaps": [],
        "wp_api": "",
        "html_fallback": [],
        "playwright": False,
    },
}
p = gerar_perfil_v131(fake, nome_preferido="Exemplo")
assert p["parser"] == "rss_cascata"
assert p["grupo"] == "RSS"
assert p["feeds"]
print("[OK] v131: motor de autoadequação importado e perfil operacional gerado.")
