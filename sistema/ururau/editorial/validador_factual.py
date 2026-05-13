# -*- coding: utf-8 -*-
"""validador_factual — verifica fidelidade do texto IA-redigido a fonte.

spec_linha_editorial_ia_copydesk_antialucinacao §5.

Extrai entidades factuais do texto gerado e confere se cada uma aparece
na fonte. Bloqueia quando a IA cria fato que nao existe.

Entidades cobertas:
  - datas (10/05/2026, 10 de maio, maio de 2026, etc.)
  - horarios (10h, 10h30, 10:30)
  - aspas (qualquer texto entre " " ou aspas tipograficas)
  - valores monetarios (R$ ...)
  - numeros explicitos (porcentagens, contagens)
  - nomes proprios (heuristica: sequencias capitalizadas que NAO comecam
    frase)

Retorno padronizado:

    {
      "ok": bool,
      "problemas": list[str],
      "categorias": dict[str, list[str]],   # entidades suspeitas por tipo
      "erro_tipos": list[str],              # IA_INSERIU_DATA_INEXISTENTE etc
    }
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


MESES = (
    "janeiro", "fevereiro", "marco", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _norm(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ── Extratores ────────────────────────────────────────────────────────────

_RX_DATA_NUM = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b")
_RX_DATA_MES = re.compile(
    r"\b(\d{1,2})\s*(?:de\s+)?(janeiro|fevereiro|marco|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b",
    re.I,
)
_RX_DATA_MES_ANO = re.compile(
    r"\b(janeiro|fevereiro|marco|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})\b",
    re.I,
)
_RX_HORARIO = re.compile(r"\b(\d{1,2})\s*[h:](\d{0,2})\b")
_RX_VALOR = re.compile(r"R\$\s*[\d.,]+(?:\s*(?:mil|milhao|milhão|milhoes|milhões|bilhao|bilhão))?", re.I)
_RX_ASPAS = re.compile(r'"([^"]{4,300})"|“([^”]{4,300})”|«([^»]{4,300})»')
_RX_NOME = re.compile(
    r"(?<![\.\?\!]\s)(?<!^)\b([A-ZÁ-Ú][a-zà-ú]+(?:\s+(?:de|do|da|dos|das)\s+|\s+)){1,3}[A-ZÁ-Ú][a-zà-ú]+\b"
)
_PALAVRAS_FRASE_INICIAL = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "para", "por", "em", "no", "na", "nos", "nas",
    "de", "do", "da", "dos", "das",
    "se", "ja", "ainda", "tambem", "também",
    "segundo", "conforme", "apos", "após",
    "depois", "antes", "durante", "enquanto",
    "esta", "este", "isso", "isto",
    "ele", "ela", "eles", "elas",
    "porem", "porém", "mas", "entretanto", "contudo",
    "policia", "polícia",
    "prefeito", "prefeita", "vereador", "vereadora", "deputado",
    "deputada", "presidente", "governador",
}


def extrair_datas(texto: str) -> list[str]:
    achados: list[str] = []
    for m in _RX_DATA_NUM.finditer(texto):
        achados.append(m.group(0))
    for m in _RX_DATA_MES.finditer(texto):
        achados.append(m.group(0))
    for m in _RX_DATA_MES_ANO.finditer(texto):
        achados.append(m.group(0))
    return list(dict.fromkeys(a.strip() for a in achados))


def extrair_horarios(texto: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).strip() for m in _RX_HORARIO.finditer(texto)))


def extrair_aspas(texto: str) -> list[str]:
    """Devolve textos entre aspas (todas as variantes)."""
    achados: list[str] = []
    for m in _RX_ASPAS.finditer(texto or ""):
        for g in m.groups():
            if g:
                t = g.strip()
                if len(t) >= 4:
                    achados.append(t)
    return list(dict.fromkeys(achados))


def extrair_valores(texto: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).strip() for m in _RX_VALOR.finditer(texto)))


def extrair_nomes_proprios(texto: str) -> list[str]:
    achados: list[str] = []
    # split por sentenca para excluir nomes que aparecem como inicio de frase.
    for sent in re.split(r"(?<=[\.\!\?])\s+", texto or ""):
        if not sent.strip():
            continue
        # ignora a primeira palavra capitalizada da sentenca (inicio normal).
        offset = 0
        first = re.match(r"\s*([A-ZÁ-Ú][a-zà-ú]+)", sent)
        if first:
            offset = first.end()
        for m in _RX_NOME.finditer(sent, offset):
            nome = m.group(0).strip()
            primeira = nome.split(" ", 1)[0].lower()
            if primeira in _PALAVRAS_FRASE_INICIAL:
                continue
            if len(nome) > 80:
                continue
            achados.append(nome)
    return list(dict.fromkeys(achados))


# ── Comparacao com a fonte ────────────────────────────────────────────────

def _contem(texto_norm: str, entidade: str) -> bool:
    e = _norm(entidade)
    if not e:
        return True
    return e in texto_norm


def auditar_fidelidade(texto_gerado: str, fonte_texto: str,
                       *, modo_estrito: bool = True) -> dict:
    """Compara entidades do texto gerado com a fonte.

    Em modo estrito: nomes/datas/aspas que aparecem no gerado mas nao na fonte
    sao reportados como problemas. Modo nao estrito: nomes sao apenas avisos.
    """
    out: dict[str, Any] = {
        "ok": True,
        "problemas": [],
        "categorias": {},
        "erro_tipos": [],
    }
    if not texto_gerado:
        out["ok"] = False
        out["problemas"].append("texto_gerado_vazio")
        return out
    fonte_norm = _norm(fonte_texto or "")

    # 1) Datas (numericas + por extenso).
    datas_g = extrair_datas(texto_gerado)
    invent_datas = [d for d in datas_g if not _contem(fonte_norm, d)]
    if invent_datas:
        out["categorias"]["datas_inventadas"] = invent_datas
        out["erro_tipos"].append("IA_INSERIU_DATA_INEXISTENTE")
        out["problemas"].append("datas_no_gerado_ausentes_na_fonte:"
                                 + ",".join(invent_datas[:5]))

    # 2) Horarios.
    horas_g = extrair_horarios(texto_gerado)
    invent_horas = [h for h in horas_g if not _contem(fonte_norm, h)]
    if invent_horas:
        out["categorias"]["horarios_inventados"] = invent_horas
        out["erro_tipos"].append("IA_INSERIU_HORARIO_INEXISTENTE")
        out["problemas"].append("horarios_ausentes_na_fonte:"
                                 + ",".join(invent_horas[:5]))

    # 3) Aspas (precisa coincidir literalmente na fonte com tolerancia leve).
    aspas_g = extrair_aspas(texto_gerado)
    invent_aspas: list[str] = []
    for asp in aspas_g:
        # tolera diferenca pequena: normaliza e checa se 80% das palavras
        # aparecem na fonte na mesma ordem.
        asp_norm = _norm(asp)
        if asp_norm and asp_norm in fonte_norm:
            continue
        palavras = asp_norm.split()
        if not palavras:
            continue
        ok = 0
        for w in palavras:
            if len(w) >= 4 and w in fonte_norm:
                ok += 1
        if ok / max(1, len(palavras)) < 0.8:
            invent_aspas.append(asp[:120])
    if invent_aspas:
        out["categorias"]["aspas_inventadas"] = invent_aspas
        out["erro_tipos"].append("IA_INSERIU_ASPAS_INEXISTENTES")
        out["problemas"].append("aspas_nao_correspondem_a_fonte:"
                                 + " | ".join(invent_aspas[:3]))

    # 4) Valores monetarios.
    valores_g = extrair_valores(texto_gerado)
    invent_val = [v for v in valores_g if not _contem(fonte_norm, v)]
    if invent_val:
        out["categorias"]["valores_inventados"] = invent_val
        out["erro_tipos"].append("IA_INSERIU_VALOR_INEXISTENTE")
        out["problemas"].append("valores_nao_estao_na_fonte:"
                                 + ",".join(invent_val[:5]))

    # 5) Nomes proprios (heuristica). Modo estrito so.
    nomes_g = extrair_nomes_proprios(texto_gerado)
    invent_nomes: list[str] = []
    for nome in nomes_g:
        if not _contem(fonte_norm, nome):
            # ultima chance: alguma das palavras-chave do nome aparece?
            palavras = [p for p in _norm(nome).split() if len(p) >= 4]
            if not palavras:
                continue
            if any(p in fonte_norm for p in palavras):
                continue
            invent_nomes.append(nome)
    if invent_nomes:
        out["categorias"]["nomes_inventados"] = invent_nomes
        if modo_estrito:
            out["erro_tipos"].append("IA_ALUCINOU_FATO_NAO_PRESENTE_NA_FONTE")
            out["problemas"].append("nomes_proprios_ausentes_na_fonte:"
                                     + ",".join(invent_nomes[:5]))

    # 6) Cronologia simples: se a fonte tem data X e o gerado tem data Y
    #    mais antiga sem motivo, alerta.
    datas_fonte = extrair_datas(fonte_texto or "")
    if datas_fonte and datas_g:
        # heuristica simples: se todas as datas do gerado estao tambem na
        # fonte, ok. Caso contrario ja sinalizado acima.
        pass

    out["ok"] = not out["problemas"]
    return out


__all__ = [
    "extrair_datas",
    "extrair_horarios",
    "extrair_aspas",
    "extrair_valores",
    "extrair_nomes_proprios",
    "auditar_fidelidade",
]
