# auto_perfil_fontes_v131.py
# v131.4 — Autoadequação operacional de fontes jornalísticas, com perfil genérico RSS/WP/Sitemap/HTML.
# Objetivo: transformar o diagnóstico de fonte em perfil de coleta testado,
# sem criar adaptador Python por site a cada erro.

from __future__ import annotations

import datetime as _dt
import email.utils
import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 UrurauBot/v131 AutoFonte",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml;q=0.9,application/atom+xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    "Cache-Control": "no-cache",
}
ASSET_RE = re.compile(r"\.(?:png|jpe?g|webp|gif|svg|ico|pdf|zip|mp4|mp3|css|js)(?:\?|$)", re.I)
REGIONAL_DOMAINS = {
    "nfnoticias.com.br", "campos24horas.com.br", "folha1.com.br", "j3news.com",
    "portalviu.com.br", "sfnoticias.com.br", "odebateon.com.br", "parahybano.com.br",
    "campos.rj.gov.br", "tribunanf.com.br",
}
ESPECIAL_HINTS = (".gov.br", ".jus.br", ".leg.br", ".mp.br", "alerj", "mprj", "tce", "tre-", "tjrj", "senado", "camara.leg")


def _base_dir() -> Path:
    try:
        return Path(__file__).resolve().parents[2]  # sistema/
    except Exception:
        return Path.cwd()


def perfis_path() -> Path:
    return _base_dir() / "perfis_fontes_v131.json"


def relatorios_dir() -> Path:
    p = _base_dir() / "relatorios_diagnostico_fontes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _norm_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    # v132.4: corrige URL colada duplicada, ex.:
    # https://www.tribunanf.com.br/https://www.tribunanf.com.br/
    matches = list(re.finditer(r"https?://", url, re.I))
    if len(matches) > 1:
        url = url[matches[-1].start():]
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    p = urllib.parse.urlparse(url)
    if not p.netloc:
        return ""
    return urllib.parse.urlunparse((p.scheme.lower(), p.netloc.lower(), p.path or "/", "", p.query or "", ""))


def _domain(url: str) -> str:
    p = urllib.parse.urlparse(_norm_url(url))
    host = (p.netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def _root(url: str) -> str:
    u = _norm_url(url)
    p = urllib.parse.urlparse(u)
    return f"{p.scheme}://{p.netloc}/" if p.scheme and p.netloc else ""


def _safe_name(domain: str) -> str:
    parts = [x for x in domain.split(".") if x not in {"www", "com", "br", "org", "net", "gov", "jus", "leg", "mp"}]
    return " ".join(x.capitalize() for x in parts[:2]) or domain or "Nova Fonte"


def _fetch(url: str, timeout: int = 15) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=HEADERS)
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
            enc = "utf-8"
            m = re.search(r"charset=([A-Za-z0-9_\-]+)", ctype, re.I)
            if m:
                enc = m.group(1)
            try:
                text = raw.decode(enc, errors="replace")
            except Exception:
                text = raw.decode("utf-8", errors="replace")
            return {"ok": True, "status": getattr(r, "status", 200), "url": url, "final_url": r.geturl(), "content_type": ctype, "text": text, "raw": raw, "error": "", "seconds": round(time.time() - start, 2)}
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            raw, text = b"", ""
        return {"ok": False, "status": getattr(e, "code", ""), "url": url, "final_url": getattr(e, "url", ""), "content_type": getattr(e, "headers", {}).get("Content-Type", "") if getattr(e, "headers", None) else "", "text": text, "raw": raw, "error": str(e), "seconds": round(time.time() - start, 2)}
    except Exception as e:
        return {"ok": False, "status": "", "url": url, "final_url": "", "content_type": "", "text": "", "raw": b"", "error": str(e), "seconds": round(time.time() - start, 2)}


def _strip(s: Any) -> str:
    s = "" if s is None else str(s)
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("ldquo;", "“").replace("rdquo;", "”").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


