# -*- coding: utf-8 -*-
"""Hidratador em background — V200_16.

Roda em thread daemon no servidor web. A cada N segundos:
  1. Busca pautas com TXT... (sem cleaned_source_text) na fila ativa
  2. Limita por janela temporal: prioriza últimas 4h, máximo 8h
  3. Para cada uma, roda o mesmo pipeline da hidratação on-demand
     (extract_pipeline_v90 + Jina + leitura_fonte como fallback)
  4. Persiste no banco (atualizar_pauta com dados_json novo)

Resultado: o usuário NÃO precisa clicar em cada pauta. À medida que o
worker processa, as pautas vão virando TXT OK na fila sozinhas.

Configuração por env (com defaults):
  URURAU_HIDRATADOR_INTERVALO_SEG=30      ciclo entre rodadas
  URURAU_HIDRATADOR_BATCH=10              pautas por rodada
  URURAU_HIDRATADOR_TIMEOUT_PAUTA=15      timeout por pauta (segundos)
  URURAU_HIDRATADOR_JANELA_MAX_H=8        janela máxima (horas)
  URURAU_HIDRATADOR_JANELA_PRIORIDADE_H=4 janela de prioridade (horas)
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)
PREFIX = "[HIDRATADOR_BG]"

# Configurável via env
INTERVALO_SEG = int(os.environ.get("URURAU_HIDRATADOR_INTERVALO_SEG", "30"))
BATCH = int(os.environ.get("URURAU_HIDRATADOR_BATCH", "10"))
TIMEOUT_PAUTA = int(os.environ.get("URURAU_HIDRATADOR_TIMEOUT_PAUTA", "15"))
JANELA_MAX_H = int(os.environ.get("URURAU_HIDRATADOR_JANELA_MAX_H", "8"))
JANELA_PRIORIDADE_H = int(
    os.environ.get("URURAU_HIDRATADOR_JANELA_PRIORIDADE_H", "4")
)
TEXTO_MIN_CHARS = 550

_stop_event = threading.Event()
_worker_thread: Optional[threading.Thread] = None
_estado = {
    "rodando": False,
    "ciclos": 0,
    "pautas_hidratadas": 0,
    "pautas_falhas": 0,
    "ultimo_ciclo_em": "",
    "ultima_pauta_uid": "",
    "ultimo_erro": "",
}
_estado_lock = threading.Lock()

# V200_34: fila de prioridade explicita.
# UIDs adicionados aqui sao processados no proximo ciclo, antes dos
# selecionados pela janela temporal. Usado quando o usuario clica numa
# pauta - ela "fura" a fila do BG e e hidratada imediatamente.
_prioridade_uids: list[str] = []
_prioridade_lock = threading.Lock()


def marcar_prioridade(uid: str) -> None:
    """Marca um uid para hidratacao prioritaria no proximo ciclo do BG."""
    if not uid:
        return
    uid = str(uid).strip()
    if not uid:
        return
    with _prioridade_lock:
        # Move para o topo (se ja estiver na fila) ou adiciona
        try:
            _prioridade_uids.remove(uid)
        except ValueError:
            pass
        _prioridade_uids.insert(0, uid)
        # Cap em 50 para nao crescer indefinidamente
        if len(_prioridade_uids) > 50:
            del _prioridade_uids[50:]


def _drenar_prioridade() -> list[str]:
    """Retorna a lista atual de prioridade e a esvazia. Thread-safe."""
    with _prioridade_lock:
        if not _prioridade_uids:
            return []
        out = list(_prioridade_uids)
        _prioridade_uids.clear()
        return out


def _texto_chars(p: dict[str, Any]) -> int:
    t = str(p.get("cleaned_source_text") or p.get("texto_fonte") or "").strip()
    return len(t)


def _imagem_ok(p: dict[str, Any]) -> bool:
    for k in ("imagem_url", "imagem", "og_image", "image_url", "imagem_capa"):
        v = p.get(k)
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            return True
    return False


def _link_pauta(p: dict[str, Any]) -> str:
    for k in ("link_origem_resolvido", "url_final", "canonical_url",
              "link_origem", "url_original", "link", "url"):
        v = p.get(k)
        if isinstance(v, str) and v.strip().startswith(("http://", "https://")):
            return v.strip()
    return ""


def _data_publicacao_iso(p: dict[str, Any]) -> str:
    """V200_17: extrai a data de publicacao REAL da fonte (quando foi
    publicado no site original), com fallback em varios campos.

    Ordem: data_pub_fonte, data_fonte, published_iso, published,
    pub_date, dataPublicacao, datePublished, data_publicacao.

    Aceita formatos:
      - ISO: 2026-05-15T10:30:00 ou 2026-05-15 10:30:00
      - RFC822: Wed, 15 May 2026 10:30:00 -0300
      - dd/mm/aaaa hh:mm
      - dd/mm/aaaa
    Retorna ISO YYYY-MM-DDTHH:MM:SS ou string vazia.
    """
    import re
    raw = ""
    for k in ("data_pub_fonte", "data_fonte", "published_iso", "published",
              "pub_date", "pubDate", "datePublished", "data_publicacao",
              "dataPublicacao"):
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            raw = v.strip()
            break
    if not raw:
        return ""
    # Limpa prefixo "Captada: " que aparece no view (fallback)
    if raw.lower().startswith("captada:"):
        return ""  # se so tem "Captada: ...", nao serve como data de fonte
    # Tenta ISO
    try:
        # Trata "2026-05-15 10:30:00" ou "2026-05-15T10:30:00..."
        s = raw.replace("T", " ")[:19].replace(" ", "T")
        dt = datetime.fromisoformat(s)
        return dt.isoformat(timespec="seconds")
    except Exception:
        pass
    # Tenta dd/mm/aaaa hh:mm[:ss]
    m = re.match(
        r"(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        raw,
    )
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        h = int(m.group(4) or 0)
        mi = int(m.group(5) or 0)
        se = int(m.group(6) or 0)
        try:
            return datetime(y, mo, d, h, mi, se).isoformat(timespec="seconds")
        except Exception:
            pass
    # Tenta RFC822 via email.utils
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            return dt.replace(tzinfo=None).isoformat(timespec="seconds")
    except Exception:
        pass
    return ""


def _selecionar_candidatas(db) -> list[dict[str, Any]]:
    """Retorna pautas TXT... dentro da janela de 8h, priorizando 4h.

    V200_33: tambem retorna pautas que JA tem texto OK mas falta imagem,
    para que o hidratador resolva o og:image em ciclo separado.
    """
    try:
        pautas = db.query_fila_ativa(incluir_baixo_score=False, limite=200)
    except Exception as e:
        logger.warning("%s query_fila_ativa falhou: %s", PREFIX, e)
        return []
    agora = datetime.now()
    janela_max = agora - timedelta(hours=JANELA_MAX_H)
    janela_prio = agora - timedelta(hours=JANELA_PRIORIDADE_H)
    candidatas: list[tuple[int, dict]] = []
    for p in pautas:
        tem_texto = _texto_chars(p) >= TEXTO_MIN_CHARS
        tem_imagem = _imagem_ok(p)
        # Ja tem texto suficiente E imagem? pula
        if tem_texto and tem_imagem:
            continue
        # Tem link real?
        if not _link_pauta(p):
            continue
        # V200_33: quarentena diferenciada
        #  - falha completa (sem texto e sem imagem): 1h
        #  - so falta imagem (texto ja OK): 30min (mais frequente)
        ult_tentativa = p.get("_hidratador_bg_tentado_em") or ""
        if ult_tentativa:
            try:
                dt = datetime.fromisoformat(ult_tentativa[:19])
                quarentena = timedelta(minutes=30) if tem_texto else timedelta(hours=1)
                if (agora - dt) < quarentena:
                    continue
            except Exception:
                pass
        # V200_17: janela considera data de publicacao da FONTE (quando a
        # materia foi publicada no site original), NAO a hora da coleta.
        # Antes: uma materia de 15/05 captada em 17/05 entrava no filtro
        # de "ultimas 8h" porque captada_em era recente.
        # Fallback cascateado: data_pub_fonte -> data_fonte -> published ->
        # captada_em (so se nao tem nenhuma data de publicacao).
        pub_iso = _data_publicacao_iso(p)
        try:
            pub_dt = datetime.fromisoformat(pub_iso) if pub_iso else None
        except Exception:
            pub_dt = None
        if pub_dt is None:
            # Sem data de publicacao confiavel -> usa captada_em como fallback
            cap_iso = str(p.get("captada_em") or p.get("atualizada_em") or "")[:19]
            try:
                pub_dt = datetime.fromisoformat(cap_iso) if cap_iso else agora
            except Exception:
                pub_dt = agora
        if pub_dt < janela_max:
            continue
        prio = 0 if pub_dt >= janela_prio else 1  # 0 = mais prioritário
        candidatas.append((prio, p))
    # Ordena: prioridade asc, captada_em desc
    candidatas.sort(key=lambda x: (
        x[0],
        -(_iso_to_ts(x[1].get("captada_em") or x[1].get("atualizada_em") or "")),
    ))
    return [p for _, p in candidatas[:BATCH]]


def _iso_to_ts(s: str) -> float:
    try:
        return datetime.fromisoformat(str(s)[:19]).timestamp()
    except Exception:
        return 0.0


def _resolver_link_real(url: str, titulo: str, fonte: str) -> str:
    """V200_33: resolve URL do Google News para a URL real da fonte
    (g1, folha, etc.) ANTES de tentar extrair. Se nao for Google News
    ou nao conseguir resolver, retorna a URL original.
    """
    if not url:
        return url
    try:
        if "news.google.com" not in url.lower():
            return url
        from ururau.coleta.link_resolver_v90 import resolver_url_final_v90
        r = resolver_url_final_v90(url, titulo or "", fonte or "")
        if r and r.get("ok") and r.get("url_final"):
            return str(r["url_final"]).strip()
    except Exception as e:
        logger.debug("%s resolve_link falhou url=%s: %s", PREFIX, url[:80], e)
    return url


def _extrair_og_image_leve(url: str, timeout: int = 8) -> str:
    """V200_33: GET leve + parse de og:image. Usado quando ja temos
    texto OK mas falta imagem. Nao requer JS, so o HTML inicial.
    """
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        import re
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        }
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        # Limita o trecho analisado pra nao gastar muito (head do HTML basta)
        html = resp.text[:120_000]
        # Procura og:image / twitter:image / link rel="image_src"
        padroes = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
            r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
        ]
        for pat in padroes:
            m = re.search(pat, html, flags=re.IGNORECASE)
            if m:
                src = m.group(1).strip()
                if src.startswith("//"):
                    src = "https:" + src
                elif src.startswith("/"):
                    from urllib.parse import urlparse
                    pu = urlparse(url)
                    src = f"{pu.scheme}://{pu.netloc}{src}"
                if src.startswith(("http://", "https://")):
                    return src
    except Exception as e:
        logger.debug("%s og_image leve falhou url=%s: %s", PREFIX, url[:80], e)
    return ""


def _hidratar_pauta(p: dict[str, Any]) -> dict[str, Any]:
    """Extrai texto + imagem da pauta usando o mesmo pipeline da on-demand.

    V200_33:
      - Resolve URL do Google News antes (para ter URL real da fonte).
      - Se ja tem texto OK e so falta imagem, pula extracao de texto
        e busca apenas og:image (modo rapido/leve).

    Retorna dict: {ok, texto, imagem_url, metodo, motivo, url_resolvida}
    """
    url_original = _link_pauta(p)
    if not url_original:
        return {"ok": False, "motivo": "sem_url"}

    titulo = str(p.get("titulo_origem") or p.get("titulo") or "")
    fonte = str(p.get("fonte_nome") or p.get("fonte") or "")

    # V200_33: resolve Google News -> URL real
    url = _resolver_link_real(url_original, titulo, fonte)
    url_resolvida = url if url != url_original else ""

    ja_tem_texto = _texto_chars(p) >= TEXTO_MIN_CHARS
    ja_tem_imagem = _imagem_ok(p)

    # MODO IMAGEM-ONLY: ja tem texto, so falta a imagem
    if ja_tem_texto and not ja_tem_imagem:
        img = _extrair_og_image_leve(url, timeout=TIMEOUT_PAUTA)
        if img:
            return {
                "ok": True,
                "texto": "",  # nao sobrescreve texto existente
                "imagem_url": img,
                "metodo": "og_image_leve",
                "motivo": "so_imagem",
                "url_resolvida": url_resolvida,
            }
        # nao achou imagem, marca tentativa e retorna falha leve
        return {"ok": False, "motivo": "og_image_nao_encontrada",
                "url_resolvida": url_resolvida}

    # MODO COMPLETO: precisa de texto (e imagem se possivel)
    # ESCADA 1: pipeline_v90 (adapters + trafilatura + Jina interno)
    try:
        from ururau.coleta.extract_pipeline_v90 import extrair_materia_v90
        from urllib.parse import urlparse
        dominio = urlparse(url).netloc.lower()
        tipo_site = "globo" if "globo.com" in dominio else (
            "uol" if "uol.com.br" in dominio else "generic"
        )
        r = extrair_materia_v90(
            url, dominio=dominio, tipo_site=tipo_site,
            contexto={"uid": p.get("uid"), "origem": "hidratador_bg"},
        )
        texto = (r.get("texto") or "").strip()
        if r.get("aceita") and len(texto) >= TEXTO_MIN_CHARS:
            imagem = (
                str(r.get("imagem") or "").strip()
                or str(r.get("og_image") or "").strip()
            )
            # V200_33: se nao trouxe imagem, tenta og:image leve
            if not imagem:
                imagem = _extrair_og_image_leve(url, timeout=TIMEOUT_PAUTA)
            return {
                "ok": True,
                "texto": texto,
                "imagem_url": imagem,
                "metodo": "pipeline_v90:" + str(r.get("metodo") or ""),
                "motivo": "ok",
                "url_resolvida": url_resolvida,
            }
    except Exception as e:
        logger.debug("%s pipeline_v90 falhou uid=%s: %s",
                     PREFIX, p.get("uid"), e)

    # ESCADA 2: Jina Reader (renderiza JS, ótimo para SPA)
    try:
        from ururau.coleta.jina_extractor import extrair_via_jina
        r = extrair_via_jina(url, timeout=TIMEOUT_PAUTA, min_chars=TEXTO_MIN_CHARS)
        if r.get("ok"):
            texto = (r.get("texto") or "").strip()
            if len(texto) >= TEXTO_MIN_CHARS:
                # V200_33: Jina nao traz imagem, mas tentamos og:image leve
                imagem = _extrair_og_image_leve(url, timeout=TIMEOUT_PAUTA)
                return {
                    "ok": True, "texto": texto,
                    "imagem_url": imagem,
                    "metodo": "jina_bg",
                    "motivo": r.get("motivo") or "ok",
                    "url_resolvida": url_resolvida,
                }
    except Exception as e:
        logger.debug("%s jina falhou uid=%s: %s", PREFIX, p.get("uid"), e)

    return {"ok": False, "motivo": "todos_metodos_falharam",
            "url_resolvida": url_resolvida}


def _persistir(db, p: dict[str, Any], resultado: dict[str, Any]) -> None:
    """Atualiza dados_json da pauta com texto+imagem+metadados."""
    uid = str(p.get("uid") or p.get("_uid") or "")
    if not uid:
        return
    # Reconstrói o payload completo do dados_json com os novos campos
    extra = dict(p)
    extra.pop("uid", None)
    extra.pop("_uid", None)

    if resultado.get("ok"):
        # V200_33: modo so_imagem nao sobrescreve texto existente
        if resultado.get("motivo") != "so_imagem" and resultado.get("texto"):
            extra["cleaned_source_text"] = resultado["texto"]
            extra["fonte_status"] = "ok"
            extra["status_fonte_v105"] = "ok"
            extra["fonte_chars_v105"] = len(resultado["texto"])
            extra["texto_fonte_chars"] = len(resultado["texto"])
        extra["hidratacao_on_demand"] = resultado.get("metodo") or "hidratador_bg"
        extra["hidratado_em"] = datetime.now().isoformat(timespec="seconds")
        extra["_hidratador_bg_tentado_em"] = extra["hidratado_em"]
        if resultado.get("imagem_url"):
            extra["imagem_url"] = resultado["imagem_url"]
        # V200_33: persiste URL resolvida para futuras hidratacoes
        if resultado.get("url_resolvida"):
            extra["link_origem_resolvido"] = resultado["url_resolvida"]
    else:
        # Marca tentativa pra não martelar a mesma pauta em loop
        extra["_hidratador_bg_tentado_em"] = datetime.now().isoformat(
            timespec="seconds"
        )
        extra["_hidratador_bg_motivo"] = resultado.get("motivo") or "falhou"

    try:
        db.atualizar_pauta(uid, {
            "dados_json": json.dumps(extra, ensure_ascii=False, default=str),
        })
    except Exception as e:
        logger.warning("%s persist falhou uid=%s: %s", PREFIX, uid, e)


def _ciclo(db) -> dict[str, int]:
    """Roda um ciclo de hidratação e retorna stats.

    V200_34: pautas marcadas como prioritarias rodam ANTES das selecionadas
    pela janela temporal. Sao processadas sem quarentena (acabou de clicar).
    """
    # V200_34: drena fila de prioridade
    prio_uids = _drenar_prioridade()
    prio_pautas: list[dict] = []
    if prio_uids:
        try:
            todas = db.query_fila_ativa(incluir_baixo_score=True, limite=500)
            por_uid = {str(p.get("uid") or ""): p for p in todas if p.get("uid")}
            for uid in prio_uids:
                p = por_uid.get(str(uid))
                if not p:
                    continue
                if not _link_pauta(p):
                    continue
                # Mesmo se ja tem texto e imagem, na prioridade NAO pula -
                # significa que o usuario clicou e quer hidratacao agora.
                # Mas se ja tem ambos, evita trabalho duplo.
                if _texto_chars(p) >= TEXTO_MIN_CHARS and _imagem_ok(p):
                    continue
                prio_pautas.append(p)
        except Exception as e:
            logger.warning("%s drenar prioridade falhou: %s", PREFIX, e)

    candidatas = _selecionar_candidatas(db)
    # Junta prioridade (ordem do clique) + candidatas, removendo duplicatas
    uids_prio = {str(p.get("uid") or "") for p in prio_pautas}
    candidatas_finais = prio_pautas + [
        p for p in candidatas if str(p.get("uid") or "") not in uids_prio
    ]
    # Cap no batch
    candidatas = candidatas_finais[:BATCH]
    if not candidatas:
        return {"candidatas": 0, "hidratadas": 0, "falhas": 0}

    hidratadas = 0
    falhas = 0
    for p in candidatas:
        if _stop_event.is_set():
            break
        uid = str(p.get("uid") or "")
        try:
            r = _hidratar_pauta(p)
            _persistir(db, p, r)
            if r.get("ok"):
                hidratadas += 1
                logger.info(
                    "%s OK uid=%s chars=%d metodo=%s",
                    PREFIX, uid[:12], len(r.get("texto") or ""),
                    r.get("metodo") or "",
                )
            else:
                falhas += 1
                logger.debug(
                    "%s FALHA uid=%s motivo=%s",
                    PREFIX, uid[:12], r.get("motivo") or "",
                )
            with _estado_lock:
                _estado["ultima_pauta_uid"] = uid
                if r.get("ok"):
                    _estado["pautas_hidratadas"] += 1
                else:
                    _estado["pautas_falhas"] += 1
        except Exception as e:
            falhas += 1
            with _estado_lock:
                _estado["ultimo_erro"] = f"{type(e).__name__}: {str(e)[:100]}"
            logger.warning("%s erro uid=%s: %s", PREFIX, uid[:12], e)
    return {"candidatas": len(candidatas), "hidratadas": hidratadas, "falhas": falhas}


def _loop(db) -> None:
    logger.info(
        "%s worker iniciado: intervalo=%ds batch=%d janela_max=%dh prio=%dh",
        PREFIX, INTERVALO_SEG, BATCH, JANELA_MAX_H, JANELA_PRIORIDADE_H,
    )
    with _estado_lock:
        _estado["rodando"] = True
    if _stop_event.wait(timeout=10.0):
        return
    while not _stop_event.is_set():
        try:
            stats = _ciclo(db)
            with _estado_lock:
                _estado["ciclos"] += 1
                _estado["ultimo_ciclo_em"] = datetime.now().isoformat(
                    timespec="seconds"
                )
            if stats["candidatas"] > 0:
                print(
                    f"[ururau_web][HIDRATADOR_BG] ciclo: "
                    f"{stats['hidratadas']} hidratadas, {stats['falhas']} falhas "
                    f"de {stats['candidatas']} candidatas",
                    flush=True,
                )
        except Exception as e:
            with _estado_lock:
                _estado["ultimo_erro"] = f"{type(e).__name__}: {str(e)[:100]}"
            logger.warning("%s ciclo falhou: %s", PREFIX, e)
        if _stop_event.wait(timeout=INTERVALO_SEG):
            break
    with _estado_lock:
        _estado["rodando"] = False
    logger.info("%s worker parado", PREFIX)


def iniciar(db) -> bool:
    """Inicia o worker em thread daemon. Idempotente."""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        return False
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=_loop, args=(db,),
        name="ururau_hidratador_bg", daemon=True,
    )
    _worker_thread.start()
    return True


def parar() -> None:
    _stop_event.set()


def status() -> dict[str, Any]:
    with _estado_lock:
        return dict(_estado)


__all__ = ["iniciar", "parar", "status", "marcar_prioridade"]
