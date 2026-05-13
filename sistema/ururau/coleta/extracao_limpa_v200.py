# -*- coding: utf-8 -*-
"""extracao_limpa_v200 — extrai APENAS o artigo da URL, sem contaminacao.

CAUSA RAIZ (auditoria):
    extract_pipeline_v90._estrategia_densidade_paragrafos aplica seletores
    como 'article', 'main', 'section', '.content' SEM remover antes os
    elementos contaminadores (nav, header, footer, aside, .sidebar,
    .related, .newsletter, .login, .ads). Em portais regionais como
    RJNEWS, esses wrappers envolvem a pagina toda — o extrator pega home/
    listagem/login/rodape junto com o artigo.

CORRECAO:
    1. limpar_html_para_extracao(html_or_soup) remove os contaminadores
       ANTES de qualquer extracao.
    2. extrair_article_de_html(html, url_pauta, titulo_pauta) tenta varias
       estrategias precisas e retorna o CANDIDATO MAIS COERENTE com o
       titulo + canonical, NAO o maior.
    3. Estrategias em ordem:
        a) JSON-LD NewsArticle/Article com articleBody (mais confiavel).
        b) <article> com [itemprop=articleBody] OU classes article-body/
           post-content/entry-content/noticia/materia/texto.
        c) <article> com filtro pos-limpeza (remove nav/aside internos).
        d) Trafilatura precision (favor_precision=True).
        e) <main> com filtro pos-limpeza.
    4. Cada candidato e scorado por:
        - score_coerencia_titulo_corpo
        - boilerplate (penaliza)
        - multiassunto (penaliza pesado)
        - tamanho razoavel (penaliza muito longo demais > 25000 chars)
    5. Devolve o melhor candidato com 'score' e 'estrategia'.

POLITICA: Esta funcao NUNCA descarta nem bloqueia. So produz candidatos
e devolve score. Quem decide e o painel + usuario.
"""
from __future__ import annotations

import re
from typing import Any

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except Exception:
    BeautifulSoup = None  # type: ignore
    BS4_OK = False


# ─────────────────────── Pre-limpeza HTML ────────────────────────────────

# Tags que SEMPRE precisam sair do soup antes de extrair.
_TAGS_LIXO = (
    "script", "style", "noscript", "iframe", "svg", "form",
    "nav", "header", "footer", "aside",
)

# Selectors CSS de elementos contaminadores tipicos.
_SELECTORS_LIXO = (
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
    '[role="complementary"]', '[role="search"]',
    '[aria-label*="naveg" i]', '[aria-label*="rodap" i]',
    '[aria-label*="lateral" i]',
    ".sidebar", ".side-bar", ".menu", ".navbar", ".nav",
    ".breadcrumb", ".breadcrumbs",
    ".header", ".site-header", ".main-header",
    ".footer", ".site-footer", ".main-footer", ".rodape",
    ".ads", ".ad", ".advertisement", ".publicidade", ".propaganda",
    ".banner", ".banners",
    ".newsletter", ".signup", ".inscricao",
    ".login", ".cadastro", ".register",
    ".related", ".relacionadas", ".recomendado", ".recomendados",
    ".leia-tambem", ".veja-tambem", ".veja-mais",
    ".compartilhe", ".compartilhar", ".share",
    ".social", ".redes-sociais", ".social-buttons",
    ".comment", ".comments", ".comentarios",
    ".tags", ".tag-list", ".tag-cloud",
    ".pagination", ".paginacao",
    ".widget", ".widgets",
    ".popup", ".modal", ".overlay",
    '[class*="login" i]', '[class*="newsletter" i]',
    '[class*="signup" i]', '[class*="related" i]',
    '[class*="recommended" i]', '[class*="relacionad" i]',
    '[class*="sidebar" i]', '[class*="rodape" i]',
    '[class*="ads-" i]', '[class*="adsense" i]',
    '[id*="sidebar" i]', '[id*="related" i]', '[id*="footer" i]',
    '[id*="header" i]', '[id*="menu" i]', '[id*="nav" i]',
)


