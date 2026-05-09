from .generic_adapter import extract as generic_extract
from .wordpress_adapter import extract as wordpress_extract
from .globo_adapter import extract as globo_extract
from .uol_adapter import extract as uol_extract
from .folha_adapter import extract as folha_extract
from .agenciabrasil_adapter import extract as agenciabrasil_extract
from .oficial_adapter import extract as oficial_extract
from .local_news_adapter import extract as local_extract

ADAPTERS = {
    "generic": generic_extract,
    "wordpress": wordpress_extract,
    "globo": globo_extract,
    "uol": uol_extract,
    "folha": folha_extract,
    "agenciabrasil": agenciabrasil_extract,
    "oficial": oficial_extract,
    "local": local_extract,
}


def get_adapter(tipo_site: str):
    return ADAPTERS.get(tipo_site, generic_extract)
