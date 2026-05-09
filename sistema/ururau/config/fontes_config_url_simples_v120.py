from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from typing import Any

URL_RE = re.compile(r"https?://[^\s|]+", re.I)


def _env_int(k: str, d: int) -> int:
    try:
        return int(str(os.getenv(k, d)).strip())
    except Exception:
        return d


@dataclass
class FonteURLSimplesV120:
    ordem: int
    url: str
    tipo: str
    nome_fonte: str
    canal_config_legado: str = ""
    canal_config_ignorado: bool = True
    max_por_link: int = 5
    ativo: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def limpar_prefixo_ordem(linha: str) -> str:
    return re.sub(r"^\s*\d+\s*[\.\-\|\)]\s*", "", (linha or "").strip()).strip()


def extrair_url(linha: str) -> str:
    linha = limpar_prefixo_ordem(linha)
    if "|" in linha:
        linha = linha.split("|", 1)[0].strip()
    m = URL_RE.search(linha)
    return m.group(0).strip() if m else ""


def is_sitemap(url: str) -> bool:
    return "sitemap" in (url or "").lower()


def detectar_tipo(url: str) -> str:
    # feed.xml/rss.xml são feeds RSS normais. Só sitemap fica fora do RSS.
    return "sitemap_xml" if is_sitemap(url) else "rss"


def nome_por_url(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    mapa = {
        "j3news.com": "J3 News",
        "portalviu.com.br": "Portal Viu",
        "sfnoticias.com.br": "SF Notícias",
        "odebateon.com.br": "O Debate",
        "cliquediario.com.br": "Clique Diário",
        "parahybano.com.br": "O Parahybano",
        "rjnewsnoticias.com.br": "RJ News Notícias",
        "jornaldesabado.com.br": "Jornal de Sábado",
        "prensadebabel.com.br": "Prensa de Babel",
        "agendadopoder.com.br": "Agenda do Poder",
        "diariodorio.com": "Diário do Rio",
        "girorj.com.br": "Giro RJ",
        "campos24horas.com.br": "Campos 24 Horas",
        "g1.globo.com": "G1 Política",
        "cnnbrasil.com.br": "CNN Brasil",
        "folha.uol.com.br": "Folha Poder",
        "uol.com.br": "UOL",
        "senado.leg.br": "Senado",
        "stf.jus.br": "STF",
        "stj.jus.br": "STJ",
        "tse.jus.br": "TSE",
        "rj.gov.br": "Governo RJ",
        "mprj.mp.br": "MPRJ",
        "poder360.com.br": "Poder360",
        "odia.ig.com.br": "O Dia",
        "bs.vibra.digital": "Band",
        "tre-rj.jus.br": "TRE-RJ",
        "metropoles.com": "Metrópoles",
        "mancheterj.com": "Manchete RJ",
        "mancheterio.com.br": "Manchete Rio",
        "campos.rj.gov.br": "Prefeitura Campos",
        "camara.leg.br": "Câmara",
        "alerj.rj.gov.br": "ALERJ",
        "tjrj.jus.br": "TJRJ",
        "defensoria.rj.def.br": "Defensoria RJ",
        "agenciabrasil.ebc.com.br": "Agência Brasil",
        "gov.br": "Gov.br",
    }
    for k, v in mapa.items():
        if k in host:
            return v
    base = host.split(".")[0] if host else "Fonte"
    return base.replace("-", " ").title()


def parse_fontes_url_simples(texto: str, tipo_forcado: str | None = None) -> list[FonteURLSimplesV120]:
    out: list[FonteURLSimplesV120] = []
    seen: set[str] = set()
    ordem = 0
    max_por_link = _env_int("URURAU_RSS_MAX_POR_LINK", 5)

    for raw in (texto or "").splitlines():
        url = extrair_url(raw)
        if not url:
            continue
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        ordem += 1

        linha = limpar_prefixo_ordem(raw)
        partes = [p.strip() for p in linha.split("|")]
        nome_legado = partes[1] if len(partes) > 1 and partes[1] else ""
        canal_legado = partes[2] if len(partes) > 2 and partes[2] else ""

        tipo = tipo_forcado or detectar_tipo(url)
        out.append(FonteURLSimplesV120(
            ordem=ordem,
            url=url,
            tipo=tipo,
            nome_fonte=nome_legado or nome_por_url(url),
            canal_config_legado=canal_legado,
            canal_config_ignorado=True,
            max_por_link=max_por_link,
            ativo=True,
        ))

    return out


def linha_interna(f: FonteURLSimplesV120) -> str:
    return f"{f.url}|{f.nome_fonte}|"


def normalizar_para_interno(texto: str, tipo_forcado: str | None = None) -> str:
    return "\n".join(linha_interna(f) for f in parse_fontes_url_simples(texto, tipo_forcado))


def formatar_visual_numerado(texto: str, tipo_forcado: str | None = None) -> str:
    return "\n".join(f"{f.ordem}  {f.url}" for f in parse_fontes_url_simples(texto, tipo_forcado))


def separar_rss_xml(texto: str) -> tuple[str, str]:
    rss: list[str] = []
    xml: list[str] = []
    for f in parse_fontes_url_simples(texto):
        if f.tipo == "sitemap_xml":
            xml.append(f.url)
        else:
            rss.append(f.url)
    return "\n".join(rss), "\n".join(xml)


def fontes_para_json(texto: str) -> tuple[list[dict], list[str]]:
    rss: list[dict] = []
    xml: list[str] = []
    for f in parse_fontes_url_simples(texto):
        if f.tipo == "sitemap_xml":
            xml.append(f.url)
        else:
            rss.append({
                "url": f.url,
                "nome": f.nome_fonte,
                "canal_forcado": "",
                "ativo": True,
                "tipo_coleta": "rss",
                "max_por_link": f.max_por_link,
                "ordem": f.ordem,
            })
    return rss, xml


def sitemap_para_lista(texto: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for f in parse_fontes_url_simples(texto, tipo_forcado="sitemap_xml"):
        if not is_sitemap(f.url):
            continue
        key = f.url.rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(f.url)
    return out