def limpar_html_para_extracao(html_or_soup: Any) -> "BeautifulSoup | None":
    """Remove elementos contaminadores e devolve soup limpo (copia).

    NAO modifica o soup original. Funciona com string HTML ou BeautifulSoup.
    """
    if not BS4_OK:
        return None
    if isinstance(html_or_soup, BeautifulSoup):
        soup = BeautifulSoup(str(html_or_soup), "html.parser")
    else:
        soup = BeautifulSoup(str(html_or_soup or ""), "html.parser")

    # 1) tags estruturais que sempre saem (em todo o documento)
    for tag in _TAGS_LIXO:
        for el in soup.find_all(tag):
            el.decompose()

    # 2) selectors com classes/ids conhecidos
    for sel in _SELECTORS_LIXO:
        try:
            for el in soup.select(sel):
                el.decompose()
        except Exception:
            continue

    # 3) comentarios HTML
    try:
        from bs4 import Comment
        for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
    except Exception:
        pass

    return soup


# ───────────────────────── Estrategias ───────────────────────────────────

def _texto_de_elemento(el) -> str:
    """Texto dos paragrafos do elemento, em ordem, separados por linha em branco."""
    if el is None:
        return ""
    paras = el.find_all("p")
    if paras:
        chunks = []
        for p in paras:
            t = p.get_text(" ", strip=True)
            if len(t) >= 25:
                chunks.append(t)
        if chunks:
            return "\n\n".join(chunks)
    # fallback: pega texto inteiro
    return el.get_text("\n", strip=True)


def _candidato_jsonld(soup_original) -> dict | None:
    """JSON-LD NewsArticle/Article com articleBody."""
    if not BS4_OK or soup_original is None:
        return None
    try:
        import json
        for tag in soup_original.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(tag.string or "{}")
            except Exception:
                continue
            stack = [data] if not isinstance(data, list) else list(data)
            while stack:
                node = stack.pop()
                if not isinstance(node, dict):
                    continue
                tipo = node.get("@type") or ""
                if isinstance(tipo, list):
                    tipo = " ".join(tipo)
                if any(t in str(tipo).lower() for t in (
                    "newsarticle", "article", "reportagenewsarticle",
                    "scholarlyarticle", "blogposting",
                )):
                    body = node.get("articleBody") or node.get("text")
                    if body and isinstance(body, str) and len(body) >= 200:
                        return {"texto": body, "estrategia": "jsonld_articleBody"}
                for v in node.values():
                    if isinstance(v, dict):
                        stack.append(v)
                    elif isinstance(v, list):
                        stack.extend([x for x in v if isinstance(x, (dict, list))])
    except Exception:
        pass
    return None


_SELETORES_ARTIGO_ESPECIFICOS = (
    "[itemprop='articleBody']",
    "article .article-body, article .post-content, article .entry-content",
    "article .noticia, article .materia, article .texto",
    ".article-body", ".post-content", ".entry-content",
    ".noticia-conteudo", ".materia-conteudo", ".texto-noticia",
    "[itemtype*='Article'] [itemprop='articleBody']",
    "main article",
    "article",  # ultimo: article inteiro depois da pre-limpeza
)


def _candidato_seletor(soup_limpo, sel: str) -> dict | None:
    if not soup_limpo:
        return None
    try:
        el = soup_limpo.select_one(sel)
    except Exception:
        return None
    if not el:
        return None
    texto = _texto_de_elemento(el)
    if texto and len(texto) >= 200:
        return {"texto": texto, "estrategia": f"seletor:{sel}"}
    return None


def _candidato_trafilatura(html: str) -> dict | None:
    try:
        import trafilatura  # type: ignore
    except Exception:
        return None
    try:
        # favor_precision evita pegar relacionadas/menu
        texto = trafilatura.extract(
            html,
            favor_precision=True,
            include_comments=False,
            include_tables=False,
            include_links=False,
            no_fallback=True,
        )
        if texto and len(texto) >= 200:
            return {"texto": texto, "estrategia": "trafilatura_precision"}
    except Exception:
        pass
    return None


def _candidato_main(soup_limpo) -> dict | None:
    if not soup_limpo:
        return None
    el = soup_limpo.find("main") or soup_limpo.select_one('[role="main"]')
    if not el:
        return None
    texto = _texto_de_elemento(el)
    if texto and len(texto) >= 200:
        return {"texto": texto, "estrategia": "main_pos_limpeza"}
    return None


# ─────────────────────── Pipeline principal ──────────────────────────────

