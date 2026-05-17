# -*- coding: utf-8 -*-
"""paywall_rules_burlesco_v200 — Regras de bypass por dominio.

Traducao das regras do projeto Burlesco (https://github.com/burlesco/burlesco)
para chamadas HTTP do nosso pipeline. O Burlesco e uma WebExtension que opera
no nivel do browser; aqui as regras viram User-Agent, Referer, Cookie por
dominio. Como `requests` nao executa JavaScript, ~27 dos 33 sites cobertos
pelo Burlesco ja entregam o HTML completo (o paywall era client-side) — para
esses, basta acertar o Referer (Google) para nao cair em pagina de assinatura.

Estrutura:
    PAYWALL_RULES: {dominio: {ua, referer, cookies?, clear_cookies?, extract_from?}}

A funcao publica `tentar_bypass_burlesco(url, titulo)` segue a mesma assinatura
das demais estrategias de `bypass_paywall_v200.py`, devolvendo dict:
    {'estrategia': str, 'status': int, 'url_final': str, 'chars': int,
     'texto': str, 'ok': bool}

Sites cobertos (33), conforme manifesto do Burlesco:
    BRPolitico, Correio 24 Horas, Correio Popular, Crusoe, Diarinho,
    Diario Popular, Diario da Regiao, Diario de Canoas, Diario do Grande ABC,
    EL PAIS Brasil, Estado de Minas, Exame, Folha de Londrina, Folha de S.Paulo,
    Gazeta Online, Gazeta do Povo, GauchaZH, JOTA, Jornal NH, Jornal Pioneiro,
    Jornal VS, NSC Total, O Estado de S. Paulo, O Globo, Observador,
    Quatro Rodas, Revista Oeste, Seu Dinheiro, Superinteressante, UOL,
    Valor Economico, Veja, Epoca.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from typing import Any, Optional

try:
    import requests
    _OK = True
except Exception:
    requests = None  # type: ignore
    _OK = False


# ─────────────────── User Agents ──────────────────────────────────────────

UA_GOOGLEBOT = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; "
    "+http://www.google.com/bot.html)"
)
UA_IPHONE_OLD = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 6_0 like Mac OS X) "
    "AppleWebKit/536.26 (KHTML, like Gecko) Version/6.0 "
    "Mobile/10A5376e Safari/8536.25"
)
UA_DEFAULT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFERER_GOOGLE = "https://www.google.com/"
REFERER_GOOGLE_NEWS = "https://news.google.com/"

TIMEOUT = int(os.getenv("URURAU_BYPASS_TIMEOUT", "15"))
MIN_CHARS_VALIDOS = int(os.getenv("URURAU_BYPASS_MIN_CHARS", "550"))


# ─────────────────── Regras por dominio ───────────────────────────────────

# Cada entrada e procurada por sufixo de hostname (ex.: "veja.abril.com.br"
# bate em "veja.abril.com.br" e em qualquer subdominio dele). Sufixos mais
# longos tem precedencia (verificacao por len decrescente).
PAYWALL_RULES: dict[str, dict[str, Any]] = {

    # --- regras explicitas do manifest do Burlesco ---

    # JOTA: o Burlesco injeta header User-Agent=Googlebot/2.1 em todas as
    # requisicoes ao dominio. E a unica regra real de header injection.
    "jota.info": {
        "ua": UA_GOOGLEBOT,
        "referer": REFERER_GOOGLE,
        "estrategia": "burlesco_jota_googlebot",
    },

    # Crusoe: cookie crs_subscriber=1 (fake de assinante client-side).
    "crusoe.uol.com.br": {
        "ua": UA_DEFAULT,
        "referer": REFERER_GOOGLE,
        "cookies": {"crs_subscriber": "1"},
        "estrategia": "burlesco_crusoe_cookie",
    },

    # Diario Popular / Gazeta Online: blockAll cookies (sem Cookie no
    # request, descarta Set-Cookie da resposta).
    "diariopopular.com.br": {
        "ua": UA_DEFAULT,
        "referer": REFERER_GOOGLE,
        "clear_cookies": True,
        "estrategia": "burlesco_diariopopular_nocookies",
    },
    "gazetaonline.com.br": {
        "ua": UA_DEFAULT,
        "referer": REFERER_GOOGLE,
        "clear_cookies": True,
        "estrategia": "burlesco_gazetaonline_nocookies",
    },

    # UOL — caso isolado: path NYT precisa de UA iPhone antigo. O UA padrao
    # cobre o resto do dominio.
    "noticias.uol.com.br": {
        "ua": UA_DEFAULT,
        "referer": REFERER_GOOGLE,
        "ua_special_path": {
            "/midiaglobal/nytimes/": UA_IPHONE_OLD,
        },
        "estrategia": "burlesco_uol",
    },
    "uol.com.br": {
        "ua": UA_DEFAULT,
        "referer": REFERER_GOOGLE,
        "estrategia": "burlesco_uol_generico",
    },

    # GauchaZH: o paywall e server-side mas o HTML embute o JSON do artigo
    # em window.__ISOMORPHIC_DATA__. Extrai dali em vez de tentar burlar.
    "gauchazh.clicrbs.com.br": {
        "ua": UA_DEFAULT,
        "referer": REFERER_GOOGLE,
        "extract_from": "__ISOMORPHIC_DATA__",
        "estrategia": "burlesco_gauchazh_isomorphic",
    },

    # --- sites com paywall client-side puro (HTML inteiro vem do servidor;
    # como nao executamos JS, paywall nao dispara). UA default + Referer
    # Google e suficiente. ---

    "brpolitico.com.br":        {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "correio24horas.com.br":    {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "correio.rac.com.br":       {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "diarinho.com.br":          {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "diariodaregiao.com.br":    {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "diariodecanoas.com.br":    {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "dgabc.com.br":             {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "exame.com":                {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "folhadelondrina.com.br":   {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "jornalnh.com.br":          {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "pioneiro.clicrbs.com.br":  {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "jornalvs.com.br":          {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "nsctotal.com.br":          {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "observador.pt":            {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "quatrorodas.abril.com.br": {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "revistaoeste.com":         {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "seudinheiro.com":          {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "super.abril.com.br":       {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},
    "veja.abril.com.br":        {"ua": UA_DEFAULT,   "referer": REFERER_GOOGLE},

    # --- sites com paywall mais agressivo (server-side + JS). Para esses,
    # combo UA Googlebot + Referer Google e o que funciona em HTTP. ---

    "elpais.com":               {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
    "brasil.elpais.com":        {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
    "em.com.br":                {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
    "folha.uol.com.br":         {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
    "gazetadopovo.com.br":      {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
    "estadao.com.br":           {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
    "oglobo.globo.com":         {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
    "valor.globo.com":          {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
    "epoca.globo.com":          {"ua": UA_GOOGLEBOT, "referer": REFERER_GOOGLE},
}


# ─────────────────── Helpers ──────────────────────────────────────────────

def _hostname(url: str) -> str:
    try:
        h = (urllib.parse.urlparse(url).netloc or "").lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _regra_para_url(url: str) -> Optional[dict[str, Any]]:
    """Encontra a regra mais especifica que casa com o hostname da URL.

    Verifica sufixos em ordem decrescente de comprimento para que
    'noticias.uol.com.br' seja preferido a 'uol.com.br' quando ambos casam.
    """
    host = _hostname(url)
    if not host:
        return None
    candidatos = sorted(PAYWALL_RULES.keys(), key=len, reverse=True)
    for dom in candidatos:
        if host == dom or host.endswith("." + dom):
            return PAYWALL_RULES[dom]
    return None


def url_e_paywall_conhecido(url: str) -> bool:
    """True se o dominio da URL esta na lista do Burlesco."""
    return _regra_para_url(url) is not None


def listar_dominios_cobertos() -> list[str]:
    """Lista dos dominios reconhecidos por este modulo (para diagnostico)."""
    return sorted(PAYWALL_RULES.keys())


# ─────────────────── Aplicacao da regra ───────────────────────────────────

def _extrair_gauchazh_isomorphic(html: str) -> str:
    """GauchaZH: extrai o corpo do artigo de window.__ISOMORPHIC_DATA__.

    O HTML traz um JSON URI-encoded. Dentro dele, o array
    'article_body_components' contem os paragrafos do artigo.
    """
    if not html:
        return ""
    m = re.search(
        r"__ISOMORPHIC_DATA__\s*=\s*['\"](?P<body>.+?)['\"]\s*[,;]",
        html, flags=re.S,
    )
    if not m:
        return ""
    try:
        raw = urllib.parse.unquote(m.group("body"))
        data = json.loads(raw)
    except Exception:
        return ""
    # Caminho conhecido para o corpo
    partes: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            tipo = (obj.get("type") or obj.get("component") or "").lower()
            if tipo in {"paragraph", "p"}:
                txt = obj.get("content") or obj.get("text") or ""
                if isinstance(txt, str) and len(txt.strip()) >= 20:
                    partes.append(txt.strip())
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for x in obj:
                _walk(x)

    _walk(data)
    return "\n\n".join(partes)


def _resolver_ua(url: str, regra: dict[str, Any]) -> str:
    """UA da regra, com override por path quando configurado."""
    ua_special = regra.get("ua_special_path") or {}
    if ua_special:
        try:
            path = urllib.parse.urlparse(url).path or ""
            for prefix, ua in ua_special.items():
                if path.startswith(prefix):
                    return ua
        except Exception:
            pass
    return regra.get("ua") or UA_DEFAULT


def _http_get_com_regra(url: str, regra: dict[str, Any]) -> tuple[int, str, str]:
    """GET HTTP aplicando UA, Referer, Cookies e clear_cookies da regra."""
    if not _OK:
        return 0, "", ""
    ua = _resolver_ua(url, regra)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    referer = regra.get("referer")
    if referer:
        headers["Referer"] = referer

    cookies = regra.get("cookies") or {}
    clear_cookies = bool(regra.get("clear_cookies"))

    try:
        if clear_cookies:
            sess = requests.Session()
            sess.cookies.clear()
            r = sess.get(
                url, headers=headers, cookies={}, timeout=TIMEOUT,
                allow_redirects=True,
            )
            # blockAll: nao mantem cookies da resposta
            sess.cookies.clear()
        else:
            r = requests.get(
                url, headers=headers, cookies=cookies, timeout=TIMEOUT,
                allow_redirects=True,
            )
        # V200_18: corrige mojibake (UTF-8 lido como Latin-1).
        # A Folha/Estadao/Globo servem UTF-8 mas o header HTTP as vezes
        # declara ISO-8859-1 ou nao declara charset. O requests confia no
        # header e cai em Latin-1, gerando "RevoluÃ§Ã£o" em vez de
        # "Revolucao". Forcamos UTF-8 quando o header for vazio/Latin-1
        # e o conteudo parecer ter sequencia UTF-8 valida.
        return int(getattr(r, "status_code", 0) or 0), str(r.url or url), _ler_texto_utf8(r)
    except Exception:
        return 0, "", ""


def _ler_texto_utf8(r) -> str:
    """V200_18: decodifica response forcando UTF-8 quando faz sentido."""
    try:
        raw = r.content or b""
        if not raw:
            return ""
        # Header HTTP declara charset?
        enc_header = (r.encoding or "").lower()
        # Tenta detectar via meta charset do HTML
        try:
            sample = raw[:2048].decode("ascii", errors="ignore").lower()
            if 'charset=utf-8' in sample or 'charset="utf-8"' in sample:
                return raw.decode("utf-8", errors="replace")
            if 'charset=iso-8859-1' in sample or 'charset=latin-1' in sample:
                return raw.decode("iso-8859-1", errors="replace")
        except Exception:
            pass
        # Se header diz ISO/Latin e o conteudo TEM bytes UTF-8 validos, prefere UTF-8
        if enc_header in ("iso-8859-1", "latin-1", "latin1", "windows-1252", ""):
            try:
                texto_utf8 = raw.decode("utf-8")
                return texto_utf8
            except UnicodeDecodeError:
                return raw.decode("iso-8859-1", errors="replace")
        # Caso normal: respeita o header
        return r.text or ""
    except Exception:
        return r.text or ""


def _extrair_texto(html: str, titulo: str, url: str,
                    regra: dict[str, Any]) -> str:
    """Aplica extrator de artigo unico; trata caso especial GauchaZH."""
    if regra.get("extract_from") == "__ISOMORPHIC_DATA__":
        txt = _extrair_gauchazh_isomorphic(html)
        if len((txt or "").strip()) >= MIN_CHARS_VALIDOS:
            return txt
        # se nao achou o JSON, cai pro extrator generico
    try:
        from ururau.coleta.extracao_limpa_v200 import extrair_article_de_html
        r = extrair_article_de_html(html, url_pauta=url, titulo_pauta=titulo)
        if r.get("ok"):
            return r.get("texto") or ""
    except Exception:
        pass
    return ""


def _texto_valido(texto: str) -> bool:
    return len((texto or "").strip()) >= MIN_CHARS_VALIDOS


# ─────────────────── Estrategia compativel com bypass_paywall_v200 ────────

def tentar_bypass_burlesco(url: str, titulo: str = "") -> dict:
    """Estrategia: aplica a regra Burlesco do dominio quando ha uma.

    Retorna o mesmo formato das demais estrategias de bypass_paywall_v200.
    Se o dominio nao for reconhecido, retorna ok=False (deixa os fallbacks
    genericos atuarem).
    """
    regra = _regra_para_url(url)
    estrategia = (regra or {}).get("estrategia") or "burlesco_rule"

    if regra is None:
        return {
            "estrategia": "burlesco_dominio_nao_listado",
            "status": 0, "url_final": "", "chars": 0,
            "texto": "", "ok": False,
        }

    status, url_final, html = _http_get_com_regra(url, regra)
    texto = _extrair_texto(html, titulo, url_final or url, regra)
    return {
        "estrategia": estrategia,
        "status": status,
        "url_final": url_final,
        "chars": len(texto),
        "texto": texto,
        "ok": _texto_valido(texto),
    }


__all__ = [
    "PAYWALL_RULES",
    "tentar_bypass_burlesco",
    "url_e_paywall_conhecido",
    "listar_dominios_cobertos",
]
