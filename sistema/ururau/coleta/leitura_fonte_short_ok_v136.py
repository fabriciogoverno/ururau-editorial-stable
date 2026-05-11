# -*- coding: utf-8 -*-
"""leitura_fonte_short_ok_v136.py

Patch runtime para aceitar texto curto válido e reaproveitar V134/cache.

Objetivo:
- Evitar que o hidratador v105 trate como falha textos úteis acima de 550 chars.
- Reaproveitar Reader Proxy/cache V134 quando a leitura legada retorna 0 chars.
- Expor aliases texto/chars/ok/get() em ResultadoLeitura para fluxos legados.
- Manter fallback legado sem remover código antigo.
"""
from __future__ import annotations

import os
from typing import Any

_INSTALADO = False
_ORIGINAL = None


def _min_chars() -> int:
    try:
        return int(os.getenv("URURAU_MIN_CHARS_TEXTO_FONTE", os.getenv("URURAU_READER_PROXY_MIN_CHARS", "550")) or "550")
    except Exception:
        return 550


def _url_da_pauta(pauta: dict) -> str:
    if not isinstance(pauta, dict):
        return ""
    return (
        pauta.get("link_origem")
        or pauta.get("url_final")
        or pauta.get("url_original")
        or pauta.get("link")
        or pauta.get("url")
        or ""
    ).strip()


def _titulo_da_pauta(pauta: dict) -> str:
    if not isinstance(pauta, dict):
        return ""
    return pauta.get("titulo_origem") or pauta.get("titulo") or pauta.get("headline") or ""


def _resultado_from_text(lf: Any, url: str, titulo: str, texto: str, imagem: str = "", metodo: str = "v136_short_ok"):
    texto = (texto or "").strip()
    return lf.ResultadoLeitura(
        url=url,
        texto_limpo=texto[:12000],
        titulo_extraido=titulo or "",
        imagem_url=imagem or "",
        termos_destacados=[],
        score_intel_adicional=0,
        intel_log=f"[{metodo}] texto curto útil aceito",
        tamanho_chars=len(texto),
        sucesso=True,
        erro="",
    )


def _instalar_aliases_resultado(lf: Any) -> None:
    """Compatibiliza ResultadoLeitura com fluxos legados do v105.

    Alguns trechos antigos consultam resultado.texto, resultado.chars,
    resultado.ok ou resultado.get('texto'), enquanto a classe real usa
    texto_limpo, tamanho_chars e sucesso. Sem estes aliases, o v105 pode
    imprimir FALHOU 0 chars mesmo após o V134 retornar texto OK.
    """
    cls = getattr(lf, "ResultadoLeitura", None)
    if cls is None:
        return

    def _get_texto(self):
        return getattr(self, "texto_limpo", "") or ""

    def _set_texto(self, value):
        try:
            self.texto_limpo = value or ""
            self.tamanho_chars = len(self.texto_limpo)
        except Exception:
            pass

    def _get_chars(self):
        try:
            return int(getattr(self, "tamanho_chars", 0) or len(getattr(self, "texto_limpo", "") or ""))
        except Exception:
            return 0

    def _set_chars(self, value):
        try:
            self.tamanho_chars = int(value or 0)
        except Exception:
            pass

    def _get_ok(self):
        return bool(getattr(self, "sucesso", False))

    def _set_ok(self, value):
        try:
            self.sucesso = bool(value)
        except Exception:
            pass

    def _get_imagem(self):
        return getattr(self, "imagem_url", "") or ""

    def _set_imagem(self, value):
        try:
            self.imagem_url = value or ""
        except Exception:
            pass

    def _dict_get(self, key, default=None):
        mapping = {
            "texto": "texto_limpo",
            "texto_limpo": "texto_limpo",
            "cleaned_source_text": "texto_limpo",
            "raw_source_text": "texto_limpo",
            "chars": "tamanho_chars",
            "tamanho_chars": "tamanho_chars",
            "ok": "sucesso",
            "sucesso": "sucesso",
            "imagem": "imagem_url",
            "imagem_url": "imagem_url",
            "titulo": "titulo_extraido",
            "titulo_extraido": "titulo_extraido",
            "erro": "erro",
            "url": "url",
        }
        return getattr(self, mapping.get(key, key), default)

    def _getitem(self, key):
        value = _dict_get(self, key, None)
        if value is None:
            raise KeyError(key)
        return value

    try:
        cls.texto = property(_get_texto, _set_texto)
        cls.chars = property(_get_chars, _set_chars)
        cls.ok = property(_get_ok, _set_ok)
        cls.imagem = property(_get_imagem, _set_imagem)
        cls.get = _dict_get
        cls.__getitem__ = _getitem
    except Exception:
        pass


