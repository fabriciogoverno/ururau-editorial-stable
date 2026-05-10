# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ResultadoFonteSeguro:
    ok: bool = False
    url_original: str = ""
    url_final: str = ""
    titulo: str = ""
    texto: str = ""
    metodo: str = "safe_failed"
    status: str = "failed"
    score: int = 0
    chars: int = 0
    util_chars: int = 0
    erro: str = ""
    motivo: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _texto_util(texto: str) -> int:
    return len(" ".join(str(texto or "").split()))


def normalizar_resultado_fonte(obj: Any, url: str = "", titulo: str = "", metodo_padrao: str = "safe_unknown") -> ResultadoFonteSeguro:
    """Converte retorno arbitrario de extrator em resultado seguro.

    Nunca levanta excecao por obj=None, dict incompleto ou objeto sem atributo.
    O resultado seguro com status failed nao autoriza redacao; ele apenas evita
    quebra de fluxo e facilita auditoria.
    """
    if obj is None:
        return ResultadoFonteSeguro(
            ok=False,
            url_original=url,
            url_final=url,
            titulo=titulo,
            metodo=metodo_padrao,
            status="failed",
            erro="extrator retornou None",
            motivo="resultado_none",
        )

    texto = str(_get(obj, "texto", "") or _get(obj, "dossie", "") or _get(obj, "cleaned_source_text", "") or "")
    util = int(_get(obj, "util_chars", 0) or _get(obj, "chars_uteis", 0) or _texto_util(texto))
    status = str(_get(obj, "status", "") or "failed")
    metodo = str(_get(obj, "metodo", "") or _get(obj, "extraction_method", "") or metodo_padrao)
    ok = bool(_get(obj, "ok", False)) and status not in {"failed", "erro", "erro_extracao", "bloqueada"}
    erro = str(_get(obj, "erro", "") or "")
    if "NoneType" in erro and "get" in erro:
        erro = "entrada invalida normalizada pelo resultado seguro"
    return ResultadoFonteSeguro(
        ok=ok,
        url_original=str(_get(obj, "url_original", "") or url),
        url_final=str(_get(obj, "url_final", "") or url),
        titulo=str(_get(obj, "titulo", "") or titulo),
        texto=texto,
        metodo=metodo,
        status=status,
        score=int(_get(obj, "score", 0) or 0),
        chars=int(_get(obj, "chars", 0) or len(texto)),
        util_chars=util,
        erro=erro,
        motivo="ok" if ok else "normalizado_sem_aprovar_redacao",
    )
