# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import re
from typing import Any


SNIPPET_METHODS = {
    "rss_fallback",
    "v104_v86:rss_fallback",
    "rss_pre_texto",
    "preextraido",
    "v104_preextraido_longo",
}

VALIDATED_STATUS = {
    "ok",
    "ok_integridade_v47_26",
    "validada",
    "fonte_validada",
}


def _norm(texto: str) -> str:
    texto = (texto or "").lower()
    mapa = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüç", "aaaaaeeeeiiiiooooouuuuc")
    texto = texto.translate(mapa)
    texto = re.sub(r"[^a-z0-9 ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def hash_texto(texto: str) -> str:
    return hashlib.sha256(_norm(texto).encode("utf-8", errors="ignore")).hexdigest()[:16]


def texto_util_chars(texto: str) -> int:
    return len(_norm(texto))


def metodo_parece_snippet(metodo: str) -> bool:
    m = (metodo or "").lower().strip()
    return any(s in m for s in SNIPPET_METHODS)


@dataclass
class FonteValidada:
    uid_pauta: str
    link_origem: str
    titulo_origem: str
    texto: str
    metodo: str = ""
    status: str = "pendente"
    score: int = 0
    hash_fonte: str = ""
    chars_uteis: int = 0
    validada: bool = False
    motivo: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def construir_fonte_validada(pauta: dict, texto: str, metodo: str = "", status: str = "", score: int = 0) -> FonteValidada:
    uid = str(pauta.get("uid") or pauta.get("_uid") or "")
    titulo = str(pauta.get("titulo_origem") or pauta.get("titulo") or "")
    link = str(pauta.get("link_origem") or "")
    chars = texto_util_chars(texto)
    hv = hash_texto(texto)
    fonte = FonteValidada(
        uid_pauta=uid,
        link_origem=link,
        titulo_origem=titulo,
        texto=texto or "",
        metodo=metodo or "",
        status=status or "pendente",
        score=int(score or 0),
        hash_fonte=hv,
        chars_uteis=chars,
    )
    fonte.validada, fonte.motivo = validar_fonte_para_redacao(fonte)
    return fonte


def validar_fonte_para_redacao(fonte: FonteValidada, min_chars: int = 900) -> tuple[bool, str]:
    if not fonte.texto or fonte.chars_uteis < min_chars:
        return False, f"texto insuficiente: {fonte.chars_uteis} chars uteis; minimo {min_chars}"
    if metodo_parece_snippet(fonte.metodo) and fonte.status not in VALIDATED_STATUS:
        return False, f"metodo {fonte.metodo} exige validacao estrita antes da redacao"
    if fonte.status in {"erro", "falhou", "erro_extracao", "bloqueada"}:
        return False, f"status de fonte invalido: {fonte.status}"
    return True, "fonte validada para redacao"


def aplicar_fonte_validada_na_pauta(pauta: dict, fonte: FonteValidada) -> dict:
    pauta["texto_fonte_validado"] = fonte.texto
    pauta["texto_fonte"] = fonte.texto
    pauta["cleaned_source_text"] = fonte.texto
    pauta["fonte_validada_v47_29"] = fonte.to_dict()
    pauta["hash_fonte_validada"] = fonte.hash_fonte
    pauta["uid_fonte_validada"] = fonte.uid_pauta
    pauta["extraction_method"] = fonte.metodo
    pauta["extraction_status"] = fonte.status
    return pauta