def _parse_date(s: str) -> _dt.datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    parsers = [
        lambda x: email.utils.parsedate_to_datetime(x),
        lambda x: _dt.datetime.fromisoformat(x.replace("Z", "+00:00")),
    ]
    for p in parsers:
        try:
            d = p(s)
            if d.tzinfo is not None:
                # normaliza para São Paulo quando disponível, senão tira timezone.
                if ZoneInfo:
                    d = d.astimezone(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
                else:
                    d = d.replace(tzinfo=None)
            return d
        except Exception:
            pass
    # v131.2: muitos portais regionais expõem data brasileira no HTML/listagem.
    try:
        return _parse_data_br_texto(s)
    except Exception:
        return None




def _parse_data_br_texto(s: str) -> _dt.datetime | None:
    """Extrai datas brasileiras de HTML/texto: 02/05/2026 17:54, com variações."""
    txt = html.unescape(s or "")
    patterns = [
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\s*(?:às|as|-)?\s*(\d{1,2})[:h](\d{2})\b",
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
    ]
    for pat in patterns:
        m = re.search(pat, txt, re.I)
        if not m:
            continue
        try:
            dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hora = int(m.group(4)) if len(m.groups()) >= 4 and m.group(4) else 0
            minuto = int(m.group(5)) if len(m.groups()) >= 5 and m.group(5) else 0
            return _dt.datetime(ano, mes, dia, hora, minuto)
        except Exception:
            pass
    return None


def _meta_content(doc: str, key: str) -> str:
    """Lê content de meta property/name/itemprop de forma tolerante."""
    key_re = re.escape(key)
    patterns = [
        rf'<meta\b[^>]*(?:property|name|itemprop)=["\']{key_re}["\'][^>]*content=["\']([^"\']+)["\'][^>]*>',
        rf'<meta\b[^>]*content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\']{key_re}["\'][^>]*>',
    ]
    for pat in patterns:
        m = re.search(pat, doc or "", re.I | re.S)
        if m:
            return html.unescape(m.group(1).strip())
    return ""


def _jsonld_date(doc: str) -> str:
    for m in re.finditer(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', doc or "", re.I | re.S):
        raw = html.unescape(m.group(1).strip())
        for key in ("datePublished", "dateCreated", "dateModified"):
            mm = re.search(rf'["\']{key}["\']\s*:\s*["\']([^"\']+)["\']', raw, re.I)
            if mm:
                return mm.group(1).strip()
    return ""


def _extrair_metadados_artigo_html_v131(url: str) -> dict[str, Any]:
    """Busca o artigo leve e extrai título, resumo, data e imagem por OG/JSON-LD/texto visível.
    Usado principalmente em html_listagem, onde a listagem não traz data confiável.
    """
    r = _fetch(url, timeout=12)
    out: dict[str, Any] = {"ok": bool(r.get("ok")), "status": r.get("status"), "url": url, "title": "", "description": "", "date": "", "image": "", "error": r.get("error", "")}
    if not r.get("ok"):
        return out
    doc = r.get("text") or ""
    title = _meta_content(doc, "og:title") or _meta_content(doc, "twitter:title")
    if not title:
        mt = re.search(r"<title[^>]*>(.*?)</title>", doc, re.I | re.S)
        title = _strip(mt.group(1)) if mt else ""
    desc = _meta_content(doc, "og:description") or _meta_content(doc, "description") or _meta_content(doc, "twitter:description")
    img = _meta_content(doc, "og:image") or _meta_content(doc, "og:image:secure_url") or _meta_content(doc, "twitter:image")
    date_s = (
        _meta_content(doc, "article:published_time")
        or _meta_content(doc, "article:modified_time")
        or _meta_content(doc, "datePublished")
        or _meta_content(doc, "dateModified")
        or _jsonld_date(doc)
    )
    d = _parse_date(date_s) if date_s else None
    if not d:
        # Folha1 e outros portais regionais costumam expor: 02/05/2026 17:54 - Atualizado...
        d = _parse_data_br_texto(doc[:80000])
        date_s = _formatar_br(d) if d else ""
    out.update({"title": _strip(title), "description": _strip(desc), "date": date_s, "image": _strip(img), "raw_date": date_s})
    return out


def _now_sp() -> _dt.datetime:
    if ZoneInfo:
        return _dt.datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    return _dt.datetime.now()


def _formatar_br(d: _dt.datetime | None) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y %H:%M")


def _ordenar_iso(d: _dt.datetime | None) -> str:
    return d.isoformat(timespec="seconds") if d else ""


def _dentro_janela(d: _dt.datetime | None, horas: int) -> tuple[bool, float]:
    if not d:
        return False, 999999.0
    delta = (_now_sp() - d).total_seconds() / 3600.0
    # tolera até 30 min no futuro por relógio/site
    return (-0.5 <= delta <= horas), delta


def _uid(link: str, titulo: str = "") -> str:
    base = (link or titulo or "").strip().lower()
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _same_domain(url: str, root: str) -> bool:
    d1 = _domain(url)
    d2 = _domain(root)
    return bool(d1 and d2 and (d1 == d2 or d1.endswith("." + d2) or d2.endswith("." + d1)))


def _collect_images_from_xml_block(block: str) -> str:
    m = re.search(r"<enclosure\b[^>]*url=[\"']([^\"']+)[\"']", block or "", re.I)
    if m:
        return html.unescape(m.group(1).strip())
    m = re.search(r"<media:content\b[^>]*url=[\"']([^\"']+)[\"']", block or "", re.I)
    if m:
        return html.unescape(m.group(1).strip())
    m = re.search(r"<image:url[^>]*>(.*?)</image:url>", block or "", re.I | re.S)
    if m:
        return _strip(m.group(1))
    return ""


def _xml_tag(block: str, tag: str) -> str:
    # Aceita tag com namespace textual, ex.: dc:date
    pattern = rf"<{re.escape(tag)}\b[^>]*>(.*?)</{re.escape(tag)}>"
    m = re.search(pattern, block or "", re.I | re.S)
    return _strip(m.group(1)) if m else ""


def parse_rss_xml_direto(xml_text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parser RSS/Atom de baixa dependência. Resolve casos em que feedparser falha ou retorna 0."""
    text = xml_text or ""
    out: list[dict[str, Any]] = []
    stats = {"parser": "regex_xml_direto", "rss_items": 0, "atom_entries": 0, "titulo_link": 0, "erro": ""}
    try:
        blocks = re.findall(r"<item\b.*?</item>", text, flags=re.I | re.S)
        stats["rss_items"] = len(blocks)
        for b in blocks:
            title = _xml_tag(b, "title")
            link = _xml_tag(b, "link") or _xml_tag(b, "guid")
            desc = _xml_tag(b, "description") or _xml_tag(b, "content:encoded")
            date = _xml_tag(b, "pubDate") or _xml_tag(b, "dc:date") or _xml_tag(b, "date")
            image = _collect_images_from_xml_block(b)
            if title and link:
                stats["titulo_link"] += 1
            out.append({"title": title, "link": link, "description": desc, "date": date, "image": image, "raw_date": date})
        entries = re.findall(r"<entry\b.*?</entry>", text, flags=re.I | re.S)
        stats["atom_entries"] = len(entries)
        for b in entries:
            title = _xml_tag(b, "title")
            m = re.search(r"<link\b[^>]*href=[\"']([^\"']+)[\"']", b, re.I)
            link = html.unescape(m.group(1).strip()) if m else _xml_tag(b, "link")
            desc = _xml_tag(b, "summary") or _xml_tag(b, "content")
            date = _xml_tag(b, "updated") or _xml_tag(b, "published") or _xml_tag(b, "date")
            image = _collect_images_from_xml_block(b)
            if title and link:
                stats["titulo_link"] += 1
            out.append({"title": title, "link": link, "description": desc, "date": date, "image": image, "raw_date": date})
    except Exception as e:
        stats["erro"] = str(e)
    # dedup
    seen = set(); dedup = []
    for it in out:
        key = it.get("link") or it.get("title")
        if key and key not in seen:
            seen.add(key); dedup.append(it)
    return dedup, stats


def parse_feedparser_safe(xml_text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import feedparser  # type: ignore
        fp = feedparser.parse(xml_text)
        out = []
        for e in getattr(fp, "entries", []) or []:
            title = _strip(getattr(e, "title", "") or e.get("title", ""))
            link = _strip(getattr(e, "link", "") or e.get("link", ""))
            desc = _strip(getattr(e, "summary", "") or e.get("summary", "") or e.get("description", ""))
            date = _strip(e.get("published", "") or e.get("updated", "") or e.get("created", ""))
            image = ""
            try:
                if e.get("enclosures"):
                    image = e.get("enclosures")[0].get("href") or e.get("enclosures")[0].get("url") or ""
            except Exception:
                pass
            out.append({"title": title, "link": link, "description": desc, "date": date, "image": image, "raw_date": date})
        return out, {"parser": "feedparser", "entries": len(out), "bozo": bool(getattr(fp, "bozo", False)), "erro": str(getattr(fp, "bozo_exception", "") or "")}
    except Exception as e:
        return [], {"parser": "feedparser", "entries": 0, "erro": str(e)}


def _parse_sitemap_locs_xml(text: str) -> list[str]:
    """Extrai URLs de sitemap XML, inclusive quando há namespace."""
    urls: list[str] = []
    if not text:
        return urls
    try:
        root = ET.fromstring(text.encode("utf-8", errors="ignore"))
        for el in root.iter():
            tag = el.tag.split("}")[-1].lower() if isinstance(el.tag, str) else ""
            if tag == "loc" and el.text:
                u = _strip(el.text)
                if u and not ASSET_RE.search(u):
                    urls.append(u)
    except Exception:
        for m in re.finditer(r"<loc[^>]*>(.*?)</loc>", text, re.I | re.S):
            u = _strip(m.group(1))
            if u and not ASSET_RE.search(u):
                urls.append(u)
    seen = set(); out = []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out


def _looks_like_news_url_v131(url: str) -> bool:
    low = (url or "").lower()
    if ASSET_RE.search(low):
        return False
    return any(x in low for x in [
        "/noticia", "/noticias", "noticia-", "/202", "/politica/", "/geral/", "/policia/",
        "/regiao/", "/esporte/", "/economia/", "/cultura", "/blogs/", ".html"
    ])


def _classificar_grupo(root: str, nome: str = "", explicit: str = "") -> str:
    if explicit:
        e = explicit.strip().lower()
        if e.startswith("reg"):
            return "Regionais"
        if e.startswith("esp"):
            return "Especiais"
        if e == "rss":
            return "RSS"
    d = _domain(root)
    low = (d + " " + (nome or "")).lower()
    if d in REGIONAL_DOMAINS or any(x in low for x in ["campos", "norte fluminense", "nfnoticias", "folha1", "j3 news", "portal viu", "sf notícias", "sf noticias", "parahybano", "o debate", "tribunanf", "tribuna nf"]):
        return "Regionais"
    if any(h in low for h in ESPECIAL_HINTS):
        return "Especiais"
    return "RSS"




def _feed_prioridade_v1325(url: str) -> tuple[int, int, str]:
    """Ordena feeds conforme o relatório original do Diagnóstico Jornalístico.

    A ferramenta externa recomenda RSS /portal/feed/ como principal quando ele existe,
    depois /portal/rss/, depois raiz /feed/ e /rss/. Essa ordem evita aplicar o link
    visualmente e depois cair no parser regional genérico errado.
    """
    u = _norm_url(url).lower()
    if "/portal/feed/" in u:
        return (0, len(u), u)
    if "/portal/rss/" in u:
        return (1, len(u), u)
    if u.endswith("/feed/"):
        return (2, len(u), u)
    if u.endswith("/rss/"):
        return (3, len(u), u)
    if "/categoria/" in u and u.endswith("/feed/"):
        return (4, len(u), u)
    return (9, len(u), u)


def _ordenar_feeds_v1325(feeds: list[str]) -> list[str]:
    seen: set[str] = set()
    norm: list[str] = []
    for f in feeds or []:
        u = _norm_url(f)
        if u and u not in seen:
            seen.add(u); norm.append(u)
    return sorted(norm, key=_feed_prioridade_v1325)


def _feeds_fallback_root_v1325(root: str, atual: str = "") -> list[str]:
    root = _root(root or atual) or _root(atual)
    out: list[str] = []
    def add(u: str):
        u = _norm_url(u)
        if u and u not in out:
            out.append(u)
    # URL informada pelo usuário entra, mas a ordem final prioriza /portal/ se existir.
    if atual:
        add(atual)
    if root:
        add(urllib.parse.urljoin(root, "/portal/feed/"))
        add(urllib.parse.urljoin(root, "/portal/rss/"))
        add(urllib.parse.urljoin(root, "/feed/"))
        add(urllib.parse.urljoin(root, "/rss/"))
    return _ordenar_feeds_v1325(out)


def _diagnostico_prova_funcional_v1325(results: dict[str, Any]) -> bool:
    """Retorna True quando o relatório original já provou que a fonte é coletável.

    Isso corrige o erro observado no Tribuna NF: o diagnóstico completo provou RSS válido
    e itens com título/link/data, mas a aplicação não deixou a fonte operacional quando
    o teste interno não fechou o ciclo. O relatório passa a ser fonte de verdade técnica.
    """
    tests = results.get("tests") or {}
    for sec in ("rss_portal", "rss_root", "rss_categorias"):
        for r in (tests.get(sec) or {}).get("results") or []:
            fu = r.get("feed_util") or {}
            if int(fu.get("itens") or fu.get("entries") or 0) > 0:
                return True
            if int(fu.get("com_titulo_link") or fu.get("titulo_link") or 0) > 0:
                return True
            if r.get("valid") and r.get("ok"):
                return True
    for r in (tests.get("wp_api") or {}).get("results") or []:
        if r.get("has_posts") or int(r.get("posts_count") or 0) > 0:
            return True
    for r in (tests.get("html_listagem") or {}).get("results") or []:
        if r.get("ok") and int(r.get("articles_found") or 0) > 0:
            return True
    return False



def _enriquecer_solucao_do_diagnostico_v1314(results: dict[str, Any]) -> dict[str, Any]:
    """Converte o relatório de diagnóstico em uma solução operacional completa.

    A regra é deliberadamente defensiva: usa a recomendação declarada em ``solucao``
    quando existir, mas também lê os testes brutos do diagnóstico para não perder
    endpoints úteis. Assim, o operador cola um link, roda o diagnóstico e o sistema
    tenta montar automaticamente um perfil funcional, sem depender de adaptação manual
    por domínio.
    """
    sol_in = results.get("solucao") or {}
    tests = results.get("tests") or {}
    root = results.get("root") or ""
    sol: dict[str, Any] = dict(sol_in)

    feeds = list(sol.get("feeds") or [])
    sitemaps = list(sol.get("sitemaps") or [])
    html_fb = list(sol.get("html_fallback") or [])
    wp_api = sol.get("wp_api") or ""

    def add_unique(lst: list[str], url: str) -> None:
        u = _norm_url(url)
        if u and u not in lst:
            lst.append(u)

    # RSS/Atom úteis detectados pelo relatório, mesmo quando a recomendação não os carregou.
    for sec in ("rss_root", "rss_portal", "rss_categorias"):
        for r in (tests.get(sec) or {}).get("results") or []:
            fu = r.get("feed_util") or {}
            if r.get("valid") or (fu.get("itens") or fu.get("entries") or 0) or (fu.get("titulo_link") or 0):
                add_unique(feeds, r.get("url") or "")

    # WP API: só usa se o diagnóstico indicar JSON real com posts.
    for r in (tests.get("wp_api") or {}).get("results") or []:
        if (r.get("has_posts") or r.get("posts_count", 0) > 0) and r.get("url"):
            wp_api = wp_api or r.get("url")
            break

    # Sitemap válido.
    for r in (tests.get("sitemap") or {}).get("results") or []:
        if r.get("valid") or r.get("urls_count", 0) > 0:
            add_unique(sitemaps, r.get("url") or "")

    # HTML de listagem com artigos encontrados. Mantém no máximo 5 para evitar peso.
    html_results = (tests.get("html_listagem") or {}).get("results") or []
    for r in html_results:
        if r.get("ok") and r.get("is_html") and int(r.get("articles_found") or 0) > 0:
            add_unique(html_fb, r.get("url") or "")
            if len(html_fb) >= 5:
                break
    if not html_fb and root:
        add_unique(html_fb, root)

    # Decide estratégia principal pela ordem de menor custo/maior estrutura.
    estrategia = sol.get("estrategia_principal") or "auto_universal"
    if feeds:
        estrategia = "rss_cascata"
    elif wp_api:
        estrategia = "wp_api"
    elif sitemaps:
        estrategia = "sitemap"
    elif html_fb:
        estrategia = "html_listagem"

    feeds = _ordenar_feeds_v1325(feeds)

    sol.update({
        "estrategia_principal": estrategia,
        "feeds": feeds,
        "sitemaps": sitemaps,
        "wp_api": wp_api,
        "html_fallback": html_fb,
        "playwright": bool(sol.get("playwright") or ((tests.get("playwright") or {}).get("needs_playwright"))),
        "_v1314_enriquecida": True,
    })
    return sol


def _sucesso_tecnico_v1314(stats: dict[str, Any]) -> bool:
    """True quando a fonte é tecnicamente coletável, ainda que não tenha notícia na janela."""
    if int(stats.get("aceitas") or 0) > 0:
        return True
    if int(stats.get("titulo_link") or 0) > 0:
        return True
    for t in stats.get("tentativas") or []:
        try:
            if int(t.get("itens") or 0) > 0:
                return True
        except Exception:
            pass
    return False

def gerar_perfil_v131(results: dict[str, Any], nome_preferido: str = "", grupo_preferido: str = "") -> dict[str, Any]:
    sol = _enriquecer_solucao_do_diagnostico_v1314(results)
    root = results.get("root") or ""
    dominio = _domain(root)
    nome = (nome_preferido or "").strip() or (results.get("name") or "").strip() or _safe_name(dominio)
    if dominio == "folha1.com.br" and re.sub(r"\W+", "", nome.lower()) in {"folhadaamanha", "folhadamanha", "folha1", "folha1combr"}:
        nome = "Folha da Manhã"
    feeds = [u for u in (sol.get("feeds") or []) if u]
    sitemaps = [u for u in (sol.get("sitemaps") or []) if u]
    html_fb = [u for u in (sol.get("html_fallback") or []) if u]
    wp_api = sol.get("wp_api") or ""

    # Detecta parser operacional. Se o diagnóstico viu item/título/link em RSS, usa cascata.
    estrategia = sol.get("estrategia_principal") or "manual"
    parser = "auto_universal_cascata"
    if feeds:
        parser = "rss_cascata"  # feedparser -> XML direto -> WP/Sitemap/HTML se RSS não render
    elif wp_api:
        parser = "wp_api"
    elif sitemaps:
        parser = "sitemap"
    elif html_fb:
        parser = "html_listagem"

    pid = hashlib.sha1((dominio + "|" + (feeds[0] if feeds else root)).encode("utf-8", errors="ignore")).hexdigest()[:12]
    grupo = _classificar_grupo(root, nome, grupo_preferido)
    return {
        "id": pid,
        "versao": "v132.5",
        "nome": nome,
        "dominio": dominio,
        "root": root,
        "ativo": True,
        "grupo": grupo,
        "estrategia": estrategia,
        "parser": parser,
        "feeds": feeds,
        "wp_api": wp_api,
        "sitemaps": sitemaps,
        "html_fallback": html_fb,
        "playwright": bool(sol.get("playwright")),
        "janela_horas": int(os.getenv("URURAU_V131_JANELA_HORAS", "24") or "24"),
        "max_itens": int(os.getenv("URURAU_V131_MAX_ITENS_FONTE", "10") or "10"),
        "bypass_score": grupo in {"Regionais", "Especiais"},
        "regional_prioritaria": grupo == "Regionais",
        "cota_minima": 2 if grupo == "Regionais" else 0,
        "criado_em": _dt.datetime.now().isoformat(timespec="seconds"),
        "diagnostico_resumo": results.get("summary") or {},
        "autoadequacao_v1314": True,
        "autoadequacao_v1325": True,
        "aplicar_so_com_teste_ok": True,
        "origem_perfil": "diagnostico_de_fonte",
        "modo": "autoadequador_universal_v1325",
        "estrategias_ativas": {
            "rss": bool(feeds),
            "wp_api": bool(wp_api),
            "sitemap": bool(sitemaps),
            "html": bool(html_fb),
            "playwright": bool(sol.get("playwright")),
        },
        "solucao_enriquecida_v1314": bool(sol.get("_v1314_enriquecida")),
    }


def _pauta_from_item(item: dict[str, Any], perfil: dict[str, Any], feed_url: str, idx: int) -> dict[str, Any] | None:
    title = _strip(item.get("title"))
    link = _strip(item.get("link"))
    if not title or not link or ASSET_RE.search(link):
        return None
    root = perfil.get("root") or feed_url
    if root and not _same_domain(link, root):
        # Aceita variação www/não-www, subdomínio do mesmo portal; bloqueia agregadores/assets.
        return None
    desc = _strip(item.get("description"))
    d = _parse_date(item.get("date") or item.get("raw_date") or "")
    data_br = _formatar_br(d)
    prio = 1
    if d:
        ok, idade = _dentro_janela(d, int(perfil.get("janela_horas") or 24))
        if not ok:
            return None
        prio = 3 if idade <= 1 else 2 if idade <= 2 else 1
    else:
        # Em fonte regional/oficial, se não vier data mas vier de feed válido, não derruba na transformação;
        # o funil posterior pode segurar se necessário.
        data_br = ""
    nome = perfil.get("nome") or _safe_name(perfil.get("dominio") or "")
    pauta = {
        "titulo_origem": title,
        "titulo": title,
        "link_origem": link,
        "link": link,
        "url": link,
        "fonte_nome": nome,
        "fonte": nome,
        "nome_fonte": nome,
        "resumo_origem": desc[:900],
        "canal_forcado": "",
        "data_pub_fonte": data_br,
        "data_pub_fonte_br": data_br,
        "data_pub_fonte_original": _strip(item.get("raw_date") or item.get("date")),
        "data_pub_metodo_v99": f"auto_perfil_v131:{perfil.get('parser')}",
        "_data_pub_ordem": _ordenar_iso(d),
        "uid": _uid(link, title),
        "_uid": _uid(link, title),
        "prioridade": prio,
        "tipo_fonte": f"auto_v131_{str(perfil.get('grupo') or 'rss').lower()}",
        "origem": f"AutoPerfil v131: {nome}",
        "origem_feed": feed_url,
        "diagnostico_v131": True,
        "perfil_v131_id": perfil.get("id"),
        "_v131_motivo": "Fonte autoadequada por diagnóstico: perfil testado antes de salvar.",
    }
    if perfil.get("bypass_score"):
        pauta["bypass_score"] = True
    if perfil.get("regional_prioritaria"):
        pauta["regional_prioritaria"] = True
        pauta["_v1304_rss_regional_prioritario"] = True
    img = _strip(item.get("image"))
    if img:
        pauta["imagem_url"] = img
        pauta["imagem_url_rss"] = img
        pauta.setdefault("imagem_credito", "Reprodução")
        pauta["imagem_status"] = "url_pendente"
    try:
        from ururau.editorial.classificador_editorial_contextual_v117 import aplicar_editoria_contextual
        pauta = aplicar_editoria_contextual(pauta)
    except Exception:
        pass
    return pauta


def coletar_por_perfil_v131(perfil: dict[str, Any], max_itens: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    max_itens = max_itens or int(perfil.get("max_itens") or 10)
    stats: dict[str, Any] = {
        "perfil_id": perfil.get("id"), "nome": perfil.get("nome"), "grupo": perfil.get("grupo"),
        "parser": perfil.get("parser"), "tentativas": [], "brutas": 0, "titulo_link": 0,
        "aceitas": 0, "fora_janela": 0, "sem_titulo_link": 0, "erro": "",
        "sucesso_tecnico": False, "status_operacional": "nao_testado",
    }
    pautas: list[dict[str, Any]] = []

    # 1. RSS/Atom com cascata: feedparser -> XML direto. Aposta principal para 80% dos portais.
    for feed_url in perfil.get("feeds") or []:
        r = _fetch(feed_url)
        tentativa = {"url": feed_url, "status": r.get("status"), "content_type": r.get("content_type"), "ok": r.get("ok"), "parser_usado": "", "itens": 0, "aceitas": 0, "erro": r.get("error", "")}
        if not r.get("ok"):
            stats["tentativas"].append(tentativa); continue
        items_fp, st_fp = parse_feedparser_safe(r.get("text") or "")
        items_xml, st_xml = parse_rss_xml_direto(r.get("text") or "")
        # Escolhe o parser com mais título/link, não o primeiro que retornou algo.
        def score_items(items: list[dict[str, Any]]) -> int:
            return sum(1 for x in items if _strip(x.get("title")) and _strip(x.get("link")))
        if score_items(items_xml) > score_items(items_fp):
            items, pst = items_xml, st_xml
        else:
            items, pst = items_fp, st_fp
        tentativa["parser_usado"] = pst.get("parser")
        tentativa["itens"] = len(items)
        stats["brutas"] += len(items)
        for i, it in enumerate(items):
            if not (_strip(it.get("title")) and _strip(it.get("link"))):
                stats["sem_titulo_link"] += 1
                continue
            stats["titulo_link"] += 1
            p = _pauta_from_item(it, perfil, feed_url, i)
            if p is None:
                # Se foi por data fora da janela, conta de forma aproximada.
                d = _parse_date(it.get("date") or it.get("raw_date") or "")
                ok, _idade = _dentro_janela(d, int(perfil.get("janela_horas") or 24)) if d else (True, 0)
                if d and not ok:
                    stats["fora_janela"] += 1
                continue
            pautas.append(p)
            tentativa["aceitas"] += 1
            if len(pautas) >= max_itens:
                break
        stats["tentativas"].append(tentativa)
        if len(pautas) >= max_itens:
            break
        # Se algum RSS rendeu pautas, não precisa insistir em fallback pesado.
        if pautas:
            break

    # 2. WP API, quando RSS não rendeu.
    if not pautas and perfil.get("wp_api"):
        url = perfil.get("wp_api")
        r = _fetch(url)
        tentativa = {"url": url, "status": r.get("status"), "content_type": r.get("content_type"), "ok": r.get("ok"), "parser_usado": "wp_api", "itens": 0, "aceitas": 0, "erro": r.get("error", "")}
        if r.get("ok"):
            try:
                data = json.loads(r.get("text") or "[]")
                posts = data if isinstance(data, list) else []
                tentativa["itens"] = len(posts); stats["brutas"] += len(posts)
                for i, post in enumerate(posts):
                    title_raw = post.get("title", {}).get("rendered") if isinstance(post.get("title"), dict) else post.get("title")
                    desc_raw = post.get("excerpt", {}).get("rendered") if isinstance(post.get("excerpt"), dict) else post.get("excerpt")
                    item = {"title": title_raw, "link": post.get("link"), "description": desc_raw, "date": post.get("date_gmt") or post.get("date"), "raw_date": post.get("date_gmt") or post.get("date")}
                    if _strip(item.get("title")) and _strip(item.get("link")):
                        stats["titulo_link"] += 1
                    p = _pauta_from_item(item, perfil, url, i)
                    if p:
                        pautas.append(p); tentativa["aceitas"] += 1
                        if len(pautas) >= max_itens: break
            except Exception as e:
                tentativa["erro"] = str(e)
        stats["tentativas"].append(tentativa)

    # 3. Sitemap, quando RSS/WP não renderam. Usa URLs de notícia e valida metadados no artigo.
    if not pautas and perfil.get("sitemaps"):
        for sm_url in perfil.get("sitemaps") or []:
            r = _fetch(sm_url)
            tentativa = {"url": sm_url, "status": r.get("status"), "content_type": r.get("content_type"), "ok": r.get("ok"), "parser_usado": "sitemap_html_meta", "itens": 0, "aceitas": 0, "erro": r.get("error", "")}
            if not r.get("ok"):
                stats["tentativas"].append(tentativa); continue
            urls = [u for u in _parse_sitemap_locs_xml(r.get("text") or "") if _same_domain(u, perfil.get("root") or sm_url) and _looks_like_news_url_v131(u)]
            tentativa["itens"] = len(urls); stats["brutas"] += len(urls)
            for i, u in enumerate(urls[: max(max_itens * 4, 20)]):
                meta = _extrair_metadados_artigo_html_v131(u)
                item = {
                    "title": meta.get("title") or u.rstrip("/").split("/")[-1].replace("-", " ").title(),
                    "link": u,
                    "description": meta.get("description") or "",
                    "date": meta.get("date") or "",
                    "raw_date": meta.get("raw_date") or meta.get("date") or "",
                    "image": meta.get("image") or "",
                }
                if _strip(item.get("title")) and _strip(item.get("link")):
                    stats["titulo_link"] += 1
                p = _pauta_from_item(item, perfil, sm_url, i)
                if p:
                    p["_v1314_sitemap_meta"] = True
                    pautas.append(p); tentativa["aceitas"] += 1
                    if len(pautas) >= max_itens: break
                else:
                    d = _parse_date(item.get("date") or item.get("raw_date") or "")
                    ok, _idade = _dentro_janela(d, int(perfil.get("janela_horas") or 24)) if d else (True, 0)
                    if d and not ok:
                        stats["fora_janela"] += 1
            stats["tentativas"].append(tentativa)
            if pautas:
                break

    # 4. HTML listagem leve, quando RSS/WP/Sitemap não renderam. Abre artigo para data real.
    if not pautas and perfil.get("html_fallback"):
        for url in perfil.get("html_fallback") or []:
            r = _fetch(url)
            tentativa = {"url": url, "status": r.get("status"), "content_type": r.get("content_type"), "ok": r.get("ok"), "parser_usado": "html_listagem", "itens": 0, "aceitas": 0, "erro": r.get("error", "")}
            if not r.get("ok"):
                stats["tentativas"].append(tentativa); continue
            links = []
            for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r.get("text") or "", re.I | re.S):
                href = urllib.parse.urljoin(url, html.unescape(m.group(1).strip()))
                if ASSET_RE.search(href) or not _same_domain(href, perfil.get("root") or url):
                    continue
                low = href.lower()
                if not any(x in low for x in ["/noticia", "/noticias", "/202", "noticia-"]):
                    continue
                title = _strip(m.group(2))
                if len(title) < 8:
                    title = href.rstrip("/").split("/")[-1].replace("-", " ").title()
                links.append({"title": title, "link": href, "description": "", "date": "", "raw_date": ""})
            # dedup
            seen = set(); items = []
            for it in links:
                if it["link"] not in seen:
                    seen.add(it["link"]); items.append(it)
            tentativa["itens"] = len(items); stats["brutas"] += len(items)
            for i, it in enumerate(items):
                # v131.2: em HTML listagem, buscar metadados do artigo para não derrubar notícia recente por falta de data.
                meta = _extrair_metadados_artigo_html_v131(it.get("link") or "")
                if meta.get("title"):
                    it["title"] = meta.get("title")
                if meta.get("description"):
                    it["description"] = meta.get("description")
                if meta.get("date"):
                    it["date"] = meta.get("date")
                    it["raw_date"] = meta.get("raw_date") or meta.get("date")
                if meta.get("image"):
                    it["image"] = meta.get("image")
                if _strip(it.get("title")) and _strip(it.get("link")):
                    stats["titulo_link"] += 1
                p = _pauta_from_item(it, perfil, url, i)
                if p:
                    p["_v1312_html_data_extraida"] = bool(meta.get("date"))
                    p["_v1312_html_meta_status"] = meta.get("status")
                    pautas.append(p); tentativa["aceitas"] += 1
                    if len(pautas) >= max_itens: break
                else:
                    d = _parse_date(it.get("date") or it.get("raw_date") or "") or _parse_data_br_texto(str(it.get("date") or it.get("raw_date") or ""))
                    ok, _idade = _dentro_janela(d, int(perfil.get("janela_horas") or 24)) if d else (True, 0)
                    if d and not ok:
                        stats["fora_janela"] += 1
            tentativa["datas_extraidas_html"] = sum(1 for p in pautas if p.get("_v1312_html_data_extraida"))
            stats["tentativas"].append(tentativa)
            if pautas:
                break

    # dedup final
    seen = set(); final = []
    for p in pautas:
        k = p.get("url") or p.get("titulo")
        if k and k not in seen:
            seen.add(k); final.append(p)
    stats["aceitas"] = len(final)
    stats["sucesso_tecnico"] = _sucesso_tecnico_v1314(stats)
    if final:
        stats["primeira_enviavel"] = final[0].get("titulo")
        stats["status_operacional"] = "funcional_com_pauta_na_janela"
    elif stats.get("sucesso_tecnico"):
        stats["status_operacional"] = "funcional_sem_pauta_na_janela"
    else:
        stats["status_operacional"] = "falhou_sem_itens"
    return final[:max_itens], stats


def testar_perfil_v131(perfil: dict[str, Any]) -> dict[str, Any]:
    lote, stats = coletar_por_perfil_v131(perfil, max_itens=min(int(perfil.get("max_itens") or 10), 5))
    sucesso_tecnico = bool(stats.get("sucesso_tecnico"))
    return {
        "ok": bool(lote),
        "sucesso_tecnico": sucesso_tecnico,
        "status_operacional": stats.get("status_operacional"),
        "qtd": len(lote),
        "primeira": lote[0].get("titulo") if lote else "",
        "stats": stats,
    }


def carregar_perfis_v131() -> list[dict[str, Any]]:
    p = perfis_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return []


def salvar_perfil_v131(perfil: dict[str, Any]) -> dict[str, Any]:
    p = perfis_path()
    perfis = carregar_perfis_v131()
    pid = perfil.get("id")
    dom = perfil.get("dominio")
    replaced = False
    for i, old in enumerate(perfis):
        if (pid and old.get("id") == pid) or (dom and old.get("dominio") == dom):
            perfil["atualizado_em"] = _dt.datetime.now().isoformat(timespec="seconds")
            perfis[i] = perfil
            replaced = True
            break
    if not replaced:
        perfis.append(perfil)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        bdir = p.parent / "backups_v131"; bdir.mkdir(exist_ok=True)
        try:
            import shutil
            shutil.copy2(p, bdir / f"{p.name}.bak_{time.strftime('%Y%m%d_%H%M%S')}")
        except Exception:
            pass
    p.write_text(json.dumps(perfis, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arquivo": str(p), "substituido": replaced, "total": len(perfis)}


def perfil_ativo_para_url_v131(url: str) -> bool:
    d = _domain(url)
    if not d:
        return False
    for p in carregar_perfis_v131():
        if p.get("ativo", True) and p.get("dominio") == d:
            return True
    return False


def coletar_todos_perfis_v131(grupos: set[str] | None = None) -> list[tuple[dict[str, Any], list[dict], dict[str, Any]]]:
    out = []
    perfis = [p for p in carregar_perfis_v131() if p.get("ativo", True)]
    perfis.sort(key=lambda p: (0 if (p.get("diagnostico_prioridade_proxima_coleta") or p.get("origem_perfil") == "diagnostico_de_fonte") else 1, str(p.get("nome") or p.get("dominio") or "").lower()))
    for perfil in perfis:
        if grupos and perfil.get("grupo") not in grupos:
            continue
        max_itens = int(perfil.get("forcar_proxima_coleta_qtd") or perfil.get("max_itens") or 10)
        lote, stats = coletar_por_perfil_v131(perfil, max_itens=max_itens)
        out.append((perfil, lote, stats))
    return out


def aplicar_diagnostico_operacional_v131(results: dict[str, Any], nome_preferido: str = "", grupo_preferido: str = "") -> dict[str, Any]:
    perfil = gerar_perfil_v131(results, nome_preferido=nome_preferido, grupo_preferido=grupo_preferido)
    teste = testar_perfil_v131(perfil)
    info = {"perfil": perfil, "teste": teste, "salvo": {}, "aplicado": False, "avisos": []}
    prova_relatorio = _diagnostico_prova_funcional_v1325(results)

    if not teste.get("ok") and not teste.get("sucesso_tecnico") and not prova_relatorio:
        info["avisos"].append("Perfil NÃO salvo como operacional: o teste imediato não gerou pauta e o relatório não comprovou caminho coletável.")
        return info

    if teste.get("ok"):
        perfil["status_operacional"] = "funcional_com_pauta_na_janela"
    elif teste.get("sucesso_tecnico"):
        info["avisos"].append("Perfil salvo como tecnicamente funcional, mas sem pauta dentro da janela neste teste. Será monitorado nas próximas coletas.")
        perfil["status_operacional"] = "funcional_sem_pauta_na_janela"
    elif prova_relatorio:
        info["avisos"].append("Perfil salvo porque o relatório completo comprovou caminho funcional, embora o teste imediato interno não tenha gerado pauta. A coleta geral usará AutoFontes v132.5 e não o regional genérico.")
        perfil["status_operacional"] = "funcional_por_relatorio_diagnostico"
        perfil["aplicado_por_prova_do_relatorio_v1325"] = True

    limite_diag = int(os.getenv("URURAU_V47_DIAG_MAX_ITENS_PROXIMA_COLETA", "10") or "10")
    perfil["max_itens"] = max(1, min(10, limite_diag))
    perfil["forcar_proxima_coleta_qtd"] = max(1, min(10, limite_diag))
    perfil["diagnostico_prioridade_proxima_coleta"] = True
    perfil["origem_perfil"] = "diagnostico_de_fonte"
    perfil["aplicar_na_proxima_coleta_v47_4"] = True
    perfil["observacao_operacional_v47_4"] = "Fonte aplicada pelo Diagnóstico: próxima coleta deve priorizar este domínio e tentar trazer até 10 matérias."
    info["salvo"] = salvar_perfil_v131(perfil)
    info["aplicado"] = True
    info.setdefault("avisos", []).append(f"Fonte aplicada: próxima coleta prioriza este domínio e tenta trazer até {perfil['max_itens']} matérias.")
    return info



def perfil_minimo_por_url_v1325(url: str, nome: str = "", grupo: str = "Regionais") -> dict[str, Any]:
    """Cria perfil temporário a partir de uma URL salva em Fontes/Links.

    Usado como rede de segurança: se a fonte entrou na aba, mas por algum motivo o
    perfil persistido não foi localizado, a coleta ainda usa a mesma lógica universal
    em cascata do Diagnóstico de Fonte, em vez de cair no parser regional_v1305.
    """
    url = _norm_url(url)
    root = _root(url)
    dominio = _domain(url)
    feeds = _feeds_fallback_root_v1325(root, url)
    return {
        "id": hashlib.sha1((dominio + "|" + url).encode("utf-8", errors="ignore")).hexdigest()[:12],
        "versao": "v132.5-temp",
        "nome": nome or _safe_name(dominio),
        "dominio": dominio,
        "root": root,
        "ativo": True,
        "grupo": _classificar_grupo(root, nome, grupo),
        "estrategia": "rss_cascata",
        "parser": "rss_cascata",
        "feeds": feeds,
        "wp_api": urllib.parse.urljoin(root, "/wp-json/wp/v2/posts?per_page=10") if root else "",
        "sitemaps": [urllib.parse.urljoin(root, x) for x in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/post-sitemap.xml") if root],
        "html_fallback": [urllib.parse.urljoin(root, x) for x in ("/", "/portal/", "/noticias/", "/noticia/", "/politica/", "/policia/", "/regiao/", "/geral/") if root],
        "playwright": False,
        "janela_horas": int(os.getenv("URURAU_V131_JANELA_HORAS", "24") or "24"),
        "max_itens": int(os.getenv("URURAU_V131_MAX_ITENS_FONTE", "10") or "10"),
        "bypass_score": grupo == "Regionais",
        "regional_prioritaria": grupo == "Regionais",
        "cota_minima": 2 if grupo == "Regionais" else 0,
        "origem_perfil": "fallback_aba_fontes_links_v1325",
        "modo": "autoadequador_universal_v1325_temp",
    }


def coletar_url_auto_v1325(url: str, nome: str = "", grupo: str = "Regionais", max_itens: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    perfil = perfil_minimo_por_url_v1325(url, nome=nome, grupo=grupo)
    lote, stats = coletar_por_perfil_v131(perfil, max_itens=max_itens)
    stats["fallback_aba_fontes_links_v1325"] = True
    stats["feeds_testados_v1325"] = perfil.get("feeds")
    return lote, stats, perfil


def formatar_relatorio_v131(info: dict[str, Any]) -> str:
    perfil = info.get("perfil") or {}
    teste = info.get("teste") or {}
    stats = teste.get("stats") or {}
    linhas = []
    linhas.append("AUTOADEQUAÇÃO OPERACIONAL DE FONTE v132.5")
    linhas.append("=" * 72)
    linhas.append(f"Fonte: {perfil.get('nome')} | domínio: {perfil.get('dominio')}")
    linhas.append(f"Grupo/aba: {perfil.get('grupo')} | estratégia: {perfil.get('estrategia')} | parser: {perfil.get('parser')}")
    linhas.append("Regra: o perfil só é salvo se o teste operacional gerar pauta real; se um parser falhar, a cascata tenta RSS XML direto, WP API, sitemap e HTML.")
    linhas.append(f"Teste imediato: {'OK COM PAUTA' if teste.get('ok') else ('OK TÉCNICO, SEM PAUTA NA JANELA' if teste.get('sucesso_tecnico') else 'FALHOU')} | pautas testadas: {teste.get('qtd', 0)}")
    if teste.get("primeira"):
        linhas.append(f"Primeira pauta: {teste.get('primeira')}")
    linhas.append(f"Brutas: {stats.get('brutas', 0)} | título+link: {stats.get('titulo_link', 0)} | aceitas: {stats.get('aceitas', 0)} | fora_janela: {stats.get('fora_janela', 0)}")
    for t in stats.get("tentativas") or []:
        linhas.append(f"  - {t.get('parser_usado') or '-'} | {t.get('url')} | status={t.get('status')} | itens={t.get('itens')} | aceitas={t.get('aceitas')} | erro={t.get('erro') or '-'}")
    if info.get("aplicado"):
        linhas.append(f"Perfil salvo em: {(info.get('salvo') or {}).get('arquivo')}")
        linhas.append("Status: será usado automaticamente na próxima coleta geral pela fase AutoFontes v132.5.")
    if info.get("avisos"):
        linhas.append("Avisos:")
        for a in info.get("avisos"):
            linhas.append(f"  - {a}")
    return "\n".join(linhas)
