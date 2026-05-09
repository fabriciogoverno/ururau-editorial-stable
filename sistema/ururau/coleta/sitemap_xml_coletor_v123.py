from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
import os
import re
import xml.etree.ElementTree as ET

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

try:
    import requests
except Exception:
    requests = None

LAST_DIAGNOSTICO_SITEMAP_V128 = {}


def obter_diagnostico_sitemap_v128() -> dict:
    try:
        import copy
        return copy.deepcopy(LAST_DIAGNOSTICO_SITEMAP_V128 or {})
    except Exception:
        return dict(LAST_DIAGNOSTICO_SITEMAP_V128 or {})


def _get_url(url: str, timeout: int = 20) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
    }
    if requests is not None:
        r = requests.get(url, timeout=timeout, headers=headers)
        r.raise_for_status()
        return r.content

    from urllib.request import Request, urlopen
    req = Request(url, headers=headers)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_data_iso(valor: str):
    valor = (valor or "").strip()
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _br_naive(dt):
    if not dt:
        return None
    try:
        if ZoneInfo is not None:
            return dt.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        return dt.replace(tzinfo=None)
    except Exception:
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt


def _titulo_por_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"[-_]+", " ", slug).strip()
    slug = re.sub(r"\s+", " ", slug)
    if not slug:
        return "Notícia"
    return slug[:1].upper() + slug[1:]


def _nome_fonte_por_url(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    if "campos24horas.com.br" in host:
        return "Campos 24 Horas"
    return host or "XML/Sitemap"


def _normalizar_chave_url_v124(url: str) -> str:
    """Normaliza URL para deduplicar www/não-www e barra final entre sitemaps."""
    try:
        p = urlparse((url or "").strip())
        host = p.netloc.lower().replace("www.", "")
        path = re.sub(r"/+$", "", p.path or "")
        return f"{host}{path}".lower()
    except Exception:
        return (url or "").strip().lower().rstrip("/")


def _uid(url: str, titulo: str) -> str:
    import hashlib
    chave = _normalizar_chave_url_v124(url)
    return hashlib.sha1((chave + "|" + titulo).encode("utf-8", "ignore")).hexdigest()[:16]


def coletar_sitemap_xml(
    url_sitemap: str,
    janela_horas: int = 48,
    limite: int = 30,
    fonte_nome: str | None = None,
) -> list[dict]:
    conteudo = _get_url(url_sitemap)
    root = ET.fromstring(conteudo)

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    itens = root.findall("sm:url", ns)
    if not itens:
        itens = root.findall(".//url")

    agora = datetime.now(timezone.utc)
    pautas: list[dict] = []
    vistos: set[str] = set()
    fonte_nome = fonte_nome or _nome_fonte_por_url(url_sitemap)

    for item in itens:
        loc = item.findtext("sm:loc", default="", namespaces=ns) or item.findtext("loc", default="")
        lastmod = item.findtext("sm:lastmod", default="", namespaces=ns) or item.findtext("lastmod", default="")
        loc = (loc or "").strip()
        if not loc or loc in vistos:
            continue
        if "/noticia/" not in loc:
            continue

        data_utc = _parse_data_iso(lastmod)
        if data_utc is not None and agora - data_utc > timedelta(hours=janela_horas):
            continue

        data_br = _br_naive(data_utc) if data_utc else None
        titulo = _titulo_por_url(loc)
        vistos.add(loc)

        pauta = {
            "titulo_origem": titulo,
            "titulo": titulo,
            "link_origem": loc,
            "url": loc,
            "link": loc,
            "fonte_nome": fonte_nome,
            "fonte": fonte_nome,
            "resumo_origem": "",
            "origem_feed": "xml_sitemap_v123",
            "origem": f"XML/Sitemap: {fonte_nome}",
            "canal_forcado": "",
            "canal": "",
            "canal_sugerido": "",
            "data_pub_fonte": data_br.strftime("%d/%m/%Y %H:%M") if data_br else "",
            "data_pub_fonte_br": data_br.strftime("%d/%m/%Y %H:%M") if data_br else "",
            "data_pub_fonte_original": lastmod,
            "_data_pub_ordem": data_br.isoformat() if data_br else "",
            "_uid": _uid(loc, titulo),
            "uid": _uid(loc, titulo),
            "tipo_fonte": "sitemap_xml",
            "_v94_listagem_rapida": True,
            "_v94_precisa_hidratar": True,
            "precisa_hidratar_fonte": True,
            # v124: sitemap serve para comprovar a fonte e alimentar pauta local.
            # Mesmo fora da janela curta de 8h, deve passar como exceção operacional.
            "_excecao_fora_janela_v123": True,
            "_sitemap_excecao_janela_v124": True,
            "_motivo_excecao_janela_v123": "sitemap_xml_local",
            "prioridade": 5,
            "score_editorial": 120,
            "score": 140,
        }
        pautas.append(pauta)
        if len(pautas) >= limite:
            break

    return pautas


def coletar_sitemaps_configurados_v123(path: str | Path = "fontes_xml_sitemap_vfinal.txt") -> list[dict]:
    global LAST_DIAGNOSTICO_SITEMAP_V128
    path = Path(path)
    LAST_DIAGNOSTICO_SITEMAP_V128 = {"arquivo_config": str(path), "sitemaps": [], "total_final": 0}
    if not path.exists():
        LAST_DIAGNOSTICO_SITEMAP_V128["erro"] = "arquivo de sitemaps não encontrado"
        return []

    janela = int(os.getenv("URURAU_V123_SITEMAP_JANELA_HORAS", os.getenv("URURAU_V99_JANELA_PUBLICACAO_HORAS", "48")))
    limite_por_sitemap = int(os.getenv("URURAU_V123_SITEMAP_LIMITE_POR_FONTE", "30"))

    saida: list[dict] = []
    vistos: set[str] = set()

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        url = raw.strip()
        if not url or url.startswith("#"):
            continue
        try:
            lote = coletar_sitemap_xml(url, janela_horas=janela, limite=limite_por_sitemap)
            LAST_DIAGNOSTICO_SITEMAP_V128["sitemaps"].append({"url": url, "itens": len(lote), "erro": ""})
            print(f"[XML/SITEMAP v123] {url}: {len(lote)} pauta(s)")
            for p in lote:
                raw_chave = p.get("link_origem") or p.get("url")
                chave = _normalizar_chave_url_v124(raw_chave)
                if chave and chave not in vistos:
                    vistos.add(chave)
                    saida.append(p)
        except Exception as exc:
            LAST_DIAGNOSTICO_SITEMAP_V128["sitemaps"].append({"url": url, "itens": 0, "erro": f"{type(exc).__name__}: {exc}"})
            print(f"[XML/SITEMAP v123] falha em {url}: {type(exc).__name__}: {exc}")

    LAST_DIAGNOSTICO_SITEMAP_V128["total_final"] = len(saida)
    return saida


def coletar_sitemap_campos24(janela_horas: int = 48, limite: int = 30):
    return coletar_sitemap_xml(
        "https://campos24horas.com.br/noticia/sitemap.xml",
        janela_horas=janela_horas,
        limite=limite,
        fonte_nome="Campos 24 Horas",
    )


if __name__ == "__main__":
    itens = coletar_sitemap_campos24(janela_horas=72, limite=10)
    print(f"{len(itens)} pauta(s) encontradas")
    for p in itens:
        print("-", p["titulo_origem"])
        print(" ", p["link_origem"])
