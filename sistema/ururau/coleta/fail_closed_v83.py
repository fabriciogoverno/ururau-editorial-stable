"""
ururau/coleta/fail_closed_v83.py

Guard final de extração para o monitor 24h.

Regra v83:
- Se a coleta não capturou texto real da matéria, a pauta não entra em redação.
- Não pode gerar matéria a partir de título, snippet, chamada curta ou resumo RSS.
- No monitor, falha de extração é bloqueio total, não rascunho CMS.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class DecisaoColetaV83:
    ok: bool
    motivo: str
    codigo: str
    util_chars: int = 0
    scraped_chars: int = 0
    metodo: str = ""
    status: str = ""


def _bool_env(nome: str, padrao: bool = False) -> bool:
    raw = str(os.getenv(nome, "1" if padrao else "0")).strip().lower()
    return raw in {"1", "true", "sim", "yes", "s", "on"}


def _int_env(nome: str, padrao: int) -> int:
    try:
        return int(str(os.getenv(nome, str(padrao))).strip())
    except Exception:
        return padrao


def _texto_util(texto: str) -> int:
    texto = re.sub(r"https?://\S+", "", texto or "")
    texto = re.sub(r"\s+", " ", texto).strip()
    return len(texto)



def _metodo_tem_url_real_v104(metodo: str) -> bool:
    """Reconhece métodos que abriram URL pública real da matéria.

    Os métodos v86/v104 retornam nomes como requests:html_density,
    v104_requests:jsonld_articleBody, v104_wordpress_rest ou
    leitura_fonte_v104. Eles equivalem a url_scraping para o gate.
    """
    m = str(metodo or "").lower()
    bons = (
        "url_scraping", "requests:", "v86_requests:", "v104_requests:",
        "playwright", "v104_playwright", "v104_wordpress",
        "wordpress_rest", "leitura_fonte_v104", "leitura_fonte_v96",
        "v104_v86:requests:",
        "readability", "trafilatura", "newspaper", "article_extractor",
        "kimi_article_extractor", "jsonld", "articlebody", "amp", "next_data",
    )
    return any(x in m for x in bons)


def avaliar_extracao_para_monitor_v83(resultado: dict[str, Any], pauta: dict[str, Any] | None = None) -> DecisaoColetaV83:
    """Avalia se a extração permite seguir para redação no monitor 24h.

    A função é propositalmente rígida. Para monitor 24h, o projeto deve ter texto
    real raspado da URL final. RSS/snippet só pode ser usado como contexto auxiliar,
    nunca como base única da matéria.
    """
    pauta = pauta or {}
    status = str(resultado.get("extraction_status") or "failed").strip().lower()
    metodo = str(resultado.get("extraction_method") or "failed").strip().lower()
    metadata = resultado.get("metadata") or {}

    dossie = str(resultado.get("cleaned_source_text") or resultado.get("dossie") or "")
    util_chars = int(metadata.get("util_chars") or _texto_util(dossie) or 0)
    scraped_chars = int(metadata.get("scraped_chars") or len(str(resultado.get("raw_source_text") or "")) or 0)

    min_util = _int_env("URURAU_MIN_CHARS_TEXTO_FONTE", _int_env("URURAU_MIN_CHARS_FONTE_MONITOR", 500))
    min_scraped = _int_env("URURAU_MIN_CHARS_SCRAPED_MONITOR", min_util)
    exigir_url_scraping = _bool_env("URURAU_EXIGIR_URL_SCRAPING_MONITOR", True)
    permitir_short = _bool_env("URURAU_PERMITIR_SHORT_USABLE_MONITOR", False)
    permitir_rss = _bool_env("URURAU_PERMITIR_RSS_ONLY_MONITOR", False)
    bloquear_google_unresolved = _bool_env("URURAU_BLOQUEAR_GOOGLE_NEWS_UNRESOLVED", True)

    if status == "failed":
        return DecisaoColetaV83(False, "extração falhou", "extracao_failed", util_chars, scraped_chars, metodo, status)

    if metodo in {"failed", "source_too_short_v81"}:
        return DecisaoColetaV83(False, f"método de extração inválido: {metodo}", "metodo_invalido", util_chars, scraped_chars, metodo, status)

    if bloquear_google_unresolved and metodo == "google_news_unresolved":
        return DecisaoColetaV83(False, "Google News não resolvido para URL real da fonte", "google_news_unresolved", util_chars, scraped_chars, metodo, status)

    if metodo == "rss_only" and not permitir_rss:
        return DecisaoColetaV83(False, "RSS/snippet não é aceito como texto da matéria no monitor", "rss_only_bloqueado", util_chars, scraped_chars, metodo, status)

    if exigir_url_scraping and not _metodo_tem_url_real_v104(metodo):
        return DecisaoColetaV83(False, f"monitor exige texto raspado de URL real; recebido: {metodo}", "sem_url_scraping", util_chars, scraped_chars, metodo, status)

    if status == "short_usable" and not permitir_short:
        return DecisaoColetaV83(False, "texto curto só pode virar pauta local, não matéria do monitor", "short_usable_bloqueado", util_chars, scraped_chars, metodo, status)

    if util_chars < min_util:
        return DecisaoColetaV83(False, f"texto útil insuficiente: {util_chars}<{min_util}", "texto_util_insuficiente", util_chars, scraped_chars, metodo, status)

    if exigir_url_scraping and scraped_chars < min_scraped:
        return DecisaoColetaV83(False, f"texto raspado insuficiente: {scraped_chars}<{min_scraped}", "scraped_insuficiente", util_chars, scraped_chars, metodo, status)

    return DecisaoColetaV83(True, f"texto da matéria capturado: util={util_chars}, scraped={scraped_chars}", "ok", util_chars, scraped_chars, metodo, status)


def aplicar_bloqueio_coleta_v83(pauta: dict[str, Any], decisao: DecisaoColetaV83) -> dict[str, Any]:
    """Marca a pauta como bloqueada por falha de coleta, sem rascunho CMS."""
    pauta["_bloqueio_coleta_v83"] = True
    pauta["bloqueio_coleta_v83"] = True
    pauta["motivo_bloqueio_coleta_v83"] = decisao.motivo
    pauta["codigo_bloqueio_coleta_v83"] = decisao.codigo
    pauta["status_validacao"] = "erro_extracao"
    pauta["status_publicacao_sugerido"] = "bloquear_total"
    pauta["revisao_humana_necessaria"] = False
    pauta["extraction_status"] = decisao.status or pauta.get("extraction_status") or "failed"
    pauta["extraction_method"] = decisao.metodo or pauta.get("extraction_method") or "failed"
    pauta["source_sufficiency_score"] = 0
    return pauta
