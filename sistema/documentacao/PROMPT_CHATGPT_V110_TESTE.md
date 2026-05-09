# PROMPT PARA CHATGPT — Integração Google News Scraper no Ururau

> **Copie todo o conteúdo abaixo e cole no ChatGPT (ou Claude, Gemini, etc.)**
> **Modelo recomendado:** GPT-4, GPT-4o, Claude 3.5 Sonnet, o1, o3

---

```
Você é um engenheiro de software sênior especializado em Python async, 
web scraping e integração de sistemas. Sua tarefa é integrar o pacote 
`google_news_scraper` no sistema Ururau de monitoramento de notícias.

═══════════════════════════════════════════════════════════════════════
CONTEXTO
═══════════════════════════════════════════════════════════════════════

O Ururau é um sistema de monitoramento e publicação automática de 
notícias focado no Rio de Janeiro (Campos dos Goytacazes, Norte 
Fluminense). Ele evoluiu de v81 até v110 e agora precisa da v111.

Cada versão adicionou uma camada de coleta Google News:
- v108: google_news_scraper_v108.py (busca por termos + trafilatura)
- v109: http_fetch_v109.py (HTTP resiliente)
- v110: kimi_bridge_v110.py (ponte Kimi)

A v111 deve CONSOLIDAR todas essas camadas em uma única interface.

═══════════════════════════════════════════════════════════════════════
PACOTE google_news_scraper (JÁ EXISTE)
═══════════════════════════════════════════════════════════════════════

O pacote completo já foi desenvolvido e testado (74/74 testes passando).
Ele está nesta estrutura:

src/google_news_scraper/
├── __init__.py              # exports: Article, SearchParams, ScraperConfig, GoogleNewsScraper, ArticleExtractor
├── models.py                # Pydantic v2: Article, SearchParams, ScraperConfig, CountryCode, LanguageCode
├── config.py                # 12 UAs, DOMAIN_BLACKLIST, GOOGLE_NEWS_RSS_URL, GOOGLE_NEWS_HTML_URL
├── scraper.py               # GoogleNewsScraper — busca RSS + HTML, resolve redirects, dedup
├── extractor.py             # ArticleExtractor — cascata 5 métodos (trafilatura→readability→jsonld→bs4→wordpress)
├── utils.py                 # fetch_with_retry, DomainCooldown, deduplicate_by_key, extract_domain, is_within_window, parse_google_date
├── cli.py                   # CLI Click
├── logger.py                # get_logger()
└── google_news_integrado.py # GoogleNewsIntegrado — interface única para o Ururau

Cascata de extração:
1. trafilatura (primário) — via trafilatura.extract() + extract_metadata()
2. readability-lxml — via readability.Document()
3. JSON-LD — parse <script type="application/ld+json"> procura @type NewsArticle/Article
4. BS4 density — seleciona por densidade textual (texto/tags) em <article>, <main>, etc.
5. WordPress REST — tenta /?rest_route=/wp/v2/posts e /wp-json/wp/v2/posts

Mínimo de caracteres para aceitar: 900 (padrão), 1200 (monitor)

Formato de saída do google_news_integrado.py:

class GoogleNewsIntegrado:
    def __init__(
        self,
        config_path: str = "radar_audiencia_config_v88.json",
        aliases_path: str = "aliases_editoriais.json",
        consultas_path: str = "consultas_google_news.json",
        fontes_path: str = "fontes_oficiais_prioritarias.json",
        scraper_config: Optional[ScraperConfig] = None,
    )
    
    async def coletar_por_termos_config(max_termos, max_resultados, janela_horas, min_peso) -> List[Dict]
    async def coletar_por_termo_livre(termo, max_resultados, janela_horas) -> List[Dict]
    async def coletar_grupo_tematico(grupo, max_por_grupo, janela_horas) -> List[Dict]
    async def extrair_fonte_completa(url, min_chars) -> Dict  # {texto, autor, data, imagens, metodo, chars, suficiente}
    def resolver_aliases(termo) -> List[str]
    def filtrar_janela_temporal(pautas, horas) -> List[Dict]
    def deduplicar_por_url(pautas) -> List[Dict]
    def calcular_score_pauta(pauta) -> int  # 0-100
    def converter_para_pauta_ururau(article, termo_busca, grupo) -> Dict

A pauta retornada tem este formato EXATO:
{
    "titulo": str,
    "descricao": str,
    "url": str,
    "dominio": str,
    "autor": str,
    "data_publicacao": str,  # ISO 8601
    "imagem": str,
    "imagens": List[str],
    "texto_fonte": str,
    "canal_sugerido": str,
    "score": int,  # 0-100
    "fonte_tipo": "google_news",
    "termo_busca": str,
    "metodo_extracao": str,
    "chars_fonte": int,
    "cidade": str,
    "regiao": str,
}

Mapeamentos internos do integrado:
CANAL_MAP = {
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
}

REGIAO_MAP = {
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

CIDADE_MAP = {
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

Cálculo de score:
- Base: 50
- +20 se domínio em fontes_oficiais_prioritarias
- +15 se termo em termos_prioritarios
- +10 se chars_fonte > 2000 (+5 se > 1200)
- +15 se recência < 1h (+8 se < 2h)
- +10 se tem autor
- +5 se tem imagem
- +5 se canal definido
- Clamp: min(100, score)

═══════════════════════════════════════════════════════════════════════
CONFIGS DO URURAU (JSONs já existem no projeto)
═══════════════════════════════════════════════════════════════════════

1. radar_audiencia_config_v88.json:
{
  "versao": "v88_radar_audiencia",
  "termos_prioritarios": ["anvisa","fgts","eduardo paes","douglas ruas","alerj","campos","norte fluminense","porto do açu","polícia","governo rj"],
  "termos_baixa_prioridade": ["bbb","casa do patrão","rafaella justus","luana piovani","fofoca"],
  "geo_prioritario": ["BR-RJ","BR"],
  "janela_horas": 4
}

2. aliases_editoriais.json:
{
  "aliases": {
    "porto do açu": ["porto do acu","porto açu","porto acu","portoacu"],
    "alerj": ["assembleia legislativa do rio","assembleia legislativa do estado do rio de janeiro","assembleia legislativa rj","assembleia do rio","assembleia fluminense"],
    "cláudio castro": ["claudio castro","governador castro","claudio","castro governador"],
    "wladimir garotinho": ["wladimir","garotinho filho","vladimir garotinho"],
    "campos dos goytacazes": ["campos rj","campos norte fluminense","campos goytacazes","municipio campos","cidade campos"],
    "norte fluminense": ["norte-fluminense","norte do rio","interior norte rj"],
    "prumo logística": ["prumo","prumo porto","prumo açu"],
    "uenf": ["universidade estadual norte fluminense","universidade norte fluminense","uenf campos"],
    "iff": ["instituto federal fluminense","iff campos","if fluminense"],
    "tce-rj": ["tribunal de contas rj","tribunal de contas do estado do rio"],
    "mprj": ["ministério público rj","ministério público do rio","mp estadual rj"],
    "tjrj": ["tribunal de justiça rj","tribunal de justiça do rio"],
    "tre-rj": ["tribunal regional eleitoral rj","tre rio de janeiro"],
    "pmerj": ["polícia militar rj","pm rj","pm rio de janeiro"],
    "pcerj": ["polícia civil rj","pc rj","policia civil rio"]
  }
}

3. consultas_google_news.json:
{
  "campos_local": ["Campos dos Goytacazes","Campos RJ notícias","Campos dos Goytacazes prefeitura","Campos dos Goytacazes segurança","Campos dos Goytacazes saúde","Campos dos Goytacazes educação","Campos dos Goytacazes economia","WRA Campos","UENF Campos","IFF Campos"],
  "norte_fluminense": ["Norte Fluminense notícias","Norte Fluminense RJ","Macaé RJ","São João da Barra","São Francisco de Itabapoana","Quissamã RJ","Rio das Ostras RJ","Itaperuna RJ","Santo Antônio de Pádua RJ","Bom Jesus do Itabapoana"],
  "porto_do_acu": ["Porto do Açu","Porto Açu São João da Barra","Prumo Logística","Porto do Açu petróleo","Porto do Açu empregos","Porto do Açu investimento","Porto do Açu expansão","Porto do Açu terminal","Porto do Açu contratos","Porto Açu obras"],
  "rj_politica": ["Rio de Janeiro política","RJ governo estado","governo Rio de Janeiro","secretaria estado Rio de Janeiro"],
  "rj_policia": ["RJ policia operação","Rio de Janeiro policia","segurança pública Rio de Janeiro","PMERJ operação","PCERJ delegacia Rio"],
  "governo_rj": ["Cláudio Castro governador","governo estado Rio de Janeiro","decreto estadual Rio de Janeiro","secretaria estado RJ"],
  "alerj": ["ALERJ assembleia legislativa Rio","ALERJ votação","ALERJ projeto lei","assembleia legislativa Rio de Janeiro","deputado estadual Rio de Janeiro"],
  "deputados_rj": ["deputado estadual RJ","Wladimir Garotinho","Rodrigo Bacellar","Andre Correa deputado","Brazão ALERJ"],
  "pre_candidatos_governo_rj": ["candidato governador Rio 2026","pré-candidato governador RJ","eleição governador Rio de Janeiro 2026","Cláudio Castro reeleição","Wladimir Garotinho candidato"],
  "servico_brasil": ["INSS benefício","Receita Federal imposto","concurso público federal","FGTS saque","Bolsa Família pagamento","tarifa energia elétrica"],
  "alto_trafego_brasil": ["operação policial preso","desastre mortos Brasil","crise política Brasil","eleição 2026 pesquisa","STF decisão","greve nacional"],
  "alertas_globais": ["terremoto hoje","tsunami alerta","crise internacional","guerra conflito"],
  "utilidade_publica_rj": ["concurso público Rio de Janeiro","vagas emprego RJ","interdição via Rio de Janeiro","apagão Rio de Janeiro","transporte público Rio de Janeiro greve"],
  "transparencia_e_investigacao": ["licitação suspeita Rio de Janeiro","TCE-RJ auditoria","MPRJ investigação","DOERJ exoneração nomeação","convênio repasse RJ","emenda parlamentar RJ"]
}

4. fontes_oficiais_prioritarias.json:
{
  "fontes": [
    {"nome": "ALERJ - Notícias", "url": "https://www.alerj.rj.gov.br/", "ativo": true, "peso": 18, "escopo": "estado_rj", "tipo": "legislativo", "canal_forcado": "Política"},
    {"nome": "TCE-RJ", "url": "https://www.tce.rj.gov.br/", "ativo": true, "peso": 15, "escopo": "estado_rj", "tipo": "controle_externo", "canal_forcado": "Estado RJ"},
    {"nome": "MPRJ", "url": "https://www.mprj.mp.br/", "ativo": true, "peso": 15, "escopo": "estado_rj", "tipo": "ministerio_publico"},
    {"nome": "Prefeitura Campos dos Goytacazes", "url": "https://www.campos.rj.gov.br/", "ativo": true, "peso": 16, "escopo": "local", "tipo": "poder_executivo_municipal", "canal_forcado": "Cidades"},
    {"nome": "Porto do Açu - Prumo", "url": "https://www.portodoacu.com.br/", "ativo": true, "peso": 20, "escopo": "local", "tipo": "entidade_estrategica", "canal_forcado": "Economia"},
    {"nome": "TJRJ", "url": "https://www.tjrj.jus.br/", "ativo": true, "peso": 12, "escopo": "estado_rj", "tipo": "poder_judiciario"},
    {"nome": "TRE-RJ", "url": "https://www.tre-rj.jus.br/", "ativo": true, "peso": 12, "escopo": "estado_rj", "tipo": "tribunal_eleitoral", "canal_forcado": "Política"}
  ]
}

═══════════════════════════════════════════════════════════════════════
VARIÁVEIS .ENV A ADICIONAR
═══════════════════════════════════════════════════════════════════════

# ===== v111 — Integração Google News Scraper =====
URURAU_V111_GNEWS_INTEGRADO=1
URURAU_V111_GNEWS_MAX_TERMOS_POR_CICLO=20
URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO=3
URURAU_V111_GNEWS_JANELA_HORAS=4
URURAU_V111_GNEWS_MIN_CHARS_FONTE=1200
URURAU_V111_USAR_EXTRACAO_COMPLETA=1
URURAU_V111_SCORE_MINIMO_PAUTA=65

# Flags de compatibilidade (mantém fallback legado se necessário)
URURAU_V110_MONITOR_GNEWS_LEGADO=0
URURAU_V108_GNEWS_TERMOS=0
URURAU_V105_USAR_BING_NEWS=0

═══════════════════════════════════════════════════════════════════════
O QUE VOCÊ PRECISA ENTREGAR
═══════════════════════════════════════════════════════════════════════

Crie os seguintes arquivos NO PROJETO URURAU existente:

─────────────────────────────────────────────────────────────────
ARQUIVO 1: ururau/coleta/gnews_v111_integrado.py
─────────────────────────────────────────────────────────────────

Este é o WRAPPER operacional que conecta o GoogleNewsIntegrado ao Ururau.

REQUISITOS:
1. Importar do pacote google_news_scraper:
   from google_news_scraper.google_news_integrado import GoogleNewsIntegrado
   from google_news_scraper.models import ScraperConfig

2. Implementar estas funções:

async def coletar_pautas_gnews_v111(
    modo: str = "termos_config",
    termo: str = "",
    grupo: str = "",
    janela_horas: int = None,
    max_resultados: int = None,
) -> List[Dict[str, Any]]:
    """
    Modos:
    - "termos_config": usa coletar_por_termos_config() do integrado
    - "termo_livre": usa coletar_por_termo_livre()
    - "grupo": usa coletar_grupo_tematico()
    
    Se janela_horas/max_resultados forem None, usa os valores do .env:
    - URURAU_V111_GNEWS_JANELA_HORAS (default 4)
    - URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO (default 3)
    """

async def extrair_fonte_v111(url: str) -> Dict[str, Any]:
    """
    Usa GoogleNewsIntegrado.extrair_fonte_completa()
    min_chars vem de URURAU_V111_GNEWS_MIN_CHARS_FONTE (default 1200)
    Retorna: {texto, autor, data, imagens, metodo, chars, url, suficiente}
    """

def _get_env_int(key: str, default: int) -> int:
    """Helper para ler int do os.environ"""

3. LOGS: Todas as operações devem logar com prefixo [V111][GNEWS]:
   logger.info("[V111][GNEWS] Iniciando coleta por termos")
   logger.info(f"[V111][GNEWS] Termo '{termo}': {n} entrada(s)")
   logger.info(f"[V111][FONTE] OK {chars} chars via {metodo}: {url}")
   logger.warning(f"[V111][FONTE] CURTO {chars} chars: {url}")

4. O wrapper deve carregar os JSONs do diretório do projeto Ururau
   (não do google_news_scraper). Use os.path.exists() para encontrar
   os arquivos em múltiplos locais possíveis.

─────────────────────────────────────────────────────────────────
ARQUIVO 2: ururau/publisher/monitor_v111_patch.py
─────────────────────────────────────────────────────────────────

Este é o ADAPTADOR que conecta o novo coletor ao ciclo do monitor.

REQUISITOS:
1. Verificar no início de cada ciclo do monitor:
   if os.environ.get("URURAU_V111_GNEWS_INTEGRADO") == "1":
       usar coletor v111
   elif os.environ.get("URURAU_V110_MONITOR_GNEWS_LEGADO") == "1":
       usar coletor v110 (manter como fallback)
   else:
       pular coleta Google News neste ciclo

2. Chamar coletar_pautas_gnews_v111() e adicionar cada pauta à fila
   do monitor com o formato compatível.

3. Para cada pauta, se URURAU_V111_USAR_EXTRACAO_COMPLETA=1:
   - Chamar extrair_fonte_v111(url)
   - Se suficiente (chars >= min), adicionar texto_fonte à pauta
   - Se insuficiente, ainda adicionar à fila mas marcar para hidratação

4. Respeitar URURAU_V111_SCORE_MINIMO_PAUTA — pautas com score abaixo
   do mínimo devem ser descartadas ou marcadas como baixa prioridade.

5. A pauta deve ter os campos exatos que o fluxo do Ururau espera:
   - titulo, descricao, url, dominio, autor
   - data_publicacao (ISO), imagem, imagens
   - texto_fonte, canal_sugerido, score
   - fonte_tipo, termo_busca, metodo_extracao, chars_fonte
   - cidade, regiao

─────────────────────────────────────────────────────────────────
ARQUIVO 3: Atualização do .env
─────────────────────────────────────────────────────────────────

Adicionar estas variáveis ao .env existente (copiar exatamente):

# ===== v111 — Integração Google News Scraper =====
URURAU_V111_GNEWS_INTEGRADO=1
URURAU_V111_GNEWS_MAX_TERMOS_POR_CICLO=20
URURAU_V111_GNEWS_MAX_RESULTADOS_POR_TERMO=3
URURAU_V111_GNEWS_JANELA_HORAS=4
URURAU_V111_GNEWS_MIN_CHARS_FONTE=1200
URURAU_V111_USAR_EXTRACAO_COMPLETA=1
URURAU_V111_SCORE_MINIMO_PAUTA=65
URURAU_V110_MONITOR_GNEWS_LEGADO=0
URURAU_V108_GNEWS_TERMOS=0
URURAU_V105_USAR_BING_NEWS=0

─────────────────────────────────────────────────────────────────
ARQUIVO 4: ururau/tests/test_gnews_v111.py (testes)
─────────────────────────────────────────────────────────────────

Testes que validam a integração:

1. Testar que coletar_pautas_gnews_v111 retorna lista de dicts
2. Testar que cada pauta tem os campos obrigatórios
3. Testar que score está entre 0 e 100
4. Testar que extrair_fonte_v111 retorna dict com 'suficiente'
5. Testar que aliases são expandidos corretamente
6. Testar que janela temporal funciona
7. Testar que deduplicação remove URLs duplicadas
8. Mock de GoogleNewsIntegrado para testes sem network

═══════════════════════════════════════════════════════════════════════
INSTRUÇÕES DE IMPLEMENTAÇÃO
═══════════════════════════════════════════════════════════════════════

PASSO 1: Copie a pasta src/google_news_scraper/ para dentro do projeto Ururau
         (mesmo nível de ururau/ ou como subpacote)

PASSO 2: Crie ururau/coleta/gnews_v111_integrado.py com o wrapper

PASSO 3: Crie ururau/publisher/monitor_v111_patch.py com o adaptador

PASSO 4: Atualize o .env com as variáveis v111

PASSO 5: No monitor.py existente, adicione a chamada ao v111:
         
         from ururau.coleta.gnews_v111_integrado import coletar_pautas_gnews_v111
         
         # No início do ciclo:
         if os.environ.get("URURAU_V111_GNEWS_INTEGRADO") == "1":
             pautas_gnews = await coletar_pautas_gnews_v111()
             for p in pautas_gnews:
                 # adicionar à fila do monitor
                 await adicionar_pauta_a_fila(p)

PASSO 6: Teste com pytest

PASSO 7: Valide com um ciclo de monitor sem publicar (dry-run)

═══════════════════════════════════════════════════════════════════════
REGRAS IMPORTANTES
═══════════════════════════════════════════════════════════════════════

1. NÃO quebre o fluxo existente do Ururau. O novo código deve ser
   ADITIVO — se a flag v111 estiver desligada, tudo continua igual.

2. NÃO remova os arquivos v108-v110. Eles são o fallback.

3. TODAS as funções async devem usar async/await corretamente.

4. O formato da pauta deve ser EXATAMENTE o dict definido acima.
   Nenhum campo a mais ou a menos.

5. Os logs devem usar o prefixo [V111] para identificação.

6. O carregamento dos JSONs deve ser tolerante a erros — se um arquivo
   não existir, use defaults sensatos e log um warning.

7. Respeite os limites de concorrência — não faça mais que 3 buscas
   simultâneas no Google News.

═══════════════════════════════════════════════════════════════════════
FORMATO DE RESPOSTA ESPERADO
═══════════════════════════════════════════════════════════════════════

Entregue o código COMPLETO e FUNCIONAL de cada arquivo.
Não omita imports, não use placeholders como "# implementar aqui".

Para cada arquivo:
1. Nome do arquivo
2. Código completo
3. Explicação do que o código faz (2-3 parágrafos)

No final, forneça:
- Checklist de validação (o que testar)
- Comando para rodar os testes
- Possíveis erros e como debugar
```