def _scorar_candidato(candidato: dict, titulo_pauta: str = "",
                      url_pauta: str = "") -> float:
    """Score 0..1 que reflete quao bom e o candidato como artigo unico.

    Penaliza:
      - boilerplate (rodape, login, newsletter)
      - multiassunto (varios titulos internos)
      - tamanho excessivo (>25000 chars provavelmente e body inteiro)

    Bonifica:
      - coerencia com o titulo (overlap de tokens)
      - estrategia mais confiavel (jsonld > seletor especifico > trafilatura)
    """
    texto = candidato.get("texto", "") or ""
    if not texto:
        return 0.0

    try:
        from ururau.coleta.extrator_artigo_unico import (
            score_coerencia_titulo_corpo,
            detectar_multiassunto,
            boilerplate_no_texto,
        )
    except Exception:
        return 0.5  # neutro sem o validador

    score = 0.5  # base

    coer = score_coerencia_titulo_corpo(titulo_pauta or "", texto)
    score += 0.30 * coer

    multi = detectar_multiassunto(texto, titulo_pauta or "")
    if multi["multiassunto"]:
        score -= 0.40

    bp = boilerplate_no_texto(texto)
    score -= 0.05 * len(bp)

    # penalidade por excesso de tamanho (provavelmente body inteiro)
    if len(texto) > 25000:
        score -= 0.20

    # bonus por estrategia confiavel
    est = candidato.get("estrategia", "")
    if "jsonld" in est:
        score += 0.20
    elif "seletor:[itemprop" in est or "article-body" in est or "post-content" in est:
        score += 0.10

    return max(0.0, min(1.0, score))


def extrair_article_de_html(html: str, *, url_pauta: str = "",
                            titulo_pauta: str = "") -> dict:
    """Extrai o artigo do HTML aplicando pre-limpeza e multiplas estrategias.

    Retorna SEMPRE um dict. Nunca levanta. Devolve o melhor candidato
    (mais coerente com titulo + canonical), com score e auditoria de
    todas as tentativas:

        {
          "ok": bool,
          "texto": str,
          "estrategia": str,
          "score": float,
          "candidatos": list[dict],   # auditoria de cada tentativa
          "url_pauta": str,
          "titulo_pauta": str,
        }
    """
    out: dict = {
        "ok": False, "texto": "", "estrategia": "",
        "score": 0.0, "candidatos": [],
        "url_pauta": url_pauta, "titulo_pauta": titulo_pauta,
    }
    if not html or not BS4_OK:
        out["estrategia"] = "sem_html_ou_bs4"
        return out

    try:
        soup_original = BeautifulSoup(html, "html.parser")
    except Exception as e:
        out["estrategia"] = f"parse_falhou:{e}"
        return out

    soup_limpo = limpar_html_para_extracao(soup_original)
    candidatos: list[dict] = []

    # 1) JSON-LD (usa soup ORIGINAL — o script type=ld+json pode estar
    #    em header/footer, e nao foi removido).
    c = _candidato_jsonld(soup_original)
    if c:
        candidatos.append(c)

    # 2) Seletores especificos (depois da pre-limpeza)
    for sel in _SELETORES_ARTIGO_ESPECIFICOS:
        c = _candidato_seletor(soup_limpo, sel)
        if c:
            candidatos.append(c)
            # nao quebra: deixa todos competirem por score

    # 3) Trafilatura precision (no HTML original — ele tem heuristicas proprias)
    c = _candidato_trafilatura(html)
    if c:
        candidatos.append(c)

    # 4) main como ultimo recurso
    c = _candidato_main(soup_limpo)
    if c:
        candidatos.append(c)

    # Escolhe o melhor por score
    if not candidatos:
        out["estrategia"] = "nenhum_candidato"
        return out

    avaliados: list[dict] = []
    for cand in candidatos:
        sc = _scorar_candidato(cand, titulo_pauta, url_pauta)
        avaliados.append({
            "estrategia": cand["estrategia"],
            "chars": len(cand["texto"]),
            "score": round(sc, 3),
        })
        cand["_score"] = sc

    melhor = max(candidatos, key=lambda c: c["_score"])
    out["ok"] = True
    out["texto"] = melhor["texto"]
    out["estrategia"] = melhor["estrategia"]
    out["score"] = round(melhor["_score"], 3)
    out["candidatos"] = avaliados
    return out


__all__ = [
    "limpar_html_para_extracao",
    "extrair_article_de_html",
]
