# diagnostico_fontes_v130.py
# Motor interno de diagnóstico de fontes jornalísticas para o Ururau.
# Integra a lógica do diagnostico_jornal_gui.py ao projeto sem abrir GUI externa.

from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

REQUEST_TIMEOUT = 12
HEADERS = {
    "User-Agent": "Mozilla/5.0 UrurauBot/1.0 (+https://www.ururau.com.br)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml;q=0.9,application/atom+xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}

ASSET_EXT_RE = re.compile(r"\.(?:png|jpe?g|webp|gif|svg|ico|pdf|zip|mp4|mp3|css|js)(?:\?|$)", re.I)


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    # v132.4: corrige colagens duplicadas, ex.:
    # https://site.com/https://site.com/ -> https://site.com/
    matches = list(re.finditer(r"https?://", url, flags=re.I))
    if len(matches) > 1:
        url = url[matches[-1].start():]
    if not re.match(r"^https?://", url, flags=re.I):
        url = "https://" + url
    p = urllib.parse.urlparse(url)
    if not p.netloc:
        return ""
    path = p.path or "/"
    if not path.endswith("/") and "." not in Path(path).name:
        path += "/"
    return urllib.parse.urlunparse((p.scheme, p.netloc, path, "", "", ""))


def site_root(url: str) -> str:
    p = urllib.parse.urlparse(normalize_url(url))
    return f"{p.scheme}://{p.netloc}/" if p.scheme and p.netloc else ""


def domain_key(url: str) -> str:
    p = urllib.parse.urlparse(normalize_url(url))
    host = (p.netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def join_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, href)


def decode_body(data: bytes, content_type: str) -> str:
    encs: list[str] = []
    m = re.search(r"charset=([A-Za-z0-9_\-]+)", content_type or "", flags=re.I)
    if m:
        encs.append(m.group(1))
    encs += ["utf-8", "iso-8859-1", "latin-1"]
    for enc in encs:
        try:
            return data.decode(enc, errors="replace")
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def fetch(url: str, timeout: int = REQUEST_TIMEOUT) -> dict[str, Any]:
    start = time.time()
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            return {
                "ok": True,
                "url": url,
                "final_url": resp.geturl(),
                "status": getattr(resp, "status", 200),
                "content_type": content_type,
                "content": decode_body(raw, content_type),
                "error": "",
                "seconds": round(time.time() - start, 2),
                "raw": raw,
            }
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
            ctype = e.headers.get("Content-Type", "") if e.headers else ""
            content = decode_body(raw, ctype)
        except Exception:
            ctype, content = "", ""
        return {
            "ok": False,
            "url": url,
            "final_url": getattr(e, "url", ""),
            "status": getattr(e, "code", ""),
            "content_type": ctype,
            "content": content,
            "error": str(e),
            "seconds": round(time.time() - start, 2),
            "raw": b"",
        }
    except Exception as e:
        return {
            "ok": False,
            "url": url,
            "final_url": "",
            "status": "",
            "content_type": "",
            "content": "",
            "error": str(e),
            "seconds": round(time.time() - start, 2),
            "raw": b"",
        }


def kind(content: str, content_type: str) -> str:
    content = content or ""
    ct = content_type or ""
    if re.search(r"<rss[\s>]", content, re.I) or re.search(r"<feed[\s>]", content, re.I) or re.search(r"rss|atom", ct, re.I):
        return "FEED_RSS_ATOM"
    if re.search(r"<urlset[\s>]", content, re.I) or re.search(r"<sitemapindex[\s>]", content, re.I) or re.search(r"sitemaps\.org", content, re.I):
        return "SITEMAP_XML"
    if re.search(r"^\s*(User-agent|Disallow|Allow|Sitemap):", content, re.I | re.M):
        return "ROBOTS_TXT"
    if re.search(r"json", ct, re.I) or re.search(r"^\s*[\{\[]", content):
        return "JSON"
    if re.search(r"<html", content, re.I) or re.search(r"text/html", ct, re.I):
        return "HTML"
    return "DESCONHECIDO"


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def _first_re(pattern: str, text: str, flags: int = re.I | re.S) -> str:
    m = re.search(pattern, text or "", flags)
    return html.unescape(m.group(1).strip()) if m else ""


def parse_feed_items(content: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    blocks = re.findall(r"<item\b.*?</item>", content or "", flags=re.I | re.S)
    for b in blocks:
        title = _strip_tags(_first_re(r"<title[^>]*>(.*?)</title>", b))
        link = _strip_tags(_first_re(r"<link[^>]*>(.*?)</link>", b))
        if not link:
            link = _first_re(r"<guid[^>]*isPermaLink=[\"']true[\"'][^>]*>(.*?)</guid>", b)
        date = _strip_tags(_first_re(r"<(?:pubDate|date|dc:date|published|updated)[^>]*>(.*?)</(?:pubDate|date|dc:date|published|updated)>", b))
        out.append({"title": title, "link": link, "date": date})
    # Atom entries
    entries = re.findall(r"<entry\b.*?</entry>", content or "", flags=re.I | re.S)
    for b in entries:
        title = _strip_tags(_first_re(r"<title[^>]*>(.*?)</title>", b))
        link = _first_re(r"<link[^>]*href=[\"']([^\"']+)[\"'][^>]*/?>", b)
        if not link:
            link = _strip_tags(_first_re(r"<link[^>]*>(.*?)</link>", b))
        date = _strip_tags(_first_re(r"<(?:updated|published|date)[^>]*>(.*?)</(?:updated|published|date)>", b))
        out.append({"title": title, "link": link, "date": date})
    # Dedup
    seen = set(); dedup = []
    for item in out:
        key = (item.get("link") or "") or (item.get("title") or "")
        if key and key not in seen:
            seen.add(key); dedup.append(item)
    return dedup


def _parse_dt(date_str: str) -> dt.datetime | None:
    s = (date_str or "").strip()
    if not s:
        return None
    for parser in (
        lambda x: parsedate_to_datetime(x),
        lambda x: dt.datetime.fromisoformat(x.replace("Z", "+00:00")),
    ):
        try:
            d = parser(s)
            if d.tzinfo is not None:
                d = d.astimezone(dt.timezone.utc).replace(tzinfo=None)
            return d
        except Exception:
            pass
    return None


def avaliar_feed_util(content: str, janela_horas: int = 24) -> dict[str, Any]:
    items = parse_feed_items(content)
    agora = dt.datetime.utcnow()
    dentro = 0
    com_data = 0
    com_titulo_link = 0
    validos = []
    for it in items:
        if it.get("title") and it.get("link") and not ASSET_EXT_RE.search(it.get("link", "")):
            com_titulo_link += 1
        d = _parse_dt(it.get("date", ""))
        if d:
            com_data += 1
            if 0 <= (agora - d).total_seconds() <= janela_horas * 3600:
                dentro += 1
                validos.append(it)
    return {
        "itens": len(items),
        "com_titulo_link": com_titulo_link,
        "com_data": com_data,
        "dentro_janela": dentro,
        "primeiros_titulos": [i.get("title") for i in items[:5] if i.get("title")],
        "primeiro_valido_janela": validos[0] if validos else None,
    }


def sitemap_locs(content: str) -> list[str]:
    return sorted(set(html.unescape(m.group(1).strip()) for m in re.finditer(r"<loc>\s*(.*?)\s*</loc>", content or "", re.I | re.S)))


def extract_json_ld(content: str) -> list[Any]:
    out = []
    pattern = r'<script[^>]*type=(["\'])application/ld\+json\1[^>]*>(.*?)</script>'
    for m in re.finditer(pattern, content or "", re.I | re.S):
        raw = m.group(2).strip()
        try:
            out.append(json.loads(raw))
        except Exception:
            out.append({"_raw": raw[:200], "_error": "JSON invalido"})
    return out


def extract_og_meta(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r'<meta[^>]+property=(["\'])(og:[^"\']+)\1[^>]+content=(["\'])([^"\']+)\3', content or "", re.I):
        out[m.group(2)] = html.unescape(m.group(4))
    for m in re.finditer(r'<meta[^>]+content=(["\'])([^"\']+)\1[^>]+property=(["\'])(og:[^"\']+)\3', content or "", re.I):
        out[m.group(4)] = html.unescape(m.group(2))
    return out


def extract_article_links(content: str, base_url: str) -> list[str]:
    links = []
    for m in re.finditer(r'href=(["\'])([^"\']+)\1', content or "", re.I):
        href = m.group(2).strip()
        if not href or href.lower().startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        full = join_url(base_url, href)
        low = full.lower()
        if ASSET_EXT_RE.search(low) or "/wp-content/uploads/" in low:
            continue
        if any(p in low for p in ["/noticia/", "/noticias/", "/post/", "/portal/", "/categoria/", "/202", "?p="]):
            links.append(full)
    return sorted(set(links))


def extract_entry_content(content: str) -> bool:
    return bool(re.search(r'<div[^>]+class=(["\'])[^"\']*entry-content[^"\']*\1', content or "", re.I))


def _log(cb: Callable[[str], None] | None, msg: str) -> None:
    if cb:
        try:
            cb(msg)
        except Exception:
            pass


def diagnostico_completo(root_url: str, log_callback: Callable[[str], None] | None = None, janela_horas: int = 24) -> dict[str, Any]:
    root = site_root(root_url)
    name = domain_key(root)
    if not root:
        raise ValueError("URL/domínio inválido.")
    results: dict[str, Any] = {"name": name, "root": root, "timestamp": dt.datetime.now().isoformat(), "tests": {}, "summary": {}, "recommendation": [], "solucao": {}}
    _log(log_callback, f"INICIANDO DIAGNÓSTICO COMPLETO: {name}\nRaiz: {root}")

    def test_urls(paths: list[str], label: str) -> tuple[list[dict[str, Any]], list[str]]:
        arr = []
        valid = []
        for path in paths:
            url = join_url(root, path)
            r = fetch(url)
            k = kind(r["content"], r["content_type"])
            is_valid = bool(r["ok"] and k == "FEED_RSS_ATOM")
            util = avaliar_feed_util(r["content"], janela_horas) if is_valid else {}
            item = {"url": url, "status": r["status"], "ok": r["ok"], "kind": k, "valid": is_valid, "error": r["error"], "content_type": r["content_type"], "feed_util": util}
            arr.append(item)
            if is_valid:
                valid.append(url)
            _log(log_callback, f"  {label}: {url} -> status={r['status']} | tipo={k} | valido={is_valid} | itens={util.get('itens', 0)} | janela={util.get('dentro_janela', 0)}")
        return arr, valid

    rss_root_results, valid_rss_root = test_urls(["/feed/", "/rss/", "/atom.xml", "/feed.xml", "/rss.xml"], "RSS raiz")
    results["tests"]["rss_root"] = {"description": "RSS/Atom na raiz", "results": rss_root_results, "valid_count": len(valid_rss_root), "valid_urls": valid_rss_root}

    rss_portal_results, valid_rss_portal = test_urls(["/portal/feed/", "/portal/rss/", "/portal/atom.xml", "/portal/feed.xml"], "RSS /portal")
    results["tests"]["rss_portal"] = {"description": "RSS/Atom em /portal/", "results": rss_portal_results, "valid_count": len(valid_rss_portal), "valid_urls": valid_rss_portal}

    cats = ["policia", "politica", "regiao", "geral", "cidade", "esporte", "economia"]
    rss_cat_results = []
    valid_rss_cat = []
    for cat in cats:
        url = join_url(root, f"/portal/categoria/{cat}/feed/")
        r = fetch(url); k = kind(r["content"], r["content_type"])
        is_valid = bool(r["ok"] and k == "FEED_RSS_ATOM")
        util = avaliar_feed_util(r["content"], janela_horas) if is_valid else {}
        rss_cat_results.append({"categoria": cat, "url": url, "status": r["status"], "ok": r["ok"], "kind": k, "valid": is_valid, "error": r["error"], "content_type": r["content_type"], "feed_util": util})
        if is_valid:
            valid_rss_cat.append({"categoria": cat, "url": url})
        _log(log_callback, f"  categoria {cat}: {r['status']} | {k} | valido={is_valid} | itens={util.get('itens', 0)}")
    results["tests"]["rss_categorias"] = {"description": "RSS por categoria", "results": rss_cat_results, "valid_count": len(valid_rss_cat), "valid_urls": valid_rss_cat}

    wp_paths = ["/wp-json/wp/v2/posts?per_page=10", "/wp-json/wp/v2/posts", "/portal/wp-json/wp/v2/posts?per_page=10", "/wp-json/"]
    wp_results = []
    wp_valid = False
    for path in wp_paths:
        url = join_url(root, path)
        r = fetch(url)
        is_json = bool(r["ok"] and kind(r["content"], r["content_type"]) == "JSON")
        has_posts = False
        count_posts = 0
        if is_json:
            try:
                data = json.loads(r["content"])
                if isinstance(data, list):
                    count_posts = len(data)
                    has_posts = any(isinstance(x, dict) and ("link" in x or "title" in x or "date" in x) for x in data)
                elif isinstance(data, dict):
                    has_posts = any(k in data for k in ("link", "title", "date", "content", "routes"))
            except Exception:
                has_posts = bool(re.search(r'"link"|"title"|"date"|"content"', r["content"] or ""))
        wp_results.append({"url": url, "status": r["status"], "ok": r["ok"], "is_json": is_json, "has_posts": has_posts, "posts_count": count_posts, "error": r["error"]})
        if has_posts:
            wp_valid = True
        _log(log_callback, f"  WP: {url} -> status={r['status']} | json={is_json} | posts={has_posts} | count={count_posts}")
    results["tests"]["wp_api"] = {"description": "WordPress REST API", "results": wp_results, "valid": wp_valid}

    sitemap_paths = ["/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/noticia/sitemap.xml", "/post-sitemap.xml", "/news-sitemap.xml", "/sitemap-news.xml", "/google-news-sitemap.xml"]
    sitemap_results = []
    valid_sitemaps = []
    sitemap_urls: list[str] = []
    for path in sitemap_paths:
        url = join_url(root, path)
        r = fetch(url); k = kind(r["content"], r["content_type"])
        is_valid = bool(r["ok"] and k == "SITEMAP_XML")
        locs: list[str] = []
        if is_valid:
            locs = sitemap_locs(r["content"])
            valid_sitemaps.append(url); sitemap_urls.extend(locs)
        sitemap_results.append({"url": url, "status": r["status"], "ok": r["ok"], "kind": k, "valid": is_valid, "urls_count": len(locs), "error": r["error"]})
        _log(log_callback, f"  Sitemap: {url} -> status={r['status']} | valido={is_valid} | urls={len(locs)}")
    news_sitemap = [u for u in sorted(set(sitemap_urls)) if any(p in u.lower() for p in ["/noticia/", "/noticias/", "/post/", "/202"])]
    results["tests"]["sitemap"] = {"description": "Sitemap XML", "results": sitemap_results, "valid_count": len(valid_sitemaps), "valid_urls": valid_sitemaps, "total_urls": len(sitemap_urls), "news_urls": news_sitemap[:100]}

    html_paths = ["/", "/portal/", "/noticias/", "/noticia/", "/politica/", "/policia/", "/regiao/", "/geral/"]
    html_results = []
    all_article_links: list[str] = []
    for path in html_paths:
        url = join_url(root, path)
        r = fetch(url); is_html = bool(r["ok"] and kind(r["content"], r["content_type"]) == "HTML")
        articles: list[str] = []
        has_entry = False
        if is_html:
            articles = extract_article_links(r["content"], url)
            has_entry = extract_entry_content(r["content"])
            all_article_links.extend(articles)
        html_results.append({"url": url, "status": r["status"], "ok": r["ok"], "is_html": is_html, "articles_found": len(articles), "has_entry_content": has_entry, "sample_articles": articles[:5], "error": r["error"]})
        _log(log_callback, f"  HTML: {url} -> status={r['status']} | artigos={len(articles)} | entry={has_entry}")
    all_article_links = sorted(set(all_article_links))
    results["tests"]["html_listagem"] = {"description": "HTML listagem", "results": html_results, "total_articles": len(all_article_links), "sample_articles": all_article_links[:30]}

    jsonld_results = []
    jsonld_valid = False
    test_urls = (all_article_links[:3] + [join_url(root, "/")])[:4]
    for url in test_urls:
        r = fetch(url)
        if not r["ok"]:
            continue
        jsonlds = extract_json_ld(r["content"])
        og = extract_og_meta(r["content"])
        if jsonlds:
            jsonld_valid = True
        jsonld_results.append({"url": url, "jsonld_count": len(jsonlds), "jsonld_types": [j.get("@type", "N/A") for j in jsonlds if isinstance(j, dict)], "og_tags": list(og.keys())[:8], "valid": bool(jsonlds or og)})
    results["tests"]["jsonld"] = {"description": "JSON-LD/Open Graph", "results": jsonld_results, "valid": jsonld_valid}

    has_raw_content = any(h.get("has_entry_content") for h in html_results)
    needs_playwright = False
    if has_raw_content:
        playwright_reason = "NAO NECESSARIO — conteúdo encontrado no HTML bruto (div.entry-content presente)."
    elif not all_article_links:
        needs_playwright = True
        playwright_reason = "POSSIVELMENTE NECESSARIO — nenhum artigo encontrado no HTML estático."
    else:
        r = fetch(all_article_links[0]) if all_article_links else {"ok": False, "content": ""}
        if r.get("ok"):
            text_len = len(_strip_tags(r.get("content", "")))
            if text_len < 200:
                needs_playwright = True; playwright_reason = f"POSSIVELMENTE NECESSARIO — artigo testado tem apenas {text_len} chars de texto puro."
            else:
                playwright_reason = f"NAO NECESSARIO — artigo testado tem {text_len} chars de texto puro no HTML."
        else:
            needs_playwright = True; playwright_reason = "POSSIVELMENTE NECESSARIO — não foi possível validar artigo estático."
    results["tests"]["playwright"] = {"description": "Avaliação Playwright", "needs_playwright": needs_playwright, "reason": playwright_reason}

    # Estratégia e config sugerido.
    all_feeds = valid_rss_portal + [u for u in valid_rss_root if u not in valid_rss_portal]
    useful_feeds = []
    for group in (rss_portal_results + rss_root_results + rss_cat_results):
        if group.get("valid"):
            util = group.get("feed_util") or {}
            # Útil mesmo sem janela quando há item com título/link: pode haver janela rígida no robô.
            if util.get("com_titulo_link", 0) > 0:
                useful_feeds.append(group.get("url"))
    useful_feeds = [u for u in all_feeds if u in useful_feeds] + [u for u in all_feeds if u not in useful_feeds]

    rec = []
    estrategia = "manual"
    if valid_rss_portal:
        estrategia = "rss_com_fallback"
        rec.append("[OK] Prioridade 1: usar RSS em /portal/feed/ ou /portal/rss/ com fallback para RSS raiz.")
    elif valid_rss_root:
        estrategia = "rss"
        rec.append("[OK] Usar RSS na raiz como principal.")
    elif wp_valid:
        estrategia = "wp_api"
        rec.append("[i] Usar WordPress REST API como alternativa leve; requer coletor compatível com WP API.")
    elif valid_sitemaps:
        estrategia = "sitemap"
        rec.append("[!] Usar sitemap/XML como fallback de cobertura.")
    elif all_article_links:
        estrategia = "html_listagem"
        rec.append("[!] Usar HTML de listagem com filtro de links e validação por OG/JSON-LD.")
    else:
        rec.append("[X] Nenhum caminho forte detectado. Requer análise manual.")
    if wp_valid:
        rec.append("[i] WP REST API disponível como fallback leve.")
    rec.append("[OK] Playwright: " + ("necessário/avaliar" if needs_playwright else "não necessário"))

    results["summary"] = {
        "RSS/Atom raiz": f"{len(valid_rss_root)} válido(s)",
        "RSS/Atom /portal/": f"{len(valid_rss_portal)} válido(s)",
        "RSS por categoria": f"{len(valid_rss_cat)} válido(s)",
        "WP REST API": "SIM" if wp_valid else "NÃO",
        "Sitemaps": f"{len(valid_sitemaps)} válido(s) | {len(sitemap_urls)} URLs | {len(news_sitemap)} notícias",
        "HTML listagem": f"{len(all_article_links)} artigos encontrados",
        "JSON-LD": "SIM" if jsonld_valid else "NÃO/Intermitente",
        "Playwright": "NECESSÁRIO" if needs_playwright else "NÃO NECESSÁRIO",
    }
    results["recommendation"] = rec
    results["solucao"] = {
        "estrategia_principal": estrategia,
        "feeds": useful_feeds or all_feeds,
        "sitemaps": valid_sitemaps,
        "wp_api": next((x["url"] for x in wp_results if x.get("has_posts")), ""),
        "html_fallback": [x["url"] for x in html_results if x.get("articles_found", 0) > 0],
        "playwright": needs_playwright,
        "config_sugerido": {
            "nome": name,
            "ativo": True,
            "tipo": estrategia,
            "feeds": useful_feeds or all_feeds,
            "sitemaps": valid_sitemaps,
            "wp_api": next((x["url"] for x in wp_results if x.get("has_posts")), ""),
            "playwright": needs_playwright,
            "observacao": "Aplicar em modo seguro: backup antes, não remover fontes funcionais, testar a coleta após aplicar.",
        },
    }
    return results


def diagnostico_rapido(root_url: str, log_callback: Callable[[str], None] | None = None) -> dict[str, Any]:
    return diagnostico_completo(root_url, log_callback=log_callback, janela_horas=24)


def format_report(results: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("RELATÓRIO DE DIAGNÓSTICO DE FONTE JORNALÍSTICA — URURAU v130")
    lines.append("=" * 90)
    lines.append(f"Gerado em: {dt.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    lines.append(f"Site: {results.get('name')}")
    lines.append(f"Raiz: {results.get('root')}")
    lines.append("=" * 90)
    lines.append("")
    lines.append("RESUMO EXECUTIVO")
    lines.append("-" * 90)
    for k, v in (results.get("summary") or {}).items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("RECOMENDAÇÃO")
    lines.append("-" * 90)
    for r in results.get("recommendation") or []:
        lines.append(f"  {r}")
    lines.append("")
    sol = results.get("solucao") or {}
    lines.append("SOLUÇÃO SUGERIDA PARA O URURAU")
    lines.append("-" * 90)
    lines.append(f"  Estratégia principal: {sol.get('estrategia_principal') or '-'}")
    if sol.get("feeds"):
        lines.append("  Feeds sugeridos:")
        for u in sol.get("feeds") or []:
            lines.append(f"    - {u}")
    if sol.get("wp_api"):
        lines.append(f"  WP API: {sol.get('wp_api')}")
    if sol.get("sitemaps"):
        lines.append("  Sitemaps sugeridos:")
        for u in sol.get("sitemaps") or []:
            lines.append(f"    - {u}")
    if sol.get("html_fallback"):
        lines.append("  HTML fallback:")
        for u in sol.get("html_fallback")[:8]:
            lines.append(f"    - {u}")
    lines.append(f"  Playwright: {'SIM' if sol.get('playwright') else 'NÃO'}")
    lines.append("")

    for test_name, test_data in (results.get("tests") or {}).items():
        lines.append(f"TESTE: {test_name.upper()}")
        lines.append("-" * 90)
        if "results" in test_data:
            for item in test_data["results"]:
                url = item.get("url") or item.get("sample") or ""
                status = item.get("status", "")
                valid = item.get("valid", item.get("ok", item.get("has_posts", "")))
                extra = ""
                if item.get("feed_util"):
                    fu = item["feed_util"]
                    extra = f" | itens={fu.get('itens', 0)} | titulo_link={fu.get('com_titulo_link', 0)} | janela={fu.get('dentro_janela', 0)}"
                if item.get("articles_found") is not None:
                    extra += f" | artigos={item.get('articles_found')}"
                if item.get("urls_count") is not None:
                    extra += f" | urls={item.get('urls_count')}"
                lines.append(f"  {'[OK]' if valid else '[X]'} {url} | status={status} | kind={item.get('kind', '')}{extra} | erro={item.get('error', '-') or '-'}")
        else:
            lines.append(json.dumps(test_data, ensure_ascii=False, indent=2))
        lines.append("")

    lines.append("CONFIG SUGERIDO (JSON)")
    lines.append("-" * 90)
    lines.append(json.dumps((results.get("solucao") or {}).get("config_sugerido", {}), ensure_ascii=False, indent=2))
    return "\n".join(lines)


def salvar_relatorio(results: dict[str, Any], pasta: str | Path | None = None) -> dict[str, str]:
    out = Path(pasta or "relatorios_diagnostico_fontes")
    out.mkdir(parents=True, exist_ok=True)
    nome = re.sub(r"[^A-Za-z0-9_.-]+", "_", results.get("name") or "fonte")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    txt = out / f"diagnostico_fonte_{nome}_{stamp}.txt"
    js = out / f"diagnostico_fonte_{nome}_{stamp}.json"
    txt.write_text(format_report(results), encoding="utf-8")
    js.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"txt": str(txt), "json": str(js)}
