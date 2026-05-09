"""
link_resolver_v90.py
Módulo de resolução de URLs finais com tratamento de redirecionamentos,
AMP, Google News, 404 e 429 (v90).
"""

import logging
import re
import time
from urllib.parse import urlparse, unquote, parse_qs, urlencode, urlunparse

logger = logging.getLogger(__name__)

def safe_get(obj, key, default=None):
    """Helper seguro para evitar AttributeError em dict.get()."""
    return obj.get(key, default) if isinstance(obj, dict) else default




def _url_invalida_para_materia_v91b(url: str) -> tuple[bool, str]:
    """Evita resolver imagens/CDNs como se fossem matérias."""
    if not url or not isinstance(url, str):
        return True, "url_vazia"
    u = url.strip().lower()
    if not (u.startswith("http://") or u.startswith("https://")):
        return True, "url_nao_http"
    try:
        parsed = urlparse(u)
        dominio = parsed.netloc.lower()
        path = parsed.path.lower()
        query = parsed.query.lower()
    except Exception:
        return True, "url_parse_invalido"

    dominios_asset = (
        "lh3.googleusercontent.com",
        "googleusercontent.com",
        "gstatic.com",
        "googleapis.com",
        "ggpht.com",
        "ytimg.com",
        "gravatar.com",
    )
    if any(dominio == d or dominio.endswith("." + d) or d in dominio for d in dominios_asset):
        return True, f"dominio_asset:{dominio}"

    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".css", ".js", ".woff", ".woff2", ".pdf", ".zip")):
        return True, "extensao_asset"

    if any(t in path for t in ("/favicon", "/logo", "/avatar", "/thumbnail", "/thumb", "/wp-content/uploads/", "/static/", "/assets/", "/images/", "/img/")):
        return True, "path_asset"

    if "googleusercontent" in dominio and ("w16" in query or "w32" in query or "w64" in query):
        return True, "thumb_google_news"

    return False, ""


