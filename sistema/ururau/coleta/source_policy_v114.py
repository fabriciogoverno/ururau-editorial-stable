"""
ururau/coleta/source_policy_v114.py

v111.4 — Politica operacional de fontes e termos para a coleta do Ururau.

Objetivo:
- separar fonte RSS de termo de busca;
- priorizar fontes que os logs mostraram como produtivas;
- colocar em quarentena fontes que retornaram 0 entradas nos ciclos analisados;
- reduzir ruido editorial evidente sem bloquear pauta local/politica relevante;
- impedir variantes mobile falsas como m.www.* e m.girorj.com.br.
"""
from __future__ import annotations

from urllib.parse import urlparse
import re
from typing import Any, Dict, Iterable, List, Tuple

FONTES_PRODUTIVAS = {
    "j3 news", "portal viu", "sf notícias", "sf noticias", "o debate",
    "clique diário", "clique diario", "o parahybano", "rj news notícias", "rj news noticias",
    "jornal de sábado", "jornal de sabado", "prensa de babel", "agenda do poder",
    "diário do rio", "diario do rio", "giro rj", "agência brasil geral", "agencia brasil geral",
    "agência brasil", "agencia brasil", "g1 rio de janeiro", "g1 política", "g1 politica",
    "g1 economia", "g1 mundo", "cnn brasil",
}

FONTES_QUARENTENA = {
    "folha 1", "campos 24 horas", "manchete rj", "g1 norte fluminense",
    "vnotícia", "vnoticia", "nf notícias", "nf noticias", "portal ozk",
    "macaé news", "macae news", "jornal o diário", "jornal o diario",
    "portal da cidade campos", "portal da cidade macaé", "portal da cidade macae",
    "quissamã notícias", "quissama noticias", "paulo noel", "tribuna nf",
    "destaque diário", "destaque diario", "cidades do rio", "notícias de macaé",
    "noticias de macae", "portal g6", "conexão noroeste", "conexao noroeste",
    "jornal zona norte", "o dia — informe do dia", "o dia - informe do dia",
}

MOBILE_INVALID_DOMAINS = {
    "j3news.com", "portalviu.com.br", "www.portalviu.com.br", "sfnoticias.com.br",
    "girorj.com.br", "prensadebabel.com.br",
}

TERMOS_NEGATIVOS = {
    "bbb", "fofoca", "horóscopo", "horoscopo", "signo", "novela",
    "receita", "cupom", "promoção", "promocao", "treonina", "mudas na água",
    "mudas na agua", "segredo", "incrível", "incrivel", "revelado", "chocante",
    "embaixador de marca", "realme", "jungkook", "shakira", "piqué", "pique",
    "programação infantil", "programacao infantil", "coração acelerado", "coracao acelerado",
    "maxiane", "jordana", "loteria", "mega-sena",
}

TERMOS_POSITIVOS = {
    "campos", "goytacazes", "norte fluminense", "macaé", "macae",
    "são joão da barra", "sao joao da barra", "porto do açu", "porto do acu",
    "alerj", "governo rj", "governo do rio", "rio de janeiro", "rj",
    "polícia", "policia", "operação", "operacao", "prefeitura", "câmara", "camara",
    "tce-rj", "mprj", "tjrj", "tre-rj", "stf", "stj", "tse",
    "licitação", "licitacao", "fraude", "investigação", "investigacao",
    "royalties", "inss", "fgts", "anvisa", "receita federal",
    "claudio castro", "cláudio castro", "eduardo paes", "douglas ruas",
    "wladimir garotinho", "rodrigo bacellar",
    "flamengo", "vasco", "vasco da gama", "botafogo", "fluminense",
    "americano de campos", "americano futebol clube", "americano fc",
    "goytacaz", "goytacaz futebol clube", "goitacaz", "goitacaz futebol clube",
}

FONTES_NACIONAIS = {
    "g1 política", "g1 politica", "g1 economia", "g1 mundo", "cnn brasil",
    "folha poder", "folha mercado", "uol esportes", "metrópoles", "metropoles",
    "poder360", "carta capital", "brasil 247", "correio braziliense",
}


