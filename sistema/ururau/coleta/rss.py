"""
coleta/rss.py — Coleta de pautas via RSS e Google News.
Inclui deduplicação por similaridade de título.

Filtro temporal v100:
  - Apenas pautas publicadas nas últimas 4 horas, em horário de Brasília.
  - Datas UTC/GMT de RSS e Google News são convertidas para America/Sao_Paulo.
  - Pautas sem data confiável, futuras ou fora da janela não entram na fila.

v43: Lê consultas_google_news.json e fontes_oficiais_prioritarias.json (se existirem).
     Chama enriquecer_pauta_com_intel() em cada pauta coletada.
"""
from __future__ import annotations

import datetime
import os
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import feedparser
import requests

from ururau.config.settings import HEADERS, TIMEOUT_PADRAO
from ururau.coleta.datas_v99 import (
    dentro_da_janela,
    formatar_br,
    janela_publicacao_horas,
    janela_para_fonte_v200,
    normalizar_data_publicacao,
    ordenar_iso,
    parse_data_br_ou_iso,
)

try:
    from ururau.coleta.source_policy_v114 import (
        deve_ignorar_pauta as _v114_deve_ignorar_pauta,
        ordenar_fontes as _v114_ordenar_fontes,
        status_fonte_por_log as _v114_status_fonte_por_log,
    )
except Exception:  # compatibilidade se o arquivo não existir
    _v114_deve_ignorar_pauta = None  # type: ignore
    _v114_ordenar_fontes = None  # type: ignore
    _v114_status_fonte_por_log = None  # type: ignore

# v200: pre-processamento de URL para endpoints oficiais quebrados +
# fetch resiliente para dominios com timeout cronico (girorj.com.br).
try:
    from ururau.coleta.fontes_oficiais_fallback_v200 import (
        substituir_url_se_quebrado as _v200_substituir_url,
        dominio_e_timeout_cronico as _v200_dominio_timeout_cronico,
        url_wayback_recente as _v200_wayback,
        habilitado as _v200_fallback_habilitado,
    )
except Exception:
    _v200_substituir_url = None  # type: ignore
    _v200_dominio_timeout_cronico = None  # type: ignore
    _v200_wayback = None  # type: ignore
    _v200_fallback_habilitado = None  # type: ignore


def _parsear_feed_resiliente_v200(url_feed: str):
    """Parser de feed que aplica fallback de URL e fetch resiliente.

    1. **V200_2**: se URL estiver na blocklist (chronic fail), pula imediato.
    2. Se URL for de endpoint oficial quebrado, substitui por GNews site:filter.
    3. Se dominio tem timeout cronico, usa http_fetch_v109 com timeout maior.
    4. Se ainda falhar, tenta Wayback Machine antes de retornar feed vazio.
    Retorna o objeto feed do feedparser (com .entries possivelmente vazio).
    """
    # V200_2: blocklist de URLs em cooldown cronico (skip imediato)
    try:
        from ururau.coleta.fontes_blocklist_v200 import eh_url_bloqueada
        _bloq, _mot = eh_url_bloqueada(url_feed)
        if _bloq:
            print(f"[RSS v200_2][BLOCKLIST] skip {url_feed[:80]} ({_mot})")
            return feedparser.parse("")
    except Exception:
        pass

    url_efetiva = url_feed
    motivo_sub = ""
    if _v200_substituir_url and _v200_fallback_habilitado and _v200_fallback_habilitado():
        try:
            url_efetiva, motivo_sub = _v200_substituir_url(url_feed, janela_horas=24)
            if motivo_sub:
                print(f"[RSS v200][FALLBACK] {url_feed} -> {url_efetiva} ({motivo_sub})")
        except Exception as _e:
            url_efetiva = url_feed

    # Timeout cronico? usa fetch resiliente
    timeout_cronico = False
    try:
        if _v200_dominio_timeout_cronico and _v200_dominio_timeout_cronico(url_efetiva):
            timeout_cronico = True
    except Exception:
        timeout_cronico = False

    if timeout_cronico:
        try:
            from ururau.coleta.http_fetch_v109 import fetch_rss_v109
            r = fetch_rss_v109(
                url_efetiva,
                timeout=int(os.getenv("URURAU_V200_GIROJ_TIMEOUT", "45") or "45"),
                max_retries=int(os.getenv("URURAU_V200_GIROJ_RETRIES", "3") or "3"),
                referer="https://www.google.com/",
            )
            if r.ok:
                print(f"[RSS v200][TIMEOUT_CRONICO_OK] {url_efetiva}")
                return feedparser.parse(r.text)
            print(f"[RSS v200][TIMEOUT_CRONICO_FALHA] {url_efetiva}: {r.erro}")
        except Exception as e:
            print(f"[RSS v200][TIMEOUT_CRONICO_ERR] {url_efetiva}: {e}")
        # Wayback como ultimo recurso
        try:
            if _v200_wayback:
                wb = _v200_wayback(url_efetiva)
                print(f"[RSS v200][WAYBACK] tentando {wb}")
                return feedparser.parse(wb)
        except Exception:
            pass
        return feedparser.parse("")  # feed vazio

    return feedparser.parse(url_efetiva)


# ── Carregadores de config externos ───────────────────────────────────────────

def _carregar_consultas_google_news() -> dict:
    """
    Carrega consultas_google_news.json do diretório raiz.
    Retorna dict de grupos de termos ou {} se não existir.
    """
    try:
        p = Path("consultas_google_news.json")
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[RSS] Aviso: não foi possível carregar consultas_google_news.json: {e}")
    return {}