def _aceitar_resultado_curto(resultado: Any, min_chars: int) -> Any:
    try:
        texto = (getattr(resultado, "texto_limpo", "") or getattr(resultado, "texto", "") or "").strip()
        chars = int(getattr(resultado, "tamanho_chars", 0) or getattr(resultado, "chars", 0) or len(texto))
        if texto and len(texto) >= min_chars:
            resultado.sucesso = True
            resultado.erro = ""
            resultado.tamanho_chars = len(texto)
            if not getattr(resultado, "texto_limpo", ""):
                resultado.texto_limpo = texto
            if not getattr(resultado, "intel_log", ""):
                resultado.intel_log = "[v136_short_ok] texto útil aceito"
            return resultado
        if texto and chars >= min_chars:
            resultado.sucesso = True
            resultado.erro = ""
            return resultado
    except Exception:
        pass
    return resultado


def instalar_short_ok_v136() -> bool:
    global _INSTALADO, _ORIGINAL
    if _INSTALADO:
        return True

    try:
        import ururau.coleta.leitura_fonte as lf
    except Exception:
        return False

    original = getattr(lf, "ler_fonte_pauta", None)
    if not callable(original):
        return False

    _instalar_aliases_resultado(lf)
    _ORIGINAL = original

    def wrapper(pauta: dict, forcar_refresh: bool = False):
        min_chars = _min_chars()
        url = _url_da_pauta(pauta)
        titulo = _titulo_da_pauta(pauta)

        resultado = original(pauta, forcar_refresh=forcar_refresh)
        resultado = _aceitar_resultado_curto(resultado, min_chars)

        try:
            if getattr(resultado, "sucesso", False):
                return resultado
        except Exception:
            pass

        # Se a leitura legada falhou, tenta cache V134 antes de declarar falha.
        try:
            from ururau.coleta.reader_proxy_cache_v134 import get_cached
            c = get_cached(url, min_chars=min_chars)
            if c:
                texto = (c.get("texto") or "").strip()
                if len(texto) >= min_chars:
                    print(f"[V136][SHORT_OK][CACHE] OK {len(texto)} chars | {url[:100]}", flush=True)
                    return _resultado_from_text(
                        lf,
                        c.get("url") or url,
                        c.get("titulo") or titulo,
                        texto,
                        c.get("imagem") or "",
                        "v136_cache_short_ok",
                    )
        except Exception:
            pass

        # Último reforço: Reader Proxy direto.
        try:
            from ururau.coleta.reader_proxy_fallback_v134 import extrair_reader_proxy_v134
            data = extrair_reader_proxy_v134(url, titulo_ref=titulo)
            texto = (data.get("texto") or "").strip() if isinstance(data, dict) else ""
            if isinstance(data, dict) and data.get("ok") and len(texto) >= min_chars:
                print(f"[V136][SHORT_OK][READER_PROXY] OK {len(texto)} chars | {url[:100]}", flush=True)
                return _resultado_from_text(
                    lf,
                    data.get("url_clean") or url,
                    data.get("titulo") or titulo,
                    texto,
                    data.get("imagem") or "",
                    "v136_reader_proxy_short_ok",
                )
        except Exception as exc:
            try:
                print(f"[V136][SHORT_OK] fallback reader proxy falhou: {exc}", flush=True)
            except Exception:
                pass

        return resultado

    lf.ler_fonte_pauta = wrapper
    _INSTALADO = True
    print(f"[V136][SHORT_OK] leitura_fonte aceita texto útil >= {_min_chars()} chars; aliases texto/chars/ok/get ativos.", flush=True)
    return True


__all__ = ["instalar_short_ok_v136"]