def _extrair_dominio(url: str) -> str:
    """Extrai o domínio de uma URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def _eh_google_news(url: str) -> bool:
    """Verifica se a URL é do Google News."""
    return "news.google.com" in url.lower() or "news.url.google.com" in url.lower()


def _eh_amp(url: str) -> bool:
    """Verifica se a URL parece ser AMP."""
    return "/amp" in url.lower() or ".amp." in url.lower() or url.endswith("?amp")


def _resolver_google_news(url: str, titulo: str = "", fonte: str = "") -> dict:
    """
    Resolve URLs do Google News seguindo redirecionamentos e decodificando.
    Se não resolver, retorna status 'google_news_nao_resolvido'.
    """
    tentativas = []
    logger.info("[v90][LINK_RESOLVER] Resolvendo Google News: %r", url)

    try:
        import requests
    except ImportError:
        logger.error("[v90][LINK_RESOLVER] requests nao disponivel")
        return {
            "ok": False,
            "url_final": url,
            "fonte_real": fonte,
            "status": "erro_requests_nao_disponivel",
            "tentativas": tentativas,
        }

    # Tentativa 1: requests com allow_redirects
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=20)
        url_final = resp.url
        tentativas.append({"metodo": "requests_redirects", "url": url_final, "status_code": resp.status_code})

        # Se chegou numa URL que não é Google News nem asset, sucesso.
        invalida, motivo = _url_invalida_para_materia_v91b(url_final)
        if not _eh_google_news(url_final) and not invalida:
            dominio_fonte = _extrair_dominio(url_final)
            logger.info("[v90][LINK_RESOLVER] Google News resolvido: %s", url_final)
            return {
                "ok": True,
                "url_final": url_final,
                "fonte_real": dominio_fonte,
                "status": "resolvido",
                "tentativas": tentativas,
            }
        if invalida:
            tentativas.append({"metodo": "requests_redirects_asset_descartado", "url": url_final, "motivo": motivo})
    except Exception as e:
        tentativas.append({"metodo": "requests_redirects", "erro": str(e)})
        logger.warning("[v90][LINK_RESOLVER] Falha requests_redirects: %s", e)

    # Tentativa 2: Extrair URL de parâmetros do Google News
    try:
        parsed = urlparse(url)
        query = parsed.query
        params = parse_qs(query)

        # Parâmetros comuns do Google News
        for param in ["url", "u", "href", "link", "article"]:
            valor_list = params.get(param, [])
            for valor in valor_list:
                valor_decod = unquote(valor)
                invalida_param, motivo_param = _url_invalida_para_materia_v91b(valor_decod)
                if valor_decod.startswith("http") and not _eh_google_news(valor_decod) and not invalida_param:
                    tentativas.append({"metodo": f"param_{param}", "url": valor_decod})
                    logger.info("[v90][LINK_RESOLVER] Google News resolvido via param %s: %s", param, valor_decod)
                    return {
                        "ok": True,
                        "url_final": valor_decod,
                        "fonte_real": _extrair_dominio(valor_decod),
                        "status": "resolvido_via_parametro",
                        "tentativas": tentativas,
                    }
                elif valor_decod.startswith("http") and invalida_param:
                    tentativas.append({"metodo": f"param_{param}_asset_descartado", "url": valor_decod, "motivo": motivo_param})

        # Ler link da tag <a> no HTML se possível
        if 'resp' in dir() and hasattr(resp, 'text'):
            links = re.findall(r'href=["\'](https?://[^"\']+)["\']', resp.text)
            for link in links:
                invalida_link, motivo_link = _url_invalida_para_materia_v91b(link)
                if not _eh_google_news(link) and link != url and not invalida_link:
                    tentativas.append({"metodo": "html_links", "url": link})
                    logger.info("[v90][LINK_RESOLVER] Google News resolvido via HTML link: %s", link)
                    return {
                        "ok": True,
                        "url_final": link,
                        "fonte_real": _extrair_dominio(link),
                        "status": "resolvido_via_html",
                        "tentativas": tentativas,
                    }
                elif invalida_link:
                    tentativas.append({"metodo": "html_links_asset_descartado", "url": link, "motivo": motivo_link})
    except Exception as e:
        tentativas.append({"metodo": "extracao_parametros", "erro": str(e)})
        logger.warning("[v90][LINK_RESOLVER] Falha extracao parametros: %s", e)

    # Tentativa 3: Buscar título na fonte conhecida
    if fonte and titulo:
        tentativas.append({"metodo": "busca_titulo_fonte", "fonte": fonte, "titulo": titulo[:80]})
        logger.info("[v90][LINK_RESOLVER] Tentando buscar titulo na fonte %s", fonte)
        # Aqui deixamos placeholder - a busca real seria feita por outro módulo

    logger.warning("[v90][LINK_RESOLVER] Google News NAO resolvido: %r", url)
    return {
        "ok": False,
        "url_final": url,
        "fonte_real": fonte,
        "status": "google_news_nao_resolvido",
        "tentativas": tentativas,
    }


def _resolver_amp(url: str, titulo: str = "", fonte: str = "") -> dict:
    """
    Resolve URLs AMP buscando a canonical.
    Testa canonical primeiro, AMP como fallback.
    """
    tentativas = []
    logger.info("[v90][LINK_RESOLVER] Resolvendo AMP: %r", url)

    try:
        import requests
    except ImportError:
        logger.error("[v90][LINK_RESOLVER] requests nao disponivel")
        return {
            "ok": False,
            "url_final": url,
            "fonte_real": fonte,
            "status": "erro_requests_nao_disponivel",
            "tentativas": tentativas,
        }

    canonical = None

    # Tentativa 1: Buscar canonical no HTML da AMP
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(url, headers=headers, timeout=15)
        tentativas.append({"metodo": "fetch_amp", "status_code": resp.status_code})

        if resp.status_code == 200:
            # Buscar <link rel="canonical">
            match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
            if match:
                canonical = match.group(1)
                tentativas.append({"metodo": "canonical_no_amp", "url": canonical})
            else:
                # Buscar og:url
                match_og = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
                if match_og:
                    canonical = match_og.group(1)
                    tentativas.append({"metodo": "og_url_no_amp", "url": canonical})
    except Exception as e:
        tentativas.append({"metodo": "fetch_amp", "erro": str(e)})
        logger.warning("[v90][LINK_RESOLVER] Falha fetch AMP: %s", e)

    # Tentativa 2: Testar canonical
    if canonical and not _eh_amp(canonical):
        try:
            resp_canonical = requests.head(canonical, headers=headers, allow_redirects=True, timeout=10)
            if resp_canonical.status_code == 200:
                logger.info("[v90][LINK_RESOLVER] AMP resolvido via canonical: %s", canonical)
                return {
                    "ok": True,
                    "url_final": canonical,
                    "fonte_real": _extrair_dominio(canonical),
                    "status": "resolvido_amp_para_canonical",
                    "tentativas": tentativas,
                }
            else:
                tentativas.append({"metodo": "testar_canonical", "status_code": resp_canonical.status_code})
        except Exception as e:
            tentativas.append({"metodo": "testar_canonical", "erro": str(e)})

    # Tentativa 3: Fallback para AMP mesmo (se acessível)
    try:
        resp_amp = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
        if resp_amp.status_code == 200:
            logger.info("[v90][LINK_RESOLVER] AMP mantido como fallback: %s", url)
            return {
                "ok": True,
                "url_final": url,
                "fonte_real": _extrair_dominio(url),
                "status": "amp_fallback",
                "tentativas": tentativas,
            }
    except Exception as e:
        tentativas.append({"metodo": "testar_amp", "erro": str(e)})

    logger.warning("[v90][LINK_RESOLVER] AMP nao resolvido: %r", url)
    return {
        "ok": False,
        "url_final": url,
        "fonte_real": fonte,
        "status": "amp_nao_resolvido",
        "tentativas": tentativas,
    }


def _tratar_404(url: str, titulo: str = "", fonte: str = "", tentativas: list = None) -> dict:
    """
    Trata 404: tenta canonical/og_url, busca título no sitemap, homepage/editoria, variantes.
    Só bloqueia depois de esgotar alternativas.
    """
    if tentativas is None:
        tentativas = []

    logger.info("[v90][LINK_RESOLVER] Tratando 404 para: %r", url)
    parsed = urlparse(url)
    dominio = parsed.netloc.lower()

    try:
        import requests
    except ImportError:
        return {
            "ok": False,
            "url_final": url,
            "fonte_real": fonte,
            "status": "404_erro_requests",
            "tentativas": tentativas,
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # Tentativa 1: Buscar og:url e canonical na página de erro (pode ter meta tags)
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code in (404, 410):
            # Tentar extrair og:url
            match_og = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
            if match_og:
                og_url = match_og.group(1)
                tentativas.append({"metodo": "og_url_na_404", "url": og_url})
                resp_og = requests.head(og_url, headers=headers, allow_redirects=True, timeout=10)
                if resp_og.status_code == 200:
                    logger.info("[v90][LINK_RESOLVER] 404 resolvido via og:url: %s", og_url)
                    return {
                        "ok": True,
                        "url_final": og_url,
                        "fonte_real": _extrair_dominio(og_url),
                        "status": "resolvido_404_via_og_url",
                        "tentativas": tentativas,
                    }

            # Tentar canonical
            match_can = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
            if match_can:
                can_url = match_can.group(1)
                tentativas.append({"metodo": "canonical_na_404", "url": can_url})
                resp_can = requests.head(can_url, headers=headers, allow_redirects=True, timeout=10)
                if resp_can.status_code == 200:
                    logger.info("[v90][LINK_RESOLVER] 404 resolvido via canonical: %s", can_url)
                    return {
                        "ok": True,
                        "url_final": can_url,
                        "fonte_real": _extrair_dominio(can_url),
                        "status": "resolvido_404_via_canonical",
                        "tentativas": tentativas,
                    }
    except Exception as e:
        tentativas.append({"metodo": "meta_na_404", "erro": str(e)})

    # Tentativa 2: Procurar título no sitemap
    if titulo:
        sitemaps = [
            f"{parsed.scheme}://{dominio}/sitemap.xml",
            f"{parsed.scheme}://{dominio}/sitemap_index.xml",
            f"{parsed.scheme}://{dominio}/post-sitemap.xml",
            f"{parsed.scheme}://{dominio}/sitemap-news.xml",
        ]
        for sm in sitemaps:
            try:
                resp_sm = requests.get(sm, headers=headers, timeout=10)
                if resp_sm.status_code == 200:
                    # Buscar título no sitemap
                    # Simplificação: buscar slug do título
                    slug_titulo = re.sub(r"[^\w]", "-", titulo.lower())[:30]
                    if slug_titulo and slug_titulo in resp_sm.text.lower():
                        # Extrair URL do sitemap que contém o slug
                        urls_encontradas = re.findall(r'<loc>([^<]+)</loc>', resp_sm.text)
                        for u in urls_encontradas:
                            if slug_titulo.replace("-", "") in u.lower().replace("-", "").replace("/", ""):
                                tentativas.append({"metodo": "sitemap", "url": u})
                                logger.info("[v90][LINK_RESOLVER] 404 resolvido via sitemap: %s", u)
                                return {
                                    "ok": True,
                                    "url_final": u,
                                    "fonte_real": _extrair_dominio(u),
                                    "status": "resolvido_404_via_sitemap",
                                    "tentativas": tentativas,
                                }
            except Exception as e:
                tentativas.append({"metodo": f"sitemap_{sm}", "erro": str(e)})

    # Tentativa 3: Procurar na homepage/editoria
    try:
        editoria = "/".join(parsed.path.split("/")[:2]) if parsed.path else "/"
        url_editoria = f"{parsed.scheme}://{dominio}{editoria}"
        resp_ed = requests.get(url_editoria, headers=headers, timeout=10)
        if resp_ed.status_code == 200 and titulo:
            # Buscar link com título similar na página
            links = re.findall(r'href=["\']([^"\']+)["\'][^>]*>([^<]{10,200})</a>', resp_ed.text, re.IGNORECASE)
            for link, texto in links:
                if len(titulo) > 10 and titulo[:15].lower() in texto.lower():
                    link_abs = link if link.startswith("http") else f"{parsed.scheme}://{dominio}{link}"
                    tentativas.append({"metodo": "homepage_editoria", "url": link_abs})
                    logger.info("[v90][LINK_RESOLVER] 404 resolvido via homepage/editoria: %s", link_abs)
                    return {
                        "ok": True,
                        "url_final": link_abs,
                        "fonte_real": _extrair_dominio(link_abs),
                        "status": "resolvido_404_via_homepage",
                        "tentativas": tentativas,
                    }
    except Exception as e:
        tentativas.append({"metodo": "homepage_editoria", "erro": str(e)})

    # Tentativa 4: Variantes por domínio
    try:
        from .url_variants_v90 import gerar_variantes_url_v90
        variantes = gerar_variantes_url_v90(url, dominio, "")
        for v in variantes:
            if v == url:
                continue
            try:
                resp_v = requests.head(v, headers=headers, allow_redirects=True, timeout=10)
                tentativas.append({"metodo": "variante", "url": v, "status_code": resp_v.status_code})
                if resp_v.status_code == 200:
                    logger.info("[v90][LINK_RESOLVER] 404 resolvido via variante: %s", v)
                    return {
                        "ok": True,
                        "url_final": v,
                        "fonte_real": _extrair_dominio(v),
                        "status": "resolvido_404_via_variante",
                        "tentativas": tentativas,
                    }
            except Exception as e:
                tentativas.append({"metodo": f"variante_{v}", "erro": str(e)})
    except ImportError:
        tentativas.append({"metodo": "variantes", "erro": "url_variants_v90 nao disponivel"})

    logger.warning("[v90][LINK_RESOLVER] 404 NAO resolvido apos todas tentativas: %r", url)
    return {
        "ok": False,
        "url_final": url,
        "fonte_real": fonte,
        "status": "404_nao_resolvido",
        "tentativas": tentativas,
    }


def _tratar_429(url: str, dominio: str, tentativas: list = None) -> dict:
    """
    Trata 429: implementa cooldown do domínio, backoff, cache, log claro.
    Não derruba o ciclo.
    """
    if tentativas is None:
        tentativas = []

    logger.warning("[v90][LINK_RESOLVER] 429 detectado para: %r", url)

    # Registrar cooldown no source_quality
    try:
        from .source_quality_v90 import definir_cooldown
        definir_cooldown(dominio, segundos=600)
        tentativas.append({"metodo": "cooldown_429", "dominio": dominio, "segundos": 600})
    except ImportError as e:
        logger.warning("[v90][LINK_RESOLVER] source_quality_v90 nao disponivel: %s", e)
        tentativas.append({"metodo": "cooldown_429", "erro": str(e)})

    # Backoff exponencial simples
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        for tentativa in range(1, 4):
            delay = min(2 ** tentativa, 60)
            logger.info("[v90][LINK_RESOLVER] 429 retry %d/3, aguardando %ds", tentativa, delay)
            time.sleep(delay)
            try:
                resp = requests.head(url, headers=headers, allow_redirects=True, timeout=15)
                tentativas.append({"metodo": f"retry_{tentativa}", "status_code": resp.status_code, "delay": delay})
                if resp.status_code == 200:
                    logger.info("[v90][LINK_RESOLVER] 429 resolvido apos retry: %s", url)
                    return {
                        "ok": True,
                        "url_final": resp.url,
                        "fonte_real": dominio,
                        "status": "resolvido_429_via_backoff",
                        "tentativas": tentativas,
                    }
                if resp.status_code != 429:
                    break
            except Exception as e:
                tentativas.append({"metodo": f"retry_{tentativa}", "erro": str(e)})
    except ImportError:
        pass

    logger.error("[v90][LINK_RESOLVER] 429 persistiu apos retries: %r", url)
    return {
        "ok": False,
        "url_final": url,
        "fonte_real": dominio,
        "status": "429_persistente",
        "tentativas": tentativas,
    }


def resolver_url_final_v90(url: str, titulo: str = "", fonte: str = "") -> dict:
    """
    Resolve a URL final de uma notícia, tratando casos especiais.

    - Google News: decodificar link real
    - AMP: buscar canonical, testar canonical primeiro, AMP fallback
    - 404: tentar canonical/og_url, sitemap, homepage, variantes
    - 429: cooldown, backoff, log claro, não derrubar ciclo

    Retorna dict com:
        ok (bool), url_final (str), fonte_real (str), status (str), tentativas (list)
    """
    tentativas = []
    logger.info("[v90][LINK_RESOLVER] Iniciando resolucao: url=%r titulo=%r fonte=%r",
                url, titulo[:80] if titulo else "", fonte)

    if not url or not isinstance(url, str):
        logger.error("[v90][LINK_RESOLVER] URL invalida: %r", url)
        return {
            "ok": False,
            "url_final": "",
            "fonte_real": fonte,
            "status": "url_invalida",
            "tentativas": tentativas,
        }

    dominio = _extrair_dominio(url)

    # ---- CASO 1: Google News ----
    if _eh_google_news(url):
        resultado = _resolver_google_news(url, titulo, fonte)
        if resultado["ok"]:
            return resultado
        # Se não resolveu, retornamos o status específico
        return resultado

    # ---- CASO 2: AMP ----
    if _eh_amp(url):
        resultado = _resolver_amp(url, titulo, fonte)
        if resultado["ok"]:
            return resultado
        # Se AMP falhou, continuar tentando a URL original
        tentativas.extend(resultado.get("tentativas", []))
        logger.info("[v90][LINK_RESOLVER] AMP nao resolvido, continuando com URL original")

    # ---- CASO GERAL: Fazer request e tratar status ----
    try:
        import requests
    except ImportError:
        logger.error("[v90][LINK_RESOLVER] requests nao disponivel")
        return {
            "ok": False,
            "url_final": url,
            "fonte_real": fonte,
            "status": "erro_requests_nao_disponivel",
            "tentativas": tentativas,
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=20)
        status_code = resp.status_code
        url_final = resp.url
        tentativas.append({"metodo": "request_principal", "status_code": status_code, "url": url_final})
    except Exception as e:
        logger.error("[v90][LINK_RESOLVER] Erro no request principal: %s", e)
        tentativas.append({"metodo": "request_principal", "erro": str(e)})
        return {
            "ok": False,
            "url_final": url,
            "fonte_real": fonte,
            "status": f"erro_request: {str(e)[:100]}",
            "tentativas": tentativas,
        }

    # ---- Status 200: Sucesso ----
    if status_code == 200:
        invalida_final, motivo_final = _url_invalida_para_materia_v91b(url_final)
        if invalida_final:
            logger.info("[v91B][LINK_RESOLVER] URL 200 descartada por não ser matéria: %s | %s", motivo_final, url_final)
            return {
                "ok": False,
                "url_final": url_final,
                "fonte_real": _extrair_dominio(url_final),
                "status": f"url_nao_materia:{motivo_final}",
                "tentativas": tentativas,
            }
        logger.info("[v90][LINK_RESOLVER] URL resolvida com sucesso: %s", url_final)
        return {
            "ok": True,
            "url_final": url_final,
            "fonte_real": _extrair_dominio(url_final),
            "status": "resolvido",
            "tentativas": tentativas,
        }

    # ---- Status 429: Rate Limit ----
    if status_code == 429:
        return _tratar_429(url, dominio, tentativas)

    # ---- Status 404/410: Não encontrado ----
    if status_code in (404, 410):
        return _tratar_404(url, titulo, fonte, tentativas)

    # ---- Status 403: Forbidden ----
    if status_code == 403:
        logger.warning("[v90][LINK_RESOLVER] 403 Forbidden: %r", url)
        # Tentar variantes
        try:
            from .url_variants_v90 import gerar_variantes_url_v90
            variantes = gerar_variantes_url_v90(url, dominio, "")
            for v in variantes:
                if v == url:
                    continue
                try:
                    resp_v = requests.head(v, headers=headers, allow_redirects=True, timeout=10)
                    tentativas.append({"metodo": "variante_403", "url": v, "status_code": resp_v.status_code})
                    if resp_v.status_code == 200:
                        logger.info("[v90][LINK_RESOLVER] 403 resolvido via variante: %s", v)
                        return {
                            "ok": True,
                            "url_final": v,
                            "fonte_real": _extrair_dominio(v),
                            "status": "resolvido_403_via_variante",
                            "tentativas": tentativas,
                        }
                except Exception as e:
                    tentativas.append({"metodo": f"variante_403_{v}", "erro": str(e)})
        except ImportError:
            pass

        return {
            "ok": False,
            "url_final": url,
            "fonte_real": fonte,
            "status": "403_forbidden",
            "tentativas": tentativas,
        }

    # ---- Outros status ----
    logger.warning("[v90][LINK_RESOLVER] Status nao tratado %d: %r", status_code, url)
    return {
        "ok": False,
        "url_final": url_final,
        "fonte_real": _extrair_dominio(url_final),
        "status": f"status_{status_code}",
        "tentativas": tentativas,
    }