def _carregar_fontes_oficiais() -> list[dict]:
    """
    Carrega fontes_oficiais_prioritarias.json e retorna lista de fontes RSS ativas.
    Retorna [] se não existir ou se todas estiverem inativas.
    """
    try:
        p = Path("fontes_oficiais_prioritarias.json")
        if p.exists():
            dados = json.loads(p.read_text(encoding="utf-8"))
            fontes = dados.get("fontes", []) if isinstance(dados, dict) else dados
            return [f for f in fontes if f.get("ativo", False) and f.get("url")]
    except Exception as e:
        print(f"[RSS] Aviso: não foi possível carregar fontes_oficiais_prioritarias.json: {e}")
    return []


def obter_termos_google_news(termos_fallback: list[str]) -> list[str]:
    """
    Retorna termos de busca para Google News.

    v111.4: por padrão, usa somente os termos simples configurados na aba
    Termos/termos_watchlist_v98.json. Consultas por grupos continuam existindo
    para o ciclo combinado v111, mas não poluem o motor rápido do painel.
    """
    termos: list[str] = []
    vistos: set[str] = set()

    def add(t):
        t = str(t or "").strip()
        if not t or t.startswith(("http://", "https://")):
            return
        # Se colaram o formato antigo Termo|Peso|Canal, usa só o termo.
        t = t.split("|", 1)[0].strip()
        if not t:
            return
        k = t.lower()
        if k not in vistos:
            termos.append(t)
            vistos.add(k)

    # Prioridade: termos simples do painel.
    try:
        from ururau.coleta.termos_config_v98 import termos_busca
        for t in termos_busca():
            add(t)
    except Exception as e:
        print(f"[RSS][TERMOS v111.4] termos simples indisponíveis: {e}")

    # Só usa consultas_google_news.json no motor rápido se a flag estiver ligada.
    if os.getenv("URURAU_TERMOS_USAR_CONSULTAS_COMPLETAS", "0").lower() in {"1", "true", "sim", "yes", "s"}:
        consultas = _carregar_consultas_google_news()
        if consultas:
            for grupo_key, grupo in consultas.items():
                if str(grupo_key).startswith("_"):
                    continue
                if isinstance(grupo, dict):
                    for t in grupo.get("termos", []):
                        add(t)
                elif isinstance(grupo, list):
                    for t in grupo:
                        add(t)
                elif isinstance(grupo, str):
                    add(grupo)

    if not termos:
        try:
            from ururau.coleta.source_policy_v114 import termos_simples_padrao
            for t in termos_simples_padrao():
                add(t)
        except Exception:
            for t in termos_fallback:
                add(t)
    return termos

def _enriquecer_pautas_com_intel(pautas: list[dict]) -> list[dict]:
    """
    Aplica enriquecer_pauta_com_intel() em cada pauta.
    Silencioso em caso de erro de importação (compatibilidade retroativa).
    """
    try:
        from ururau.coleta.intel_editorial import enriquecer_pauta_com_intel
        return [enriquecer_pauta_com_intel(p) for p in pautas]
    except Exception as e:
        print(f"[RSS] Intel editorial indisponível (fallback): {e}")
    return pautas

# ── Janela temporal ───────────────────────────────────────────────────────────
# v99: somente matérias publicadas nas últimas 4 horas. Pode ser ajustado via .env.
MAX_HORAS_PAUTA    = janela_publicacao_horas(4)
PRIO_ALTA_HORAS    = MAX_HORAS_PAUTA


# ── Utilitários ───────────────────────────────────────────────────────────────

def _normalizar_titulo(titulo: str) -> str:
    """Normaliza título para comparação de duplicatas."""
    t = titulo.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _similaridade(a: str, b: str) -> float:
    """
    Similaridade simples entre dois títulos baseada em palavras comuns.
    Retorna float entre 0 e 1.
    """
    palavras_a = set(_normalizar_titulo(a).split())
    palavras_b = set(_normalizar_titulo(b).split())

    # Remove stopwords comuns
    stopwords = {
        "de", "da", "do", "das", "dos", "em", "na", "no", "nas", "nos",
        "e", "ou", "a", "o", "as", "os", "um", "uma", "uns", "umas",
        "que", "se", "com", "por", "para", "ao", "à", "é", "foi",
    }
    palavras_a -= stopwords
    palavras_b -= stopwords

    if not palavras_a or not palavras_b:
        return 0.0

    intersecao = palavras_a & palavras_b
    uniao = palavras_a | palavras_b
    return len(intersecao) / len(uniao)


def _uid_pauta(link: str, titulo: str) -> str:
    return hashlib.md5(f"{link}{titulo}".encode()).hexdigest()[:16]


def _limpar_html(texto: str) -> str:
    """Remove tags HTML básicas de resumos RSS."""
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _texto_util_len_v106(texto: str) -> int:
    try:
        from ururau.coleta.limpeza_texto_v81 import texto_util_chars
        return int(texto_util_chars(str(texto or "")))
    except Exception:
        return len(str(texto or "").strip())


def _html_para_texto_rss_v106(valor: str, titulo: str = "") -> str:
    valor = str(valor or "").strip()
    if not valor:
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(valor, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "button", "iframe", "svg"]):
            tag.decompose()
        texto = soup.get_text("\n", strip=True)
    except Exception:
        texto = _limpar_html(valor)
    try:
        from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101
        texto = limpar_texto_artigo_v101(texto, titulo=titulo, max_chars=16000)
    except Exception:
        texto = re.sub(r"\n{3,}", "\n\n", texto or "").strip()
    return texto.strip()


