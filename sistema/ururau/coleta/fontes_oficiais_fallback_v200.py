from __future__ import annotations

"""fontes_oficiais_fallback_v200 — fallback automatico para feeds quebrados.

Quando o feed oficial de um orgao (ALERJ, MPRJ, TJRJ, TRE-RJ, Defensoria,
Camara, STJ, Governo RJ, Porto do Acu, TCE-RJ) responde 404, 302-loop ou
HTML em vez de RSS, este modulo substitui automaticamente a URL por uma
busca site:dominio no Google News RSS, que cobre o mesmo conteudo e e
estavel.

Tambem implementa fallback para domínios com timeout cronico (ex.:
girorj.com.br) — tenta Wayback Machine antes de declarar fracasso.

Politica: NUNCA inventa conteudo. Apenas troca a porta de entrada.
"""

from urllib.parse import quote_plus, urlparse
import os
import re

# Mapeamento: dominio (sem www) -> URL Google News RSS site:filter
# Estas sao as fontes onde a URL RSS oficial esta quebrada hoje.
DOMINIO_PARA_GNEWS = {
    "alerj.rj.gov.br": "site:alerj.rj.gov.br",
    "www.alerj.rj.gov.br": "site:alerj.rj.gov.br",
    "mprj.mp.br": "site:mprj.mp.br",
    "www.mprj.mp.br": "site:mprj.mp.br",
    "tre-rj.jus.br": "site:tre-rj.jus.br",
    "www.tre-rj.jus.br": "site:tre-rj.jus.br",
    "tjrj.jus.br": "site:tjrj.jus.br",
    "www.tjrj.jus.br": "site:tjrj.jus.br",
    "defensoria.rj.def.br": "site:defensoria.rj.def.br",
    "camara.leg.br": "site:camara.leg.br",
    "www.camara.leg.br": "site:camara.leg.br",
    "rj.gov.br": "site:rj.gov.br",
    "www.rj.gov.br": "site:rj.gov.br",
    "tce.rj.gov.br": "site:tce.rj.gov.br",
    "www.tce.rj.gov.br": "site:tce.rj.gov.br",
    "portodoacu.com.br": "site:portodoacu.com.br",
    "www.portodoacu.com.br": "site:portodoacu.com.br",
    "stj.jus.br": "site:stj.jus.br",
    "res.stj.jus.br": "site:stj.jus.br",
}

# Dominios com timeout cronico — tentar Wayback antes de desistir
DOMINIOS_TIMEOUT_CRONICO = {
    "girorj.com.br",
    "www.girorj.com.br",
}

# Padroes de URL que indicam endpoint comprovadamente quebrado
PADROES_ENDPOINT_QUEBRADO = [
    (re.compile(r"camara\.leg\.br/rss/noticias\.xml"), "site:camara.leg.br"),
    (re.compile(r"alerj\.rj\.gov\.br/Noticias/rss", re.I), "site:alerj.rj.gov.br"),
    (re.compile(r"mprj\.mp\.br/rss"), "site:mprj.mp.br"),
    (re.compile(r"tre-rj\.jus\.br/.*RSS", re.I), "site:tre-rj.jus.br"),
    (re.compile(r"tjrj\.jus\.br/.*noticias/rss"), "site:tjrj.jus.br"),
    (re.compile(r"defensoria\.rj\.def\.br/rss"), "site:defensoria.rj.def.br"),
    (re.compile(r"rj\.gov\.br/noticias/rss"), "site:rj.gov.br"),
]


def construir_url_gnews(query: str, janela_horas: int = 24) -> str:
    """Retorna URL RSS do Google News para uma query."""
    janela = f"+when:{janela_horas}h" if janela_horas else ""
    q = quote_plus(query) + janela
    return (
        f"https://news.google.com/rss/search?q={q}"
        "&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    )


def _host_sem_www(url: str) -> str:
    try:
        h = urlparse((url or "").strip()).netloc.lower()
        return h.replace("www.", "")
    except Exception:
        return ""


def substituir_url_se_quebrado(url_original: str, janela_horas: int = 24) -> tuple[str, str]:
    """Retorna (url_efetiva, motivo).

    - Se a URL bate em padrao quebrado, retorna URL GNews.
    - Se o dominio esta na lista de Google News fallback, retorna URL GNews.
    - Senao, retorna a URL original.
    """
    if not url_original:
        return url_original, ""

    # 1. padrao explicito de endpoint quebrado
    for padrao, query in PADROES_ENDPOINT_QUEBRADO:
        if padrao.search(url_original):
            return construir_url_gnews(query, janela_horas), f"endpoint_oficial_quebrado:{query}"

    # 2. dominio mapeado
    host = _host_sem_www(url_original)
    if host in DOMINIO_PARA_GNEWS:
        return construir_url_gnews(DOMINIO_PARA_GNEWS[host], janela_horas), f"dominio_mapeado_gnews:{host}"

    return url_original, ""


def dominio_e_timeout_cronico(url: str) -> bool:
    host = _host_sem_www(url)
    return host in DOMINIOS_TIMEOUT_CRONICO


def url_wayback_recente(url_original: str) -> str:
    """URL para versao mais recente no Wayback Machine."""
    return f"https://web.archive.org/web/2026/{url_original}"


def aplicar_fallback_em_fontes_especiais(fontes: list[dict], janela_horas: int = 24) -> list[dict]:
    """Recebe lista de fontes e retorna nova lista com URLs corrigidas.

    Mantem url_original em campo `_url_original_v200` para auditoria.
    """
    saida = []
    for f in fontes or []:
        nova = dict(f)
        url = nova.get("url") or ""
        url_nova, motivo = substituir_url_se_quebrado(url, janela_horas)
        if motivo:
            nova["_url_original_v200"] = url
            nova["url"] = url_nova
            nova["_fallback_motivo_v200"] = motivo
            # como agora vem de Google News, e RSS valido
            nova["tipo"] = "rss"
        saida.append(nova)
    return saida


def habilitado() -> bool:
    return os.getenv("URURAU_FONTES_OFICIAIS_FALLBACK_V200", "1") not in ("0", "false", "False")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for u in sys.argv[1:]:
            nova, motivo = substituir_url_se_quebrado(u)
            print(f"{u}\n  -> {nova}\n  motivo: {motivo or '(nenhuma alteracao)'}")
    else:
        amostras = [
            "https://www.alerj.rj.gov.br/Noticias/rss",
            "https://www.mprj.mp.br/rss",
            "https://www.camara.leg.br/rss/noticias.xml",
            "https://www.tre-rj.jus.br/comunicacao/noticias/RSS",
            "https://www.tjrj.jus.br/web/guest/home/-/noticias/rss",
            "https://defensoria.rj.def.br/rss/noticias",
            "https://www.rj.gov.br/noticias/rss",
            "https://noticias.stf.jus.br/feed/",  # nao alterar
        ]
        for u in amostras:
            nova, motivo = substituir_url_se_quebrado(u)
            mark = "DIFF" if nova != u else "OK  "
            print(f"[{mark}] {u}\n      -> {nova}\n      motivo: {motivo or '(nenhuma)'}")
