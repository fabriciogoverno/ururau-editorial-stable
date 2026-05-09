"""ArticleExtractor — extracao completa de artigos com cascata de metodos."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import aiohttp
from bs4 import BeautifulSoup

from .config import HTML_CLEANUP_TAGS, get_random_ua
from .logger import get_logger
from .models import ScraperConfig
from .utils import DomainCooldown, extract_domain

logger = get_logger("extractor")

# Tenta importar extratores opcionais
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

try:
    from readability import Document
    HAS_READABILITY = True
except ImportError:
    HAS_READABILITY = False


class ArticleExtractor:
    """Extrator de conteudo completo de artigos.

    Cascata de extracao:
        1. Trafilatura (primario)
        2. readability-lxml (fallback 1)
        3. JSON-LD NewsArticle/Article (fallback 2)
        4. BeautifulSoup density-based (fallback 3)
        5. Newspaper4k-style scoring (stopwords + link density + siblings)
        6. WordPress REST API (fallback 5)

    v111.2 Plus:
        - reforca metadados e imagens em todos os metodos via OpenGraph,
          Twitter Cards, JSON-LD, canonical e srcset;
        - usa heuristicas inspiradas em newspaper/newspaper4k para capturar
          texto quando o HTML nao usa seletores convencionais;
        - mantem operacao apenas sobre paginas publicas, sem login/paywall.
    """

    def __init__(self, config: Optional[ScraperConfig] = None):
        self.config = config or ScraperConfig()
        self.cooldown = DomainCooldown(self.config.cooldown_429_seconds)
        self._semaphore = asyncio.Semaphore(self.config.concurrency)

    # ------------------------------------------------------------------
    # Extracao publica
    # ------------------------------------------------------------------

    async def extract(self, url: str) -> Dict[str, Any]:
        """Extrai conteudo completo de uma URL.

        Tenta cada metodo em cascata ate encontrar texto suficiente.

        Args:
            url: URL do artigo.

        Returns:
            Dict com: title, author, published_date, article_text,
            images, language, method (qual metodo funcionou).
        """
        if not url or not url.startswith("http"):
            return self._empty_result("invalid_url")

        domain = extract_domain(url)
        await self.cooldown.wait_if_needed(domain)

        # Fetch HTML
        html = await self._fetch_html(url)
        if not html:
            return self._empty_result("fetch_failed")

        result: Optional[Dict[str, Any]] = None

        # 1. Trafilatura (primario)
        if HAS_TRAFILATURA:
            result = await self._extract_trafilatura(html, url)
            if result and self._is_valid(result):
                result["method"] = "trafilatura"
                return self._post_process(self._merge_html_metadata(result, html, url))

        # 2. Readability-lxml
        if HAS_READABILITY:
            result = await self._extract_readability(html, url)
            if result and self._is_valid(result):
                result["method"] = "readability"
                return self._post_process(self._merge_html_metadata(result, html, url))

        # 3. JSON-LD
        result = await self._extract_jsonld(html, url)
        if result and self._is_valid(result):
            result["method"] = "jsonld"
            return self._post_process(self._merge_html_metadata(result, html, url))

        # 4. BS4 density
        result = await self._extract_bs4_density(html, url)
        if result and self._is_valid(result):
            result["method"] = "bs4_density"
            return self._post_process(self._merge_html_metadata(result, html, url))

        # 5. Newspaper4k-style scoring: bom para sites sem <article>/<main>
        result_plus = await self._extract_newspaper_plus(html, url)
        if result_plus and self._is_valid(result_plus):
            result_plus["method"] = "newspaper_plus"
            return self._post_process(self._merge_html_metadata(result_plus, html, url))
        if result_plus:
            result = result_plus

        # 6. WordPress REST
        result_wp = await self._extract_wordpress_rest(url)
        if result_wp and self._is_valid(result_wp):
            result_wp["method"] = "wordpress_rest"
            return self._post_process(self._merge_html_metadata(result_wp, html, url))
        if result_wp:
            result = result_wp

        # Nenhum metodo funcionou adequadamente.
        # Retorna o melhor resultado encontrado (mesmo que curto), com imagens/metadados.
        if result:
            result["method"] = result.get("method") or "insufficient"
            return self._post_process(self._merge_html_metadata(result, html, url))

        return self._empty_result("all_methods_failed")

    async def extract_many(
        self, urls: List[str]
    ) -> List[Dict[str, Any]]:
        """Extrai multiplas URLs com concorrencia controlada.

        Args:
            urls: Lista de URLs.

        Returns:
            Lista de dicts com resultados.
        """
        semaphore = asyncio.Semaphore(self.config.concurrency)

        async def _extract_one(url: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.extract(url)
                except Exception as e:
                    logger.warning(f"Erro extraindo {url}: {e}")
                    return {"url": url, "error": str(e), "method": "exception"}

        tasks = [_extract_one(u) for u in urls]
        return await asyncio.gather(*tasks)

    # ------------------------------------------------------------------
    # Fetch HTML
    # ------------------------------------------------------------------

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML com retry, UA rotativo e cooldown."""
        from .utils import fetch_with_retry

        try:
            async with aiohttp.ClientSession() as session:
                if self.config.rotate_user_agent:
                    session.headers["User-Agent"] = get_random_ua()

                result = await fetch_with_retry(
                    url,
                    session=session,
                    max_retries=self.config.max_retries,
                    backoff=self.config.backoff_factor,
                    max_sleep=self.config.max_sleep,
                    timeout=self.config.timeout,
                )

                if result is None:
                    self.cooldown.mark_429(extract_domain(url))

                return result

        except Exception as e:
            logger.debug(f"Fetch HTML falhou para {url}: {e}")
            return None

    # ------------------------------------------------------------------
    # 1. Trafilatura (primario)
    # ------------------------------------------------------------------

    async def _extract_trafilatura(
        self, html: str, url: str
    ) -> Optional[Dict[str, Any]]:
        """Extracao primaria usando trafilatura."""
        if not HAS_TRAFILATURA:
            return None

        try:
            # Extrai texto
            text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            )

            # Extrai metadata
            metadata = trafilatura.extract_metadata(html)

            result: Dict[str, Any] = {
                "article_text": text,
                "url": url,
            }

            if metadata:
                result["title"] = metadata.title
                result["author"] = metadata.author
                result["published_date"] = self._parse_iso_date(metadata.date)
                result["language"] = metadata.language

            return result

        except Exception as e:
            logger.debug(f"Trafilatura falhou: {e}")
            return None

    # ------------------------------------------------------------------
    # 2. Readability-lxml (fallback 1)
    # ------------------------------------------------------------------

    async def _extract_readability(
        self, html: str, url: str
    ) -> Optional[Dict[str, Any]]:
        """Extracao via readability-lxml."""
        if not HAS_READABILITY:
            return None

        try:
            doc = Document(html)
            summary = doc.summary()
            title = doc.title()

            # Parse do summary HTML para texto limpo
            soup = BeautifulSoup(summary, "html.parser")

            # Remove tags de navegacao/boilerplate
            for tag_name in HTML_CLEANUP_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Extrai paragrafos
            paragraphs = []
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 20:
                    paragraphs.append(text)

            article_text = "\n\n".join(paragraphs)

            # Tenta extrair author do HTML original
            author = self._extract_author_meta(html)

            # Tenta extrair data do HTML original
            pub_date = self._extract_date_meta(html)

            return {
                "title": title,
                "article_text": article_text,
                "author": author,
                "published_date": pub_date,
                "url": url,
            }

        except Exception as e:
            logger.debug(f"Readability falhou: {e}")
            return None

    # ------------------------------------------------------------------
    # 3. JSON-LD (fallback 2)
    # ------------------------------------------------------------------

    async def _extract_jsonld(
        self, html: str, url: str
    ) -> Optional[Dict[str, Any]]:
        """Extracao via JSON-LD structured data."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            scripts = soup.find_all("script", type="application/ld+json")

            for script in scripts:
                if not script.string:
                    continue

                try:
                    data = json.loads(script.string)
                except json.JSONDecodeError:
                    continue

                # Pode ser uma lista ou dict
                items = data if isinstance(data, list) else [data]

                for item in items:
                    item_type = item.get("@type", "")
                    if isinstance(item_type, list):
                        types = [t.lower() for t in item_type]
                    else:
                        types = [item_type.lower()]

                    if any(t in ("newsarticle", "article", "webpage") for t in types):
                        article_body = item.get("articleBody", "")
                        if not article_body:
                            # Tenta description como fallback
                            article_body = item.get("description", "")

                        headline = item.get("headline", "")

                        # Author
                        author = ""
                        author_data = item.get("author")
                        if isinstance(author_data, dict):
                            author = author_data.get("name", "")
                        elif isinstance(author_data, list) and author_data:
                            author = author_data[0].get("name", "") if isinstance(author_data[0], dict) else str(author_data[0])

                        # Date
                        date_str = item.get("datePublished", item.get("dateModified", ""))
                        pub_date = self._parse_iso_date(date_str)

                        # Images
                        images = []
                        image_data = item.get("image")
                        if isinstance(image_data, dict):
                            img_url = image_data.get("url", "")
                            if img_url:
                                images.append(img_url)
                        elif isinstance(image_data, str):
                            images.append(image_data)

                        return {
                            "title": headline,
                            "article_text": article_body,
                            "author": author or None,
                            "published_date": pub_date,
                            "images": images,
                            "url": url,
                        }

            return None

        except Exception as e:
            logger.debug(f"JSON-LD falhou: {e}")
            return None

    # ------------------------------------------------------------------
    # 4. BS4 density-based (fallback 3)
    # ------------------------------------------------------------------

    async def _extract_bs4_density(
        self, html: str, url: str
    ) -> Optional[Dict[str, Any]]:
        """Extracao via BeautifulSoup com selecao por densidade textual."""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove tags de boilerplate
            for tag_name in HTML_CLEANUP_TAGS:
                for tag in soup.find_all(tag_name):
                    tag.decompose()

            # Seletores por ordem de prioridade
            selectors = [
                "article",
                "[role=main]",
                "main",
                ".article-content",
                ".post-content",
                ".entry-content",
                ".content",
                ".story",
                "#content",
                ".article",
                ".post",
                ".news-detail",
            ]

            best_element = None
            best_score = 0.0

            for selector in selectors:
                elements = soup.select(selector)
                for elem in elements:
                    score = self._text_density(elem)
                    if score > best_score:
                        best_score = score
                        best_element = elem

            if best_element is None:
                # Fallback: body
                body = soup.find("body")
                if body:
                    best_element = body
                else:
                    return None

            # Extrai paragrafos do melhor elemento
            paragraphs = []
            for p in best_element.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 15:
                    paragraphs.append(text)

            # Se nao achou <p>, pega todo o texto
            if not paragraphs:
                text = best_element.get_text(separator="\n", strip=True)
                paragraphs = [t for t in text.split("\n") if len(t) > 15]

            article_text = "\n\n".join(paragraphs)

            if len(article_text) < 100:
                return None

            # Extrai metadata do HTML
            title = self._extract_title(soup)
            author = self._extract_author_meta(html)
            pub_date = self._extract_date_meta(html)

            return {
                "title": title,
                "article_text": article_text,
                "author": author,
                "published_date": pub_date,
                "url": url,
            }

        except Exception as e:
            logger.debug(f"BS4 density falhou: {e}")
            return None

    def _text_density(self, element) -> float:
        """Calcula densidade textual de um elemento BS4."""
        text = element.get_text(strip=True)
        text_len = len(text)
        if text_len == 0:
            return 0.0

        tag_count = len(element.find_all())
        if tag_count == 0:
            return float(text_len)

        # Densidade = caracteres de texto / numero de tags
        # Penaliza elementos com muitas tags e pouco texto
        return text_len / (tag_count + 1)


    # ------------------------------------------------------------------
    # 5. Newspaper4k-style scoring (fallback Plus)
    # ------------------------------------------------------------------

    async def _extract_newspaper_plus(
        self, html: str, url: str
    ) -> Optional[Dict[str, Any]]:
        """Extracao inspirada em newspaper4k.

        Diferenca para o BS4 density simples:
        - calcula link density;
        - usa bonus/penalidade por classes/ids;
        - usa stopwords em portugues para detectar texto jornalistico;
        - complementa o bloco principal com paragrafos irmaos relevantes.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            self._limpar_soup_plus(soup)

            candidates = []
            selectors = [
                "article", "main", "[role=main]",
                ".materia", ".noticia", ".post", ".entry", ".story",
                ".article-body", ".article-content", ".post-content",
                ".entry-content", ".content-body", ".texto", ".corpo",
                "#article", "#materia", "#noticia", "#content", "#main",
            ]
            seen_ids: set[int] = set()
            for selector in selectors:
                for elem in soup.select(selector):
                    if id(elem) not in seen_ids:
                        seen_ids.add(id(elem))
                        candidates.append(elem)

            # Fallback amplo: div/section com paragrafos.
            if len(candidates) < 3:
                for elem in soup.find_all(["article", "main", "section", "div"]):
                    if id(elem) in seen_ids:
                        continue
                    text_len = len(elem.get_text(" ", strip=True))
                    p_count = len(elem.find_all("p"))
                    if text_len >= 300 and p_count >= 2:
                        seen_ids.add(id(elem))
                        candidates.append(elem)

            best_elem = None
            best_score = -1.0
            for elem in candidates:
                score = self._newspaper_node_score(elem)
                if score > best_score:
                    best_score = score
                    best_elem = elem

            if best_elem is None:
                body = soup.find("body")
                if body is None:
                    return None
                best_elem = body
                best_score = self._newspaper_node_score(best_elem)

            paragraphs = self._paragraphs_from_element_plus(best_elem)

            # Complementa com paragrafos irmaos quando o bloco principal veio incompleto.
            if len("\n\n".join(paragraphs)) < max(500, self.config.min_article_chars // 2):
                for sibling in list(best_elem.find_previous_siblings(limit=3))[::-1] + list(best_elem.find_next_siblings(limit=5)):
                    if sibling and getattr(sibling, "name", None) in {"p", "div", "section"}:
                        sibling_texts = self._paragraphs_from_element_plus(sibling)
                        for paragraph in sibling_texts:
                            if paragraph not in paragraphs and self._looks_like_news_paragraph(paragraph):
                                paragraphs.append(paragraph)

            article_text = "\n\n".join(paragraphs).strip()
            if len(article_text) < 120:
                return None

            return {
                "title": self._extract_title(soup),
                "article_text": article_text,
                "author": self._extract_author_meta(html),
                "published_date": self._extract_date_meta(html),
                "images": self._extract_images_from_html(html, url),
                "url": url,
                "newspaper_plus_score": round(best_score, 2),
            }

        except Exception as e:
            logger.debug(f"Newspaper Plus falhou: {e}")
            return None

    def _limpar_soup_plus(self, soup: BeautifulSoup) -> None:
        """Remove boilerplate comum antes do score textual."""
        extra_tags = set(HTML_CLEANUP_TAGS) | {
            "aside", "noscript", "svg", "canvas", "form", "button",
            "input", "select", "textarea", "iframe", "style", "script",
        }
        for tag_name in extra_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        negative_re = re.compile(
            r"(menu|nav|sidebar|footer|header|share|social|coment|comment|"
            r"newsletter|related|relacionad|publicidade|advert|ads|banner|"
            r"cookie|login|modal|paywall|assinatura|breadcrumb)",
            re.I,
        )
        for elem in soup.find_all(True):
            ident = " ".join(
                str(x) for x in [
                    elem.get("id", ""),
                    " ".join(elem.get("class", []) if isinstance(elem.get("class"), list) else [elem.get("class", "")]),
                    elem.get("role", ""),
                    elem.get("aria-label", ""),
                ]
            )
            if negative_re.search(ident):
                text_len = len(elem.get_text(" ", strip=True))
                # Nao apaga bloco grande, apenas elementos curtos claramente de ruido.
                if text_len < 600:
                    elem.decompose()

    def _newspaper_node_score(self, elem: Any) -> float:
        text = elem.get_text(" ", strip=True)
        text_len = len(text)
        if text_len < 80:
            return -1000.0

        p_count = len(elem.find_all("p"))
        link_density = self._link_density_plus(elem)
        stopwords = self._pt_stopword_count(text)
        punctuation = text.count(".") + text.count("!") + text.count("?")

        ident = " ".join(
            str(x).lower() for x in [
                elem.name or "",
                elem.get("id", ""),
                " ".join(elem.get("class", []) if isinstance(elem.get("class"), list) else [elem.get("class", "")]),
            ]
        )

        positive = 0
        negative = 0
        if re.search(r"(article|materia|mat[eé]ria|noticia|notícia|post|entry|story|content|texto|corpo|main)", ident):
            positive += 1
        if re.search(r"(menu|nav|sidebar|footer|header|share|social|coment|related|publicidade|advert|ads|banner|cookie)", ident):
            negative += 1

        score = 0.0
        score += min(text_len, 12000) / 8.0
        score += p_count * 80
        score += stopwords * 7
        score += punctuation * 12
        score += positive * 350
        score -= negative * 500
        score -= link_density * 1600
        return score

    def _paragraphs_from_element_plus(self, elem: Any) -> List[str]:
        paragraphs: List[str] = []
        tags = elem.find_all(["p", "h2", "h3", "blockquote", "li"])
        if not tags:
            raw = elem.get_text("\n", strip=True)
            tags_text = [x.strip() for x in raw.split("\n")]
        else:
            tags_text = [tag.get_text(" ", strip=True) for tag in tags]

        seen = set()
        for text in tags_text:
            text = self._clean_inline_text_plus(text)
            if not text or text in seen:
                continue
            if self._looks_like_news_paragraph(text):
                paragraphs.append(text)
                seen.add(text)
        return paragraphs

    def _looks_like_news_paragraph(self, text: str) -> bool:
        if not text:
            return False
        t = text.strip()
        if len(t) < 35:
            return False
        if len(t.split()) < 6:
            return False
        lower = t.lower()
        bad_starts = (
            "publicidade", "continua após", "leia também", "leia mais",
            "receba as notícias", "siga o", "compartilhe", "comentários",
            "newsletter", "cookies", "assine", "entrar", "cadastre-se",
        )
        if lower.startswith(bad_starts):
            return False
        if self._pt_stopword_count(t) < 2 and len(t) < 180:
            return False
        return True

    def _clean_inline_text_plus(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        text = re.sub(r"^(PUBLICIDADE|Publicidade|publicidade)\s*[:\-–—]?\s*", "", text).strip()
        return text

    def _link_density_plus(self, elem: Any) -> float:
        text_len = len(elem.get_text(" ", strip=True))
        if text_len <= 0:
            return 1.0
        link_text_len = sum(len(a.get_text(" ", strip=True)) for a in elem.find_all("a"))
        return min(1.0, link_text_len / max(1, text_len))

    def _pt_stopword_count(self, text: str) -> int:
        stopwords = {
            "a", "ao", "aos", "as", "às", "com", "como", "da", "das", "de",
            "do", "dos", "e", "em", "entre", "foi", "foram", "há", "mais",
            "mas", "na", "nas", "no", "nos", "o", "os", "ou", "para",
            "pela", "pelo", "por", "que", "se", "sem", "ser", "sobre",
            "também", "um", "uma", "à", "após", "até", "contra", "desde",
            "durante", "ele", "ela", "eles", "elas", "são", "tem", "ter",
        }
        words = re.findall(r"[A-Za-zÀ-ÿ]{2,}", (text or "").lower())
        return sum(1 for w in words if w in stopwords)


    # ------------------------------------------------------------------
    # 6. WordPress REST API (fallback 5)
    # ------------------------------------------------------------------

    async def _extract_wordpress_rest(
        self, url: str
    ) -> Optional[Dict[str, Any]]:
        """Tenta extrair via WordPress REST API."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        endpoints = [
            f"{base}/?rest_route=/wp/v2/posts&per_page=1&_embed",
            f"{base}/wp-json/wp/v2/posts?per_page=1&_embed",
        ]

        for endpoint in endpoints:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        endpoint,
                        timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                        headers={"User-Agent": get_random_ua()},
                    ) as response:
                        if response.status != 200:
                            continue

                        data = await response.json()
                        if not isinstance(data, list) or not data:
                            continue

                        post = data[0]

                        title = self._strip_html(
                            post.get("title", {}).get("rendered", "")
                        )
                        content = self._strip_html(
                            post.get("content", {}).get("rendered", "")
                        )
                        date_str = post.get("date", "")
                        pub_date = self._parse_iso_date(date_str)

                        # Autor
                        author = ""
                        embedded = post.get("_embedded", {})
                        authors = embedded.get("author", [])
                        if authors:
                            author = authors[0].get("name", "")

                        # Imagem
                        images = []
                        featured = embedded.get("wp:featuredmedia", [])
                        if featured:
                            img_url = featured[0].get("source_url", "")
                            if img_url:
                                images.append(img_url)

                        return {
                            "title": title,
                            "article_text": content,
                            "author": author or None,
                            "published_date": pub_date,
                            "images": images,
                            "url": url,
                        }

            except Exception as e:
                logger.debug(f"WordPress REST falhou ({endpoint}): {e}")
                continue

        return None

    # ------------------------------------------------------------------
    # Post-processamento
    # ------------------------------------------------------------------

    def _post_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Limpa e formata o resultado final.

        - Preserva paragrafos
        - Remove espacos excessivos
        - Garante que nao seja bloco unico
        """
        text = result.get("article_text", "")
        if not text:
            return result

        # Normaliza quebras de linha
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Remove linhas vazias excessivas
        lines = text.split("\n")
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not prev_empty:
                    cleaned_lines.append("")
                    prev_empty = True
            else:
                cleaned_lines.append(stripped)
                prev_empty = False

        # Junta paragrafos com linha em branco
        text = "\n\n".join(
            " ".join(p.split()) for p in "\n".join(cleaned_lines).split("\n\n")
        )

        # Remove padroes de boilerplate comuns
        boilerplate_patterns = [
            r"Read more.*",
            r"Subscribe now.*",
            r"Advertisement.*",
            r"Share this article.*",
            r"Follow us.*",
            r"Comments.*",
            r"Related articles.*",
            r"Continue reading.*",
            r"Click here to.*",
            r"Sign up for.*",
        ]
        for pattern in boilerplate_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        result["article_text"] = text.strip()
        result["chars"] = len(result["article_text"])

        # Garante que images seja uma lista
        if "images" not in result:
            result["images"] = []

        return result

    def _is_valid(self, result: Dict[str, Any]) -> bool:
        """Verifica se o resultado tem texto suficiente."""
        text = result.get("article_text", "")
        return isinstance(text, str) and len(text) >= self.config.min_article_chars


    def _merge_html_metadata(self, result: Dict[str, Any], html: str, url: str) -> Dict[str, Any]:
        """Enriquece qualquer metodo com metadados de HTML.

        Inspirado no newspaper4k: titulo visivel, canonical, OpenGraph,
        Twitter Cards, JSON-LD, meta author/date e lista de imagens.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return result

        if not result.get("title"):
            result["title"] = self._extract_title(soup)

        if not result.get("author"):
            result["author"] = self._extract_author_meta(html)

        if not result.get("published_date"):
            result["published_date"] = self._extract_date_meta(html)

        canonical = self._extract_canonical_url(soup, url)
        if canonical:
            result["canonical_url"] = canonical
            result.setdefault("url", canonical)

        description = self._extract_description_meta(soup)
        if description:
            result.setdefault("description", description)

        images = list(result.get("images") or [])
        images.extend(self._extract_images_from_soup(soup, url))
        result["images"] = self._dedupe_images_plus(images)
        if result["images"] and not result.get("image"):
            result["image"] = result["images"][0]

        return result

    def _extract_description_meta(self, soup: BeautifulSoup) -> Optional[str]:
        for attrs in (
            {"property": "og:description"},
            {"name": "twitter:description"},
            {"name": "description"},
        ):
            meta = soup.find("meta", attrs=attrs)
            if meta and meta.get("content"):
                return str(meta["content"]).strip()
        return None

    def _extract_canonical_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        for selector in (
            ('link', {"rel": lambda value: value and "canonical" in value}),
            ('meta', {"property": "og:url"}),
        ):
            tag = soup.find(selector[0], attrs=selector[1])
            if tag:
                href = tag.get("href") or tag.get("content")
                if href:
                    return self._absolute_url_plus(str(href), base_url)
        return None

    def _extract_images_from_html(self, html: str, url: str) -> List[str]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            return self._extract_images_from_soup(soup, url)
        except Exception:
            return []

    def _extract_images_from_soup(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        images: List[str] = []

        # 1) OpenGraph/Twitter/link rel image_src
        meta_selectors = [
            {"property": "og:image"},
            {"property": "og:image:secure_url"},
            {"name": "twitter:image"},
            {"name": "twitter:image:src"},
            {"itemprop": "image"},
        ]
        for attrs in meta_selectors:
            meta = soup.find("meta", attrs=attrs)
            if meta and meta.get("content"):
                images.append(self._absolute_url_plus(str(meta["content"]), base_url))

        link_img = soup.find("link", rel=lambda value: value and "image_src" in value)
        if link_img and link_img.get("href"):
            images.append(self._absolute_url_plus(str(link_img["href"]), base_url))

        # 2) JSON-LD image/logo/thumbnailUrl
        for item in self._iter_jsonld_items(soup):
            for key in ("image", "thumbnailUrl", "logo"):
                images.extend(self._extract_jsonld_image_values(item.get(key), base_url))

        # 3) Imagens dentro do artigo/main/body, com srcset e data-src.
        containers = soup.select("article, main, [role=main], .article-content, .post-content, .entry-content")
        if not containers and soup.body:
            containers = [soup.body]
        for container in containers[:3]:
            for img in container.find_all("img"):
                for attr in ("src", "data-src", "data-original", "data-lazy-src"):
                    src = img.get(attr)
                    if src:
                        images.append(self._absolute_url_plus(str(src), base_url))
                srcset = img.get("srcset") or img.get("data-srcset")
                if srcset:
                    images.extend(self._images_from_srcset_plus(str(srcset), base_url))

        return self._dedupe_images_plus(images)

    def _iter_jsonld_items(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                if "@graph" in value and isinstance(value["@graph"], list):
                    for child in value["@graph"]:
                        walk(child)
                else:
                    items.append(value)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text() or ""
            raw = raw.strip()
            if not raw:
                continue
            try:
                walk(json.loads(raw))
            except Exception:
                continue
        return items

    def _extract_jsonld_image_values(self, value: Any, base_url: str) -> List[str]:
        out: List[str] = []
        if not value:
            return out
        if isinstance(value, str):
            out.append(self._absolute_url_plus(value, base_url))
        elif isinstance(value, dict):
            for key in ("url", "contentUrl", "@id"):
                if value.get(key):
                    out.append(self._absolute_url_plus(str(value[key]), base_url))
        elif isinstance(value, list):
            for item in value:
                out.extend(self._extract_jsonld_image_values(item, base_url))
        return out

    def _images_from_srcset_plus(self, srcset: str, base_url: str) -> List[str]:
        urls: List[str] = []
        for candidate in srcset.split(","):
            part = candidate.strip().split(" ")[0].strip()
            if part:
                urls.append(self._absolute_url_plus(part, base_url))
        return urls

    def _absolute_url_plus(self, value: str, base_url: str) -> str:
        value = (value or "").strip()
        if not value:
            return ""
        if value.startswith("//"):
            parsed = urlparse(base_url)
            value = f"{parsed.scheme}:{value}"
        return urljoin(base_url, value)

    def _dedupe_images_plus(self, images: List[str]) -> List[str]:
        out: List[str] = []
        seen: set[str] = set()
        bad = re.compile(r"(sprite|logo|favicon|avatar|placeholder|blank|pixel|1x1|transparent|loading)", re.I)
        for img in images:
            if not img:
                continue
            img = img.strip()
            if not img.startswith(("http://", "https://")):
                continue
            if bad.search(img):
                continue
            key = img.split("#", 1)[0]
            key = re.sub(r"([?&])(utm_[^=&]+|fbclid|gclid|cache|v)=[^&]+", "", key, flags=re.I)
            if key in seen:
                continue
            seen.add(key)
            out.append(img)
        return out[:12]


    def _empty_result(self, method: str) -> Dict[str, Any]:
        """Retorna resultado vazio."""
        return {
            "article_text": None,
            "title": None,
            "author": None,
            "published_date": None,
            "images": [],
            "url": None,
            "method": f"failed_{method}",
            "chars": 0,
        }

    # ------------------------------------------------------------------
    # Extratores de metadata
    # ------------------------------------------------------------------

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrai titulo do HTML."""
        # og:title
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"].strip()

        # twitter:title
        tw = soup.find("meta", attrs={"name": "twitter:title"})
        if tw and tw.get("content"):
            return tw["content"].strip()

        # <title>
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        # <h1>
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return None

    def _extract_author_meta(self, html: str) -> Optional[str]:
        """Extrai autor de meta tags do HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")

            # author meta
            for name in ["author", "sauthor", "article:author", "og:author"]:
                meta = soup.find("meta", attrs={"name": name}) or soup.find(
                    "meta", property=name
                )
                if meta and meta.get("content"):
                    return meta["content"].strip()

            # Schema.org author
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string or "{}")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        author_data = item.get("author")
                        if isinstance(author_data, dict):
                            return author_data.get("name")
                        elif isinstance(author_data, list) and author_data:
                            return author_data[0].get("name") if isinstance(author_data[0], dict) else str(author_data[0])
                except Exception:
                    continue

        except Exception:
            pass

        return None

    def _extract_date_meta(self, html: str) -> Optional[datetime]:
        """Extrai data de publicacao de meta tags."""
        try:
            soup = BeautifulSoup(html, "html.parser")

            for name in [
                "article:published_time",
                "publishedDate",
                "datePublished",
                "og:updated_time",
                "date",
            ]:
                meta = soup.find("meta", property=name) or soup.find(
                    "meta", attrs={"name": name}
                )
                if meta and meta.get("content"):
                    dt = self._parse_iso_date(meta["content"])
                    if dt:
                        return dt

        except Exception:
            pass

        return None

    def _parse_iso_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse de data ISO 8601."""
        if not date_str:
            return None

        date_str = date_str.strip()

        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        return None

    def _strip_html(self, html: str) -> str:
        """Remove tags HTML de uma string."""
        if not html:
            return ""
        try:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator=" ", strip=True)
        except Exception:
            # Fallback com regex
            return re.sub(r"<[^>]+>", " ", html).strip()