def _extrair_texto_rss_integral_v106(entry: dict, titulo: str = "") -> str:
    """Aproveita texto integral quando o feed entrega content:encoded/content.value.

    A v105 passou a recusar snippet curto corretamente, mas isso também fez o
    painel perder os casos bons em que o RSS já trazia texto completo. A v106
    volta a preservar apenas RSS realmente longo e útil.
    """
    candidatos: list[str] = []
    try:
        for c in entry.get("content") or []:
            if isinstance(c, dict):
                candidatos.append(c.get("value") or c.get("content") or "")
            else:
                candidatos.append(str(c or ""))
    except Exception:
        pass
    for key in list(getattr(entry, "keys", lambda: [])()):
        lk = str(key).lower()
        if lk in ("content:encoded", "encoded", "content_encoded") or "encoded" in lk:
            try:
                candidatos.append(entry.get(key) or "")
            except Exception:
                pass
    try:
        sd = entry.get("summary_detail") or {}
        if isinstance(sd, dict):
            candidatos.append(sd.get("value") or "")
    except Exception:
        pass
    candidatos.extend([entry.get("description") or "", entry.get("summary") or ""])

    min_chars = int(os.getenv("URURAU_V106_MIN_CHARS_RSS_PRETEXTO", "900") or "900")
    melhor = ""
    melhor_util = 0
    for raw in candidatos:
        txt = _html_para_texto_rss_v106(raw, titulo=titulo)
        util = _texto_util_len_v106(txt)
        if util > melhor_util:
            melhor = txt
            melhor_util = util
    if melhor_util >= min_chars:
        return melhor[:16000]
    return ""


def _extrair_imagem_rss_v106(entry: dict) -> str:
    """Extrai imagem já declarada no RSS, quando houver."""
    def clean(u):
        u = str(u or "").strip()
        if not u or u.startswith("data:"):
            return ""
        if any(x in u.lower() for x in ("favicon", "logo", "sprite", "pixel", "1x1", "blank")):
            return ""
        return u
    for key in ("media_content", "media_thumbnail", "media_credit"):
        try:
            val = entry.get(key) or []
            if isinstance(val, dict):
                val = [val]
            for item in val:
                if isinstance(item, dict):
                    u = clean(item.get("url") or item.get("href"))
                    if u:
                        return u
        except Exception:
            pass
    try:
        for enc in entry.get("enclosures") or []:
            if isinstance(enc, dict):
                typ = str(enc.get("type") or "").lower()
                u = clean(enc.get("href") or enc.get("url"))
                if u and ("image" in typ or any(ext in u.lower() for ext in (".jpg", ".jpeg", ".png", ".webp"))):
                    return u
    except Exception:
        pass
    try:
        for link in entry.get("links") or []:
            if isinstance(link, dict):
                typ = str(link.get("type") or "").lower()
                rel = str(link.get("rel") or "").lower()
                u = clean(link.get("href") or link.get("url"))
                if u and ("image" in typ or rel in ("enclosure", "image") or any(ext in u.lower() for ext in (".jpg", ".jpeg", ".png", ".webp"))):
                    return u
    except Exception:
        pass
    for key in ("image", "thumbnail", "thumb"):
        try:
            val = entry.get(key)
            if isinstance(val, dict):
                u = clean(val.get("href") or val.get("url"))
            else:
                u = clean(val)
            if u:
                return u
        except Exception:
            pass
    return ""


def _aplicar_preconteudo_rss_v106(pauta: dict, entry: dict, titulo: str) -> dict:
    """Marca pauta como TXT OK quando o RSS já traz matéria integral."""
    texto = _extrair_texto_rss_integral_v106(entry, titulo=titulo)
    if texto:
        util = _texto_util_len_v106(texto)
        pauta.update({
            "_fonte_aba_texto": texto,
            "fonte_aba_texto": texto,
            "leitura_fonte_texto": texto,
            "cleaned_source_text": texto,
            "raw_source_text": texto,
            "original_source_text": texto,
            "texto_fonte": texto[:12000],
            "dossie": texto[:12000],
            "extraction_status": "ok",
            "extraction_method": "rss_fulltext_v106",
            "status_fonte_v105": "ok",
            "status_fonte_v106": "ok",
            "fonte_chars_v105": util,
            "fonte_chars_v106": util,
        })
    img = _extrair_imagem_rss_v106(entry)
    if img:
        pauta.setdefault("imagem_url", img)
        pauta["imagem_url_rss"] = img
        pauta.setdefault("imagem_credito", "Reprodução")
        if not pauta.get("imagem_status"):
            pauta["imagem_status"] = "url_pendente"
    return pauta


def _extrair_dt(entry: dict) -> Optional[datetime.datetime]:
    """Extrai e normaliza a data da fonte para horário de Brasília."""
    dt, _raw, _metodo = normalizar_data_publicacao(entry)
    return dt


def _campos_data_publicacao(entry: dict, dt: Optional[datetime.datetime]) -> dict:
    dt_norm, raw, metodo = normalizar_data_publicacao(entry)
    if dt_norm is not None:
        dt = dt_norm
    return {
        "data_pub_fonte": formatar_br(dt),
        "data_pub_fonte_br": formatar_br(dt),
        "data_pub_fonte_original": raw,
        "data_pub_metodo_v99": metodo,
        "_data_pub_ordem": ordenar_iso(dt),
    }


