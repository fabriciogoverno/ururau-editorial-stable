from __future__ import annotations

"""sitemap_xml_coletor_v200 - coletor de sitemap RECURSIVO e tolerante.

Resolve limitacoes do v123:
1. Descer dentro de sitemap_index (urlset vs sitemapindex).
2. Sanitizar entidades XML invalidas (& solto, nbsp etc) antes do parse.
3. Detectar URL parece noticia sem depender de /noticia/ no path.

Mantem compatibilidade com a interface do v123.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
import hashlib
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

LAST_DIAGNOSTICO_SITEMAP_V200 = {}

PROFUNDIDADE_MAX_SITEMAP_INDEX = 3
LIMITE_SITEMAPS_FILHOS = 50

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; Googlebot-News; +http://www.google.com/bot.html)",
]


def obter_diagnostico_sitemap_v200():
    import copy
    try:
        return copy.deepcopy(LAST_DIAGNOSTICO_SITEMAP_V200 or {})
    except Exception:
        return dict(LAST_DIAGNOSTICO_SITEMAP_V200 or {})


def _get_url(url, timeout=20):
    ultimo_erro = None
    for ua in UAS:
        try:
            headers = {"User-Agent": ua, "Accept": "application/xml, text/xml, */*"}
            if requests is not None:
                r = requests.get(url, timeout=timeout, headers=headers)
                r.raise_for_status()
                return r.content
            from urllib.request import Request, urlopen
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            ultimo_erro = exc
            continue
    if ultimo_erro:
        raise ultimo_erro
    return b""


_RE_AMP_SOLTO = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)")
_RE_ENTIDADES_INVALIDAS = re.compile(r"&([a-zA-Z][a-zA-Z0-9]*);")
ENTIDADES_HTML_OK = {"amp", "lt", "gt", "quot", "apos"}

_MAPA_ENTIDADES = {
    "nbsp": " ", "ndash": "-", "mdash": "-",
    "hellip": "...", "lsquo": "'", "rsquo": "'",
    "ldquo": '"', "rdquo": '"', "laquo": "<<",
    "raquo": ">>", "copy": "(c)", "reg": "(R)",
    "trade": "(TM)", "deg": " graus ", "bull": "*",
    "Aacute": "Á", "aacute": "á",
    "Eacute": "É", "eacute": "é",
    "Iacute": "Í", "iacute": "í",
    "Oacute": "Ó", "oacute": "ó",
    "Uacute": "Ú", "uacute": "ú",
    "Ccedil": "Ç", "ccedil": "ç",
    "Atilde": "Ã", "atilde": "ã",
    "Otilde": "Õ", "otilde": "õ",
    "Acirc": "Â", "acirc": "â",
    "Ecirc": "Ê", "ecirc": "ê",
    "Ocirc": "Ô", "ocirc": "ô",
    "Agrave": "À", "agrave": "à",
}


def sanitizar_xml(conteudo):
    try:
        texto = conteudo.decode("utf-8", errors="ignore")
    except Exception:
        return conteudo

    def _troca(m):
        nome = m.group(1)
        if nome in ENTIDADES_HTML_OK:
            return m.group(0)
        if nome in _MAPA_ENTIDADES:
            return _MAPA_ENTIDADES[nome]
        return "&amp;" + nome + ";"

    texto = _RE_ENTIDADES_INVALIDAS.sub(_troca, texto)
    texto = _RE_AMP_SOLTO.sub("&amp;", texto)
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", texto)
    return texto.encode("utf-8")


def _parse_data_iso(valor):
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


def _titulo_por_url(url):
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    slug = re.sub(r"\.(html?|amp|aspx?|jsp)$", "", slug, flags=re.I)
    slug = re.sub(r"[-_]+", " ", slug).strip()
    slug = re.sub(r"\s+", " ", slug)
    if not slug:
        return "Noticia"
    return slug[:1].upper() + slug[1:]


def _nome_fonte_por_url(url):
    host = urlparse(url).netloc.lower().replace("www.", "")
    return host or "XML/Sitemap"


def _normalizar_chave_url(url):
    try:
        p = urlparse((url or "").strip())
        host = p.netloc.lower().replace("www.", "")
        path = re.sub(r"/+$", "", p.path or "")
        return (host + path).lower()
    except Exception:
        return (url or "").strip().lower().rstrip("/")


def _uid(url, titulo):
    chave = _normalizar_chave_url(url)
    return hashlib.sha1((chave + "|" + titulo).encode("utf-8", "ignore")).hexdigest()[:16]


RE_SLUG_NOTICIA = re.compile(r"/[a-z0-9][a-z0-9-]{18,}", re.I)
SEGS_NOTICIA = ("/noticia", "/materia", "/post/", "/artigo", "/news/", "/blog/", "/portal/", "/-/")


def _parece_url_de_noticia(url):
    if not url:
        return False
    p = urlparse(url).path.lower()
    if any(seg in p for seg in SEGS_NOTICIA):
        return True
    if p.endswith(".html") or p.endswith(".htm"):
        return True
    if RE_SLUG_NOTICIA.search(p):
        if not re.search(r"/(categoria|category|tag|page|secao|editoria)/", p):
            return True
    return False


def _root_e_sitemap_index(root):
    tag = (root.tag or "").split("}")[-1].lower()
    return tag == "sitemapindex"


def _extrair_urls_de_urlset(root):
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    itens = root.findall("sm:url", ns)
    if not itens:
        itens = root.findall(".//url")
    out = []
    for item in itens:
        loc = item.findtext("sm:loc", default="", namespaces=ns) or item.findtext("loc", default="") or ""
        lastmod = item.findtext("sm:lastmod", default="", namespaces=ns) or item.findtext("lastmod", default="") or ""
        loc = loc.strip()
        if loc:
            out.append((loc, lastmod.strip()))
    return out


def _extrair_filhos_de_sitemapindex(root):
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    itens = root.findall("sm:sitemap", ns)
    if not itens:
        itens = root.findall(".//sitemap")
    out = []
    for item in itens:
        loc = item.findtext("sm:loc", default="", namespaces=ns) or item.findtext("loc", default="") or ""
        loc = loc.strip()
        if loc:
            out.append(loc)
    return out


def coletar_sitemap_xml(url_sitemap, janela_horas=48, limite=30, fonte_nome=None, profundidade=0, aceitar_apenas_noticias=True):
    fonte_nome = fonte_nome or _nome_fonte_por_url(url_sitemap)

    conteudo = _get_url(url_sitemap)
    conteudo_seguro = sanitizar_xml(conteudo)
    try:
        root = ET.fromstring(conteudo_seguro)
    except ET.ParseError as e:
        s = conteudo_seguro.lstrip(b"\xef\xbb\xbf").decode("utf-8", errors="ignore")
        s = re.sub(r"^\s*<\?xml[^>]*\?>", "", s)
        try:
            root = ET.fromstring(s.encode("utf-8"))
        except Exception:
            raise e

    pautas = []
    vistos = set()
    agora = datetime.now(timezone.utc)

    if _root_e_sitemap_index(root):
        if profundidade >= PROFUNDIDADE_MAX_SITEMAP_INDEX:
            return []
        filhos = _extrair_filhos_de_sitemapindex(root)[:LIMITE_SITEMAPS_FILHOS]
        for sub in filhos:
            try:
                sublote = coletar_sitemap_xml(
                    sub, janela_horas=janela_horas, limite=limite,
                    fonte_nome=fonte_nome, profundidade=profundidade + 1,
                    aceitar_apenas_noticias=aceitar_apenas_noticias,
                )
                for p in sublote:
                    chave = _normalizar_chave_url(p.get("link_origem") or p.get("url") or "")
                    if chave and chave not in vistos:
                        vistos.add(chave)
                        pautas.append(p)
                        if len(pautas) >= limite:
                            return pautas
            except Exception:
                continue
        return pautas

    for loc, lastmod in _extrair_urls_de_urlset(root):
        if loc in vistos:
            continue
        if aceitar_apenas_noticias and not _parece_url_de_noticia(loc):
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
            "origem_feed": "xml_sitemap_v200",
            "origem": "XML/Sitemap: " + fonte_nome,
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


def coletar_sitemaps_configurados_v200(path="fontes_xml_sitemap_vfinal.txt"):
    global LAST_DIAGNOSTICO_SITEMAP_V200
    path = Path(path)
    LAST_DIAGNOSTICO_SITEMAP_V200 = {"arquivo_config": str(path), "sitemaps": [], "total_final": 0}
    if not path.exists():
        LAST_DIAGNOSTICO_SITEMAP_V200["erro"] = "arquivo de sitemaps nao encontrado"
        return []

    janela = int(os.getenv("URURAU_V123_SITEMAP_JANELA_HORAS", os.getenv("URURAU_V99_JANELA_PUBLICACAO_HORAS", "48")))
    limite_por_sitemap = int(os.getenv("URURAU_V123_SITEMAP_LIMITE_POR_FONTE", "30"))

    saida = []
    vistos = set()

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        url = raw.strip()
        if not url or url.startswith("#"):
            continue
        try:
            lote = coletar_sitemap_xml(url, janela_horas=janela, limite=limite_por_sitemap)
            LAST_DIAGNOSTICO_SITEMAP_V200["sitemaps"].append({"url": url, "itens": len(lote), "erro": ""})
            print("[XML/SITEMAP v200] " + url + ": " + str(len(lote)) + " pauta(s)")
            for p in lote:
                raw_chave = p.get("link_origem") or p.get("url")
                chave = _normalizar_chave_url(raw_chave)
                if chave and chave not in vistos:
                    vistos.add(chave)
                    saida.append(p)
        except Exception as exc:
            LAST_DIAGNOSTICO_SITEMAP_V200["sitemaps"].append({"url": url, "itens": 0, "erro": type(exc).__name__ + ": " + str(exc)})
            print("[XML/SITEMAP v200] falha em " + url + ": " + type(exc).__name__ + ": " + str(exc))

    LAST_DIAGNOSTICO_SITEMAP_V200["total_final"] = len(saida)
    return saida


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for url in sys.argv[1:]:
            itens = coletar_sitemap_xml(url, janela_horas=72, limite=20)
            print("--- " + url + ": " + str(len(itens)) + " item(s) ---")
            for p in itens:
                print(" -", p["titulo_origem"][:80])
                print("  ", p["link_origem"])
