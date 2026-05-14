"""
coleta/leitura_fonte.py — Leitura e extração de texto da fonte original.

Bloco 21 — Funcionalidade "Leitura da Fonte":
  - Busca o texto completo do artigo original via URL
  - Sanitiza o HTML e extrai o conteúdo principal
  - Destaca termos das watchlists editoriais
  - Cache em memória para evitar re-fetch
  - Timeout configurável via TIMEOUT_LEITURA_FONTE
  - Fallback silencioso: se falhar, retorna resultado vazio

Uso:
    from ururau.coleta.leitura_fonte import ler_fonte_pauta
    resultado = ler_fonte_pauta(pauta)
    print(resultado.texto_limpo)
    print(resultado.termos_destacados)
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import requests

try:
    from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101
except Exception:
    def limpar_texto_artigo_v101(texto: str, titulo: str = "", max_chars: int = 16000) -> str:
        return str(texto or "").strip()[:max_chars]


# ── Configurações ─────────────────────────────────────────────────────────────
try:
    from ururau.config.settings import HEADERS, TIMEOUT_LEITURA_FONTE, CACHE_LEITURA_FONTE_MIN
except Exception:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    TIMEOUT_LEITURA_FONTE   = 12
    CACHE_LEITURA_FONTE_MIN = 30

_CACHE_TTL_SEG = CACHE_LEITURA_FONTE_MIN * 60  # segundos

# Cache em memória: url → (timestamp, ResultadoLeitura)
_cache: dict[str, tuple[float, "ResultadoLeitura"]] = {}


# ── Resultado ─────────────────────────────────────────────────────────────────

@dataclass
class ResultadoLeitura:
    """Resultado da leitura e extração de texto de uma fonte."""
    url: str = ""
    texto_limpo: str = ""            # texto principal extraído
    titulo_extraido: str = ""        # título encontrado no HTML
    imagem_url: str = ""             # URL da imagem principal (og:image ou primeiro <img>)
    termos_destacados: list[str] = field(default_factory=list)  # termos das watchlists detectados
    score_intel_adicional: int = 0   # score extra detectado no texto completo
    intel_log: str = ""              # log da análise intel
    tamanho_chars: int = 0           # comprimento do texto extraído
    sucesso: bool = False
    erro: str = ""


# ── Seletores CSS para extração de conteúdo principal ─────────────────────────
_SELETORES_CONTEUDO = [
    "article",
    "[class*='article-body']",
    "[class*='post-content']",
    "[class*='entry-content']",
    "[class*='content-body']",
    "[class*='news-content']",
    "[class*='materia-body']",
    "[class*='noticia-body']",
    "[class*='texto-noticia']",
    "main",
    ".content",
    "#content",
]

_TAGS_REMOVER = {
    "script", "style", "nav", "header", "footer", "aside",
    "noscript", "iframe", "svg", "form", "button",
    "figure",  # mantém alt text da imagem mas remove markup
}

# ── Utilidades ────────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def _extrair_texto_html(html: str) -> tuple[str, str]:
    """
    Extrai título e texto limpo de um HTML.
    Usa BeautifulSoup se disponível, fallback para regex.
    Retorna (titulo, texto_limpo).
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Título
        titulo = ""
        tag_titulo = soup.find("h1") or soup.find("title")
        if tag_titulo:
            titulo = tag_titulo.get_text(separator=" ", strip=True)

        # Remove tags indesejadas
        for tag in soup.find_all(_TAGS_REMOVER):
            tag.decompose()

        # Tenta seletores de conteúdo principal
        conteudo = None
        for sel in _SELETORES_CONTEUDO:
            elemento = soup.select_one(sel)
            if elemento:
                texto_candidato = elemento.get_text(separator="\n", strip=True)
                if len(texto_candidato) > 200:
                    conteudo = texto_candidato
                    break

        # Fallback: pega todo o body
        if not conteudo:
            body = soup.find("body")
            conteudo = body.get_text(separator="\n", strip=True) if body else ""

        # Limpa espaços excessivos
        linhas = [l.strip() for l in conteudo.split("\n") if l.strip() and len(l.strip()) > 20]
        texto_limpo = "\n".join(linhas[:80])  # limita a 80 parágrafos para não sobrecarregar

        return titulo.strip(), texto_limpo

    except ImportError:
        # Fallback: regex básico sem BeautifulSoup
        titulo = ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        if m:
            titulo = re.sub(r"<[^>]+>", "", m.group(1)).strip()

        texto = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        texto = re.sub(r"<style[^>]*>.*?</style>", " ", texto, flags=re.DOTALL | re.IGNORECASE)
        texto = re.sub(r"<[^>]+>", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip()
        return titulo, texto[:8000]


def _extrair_imagem_html(html: str, url_base: str = "") -> str:
    """
    Extrai a URL da imagem principal do artigo.
    Prioridade: og:image > twitter:image > primeiro <img> de conteúdo (>= 100px).
    Retorna string vazia se não encontrar.
    """
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        soup = BeautifulSoup(html, "html.parser")

        # 1. og:image
        og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "og:image"})
        if og and og.get("content", "").strip():
            return og["content"].strip()

        # 2. twitter:image
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content", "").strip():
            return tw["content"].strip()

        # 3. Primeiro <img> dentro de article/main com src razoável (não ícone)
        container = soup.find("article") or soup.find("main") or soup.find("body")
        if container:
            for img in container.find_all("img", src=True):
                src = img.get("src", "").strip()
                if not src or src.startswith("data:"):
                    continue
                # Filtra ícones pequenos por atributo width/height
                w = img.get("width", "")
                h = img.get("height", "")
                try:
                    if int(str(w).replace("px", "").strip() or "999") < 100:
                        continue
                    if int(str(h).replace("px", "").strip() or "999") < 80:
                        continue
                except (ValueError, TypeError):
                    pass
                # Ignora URLs de trackers e ícones por padrão
                if any(x in src for x in ("pixel", "tracker", "1x1", "spacer", "blank")):
                    continue
                return urljoin(url_base, src) if url_base else src
    except Exception:
        # Fallback com regex apenas para og:image
        m = re.search(r'og:image["\s]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(r'content=["\']([^"\']+)["\']["\s]+property=["\']og:image["\']', html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _detectar_termos_watchlist(texto_norm: str) -> list[str]:
    """Detecta termos das watchlists editoriais e da aba Config > Termos."""
    termos: list[str] = []
    try:
        p = Path("watchlists_editoriais.json")
        if p.exists():
            dados = json.loads(p.read_text(encoding="utf-8"))
            for grupo in dados.values():
                if isinstance(grupo, dict):
                    for nome in grupo.get("nomes", []) or grupo.get("termos", []):
                        n = _normalizar(str(nome))
                        if n and n in texto_norm and str(nome) not in termos:
                            termos.append(str(nome))
                            if len(termos) >= 8:
                                return termos
    except Exception:
        pass
    try:
        from ururau.coleta.termos_config_v98 import carregar_termos, normalizar
        for item in carregar_termos():
            nome = str(item.get("termo") or "").strip()
            if not nome or not item.get("ativo", True):
                continue
            if normalizar(nome) in texto_norm and nome not in termos:
                termos.append(nome)
                if len(termos) >= 12:
                    break
    except Exception:
        pass
    return termos

def ler_fonte_pauta(pauta: dict, forcar_refresh: bool = False) -> ResultadoLeitura:
    """
    Busca e extrai o texto completo da fonte original de uma pauta.

    Parâmetros:
      - pauta: dict com campo 'link_origem'
      - forcar_refresh: ignora cache e refaz o fetch

    Retorna ResultadoLeitura. Em caso de erro, retorna ResultadoLeitura com
    sucesso=False e erro descritivo (NUNCA levanta exceção).
    """
    try:
        return _ler_fonte_impl(pauta, forcar_refresh)
    except Exception as e:
        return ResultadoLeitura(
            url=pauta.get("link_origem", ""),
            sucesso=False,
            erro=f"Erro inesperado: {e}",
        )


def _ler_fonte_impl(pauta: dict, forcar_refresh: bool) -> ResultadoLeitura:
    url = (pauta.get("link_origem") or pauta.get("url_final") or pauta.get("url_original") or "").strip()
    texto_preextraido = (
        pauta.get("texto_fonte")
        or pauta.get("cleaned_source_text")
        or pauta.get("raw_source_text")
        or pauta.get("dossie")
        or ""
    )
    # v104: não confiar em snippet/RSS curto como se fosse texto completo.
    # Antes a aba Fonte aceitava 120+ caracteres pré-extraídos e por isso
    # devolvia resumos de 1 parágrafo sem tentar abrir a URL real.
    min_preextraido = int(os.getenv("URURAU_V104_MIN_PREEXTRAIDO", os.getenv("URURAU_MIN_CHARS_TEXTO_FONTE", "900")) or "900")
    if isinstance(texto_preextraido, str) and len(texto_preextraido.strip()) >= min_preextraido:
        texto_limpo = limpar_texto_artigo_v101(texto_preextraido.strip(), titulo=pauta.get("titulo_origem", ""), max_chars=12000)
        try:
            from ururau.coleta.limpeza_texto_v81 import texto_util_chars
            util_pre = texto_util_chars(texto_limpo)
        except Exception:
            util_pre = len(texto_limpo)
        if util_pre >= min_preextraido:
            try:
                from ururau.coleta.intel_editorial import analisar_intel_editorial
                intel = analisar_intel_editorial(
                    titulo=pauta.get("titulo_origem", ""),
                    resumo=pauta.get("resumo_origem", ""),
                    texto_fonte=texto_limpo[:3000],
                    canal=pauta.get("canal_forcado", ""),
                )
                score_intel = intel.score_adicional_total
                intel_log = intel.resumo_log()
            except Exception:
                score_intel = 0
                intel_log = "[v104] texto pré-extraído longo usado"
            return ResultadoLeitura(
                url=url,
                texto_limpo=texto_limpo,
                titulo_extraido=pauta.get("titulo_origem", ""),
                imagem_url=pauta.get("imagem_url") or pauta.get("imagem") or "",
                termos_destacados=[],
                score_intel_adicional=score_intel,
                intel_log=intel_log,
                tamanho_chars=len(texto_limpo),
                sucesso=True,
            )
    if not url:
        return ResultadoLeitura(sucesso=False, erro="URL não informada")

    # V200_2: blocklist de URLs em cooldown cronico (band/melhores-momentos,
    # mls-melhores-gols, charge-do-aroeira, cpi-do-banco-master etc). Antes
    # essas URLs mortas eram tentadas centenas de vezes por V110/V86/v90,
    # poluindo o log e travando a hidratacao. Agora pula na hora.
    try:
        from ururau.coleta.fontes_blocklist_v200 import eh_url_bloqueada
        _bloq, _mot = eh_url_bloqueada(url)
        if _bloq:
            print(f"[LEITURA_FONTE][v200_2][BLOCKLIST] skip {url[:80]} ({_mot})")
            return ResultadoLeitura(
                url=url, sucesso=False,
                erro=f"URL em blocklist v200_2 ({_mot})",
            )
    except Exception:
        pass

    # Verifica cache
    agora = time.time()
    if not forcar_refresh and url in _cache:
        ts, resultado = _cache[url]
        ttl_cache = _CACHE_TTL_SEG if getattr(resultado, "sucesso", False) else int(os.getenv("URURAU_LEITURA_FONTE_FAIL_CACHE_TTL_SEG", "180") or "180")
        if (agora - ts) < ttl_cache:
            return resultado

    print(f"[LEITURA_FONTE] Buscando: {url[:80]}")

    try:
        from ururau.coleta.scraper_defaults_v47_10 import aplicar_defaults_scrapers
        aplicar_defaults_scrapers(forcar=True)
    except Exception:
        pass

    # v134: Reader Proxy prioritário para itens problemáticos/aba Fonte/F5.
    # Se funcionar, já retorna texto limpo e evita gastar tempo em variações que falham.
    try:
        if _deve_priorizar_reader_proxy_v134(pauta):
            proxy_pre_v134 = _tentar_reader_proxy_v134(pauta, None)
            if proxy_pre_v134 is not None and getattr(proxy_pre_v134, "sucesso", False):
                _cache[url] = (agora, proxy_pre_v134)
                return proxy_pre_v134
    except Exception as _e_proxy_pre_v134:
        print(f"[V134][READER_PROXY] prioridade falhou: {_e_proxy_pre_v134}", flush=True)

    # V200_2: SCRAPLING como PRIMEIRA tentativa na hidratacao do painel.
    # Ate aqui, o Scrapling (com bypass de paywall/anti-bot) so era usado
    # em scraping.extrair_dossie_completo — caminho do workflow, NUNCA a
    # hidratacao do painel (aba Fonte / fila). Agora a leitura de fonte
    # tenta o Scrapling primeiro e so cai na cascata v104/v110/v86 se ele
    # nao trouxer texto suficiente. Desativavel: URURAU_SCRAPLING_NA_LEITURA_FONTE=0
    try:
        if os.getenv("URURAU_SCRAPLING_NA_LEITURA_FONTE", "1").strip().lower() not in {"0", "false", "nao", "n\u00e3o", "off"}:
            from ururau.coleta.scraping import extrair_dossie_completo
            from ururau.coleta.limpeza_texto_v81 import texto_util_chars as _tuc_scr
            _min_scr = int(os.getenv("URURAU_SCRAPLING_MIN_CHARS", os.getenv("URURAU_MIN_CHARS_TEXTO_FONTE", "900")) or "900")
            _dossie_scr = extrair_dossie_completo(url, texto_existente=texto_preextraido or pauta.get("resumo_origem", "") or "")
            _txt_scr = str((_dossie_scr or {}).get("cleaned_source_text") or (_dossie_scr or {}).get("dossie") or "").strip()
            _metodo_scr = str((_dossie_scr or {}).get("extraction_method") or "")
            if _txt_scr and _metodo_scr.startswith("scrapling") and _tuc_scr(_txt_scr) >= _min_scr:
                _meta_scr = (_dossie_scr or {}).get("metadata") or {}
                _texto_limpo_scr = limpar_texto_artigo_v101(
                    _txt_scr, titulo=pauta.get("titulo_origem", ""), max_chars=12000)
                print(f"[LEITURA_FONTE][SCRAPLING] OK {_tuc_scr(_texto_limpo_scr)} chars "
                      f"via {_metodo_scr}: {url[:70]}")
                resultado = ResultadoLeitura(
                    url=str(_meta_scr.get("resolved_url") or url),
                    texto_limpo=_texto_limpo_scr[:12000],
                    titulo_extraido=str(_meta_scr.get("titulo") or pauta.get("titulo_origem", "")),
                    imagem_url=str(_meta_scr.get("imagem") or pauta.get("imagem_url")
                                   or pauta.get("imagem") or ""),
                    termos_destacados=[],
                    score_intel_adicional=0,
                    intel_log=f"[scrapling] {_metodo_scr}",
                    tamanho_chars=len(_texto_limpo_scr),
                    sucesso=True,
                )
                _cache[url] = (agora, resultado)
                return resultado
    except Exception as _e_scr_lf:
        print(f"[LEITURA_FONTE][SCRAPLING] indisponivel/falhou, seguindo cascata v104: {_e_scr_lf}")

    # v104: usa o extrator definitivo também na aba Fonte.
    try:
        from ururau.coleta.fonte_extractor_v104 import extrair_artigo_v104
        from ururau.coleta.limpeza_texto_v81 import texto_util_chars
        res104 = extrair_artigo_v104(
            url,
            texto_preextraido or pauta.get("resumo_origem", "") or "",
            titulo=pauta.get("titulo_origem", "") or "",
            forcar_refresh=forcar_refresh,
        )
        txt104 = (getattr(res104, "texto", "") or "").strip()
        min104 = int(os.getenv("URURAU_V108_MIN_TEXTO_FONTE_OK", os.getenv("URURAU_V104_MIN_CHARS_ARTIGO", os.getenv("URURAU_MIN_CHARS_TEXTO_FONTE", "900"))) or "900")
        if getattr(res104, "ok", False) and texto_util_chars(txt104) >= min104:
            texto_limpo = limpar_texto_artigo_v101(txt104, titulo=pauta.get("titulo_origem", ""), max_chars=12000)
            imagem_url = getattr(res104, "imagem", "") or pauta.get("imagem_url") or pauta.get("imagem") or ""
            texto_norm = _normalizar(texto_limpo)
            termos = _detectar_termos_watchlist(texto_norm)
            try:
                from ururau.coleta.intel_editorial import analisar_intel_editorial
                intel = analisar_intel_editorial(
                    titulo=pauta.get("titulo_origem", ""),
                    resumo=pauta.get("resumo_origem", ""),
                    texto_fonte=texto_limpo[:3000],
                    canal=pauta.get("canal_forcado", ""),
                )
                score_intel = intel.score_adicional_total
                intel_log = intel.resumo_log()
            except Exception:
                score_intel = 0
                intel_log = f"[v104] {getattr(res104, 'metodo', '')}"
            resultado = ResultadoLeitura(
                url=getattr(res104, "url_final", "") or url,
                texto_limpo=texto_limpo[:12000],
                titulo_extraido=getattr(res104, "titulo", "") or pauta.get("titulo_origem", ""),
                imagem_url=imagem_url,
                termos_destacados=termos,
                score_intel_adicional=score_intel,
                intel_log=intel_log,
                tamanho_chars=len(texto_limpo),
                sucesso=True,
            )
            _cache[url] = (agora, resultado)
            print(f"[LEITURA_FONTE][v104] OK — {len(texto_limpo)} chars via {getattr(res104, 'metodo', '')}")
            return resultado
    except Exception as e104:
        print(f"[LEITURA_FONTE][v104] fallback HTML: {e104}")

    # Fetch antigo como último fallback
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get(url, timeout=TIMEOUT_LEITURA_FONTE, allow_redirects=True)
        if resp.status_code != 200:
            resultado = ResultadoLeitura(
                url=url,
                sucesso=False,
                erro=f"HTTP {resp.status_code}",
            )
            _cache[url] = (agora, resultado)
            return resultado
        html = resp.text
    except Exception as e:
        resultado = ResultadoLeitura(url=url, sucesso=False, erro=str(e))
        _cache[url] = (agora, resultado)
        return resultado

    # Extração de texto e imagem
    titulo_ext, texto_limpo = _extrair_texto_html(html)
    texto_limpo = limpar_texto_artigo_v101(texto_limpo, titulo=pauta.get("titulo_origem", "") or titulo_ext, max_chars=12000)
    imagem_url = _extrair_imagem_html(html, url_base=url)
    texto_norm = _normalizar(texto_limpo)

    # Detecção de termos das watchlists
    termos = _detectar_termos_watchlist(texto_norm)

    # Análise intel editorial no texto completo
    score_intel = 0
    intel_log = ""
    try:
        from ururau.coleta.intel_editorial import analisar_intel_editorial
        intel = analisar_intel_editorial(
            titulo=pauta.get("titulo_origem", ""),
            resumo=pauta.get("resumo_origem", ""),
            texto_fonte=texto_limpo[:3000],
            canal=pauta.get("canal_forcado", ""),
        )
        score_intel = intel.score_adicional_total
        intel_log = intel.resumo_log()
    except Exception:
        pass

    # v105: o fallback HTML antigo também precisa obedecer ao mínimo de texto útil.
    # Antes ele retornava sucesso=True até com 0/90/500 chars, permitindo matéria de 1 parágrafo.
    try:
        from ururau.coleta.limpeza_texto_v81 import texto_util_chars as _util_chars_v105
        util_fallback = int(_util_chars_v105(texto_limpo))
    except Exception:
        util_fallback = len((texto_limpo or "").strip())
    min_fonte_v105 = int(os.getenv("URURAU_V108_MIN_TEXTO_FONTE_OK", os.getenv("URURAU_V105_MIN_CHARS_FONTE_OK", os.getenv("URURAU_V104_MIN_CHARS_ARTIGO", "900"))) or "900")
    sucesso_fallback = util_fallback >= min_fonte_v105

    resultado = ResultadoLeitura(
        url=url,
        texto_limpo=texto_limpo[:8000] if sucesso_fallback else "",
        titulo_extraido=titulo_ext,
        imagem_url=imagem_url,
        termos_destacados=termos if sucesso_fallback else [],
        score_intel_adicional=score_intel if sucesso_fallback else 0,
        intel_log=intel_log if sucesso_fallback else "",
        tamanho_chars=util_fallback,
        sucesso=sucesso_fallback,
        erro="" if sucesso_fallback else f"texto útil insuficiente no fallback HTML ({util_fallback} chars; mínimo {min_fonte_v105})",
    )

    if not sucesso_fallback:
        proxy_v134 = _tentar_reader_proxy_v134(pauta, resultado)
        if proxy_v134 is not None and getattr(proxy_v134, "sucesso", False):
            _cache[url] = (agora, proxy_v134)
            return proxy_v134

    _cache[url] = (agora, resultado)
    if sucesso_fallback:
        print(f"[LEITURA_FONTE] OK — {util_fallback} chars, {len(termos)} termos detectados")
    else:
        print(f"[LEITURA_FONTE] FAIL — {util_fallback} chars úteis no fallback HTML")
    return resultado




def _deve_priorizar_reader_proxy_v134(pauta: dict) -> bool:
    """
    Decide se o Reader Proxy deve entrar cedo.

    Regra operacional:
    - se URURAU_READER_PROXY_PRIORITARIO=1, entra antes do fallback HTML;
    - útil para itens da fila abaixo de 100%, links problemáticos, F5 e varredura persistente.
    """
    raw = str(os.getenv("URURAU_READER_PROXY_PRIORITARIO", "1")).strip().lower()
    if raw not in {"1", "true", "sim", "yes", "s", "on"}:
        return False

    try:
        url = (
            pauta.get("link_origem")
            or pauta.get("url_final")
            or pauta.get("url_original")
            or pauta.get("link")
            or ""
        ).strip()
    except Exception:
        url = ""

    if not url:
        return False

    # Entrar cedo para qualquer link real do projeto quando a meta for chegar a 100%.
    return True

def _tentar_reader_proxy_v134(pauta: dict, resultado_base=None):
    """
    Último fallback autorizado: SemPaywall/reader proxy.

    Entra quando os extratores normais não conseguiram texto útil suficiente.
    Deve ficar dentro do fluxo real de leitura, não apenas como monkey patch externo.
    """
    try:
        from ururau.coleta.reader_proxy_fallback_v134 import extrair_reader_proxy_v134

        url = (
            pauta.get("link_origem")
            or pauta.get("url_final")
            or pauta.get("url_original")
            or pauta.get("link")
            or ""
        ).strip()

        titulo_ref = pauta.get("titulo_origem") or pauta.get("titulo") or ""

        if not url:
            return None

        data = extrair_reader_proxy_v134(url, titulo_ref=titulo_ref)

        if not data.get("ok"):
            print(f"[V134][READER_PROXY] FAIL {data.get('erro')} | {url[:120]}", flush=True)
            return None

        texto = (data.get("texto") or "").strip()
        if not texto:
            return None

        imagem = data.get("imagem") or ""
        if resultado_base is not None:
            imagem = imagem or getattr(resultado_base, "imagem_url", "") or ""

        novo = ResultadoLeitura(
            url=data.get("url_clean") or url,
            texto_limpo=texto[:12000],
            titulo_extraido=data.get("titulo") or titulo_ref,
            imagem_url=imagem,
            termos_destacados=[],
            score_intel_adicional=0,
            intel_log="[v134] reader proxy autorizado",
            tamanho_chars=int(data.get("chars") or len(texto)),
            sucesso=True,
            erro="",
        )

        print(
            f"[V134][READER_PROXY] OK {novo.tamanho_chars} chars via {data.get('url_clean')}",
            flush=True
        )

        return novo

    except Exception as e:
        print(f"[V134][READER_PROXY] ERRO {type(e).__name__}: {e}", flush=True)
        return None

def limpar_cache_leitura():
    """Limpa todo o cache de leitura de fonte."""
    global _cache
    _cache = {}


def obter_texto_para_redacao(pauta: dict) -> str:
    """
    Convenience: retorna apenas o texto limpo da fonte para uso na redação.
    Retorna string vazia se a leitura falhar.
    """
    resultado = ler_fonte_pauta(pauta)
    return resultado.texto_limpo if resultado.sucesso else ""