def _dt_para_str(dt: Optional[datetime.datetime]) -> str:
    """Formata datetime já normalizado para horário de Brasília."""
    return formatar_br(dt)


def _calcular_prioridade(dt: Optional[datetime.datetime], agora: datetime.datetime) -> int:
    """Aceita somente pautas publicadas dentro da janela v99."""
    ok, _motivo, idade_horas = dentro_da_janela(dt, agora)
    if not ok:
        return 0
    if idade_horas <= 1:
        return 3
    if idade_horas <= 2:
        return 2
    return 1



try:
    from ururau.coleta.fonte_registry_v126 import normalizar_nome_fonte_v126
except Exception:
    def normalizar_nome_fonte_v126(url, nome_atual=None):
        return nome_atual or urlparse_nome(url)

def _v1304_aplicar_flags_fonte_rss(pauta: dict, fonte: dict, nome_fonte: str, url_feed: str) -> dict:
    """v130.4: preserva flags de fonte regional prioritária no item retornado pelo RSS.

    NF Notícias não deve usar o coletor de Fonte Especial genérica. Ele usa o RSS normal,
    mas com bypass de score e cota mínima por interesse, para entrar na fila quando o feed
    trouxer factual policial/regional de Campos e Norte Fluminense.
    """
    try:
        nfonte = (nome_fonte or "").lower()
        ufeed = (url_feed or "").lower()
        regional = bool(
            fonte.get("regional_prioritaria")
            or fonte.get("regional_prioritaria_v1304")
            or fonte.get("tipo") == "rss_regional_prioritario_v1304"
            or fonte.get("tipo_coleta") == "rss_regional_prioritario_v1304"
            or "nfnoticias.com.br" in ufeed
            or "nf noticias" in nfonte
            or "nfnoticias" in nfonte
        )
        if regional:
            pauta["_v1304_rss_regional_prioritario"] = True
            pauta["_v1304_fonte_regional_prioritaria"] = True
            pauta["_v1304_motivo_regional_prioritario"] = "NF Notícias/fonte regional prioritária por RSS normal"
            pauta["bypass_score"] = True
            pauta["regional_prioritaria"] = True
            pauta["tipo_fonte"] = "rss_regional_prioritario_v1304"
    except Exception:
        pass
    return pauta

# ── Coleta RSS ────────────────────────────────────────────────────────────────

