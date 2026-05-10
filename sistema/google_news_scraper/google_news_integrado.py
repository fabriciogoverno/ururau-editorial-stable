"""
Integracao profunda do google_news_scraper no motor Ururau.
Consolida: google_news_scraper_v108, http_fetch_v109, kimim_bridge_v110

Carrega:
- consultas de consultas_google_news.json
- aliases de aliases_editoriais.json
- prioridades de fontes_oficiais_prioritarias.json
- config de radar_audiencia_config_v88.json

Integra com formato de pauta do Ururau (dict padrao).

Uso:
    integrado = GoogleNewsIntegrado()
    async with integrado:
        pautas = await integrado.coletar_por_termos_config()
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .extractor import ArticleExtractor
from .logger import get_logger
from .models import Article, CountryCode, LanguageCode, ScraperConfig, SearchParams
from .scraper import GoogleNewsScraper
from .utils import is_within_window
from sistema.ururau_ai_auditor.fonte_validada import validar_resultado_fonte

logger = get_logger("ururau.integracao")

# ---------------------------------------------------------------------------
# Mapeamentos
# ---------------------------------------------------------------------------

CANAL_MAP: Dict[str, str] = {
    "alerj": "Política",
    "governo_rj": "Estado RJ",
    "rj_politica": "Política",
    "rj_policia": "Polícia",
    "campos_local": "Cidades",
    "norte_fluminense": "Cidades",
    "porto_do_acu": "Economia",
    "servico_brasil": "Serviço",
    "alto_trafego_brasil": "Brasil",
    "alertas_globais": "Brasil e Mundo",
    "deputados_rj": "Política",
    "pre_candidatos_governo_rj": "Política",
    "transparencia_e_investigacao": "Política",
    "utilidade_publica_rj": "Estado RJ",
    "rj_esporte": "Esportes",
}

REGIAO_MAP: Dict[str, str] = {
    "campos_local": "Campos dos Goytacazes",
    "norte_fluminense": "Norte Fluminense",
    "porto_do_acu": "São João da Barra",
    "rj_politica": "Rio de Janeiro",
    "rj_policia": "Rio de Janeiro",
    "governo_rj": "Rio de Janeiro",
    "alerj": "Rio de Janeiro",
    "deputados_rj": "Rio de Janeiro",
    "macae": "Macaé",
    "quissama": "Quissamã",
}

CIDADE_MAP: Dict[str, str] = {
    "campos_local": "Campos dos Goytacazes",
    "norte_fluminense": "Campos dos Goytacazes",
    "porto_do_acu": "São João da Barra",
    "rj_politica": "Rio de Janeiro",
    "rj_policia": "Rio de Janeiro",
    "governo_rj": "Rio de Janeiro",
    "alerj": "Rio de Janeiro",
    "deputados_rj": "Rio de Janeiro",
    "macae": "Macaé",
    "quissama": "Quissamã",
}

# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------


class GoogleNewsIntegrado:
    """Interface unica para coleta Google News no Ururau.

    Uso:
        integrado = GoogleNewsIntegrado()
        async with integrado:
            pautas = await integrado.coletar_por_termos_config()
    """

    def __init__(
        self,
        config_path: str = "radar_audiencia_config_v88.json",
        aliases_path: str = "aliases_editoriais.json",
        consultas_path: str = "consultas_google_news.json",
        fontes_path: str = "fontes_oficiais_prioritarias.json",
        scraper_config: Optional[ScraperConfig] = None,
    ):
        self.scraper = GoogleNewsScraper(scraper_config)
        self.extractor = ArticleExtractor(scraper_config)

        # Carrega configs JSON
        self.config = self._carregar_json(config_path) or {}
        self.aliases = self._carregar_json(aliases_path) or {}
        self.consultas = self._carregar_json(consultas_path) or {}
        self.fontes = self._carregar_json(fontes_path) or {}

        # Extrai termos prioritarios
        self.termos_prioritarios = self.config.get("termos_prioritarios", [])
        self.termos_baixa_prioridade = self.config.get(
            "termos_baixa_prioridade", []
        )

        # Cache de fontes oficiais (dominios)
        self._fontes_oficiais_dominios: set = set()
        if self.fontes:
            fontes_list = self.fontes.get("fontes", [])
            for f in fontes_list:
                if f.get("ativo"):
                    url = f.get("url", "")
                    if url:
                        from .utils import extract_domain
                        self._fontes_oficiais_dominios.add(
                            extract_domain(url)
                        )

    def _carregar_json(self, path: str) -> Optional[Dict[str, Any]]:
        """Tenta carregar JSON de multiplos locais."""
        # Busca tolerante: diretório atual, raiz do projeto Ururau e pais.
        caminhos = []
        candidatos_base = [
            os.getcwd(),
            os.path.dirname(os.getcwd()),
            os.path.dirname(os.path.dirname(os.getcwd())),
            "/mnt/agents/upload",
        ]
        for base in candidatos_base:
            caminhos.append(os.path.join(base, path))
        caminhos.extend([path, f"./{path}", f"../{path}", f"../../{path}", f"../../upload/{path}"])
        for p in caminhos:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Erro carregando {p}: {e}")
                    continue
        logger.debug(f"Arquivo nao encontrado: {path}")
        return None

    async def __aenter__(self) -> "GoogleNewsIntegrado":
        await self.scraper.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.scraper.__aexit__(*args)

    # ------------------------------------------------------------------
    # Coleta por termos do config
    # ------------------------------------------------------------------

    async def coletar_por_termos_config(
        self,
        max_termos_por_ciclo: int = 20,
        max_resultados_por_termo: int = 3,
        janela_horas: int = 4,
        min_peso_termo: int = 18,
    ) -> List[Dict[str, Any]]:
        """Coleta Google News usando termos da watchlist.

        Fluxo:
        1. Carrega termos ativos do config
        2. Expande aliases
        3. Busca cada termo no Google News
        4. Resolve links reais
        5. Filtra por janela temporal
        6. Deduplica
        7. Converte para formato pauta Ururau

        Args:
            max_termos_por_ciclo: Maximo de termos por ciclo.
            max_resultados_por_termo: Maximo de resultados por termo.
            janela_horas: Janela temporal em horas.
            min_peso_termo: Peso minimo do termo.

        Returns:
            Lista de pautas no formato Ururau.
        """
        logger.info(
            f"[GNEWS] Buscando termos da watchlist, "
            f"janela={janela_horas}h, max={max_resultados_por_termo}/termo"
        )

        # Coleta termos ativos (exclui baixa prioridade)
        termos = [
            t for t in self.termos_prioritarios
            if t not in self.termos_baixa_prioridade
        ][:max_termos_por_ciclo]

        if not termos:
            logger.warning("Nenhum termo prioritario encontrado")
            return []

        todas_pautas: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(3)  # Max 3 buscas concorrentes

        async def _buscar_termo(termo: str) -> List[Dict[str, Any]]:
            async with semaphore:
                try:
                    params = SearchParams(
                        query=termo,
                        max_results=max_resultados_por_termo,
                        country=CountryCode.BR,
                        language=LanguageCode.PT,
                    )
                    articles = await self.scraper.search(params)
                    pautas = [
                        self.converter_para_pauta_ururau(a, termo_busca=termo)
                        for a in articles
                    ]
                    logger.info(
                        f"[GNEWS] Termo '{termo}': {len(pautas)} entrada(s)"
                    )
                    return pautas
                except Exception as e:
                    logger.warning(f"Erro buscando '{termo}': {e}")
                    return []

        # Busca todos os termos em paralelo
        tasks = [_buscar_termo(t) for t in termos]
        resultados = await asyncio.gather(*tasks)

        for pautas in resultados:
            todas_pautas.extend(pautas)

        # Filtra janela temporal
        todas_pautas = self.filtrar_janela_temporal(
            todas_pautas, janela_horas
        )

        # Deduplica
        todas_pautas = self.deduplicar_por_url(todas_pautas)

        # Ordena por score
        todas_pautas.sort(key=lambda x: x.get("score", 0), reverse=True)

        logger.info(
            f"[GNEWS] Total: {len(todas_pautas)} pautas unicas"
        )
        return todas_pautas

    # ------------------------------------------------------------------
    # Coleta por termo livre
    # ------------------------------------------------------------------

    async def coletar_por_termo_livre(
        self,
        termo: str,
        max_resultados: int = 10,
        janela_horas: int = 4,
    ) -> List[Dict[str, Any]]:
        """Coleta por termo livre (busca ad-hoc).

        Args:
            termo: Termo de busca livre.
            max_resultados: Maximo de resultados.
            janela_horas: Janela temporal.

        Returns:
            Lista de pautas no formato Ururau.
        """
        logger.info(f"[GNEWS] Busca livre: '{termo}'")

        # Expande aliases
        termos_expandidos = self.resolver_aliases(termo)
        todas_pautas: List[Dict[str, Any]] = []

        for t in termos_expandidos:
            params = SearchParams(
                query=t,
                max_results=max_resultados,
                country=CountryCode.BR,
                language=LanguageCode.PT,
            )
            articles = await self.scraper.search(params)
            pautas = [
                self.converter_para_pauta_ururau(a, termo_busca=t)
                for a in articles
            ]
            todas_pautas.extend(pautas)

        # Filtra e deduplica
        todas_pautas = self.filtrar_janela_temporal(
            todas_pautas, janela_horas
        )
        todas_pautas = self.deduplicar_por_url(todas_pautas)
        todas_pautas.sort(key=lambda x: x.get("score", 0), reverse=True)

        return todas_pautas

    # ------------------------------------------------------------------
    # Coleta por grupo tematico
    # ------------------------------------------------------------------

    async def coletar_grupo_tematico(
        self,
        grupo: str,
        max_por_grupo: int = 5,
        janela_horas: int = 4,
    ) -> List[Dict[str, Any]]:
        """Coleta usando consultas pre-definidas de um grupo tematico.

        Grupos disponiveis (de consultas_google_news.json):
        - campos_local, norte_fluminense, porto_do_acu
        - rj_politica, rj_policia, governo_rj, alerj
        - deputados_rj, pre_candidatos_governo_rj
        - servico_brasil, alto_trafego_brasil, alertas_globais
        - utilidade_publica_rj, transparencia_e_investigacao

        Args:
            grupo: Nome do grupo tematico.
            max_por_grupo: Maximo de resultados por grupo.
            janela_horas: Janela temporal.

        Returns:
            Lista de pautas no formato Ururau.
        """
        logger.info(f"[GNEWS] Grupo tematico: '{grupo}'")

        consultas = self.consultas.get(grupo) if self.consultas else None
        if not consultas:
            logger.warning(f"Grupo '{grupo}' nao encontrado em consultas")
            return []

        todas_pautas: List[Dict[str, Any]] = []
        semaphore = asyncio.Semaphore(2)

        queries = consultas[:max_por_grupo]

        async def _buscar(query: str) -> List[Dict[str, Any]]:
            async with semaphore:
                params = SearchParams(
                    query=query,
                    max_results=3,
                    country=CountryCode.BR,
                    language=LanguageCode.PT,
                )
                articles = await self.scraper.search(params)
                return [
                    self.converter_para_pauta_ururau(
                        a, termo_busca=query, grupo=grupo
                    )
                    for a in articles
                ]

        tasks = [_buscar(q) for q in queries]
        resultados = await asyncio.gather(*tasks)

        for pautas in resultados:
            todas_pautas.extend(pautas)

        todas_pautas = self.filtrar_janela_temporal(
            todas_pautas, janela_horas
        )
        todas_pautas = self.deduplicar_por_url(todas_pautas)
        todas_pautas.sort(key=lambda x: x.get("score", 0), reverse=True)

        return todas_pautas

    # ------------------------------------------------------------------
    # Extracao de fonte
    # ------------------------------------------------------------------

    async def extrair_fonte_completa(
        self,
        url: str,
        min_chars: int = 1200,
    ) -> Dict[str, Any]:
        """Extrai texto completo de uma URL.

        Cascata: trafilatura -> readability -> jsonld -> bs4 -> wordpress

        Args:
            url: URL do artigo.
            min_chars: Minimo de caracteres para considerar OK.

        Returns:
            Dict com: texto, autor, data, imagens, metodo, chars.
        """
        logger.debug(f"[EXTRATOR] Iniciando extracao: {url}")

        result = await self.extractor.extract(url)

        chars = result.get("chars", 0)
        method = result.get("method", "unknown")

        # Se texto insuficiente, tenta com params relaxados
        if chars < min_chars and result.get("article_text"):
            logger.debug(
                f"[EXTRATOR] Texto curto ({chars} chars), "
                f"tentando params relaxados"
            )
            # Tenta novamente com min chars menor
            old_min = self.extractor.config.min_article_chars
            self.extractor.config.min_article_chars = min_chars // 2
            result2 = await self.extractor.extract(url)
            self.extractor.config.min_article_chars = old_min

            if result2.get("chars", 0) > chars:
                result = result2
                chars = result.get("chars", 0)
                method = result.get("method", "unknown")

        status = "OK" if chars >= min_chars else "CURTO"
        logger.info(
            f"[EXTRATOR] {status} {chars} chars via {method}: {url[:80]}"
        )

        return {
            "texto": result.get("article_text") or "",
            "autor": result.get("author") or "",
            "data": (
                result["published_date"].isoformat()
                if result.get("published_date")
                else ""
            ),
            "imagens": result.get("images", []),
            "metodo": method,
            "chars": chars,
            "url": url,
            "suficiente": chars >= min_chars,
        }

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def resolver_aliases(self, termo: str) -> List[str]:
        """Resolve aliases editoriais para um termo.

        Args:
            termo: Termo original.

        Returns:
            Lista com o termo original + aliases encontrados.
        """
        aliases_data = self.aliases.get("aliases", {})
        if not aliases_data:
            return [termo]

        termo_lower = termo.lower().strip()
        resultados = [termo]

        for chave, valor in aliases_data.items():
            if chave.lower() == termo_lower:
                # Adiciona aliases
                if isinstance(valor, list):
                    resultados.extend(valor)
                elif isinstance(valor, dict):
                    alias_list = valor.get("aliases", [])
                    if isinstance(alias_list, list):
                        resultados.extend(alias_list)
                break

            # Verifica se algum alias corresponde ao termo
            aliases_list: List[str] = []
            if isinstance(valor, list):
                aliases_list = [v.lower() for v in valor]
            elif isinstance(valor, dict):
                aliases_list = [
                    a.lower() for a in valor.get("aliases", [])
                ]

            if termo_lower in aliases_list:
                resultados.append(chave)
                if isinstance(valor, list):
                    resultados.extend(valor)
                elif isinstance(valor, dict):
                    resultados.extend(valor.get("aliases", []))
                break

        # Remove duplicatas preservando ordem
        unicos = []
        for r in resultados:
            r_stripped = r.strip()
            if r_stripped and r_stripped not in unicos:
                unicos.append(r_stripped)
        return unicos

    def filtrar_janela_temporal(
        self,
        pautas: List[Dict[str, Any]],
        horas: int = 4,
    ) -> List[Dict[str, Any]]:
        """Filtra pautas por janela temporal (ultimas N horas).

        Args:
            pautas: Lista de pautas.
            horas: Tamanho da janela.

        Returns:
            Pautas dentro da janela temporal.
        """
        agora = datetime.now(timezone.utc)
        resultado = []

        for p in pautas:
            data_str = p.get("data_publicacao")
            if not data_str:
                # Se nao tem data, mantem (nao filtra)
                resultado.append(p)
                continue

            try:
                if isinstance(data_str, str):
                    dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
                elif isinstance(data_str, datetime):
                    dt = data_str
                else:
                    resultado.append(p)
                    continue

                delta = agora - dt
                if delta <= __import__("datetime").timedelta(hours=horas):
                    resultado.append(p)
            except Exception:
                # Erro de parse — mantem a pauta
                resultado.append(p)

        return resultado

    def deduplicar_por_url(
        self,
        pautas: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Remove pautas com URL duplicada.

        Args:
            pautas: Lista de pautas.

        Returns:
            Pautas sem duplicatas (primeira ocorrencia mantida).
        """
        seen: set = set()
        resultado = []

        for p in pautas:
            url = p.get("url", "")
            url_norm = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url)
            chave = f"{url_norm.netloc}{url_norm.path}".lower().rstrip("/")

            if chave and chave not in seen:
                seen.add(chave)
                resultado.append(p)
            elif not chave:
                resultado.append(p)

        return resultado

    def calcular_score_pauta(self, pauta: Dict[str, Any]) -> int:
        """Calcula score editorial da pauta (0-100).

        Fatores:
        - Base: 50
        - Fonte oficial (+20)
        - Termo prioritario (+15)
        - Regiao prioritario (+10)
        - Texto fonte longo (+10)
        - Recencia < 1h (+15)
        - Tem autor (+10)
        - Tem imagem (+5)
        - Canal definido (+5)

        Args:
            pauta: Dict de pauta.

        Returns:
            Score entre 0 e 100.
        """
        score = 50  # Base

        # Fonte oficial
        dominio = pauta.get("dominio", "")
        if dominio in self._fontes_oficiais_dominios:
            score += 20

        # Termo prioritario
        termo = pauta.get("termo_busca", "").lower()
        if any(t.lower() in termo for t in self.termos_prioritarios):
            score += 15

        # Texto fonte longo
        chars = pauta.get("chars_fonte", 0)
        if chars > 2000:
            score += 10
        elif chars > 1200:
            score += 5

        # Recencia
        data_str = pauta.get("data_publicacao")
        if data_str:
            try:
                if isinstance(data_str, str):
                    dt = datetime.fromisoformat(
                        data_str.replace("Z", "+00:00")
                    )
                else:
                    dt = data_str
                agora = datetime.now(timezone.utc)
                delta = agora - dt
                if delta <= __import__("datetime").timedelta(hours=1):
                    score += 15
                elif delta <= __import__("datetime").timedelta(hours=2):
                    score += 8
            except Exception:
                pass

        # Tem autor
        if pauta.get("autor"):
            score += 10

        # Tem imagem
        if pauta.get("imagem") or pauta.get("imagens"):
            score += 5

        # Canal definido
        if pauta.get("canal_sugerido"):
            score += 5

        return min(100, score)

    def converter_para_pauta_ururau(
        self,
        article: Article,
        termo_busca: str = "",
        grupo: str = "",
    ) -> Dict[str, Any]:
        """Converte Article para dict de pauta no formato Ururau.

        Args:
            article: Article do google_news_scraper.
            termo_busca: Termo usado na busca.
            grupo: Grupo tematico.

        Returns:
            Pauta no formato Ururau.
        """
        data_iso = ""
        if article.published_date:
            if article.published_date.tzinfo is None:
                dt = article.published_date.replace(tzinfo=timezone.utc)
            else:
                dt = article.published_date
            data_iso = dt.isoformat()

        chars_fonte = len(article.article_text) if article.article_text else 0

        coletado_em = datetime.now(timezone.utc).isoformat()

        validacao_fonte = validar_resultado_fonte({
            "status": 200,
            "texto": article.article_text or "",
            "url": article.url
        })

        pauta: Dict[str, Any] = {
            "id": f"gnews_{abs(hash(article.url))}",
            "titulo": article.title,
            "descricao": article.description or "",
            "url": article.url,
            "dominio": article.domain,
            "autor": article.author or "",
            "data_publicacao": data_iso,
            "imagem": article.image or "",
            "imagens": article.images or [],
            "texto_fonte": article.article_text or "",
            "canal_sugerido": self._get_canal_por_grupo(grupo),
            "score": 0,
            "fonte_tipo": "google_news",
            "termo_busca": termo_busca,
            "metodo_extracao": "google_news_rss",
            "chars_fonte": chars_fonte,
            "cidade": self._get_cidade_por_grupo(grupo),
            "regiao": self._get_regiao_por_grupo(grupo),
            "coletado_em": coletado_em,
            "status": (
                "bloqueada_fonte"
                if not validacao_fonte["ok"]
                else "pendente" if chars_fonte >= self.extractor.config.min_article_chars
                else "hidratacao"
            ),
            "fonte_validada": validacao_fonte["ok"],
            "fonte_erro": validacao_fonte.get("erro"),
        }

        # Calcula score
        pauta["score"] = self.calcular_score_pauta(pauta)

        return pauta

    def _get_canal_por_grupo(self, grupo: str) -> str:
        """Mapeia grupo tematico para canal editorial."""
        return CANAL_MAP.get(grupo, "")

    def _get_regiao_por_grupo(self, grupo: str) -> str:
        """Mapeia grupo tematico para regiao."""
        return REGIAO_MAP.get(grupo, "")

    def _get_cidade_por_grupo(self, grupo: str) -> str:
        """Mapeia grupo tematico para cidade."""
        return CIDADE_MAP.get(grupo, "")