def _norm(texto: str) -> str:
    return re.sub(r"\s+", " ", str(texto or "").strip().lower())


def _as_dict(fonte: Any) -> Dict[str, Any]:
    return fonte if isinstance(fonte, dict) else {}


def dominio(url: str) -> str:
    try:
        host = (urlparse(url or "").netloc or "").lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def is_feed_url(url: str) -> bool:
    u = (url or "").lower()
    return any(x in u for x in ("/feed", "/rss", "rss.xml", "feed.xml", "rss2.xml", "atom.xml", "?feed="))


def mobile_variant_allowed(url: str) -> bool:
    d = dominio(url)
    if not d or d in MOBILE_INVALID_DOMAINS or d.startswith("m."):
        return False
    return d in set()


def fonte_nome(fonte: Dict[str, Any] | Any) -> str:
    f = _as_dict(fonte)
    return _norm(f.get("nome") or f.get("fonte_nome") or f.get("url") or "")


def status_fonte_por_log(fonte: Dict[str, Any] | Any) -> str:
    nome = fonte_nome(fonte)
    if nome in FONTES_PRODUTIVAS:
        return "produtiva"
    if nome in FONTES_QUARENTENA:
        return "quarentena"
    return "desconhecida"


def prioridade_fonte(fonte: Dict[str, Any] | Any) -> int:
    f = _as_dict(fonte)
    nome = fonte_nome(f)
    escopo = _norm(f.get("escopo") or f.get("regiao") or f.get("canal_forcado") or "")
    try:
        peso = int(f.get("peso") or f.get("peso_fonte") or f.get("prioridade") or 0)
    except Exception:
        peso = 0
    score = 50 + min(30, max(0, peso))
    if nome in FONTES_PRODUTIVAS:
        score += 100
    if nome in FONTES_QUARENTENA:
        score -= 100
    if any(x in escopo for x in ("local", "campos", "norte")):
        score += 30
    if nome in FONTES_NACIONAIS:
        score -= 10
    return score


def ordenar_fontes(fontes: Iterable[Dict[str, Any]], incluir_quarentena: bool = False) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for f in fontes or []:
        if not isinstance(f, dict):
            continue
        if f.get("ativo", True) is False:
            continue
        st = status_fonte_por_log(f)
        g = dict(f)
        g["source_health_v114"] = st
        if st == "quarentena" and not incluir_quarentena:
            continue
        out.append(g)
    return sorted(out, key=prioridade_fonte, reverse=True)


def deve_ignorar_pauta(titulo: str, resumo: str = "", url: str = "", fonte: str = "") -> Tuple[bool, str]:
    texto = _norm(" ".join([titulo or "", resumo or "", url or "", fonte or ""]))
    if not texto:
        return True, "sem_texto"

    tem_pos = any(t in texto for t in TERMOS_POSITIVOS)
    try:
        from ururau.coleta.linha_editorial_v129 import analisar_texto_linha_editorial_v129
        analise_v129 = analisar_texto_linha_editorial_v129(titulo, resumo, fonte, url)
        if analise_v129.get("termos"):
            tem_pos = True
    except Exception:
        pass

    negs = [t for t in TERMOS_NEGATIVOS if t in texto]
    if negs and not tem_pos:
        return True, "ruido_editorial:" + ",".join(negs[:3])
    return False, "ok"


def termos_simples_padrao() -> List[str]:
    termos = [
        "Campos dos Goytacazes", "Norte Fluminense", "Porto do Açu", "São João da Barra",
        "Alerj", "Douglas Ruas", "Wladimir Garotinho", "Rodrigo Bacellar", "Eduardo Paes",
        "Cláudio Castro", "TCE-RJ", "MPRJ", "Campos 24 Horas", "Folha 1 Campos",
    ]
    try:
        from ururau.coleta.linha_editorial_v129 import termos_padrao_config_v129
        for item in termos_padrao_config_v129():
            termo = str(item.get("termo") or "").strip()
            if termo and termo not in termos:
                termos.append(termo)
    except Exception:
        pass
    return termos