def coletar_rss(fontes_config: list[dict], incluir_oficiais: bool = True) -> list[dict]:
    """
    Coleta pautas de uma lista de feeds RSS configurados.

    Parâmetro fontes_config: lista de dicts com:
      - url: str — URL do feed RSS
      - nome: str — Nome da fonte para exibição
      - canal_forcado: str (opcional) — Canal editorial pré-definido

    Retorna lista de dicts com campos padronizados.
    """
    pautas: list[dict] = []

    from zoneinfo import ZoneInfo as _ZI
    agora    = datetime.datetime.now(_ZI("America/Sao_Paulo")).replace(tzinfo=None)
    filtradas = 0
    motivos_filtro: dict[str, int] = {}

    # V200_2: zera o cache de auto-cura no inicio de cada coleta geral
    try:
        from ururau.coleta.diagnostico_auto_v200 import limpar_cache_autocura
        limpar_cache_autocura()
    except Exception:
        pass

    try:
        if _v114_ordenar_fontes is not None:
            incluir_quarentena = os.getenv("URURAU_FONTES_INCLUIR_QUARENTENA", "0").lower() in {"1", "true", "sim", "yes", "s"}
            fontes_config = _v114_ordenar_fontes(fontes_config, incluir_quarentena=incluir_quarentena)
    except Exception:
        pass

    for fonte in fontes_config:
        if fonte.get("ativo", True) is False:
            continue
        url_feed   = fonte.get("url", "")
        nome_fonte = normalizar_nome_fonte_v126(url_feed, fonte.get("nome", urlparse_nome(url_feed)))
        canal      = ""  # v117: canal da fonte ignorado; editoria é contextual
        try:
            st_v114 = _v114_status_fonte_por_log(fonte) if _v114_status_fonte_por_log else ""
            if st_v114 == "quarentena":
                print(f"[RSS][v111.4][QUARENTENA] pulando fonte sem produtividade recente: {nome_fonte}")
                continue
        except Exception:
            pass

        if not url_feed:
            continue

        try:
            feed = _parsear_feed_resiliente_v200(url_feed)
            entradas = feed.get("entries", [])
            print(f"[RSS] {nome_fonte}: {len(entradas)} entradas")

            # V200_2 AUTO-CURA: feed devolveu 0 itens — roda o diagnostico
            # de fonte inline, aplica perfil fresco e tenta a cascata
            # universal (rss xml -> wp api -> sitemap -> html). Cacheado
            # por dominio. Politica: so sinaliza, nunca desativa.
            if not entradas:
                try:
                    if os.getenv("URURAU_V200_AUTOCURA_COLETA", "1").strip().lower() in {"1", "true", "sim", "yes", "s", "on"}:
                        from ururau.coleta.diagnostico_auto_v200 import auto_curar_fonte_v200
                        _cura = auto_curar_fonte_v200(
                            url_feed, nome=nome_fonte,
                            grupo=str(fonte.get("grupo") or "RSS"),
                            log=lambda m: print(m),
                        )
                        if _cura.get("ok") and _cura.get("pautas"):
                            _pautas_cura = _cura["pautas"]
                            print(f"[RSS][AUTOCURA_V200] {nome_fonte}: "
                                  f"+{len(_pautas_cura)} pauta(s) via {_cura.get('estrategia')}")
                            for _pc in _pautas_cura:
                                if isinstance(_pc, dict):
                                    _pc.setdefault("_origem_autocura_v200", True)
                                    _pc.setdefault("fonte_nome", nome_fonte)
                                    pautas.append(_pc)
                except Exception as _e_cura:
                    print(f"[RSS][AUTOCURA_V200] {nome_fonte}: auto-cura falhou: {_e_cura}")
            try:
                max_por_link_v117 = int(os.getenv("URURAU_RSS_MAX_POR_LINK", "10"))
            except Exception:
                max_por_link_v117 = 10
            aceitas_fonte_v117 = 0
            fallback_fora_janela_v123 = None  # v123: guarda 1 item mais recente fora da janela

            for entry in entradas[:30]:
                if max_por_link_v117 > 0 and aceitas_fonte_v117 >= max_por_link_v117:
                    break
                titulo = (entry.get("title") or "").strip()
                link   = (entry.get("link") or "").strip()
                if not titulo or not link:
                    continue

                resumo = _limpar_html(
                    entry.get("summary") or
                    entry.get("description") or
                    ""
                )
                if _v114_deve_ignorar_pauta is not None:
                    ignorar, motivo_ruido = _v114_deve_ignorar_pauta(titulo, resumo, link, nome_fonte)
                    if ignorar:
                        print(f"[RSS][v111.4][RUIDO] {motivo_ruido}: {titulo[:80]}")
                        continue

                # Data de publicação original na fonte, convertida para Brasília
                dt = _extrair_dt(entry)
                campos_data = _campos_data_publicacao(entry, dt)
                data_pub = campos_data["data_pub_fonte"]

                # Filtro temporal v100/v200 — janela diferenciada por tipo de fonte.
                janela_fonte = janela_para_fonte_v200(fonte, url_feed, nome_fonte)
                ok_janela, motivo_janela, idade_horas = dentro_da_janela(dt, agora, janela_horas=janela_fonte)
                if not ok_janela:
                    filtradas += 1
                    try:
                        motivos_filtro[motivo_janela] = motivos_filtro.get(motivo_janela, 0) + 1
                    except NameError:
                        pass
                    # v123: se uma fonte não tiver nada dentro da janela,
                    # guardamos o item mais recente dela para entrar como exceção operacional.
                    try:
                        permitir_excecao_v123 = os.getenv("URURAU_RSS_COLETAR_1_FORA_JANELA", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
                        if permitir_excecao_v123 and fallback_fora_janela_v123 is None and dt is not None:
                            fallback_fora_janela_v123 = (entry, titulo, link, resumo, campos_data, data_pub, idade_horas, motivo_janela)
                    except Exception:
                        pass
                    continue
                if idade_horas <= 1:
                    prio = 3
                elif idade_horas <= 2:
                    prio = 2
                else:
                    prio = 1

                pauta = {
                    "titulo_origem":   titulo,
                    "link_origem":     link,
                    "fonte_nome":      nome_fonte,
                    "resumo_origem":   resumo[:600],
                    "canal_forcado":   canal,
                    "data_pub_fonte":  data_pub,
                    **campos_data,
                    "_uid":            _uid_pauta(link, titulo),
                    "prioridade":      prio,   # v99: 3=última hora, 2=até 2h, 1=até 4h
                    "_janela_aplicada_v200_horas": janela_fonte,
                }
                pauta = _aplicar_preconteudo_rss_v106(pauta, entry, titulo)
                pauta = _v1304_aplicar_flags_fonte_rss(pauta, fonte, nome_fonte, url_feed)
                try:
                    from ururau.editorial.classificador_editorial_contextual_v117 import aplicar_editoria_contextual
                    pauta = aplicar_editoria_contextual(pauta)
                except Exception:
                    pass
                pautas.append(pauta)
                try:
                    aceitas_fonte_v117 += 1
                except Exception:
                    pass

            # v123: exceção operacional — se a fonte respondeu, mas tudo ficou fora da janela,
            # entra 1 pauta mais recente para comprovar funcionamento e alimentar a fila.
            try:
                if aceitas_fonte_v117 == 0 and fallback_fora_janela_v123 is not None:
                    entry_fb, titulo_fb, link_fb, resumo_fb, campos_data_fb, data_pub_fb, idade_fb, motivo_fb = fallback_fora_janela_v123
                    pauta_fb = {
                        "titulo_origem":   titulo_fb,
                        "link_origem":     link_fb,
                        "fonte_nome":      nome_fonte,
                        "resumo_origem":   resumo_fb[:600],
                        "canal_forcado":   canal,
                        "data_pub_fonte":  data_pub_fb,
                        **campos_data_fb,
                        "_uid":            _uid_pauta(link_fb, titulo_fb),
                        "prioridade":      0,
                        "_excecao_fora_janela_v123": True,
                        "_motivo_excecao_janela_v123": str(motivo_fb),
                        "_idade_pub_horas_v123": round(float(idade_fb), 2),
                    }
                    pauta_fb = _aplicar_preconteudo_rss_v106(pauta_fb, entry_fb, titulo_fb)
                    pauta_fb = _v1304_aplicar_flags_fonte_rss(pauta_fb, fonte, nome_fonte, url_feed)
                    try:
                        from ururau.editorial.classificador_editorial_contextual_v117 import aplicar_editoria_contextual
                        pauta_fb = aplicar_editoria_contextual(pauta_fb)
                    except Exception:
                        pass
                    pautas.append(pauta_fb)
                    aceitas_fonte_v117 += 1
                    print(f"[RSS][v123][EXCECAO_JANELA] {nome_fonte}: entrou 1 mais recente fora da janela ({idade_fb:.2f}h)")
            except Exception as _e_fallback_janela_v123:
                print(f"[RSS][v123][EXCECAO_JANELA] falhou em {nome_fonte}: {_e_fallback_janela_v123}")

        except Exception as e:
            print(f"[RSS] Falha ao processar feed {url_feed}: {e}")

        time.sleep(0.3)  # Pausa gentil entre feeds

    if filtradas:
        detalhes = ", ".join(f"{k}={v}" for k, v in sorted(motivos_filtro.items())) or "sem detalhe"
        print(f"[RSS][v100] {filtradas} entradas ignoradas (janela de {janela_publicacao_horas()}h; {detalhes})")

    # ── Fontes oficiais prioritárias (adicional v43) ───────────────────────────
    # v94: permite desativar oficiais quando o painel coleta RSS fonte por fonte.
    fontes_oficiais = _carregar_fontes_oficiais() if incluir_oficiais else []
    if fontes_oficiais:
        print(f"[RSS] Fontes oficiais: {len(fontes_oficiais)} ativa(s)")
        for fo in fontes_oficiais:
            fo_config = {
                "url":           fo.get("url", ""),
                "nome":          fo.get("nome", fo.get("id", "Fonte oficial")),
                "canal_forcado": "",  # v117: fonte oficial não define editoria
            }
            try:
                feed = _parsear_feed_resiliente_v200(fo_config["url"])
                entradas = feed.get("entries", [])
                print(f"[RSS-OFICIAL] {fo_config['nome']}: {len(entradas)} entradas")
                for entry in entradas[:20]:
                    titulo = (entry.get("title") or "").strip()
                    link   = (entry.get("link") or "").strip()
                    if not titulo or not link:
                        continue
                    resumo = _limpar_html(entry.get("summary") or entry.get("description") or "")
                    dt = _extrair_dt(entry)
                    campos_data = _campos_data_publicacao(entry, dt)
                    data_pub = campos_data["data_pub_fonte"]
                    prio = _calcular_prioridade(dt, agora)
                    if prio == 0:
                        filtradas += 1
                        continue
                    pauta = {
                        "titulo_origem":   titulo,
                        "link_origem":     link,
                        "fonte_nome":      fo_config["nome"],
                        "resumo_origem":   resumo[:600],
                        "canal_forcado":   "",
                        "data_pub_fonte":  data_pub,
                        **campos_data,
                        "_uid":            _uid_pauta(link, titulo),
                        "prioridade":      prio,
                        "sinal_fonte_oficial": True,  # flag para scoring
                    }
                    pauta = _aplicar_preconteudo_rss_v106(pauta, entry, titulo)
                    try:
                        from ururau.editorial.classificador_editorial_contextual_v117 import aplicar_editoria_contextual
                        pauta = aplicar_editoria_contextual(pauta)
                    except Exception:
                        pass
                    pautas.append(pauta)
            except Exception as e_fo:
                print(f"[RSS-OFICIAL] Falha ao processar {fo_config['nome']}: {e_fo}")
            time.sleep(0.3)

    # ── Enriquece com intel editorial ─────────────────────────────────────────
    pautas = _enriquecer_pautas_com_intel(pautas)
    pautas.sort(key=lambda p: p.get("_data_pub_ordem", ""), reverse=True)
    return pautas


def urlparse_nome(url: str) -> str:
    """Extrai nome legível da URL do feed."""
    try:
        from urllib.parse import urlparse as _urlparse
        hostname = _urlparse(url).hostname or url
        # Remove www. e extensões de domínio comuns
        return re.sub(r"^www\.", "", hostname).split(".")[0].capitalize()
    except Exception:
        return "Fonte desconhecida"


# ── Google News RSS ───────────────────────────────────────────────────────────

def coletar_google_news(
    termos: list[str],
    max_por_termo: int = 10,
) -> list[dict]:
    """
    Coleta pautas do Google News via RSS para cada termo de busca.

    Parâmetros:
      - termos: lista de strings de busca (ex: ["Rio de Janeiro", "Lula"])
      - max_por_termo: número máximo de resultados por termo

    Retorna lista de dicts com campos padronizados.
    """
    pautas: list[dict] = []
    BASE_URL  = "https://news.google.com/rss/search?q={query}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
    from zoneinfo import ZoneInfo as _ZI
    agora     = datetime.datetime.now(_ZI("America/Sao_Paulo")).replace(tzinfo=None)
    filtradas = 0
    motivos_filtro: dict[str, int] = {}

    for termo in termos:
        query = quote_plus(termo)
        url_feed = BASE_URL.format(query=query)

        try:
            # v110: Google News RSS também passa pelo HTTP resiliente v109.
            try:
                from ururau.coleta.http_fetch_v109 import fetch_rss_v109
                frss = fetch_rss_v109(
                    url_feed,
                    timeout=int(os.getenv("URURAU_V109_GNEWS_RSS_TIMEOUT", "12") or "12"),
                    max_retries=int(os.getenv("URURAU_V109_GNEWS_RSS_RETRIES", os.getenv("URURAU_V109_HTTP_MAX_RETRIES", "3")) or "3"),
                    referer="https://news.google.com/",
                )
                if frss.ok:
                    feed = feedparser.parse(frss.text)
                else:
                    print(f"[GNEWS v110] Termo '{termo}': falha RSS resiliente ({frss.erro}); tentando feedparser direto")
                    feed = feedparser.parse(url_feed)
            except Exception:
                feed = feedparser.parse(url_feed)
            entradas = feed.get("entries", [])
            print(f"[GNEWS v110] Termo '{termo}': {len(entradas)} entradas")

            for entry in entradas[:max_por_termo]:
                titulo = (entry.get("title") or "").strip()
                link   = (entry.get("link") or "").strip()
                if not titulo or not link:
                    continue

                # Google News codifica a fonte no título: "Título - Fonte"
                fonte_nome = "Google News"
                if " - " in titulo:
                    partes = titulo.rsplit(" - ", 1)
                    titulo = partes[0].strip()
                    fonte_nome = partes[1].strip() if len(partes) > 1 else "Google News"

                resumo   = _limpar_html(entry.get("summary") or "")
                if _v114_deve_ignorar_pauta is not None:
                    ignorar, motivo_ruido = _v114_deve_ignorar_pauta(titulo, resumo, link, fonte_nome)
                    if ignorar:
                        print(f"[GNEWS][v111.4][RUIDO] {motivo_ruido}: {titulo[:80]}")
                        continue
                dt = _extrair_dt(entry)
                campos_data = _campos_data_publicacao(entry, dt)
                data_pub = campos_data["data_pub_fonte"]

                # Filtro temporal v100 — só entra se publicada dentro da janela configurada.
                ok_janela, motivo_janela, idade_horas = dentro_da_janela(dt, agora)
                if not ok_janela:
                    filtradas += 1
                    try:
                        motivos_filtro[motivo_janela] = motivos_filtro.get(motivo_janela, 0) + 1
                    except NameError:
                        pass
                    # v123: se uma fonte não tiver nada dentro da janela,
                    # guardamos o item mais recente dela para entrar como exceção operacional.
                    try:
                        permitir_excecao_v123 = os.getenv("URURAU_RSS_COLETAR_1_FORA_JANELA", "1").strip().lower() not in {"0", "false", "nao", "não", "off"}
                        if permitir_excecao_v123 and fallback_fora_janela_v123 is None and dt is not None:
                            fallback_fora_janela_v123 = (entry, titulo, link, resumo, campos_data, data_pub, idade_horas, motivo_janela)
                    except Exception:
                        pass
                    continue
                if idade_horas <= 1:
                    prio = 3
                elif idade_horas <= 2:
                    prio = 2
                else:
                    prio = 1

                try:
                    from ururau.coleta.kimi_bridge_v110 import _resolver_google_news_publico
                    link_real = _resolver_google_news_publico(link)
                except Exception:
                    link_real = link

                pauta = {
                    "titulo_origem":  titulo,
                    "link_origem":    link_real or link,
                    "fonte_nome":     fonte_nome,
                    "resumo_origem":  resumo[:600],
                    "canal_forcado":  "",
                    "data_pub_fonte": data_pub,
                    **campos_data,
                    "origem_feed": "google_news",
                    "link_google_news": link,
                    "_uid":           _uid_pauta(link_real or link, titulo),
                    "prioridade":     prio,
                }
                pauta = _aplicar_preconteudo_rss_v106(pauta, entry, titulo)
                try:
                    from ururau.editorial.classificador_editorial_contextual_v117 import aplicar_editoria_contextual
                    pauta = aplicar_editoria_contextual(pauta)
                except Exception:
                    pass
                pautas.append(pauta)

        except Exception as e:
            print(f"[GNEWS] Falha para termo '{termo}': {e}")

        time.sleep(0.5)

    if filtradas:
        detalhes = ", ".join(f"{k}={v}" for k, v in sorted(motivos_filtro.items())) or "sem detalhe"
        print(f"[GNEWS][v100] {filtradas} entradas ignoradas (janela de {janela_publicacao_horas()}h; {detalhes})")

    # ── Enriquece com intel editorial ─────────────────────────────────────────
    pautas = _enriquecer_pautas_com_intel(pautas)
    pautas.sort(key=lambda p: p.get("_data_pub_ordem", ""), reverse=True)
    return pautas


# ── Filtragem contra banco de dados ──────────────────────────────────────────

def filtrar_contra_banco(
    pautas: list[dict],
    db,
    janela_horas: int = 48,
) -> tuple[list[dict], dict]:
    """
    Filtra pautas já conhecidas no banco antes de entrar na fila.

    Checagens realizadas (em ordem):
      1. Pauta já publicada no Ururau (link exato ou uid)       → descarta
      2. Pauta descartada/rejeitada/bloqueada anteriormente     → descarta
      3. Pauta já captada e em processamento (em_redacao/pronta)→ descarta
      4. Título similar já publicado nas últimas 72h             → descarta
      5. Título similar a publicações das últimas janela_horas   → descarta

    Parâmetros:
      - pautas: lista de dicts vindos de coletar_rss / coletar_google_news
      - db: instância de Database (ururau.core.database.Database)
      - janela_horas: janela de horas para deduplicação temática (padrão 48h)

    Retorna:
      - (novas, resumo) onde 'novas' é a lista filtrada e 'resumo' é um dict
        com contagens de cada motivo de descarte.
    """
    novas: list[dict] = []
    resumo = {
        "total":       len(pautas),
        "publicadas":  0,
        "descartadas": 0,
        "em_fila":     0,
        "similares":   0,
        "aprovadas":   0,
    }

    # Busca títulos publicados nas últimas janela_horas para deduplicação temática
    try:
        publicadas_recentes = db.listar_publicadas_recentes(horas=janela_horas)
        titulos_recentes = [
            p.get("titulo_origem", "") or p.get("titulo", "")
            for p in publicadas_recentes if p
        ]
    except Exception:
        titulos_recentes = []

    for pauta in pautas:
        link  = pauta.get("link_origem", "")
        uid   = pauta.get("_uid", "")
        titulo = pauta.get("titulo_origem", "")

        # 0. Barreira definitiva: link bloqueado permanentemente
        #    Cobre tanto pautas descartadas quanto publicadas com um único índice
        try:
            if link and db.link_esta_bloqueado(link):
                resumo["descartadas"] += 1
                motivo_bloq = "bloqueado previamente"
                try:
                    motivo_bloq = db.motivo_link_bloqueado(link) or motivo_bloq
                except Exception:
                    pass
                print(f"[FILTRO][BLOQUEIO] {motivo_bloq}: {titulo[:80]}")
                continue
        except AttributeError:
            pass  # db mais antigo sem o método — segue com os checks normais

        # 1. Já publicada no Ururau?
        if db.pauta_ja_publicada(link, uid):
            resumo["publicadas"] += 1
            print(f"[FILTRO] Já publicada: {titulo[:60]}")
            continue

        # 2. Foi descartada/bloqueada antes?
        if db.pauta_foi_descartada(link, uid):
            resumo["descartadas"] += 1
            print(f"[FILTRO] Descartada anteriormente: {titulo[:60]}")
            continue

        # 3. Já está sendo processada (captada / em_redacao / pronta)?
        status_atual = db.classificar_pauta(link, uid)
        if status_atual in ("captada", "triada", "aprovada", "em_redacao", "revisada", "pronta"):
            resumo["em_fila"] += 1
            print(f"[FILTRO] Já na fila ({status_atual}): {titulo[:60]}")
            continue

        # 4. Título similar já publicado nas últimas 72h?
        titulo_similar = db.titulo_similar_ja_publicado(titulo)
        if titulo_similar:
            resumo["similares"] += 1
            print(f"[FILTRO] Título similar publicado: '{titulo_similar[:50]}' ← '{titulo[:50]}'")
            continue

        # 5. Verifica similaridade com publicações das últimas janela_horas
        if titulos_recentes:
            similar_recente = None
            for titulo_pub in titulos_recentes:
                if titulo_pub and _similaridade(titulo, titulo_pub) > 0.60:
                    similar_recente = titulo_pub
                    break
            if similar_recente:
                resumo["similares"] += 1
                print(f"[FILTRO] Similar a publicação recente ({janela_horas}h): "
                      f"'{similar_recente[:50]}' ← '{titulo[:50]}'")
                continue

        novas.append(pauta)
        resumo["aprovadas"] += 1

    print(
        f"[FILTRO] {resumo['total']} pautas - "
        f"{resumo['aprovadas']} novas | "
        f"{resumo['publicadas']} ja publicadas | "
        f"{resumo['descartadas']} descartadas | "
        f"{resumo['em_fila']} em fila | "
        f"{resumo['similares']} similares"
    )
    return novas, resumo


def deduplicar(pautas, limiar_similaridade=0.65):
    unicas = []
    titulos_aceitos = []
    for pauta in pautas:
        titulo = pauta.get("titulo_origem", "")
        if not titulo:
            continue
        links_aceitos = {p["link_origem"] for p in unicas}
        if pauta.get("link_origem") in links_aceitos:
            continue
        duplicata = False
        for titulo_aceito in titulos_aceitos:
            if _similaridade(titulo, titulo_aceito) >= limiar_similaridade:
                duplicata = True
                break
        if not duplicata:
            unicas.append(pauta)
            titulos_aceitos.append(titulo)
    print(f"[RSS] Deduplicacao: {len(pautas)} -> {len(unicas)} pautas")
    return unicas


def coletar_source_hunter_premium_v88():
    try:
        import os
        if os.getenv("URURAU_V91_SOURCE_HUNTER", "1").lower() in ("1","true","sim","yes","s"):
            from ururau.coleta.v91_pipeline_bridge import coletar_e_prevalidar_v91
            limite = int(os.getenv("URURAU_V91_MAX_TOTAL", os.getenv("URURAU_V88_MAX_TOTAL", "120")))
            janela = int(os.getenv("JANELA_BUSCA_MAXIMA_HORAS", "4"))
            return coletar_e_prevalidar_v91(limite=limite, janela=janela)
        if os.getenv("URURAU_V88_SOURCE_HUNTER", "1").lower() not in ("1","true","sim","yes","s"):
            return []
        from ururau.coleta.source_hunter_v88 import coletar_source_hunter_v88
        return coletar_source_hunter_v88()
    except Exception as e:
        print(f"[v91][SOURCE_HUNTER] indisponivel: {e}")
        return []


def obter_termos_radar_audiencia_v88():
    try:
        import os
        if os.getenv("URURAU_V88_RADAR_AUDIENCIA", "1").lower() not in ("1","true","sim","yes","s"):
            return []
        from ururau.coleta.radar_audiencia_v88 import termos_para_google_news_v88
        return termos_para_google_news_v88()
    except Exception as e:
        print(f"[v88][RADAR] indisponivel: {e}")
        return []
