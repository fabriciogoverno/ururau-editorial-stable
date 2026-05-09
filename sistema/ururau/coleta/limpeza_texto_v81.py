"""
ururau/coleta/limpeza_texto_v81.py
Limpeza defensiva de texto-fonte antes da redação.
"""
from __future__ import annotations
import re

_LINHAS_LIXO_RE = [
    r"^benef[ií]cio do assinante$",
    r"^voc[eê] tem \d+ acessos por dia",
    r"^assinantes podem liberar",
    r"^j[aá] [ée] assinante\??",
    r"^assine( a [a-z]+)?$",
    r"^assine ou fa[cç]a login$",
    r"^fa[cç]a seu login$",
    r"^copiar link$",
    r"^salvar para ler depois$",
    r"^salvar artigos$",
    r"^recurso exclusivo para assinantes$",
    r"^diminuir fonte.*aumentar fonte$",
    r"^ouvir o texto$",
    r"^compartilhe$",
    r"^publicidade$",
    r"^continua ap[oó]s a publicidade$",
]
_BLOCOS_LIXO_CONTEM = [
    "benefício do assinante", "beneficio do assinante", "recurso exclusivo para assinantes",
    "assine a folha", "salvar para ler depois", "copiar link",
    "diminuir fonte aumentar fonte",
]

def normalizar_espacos(texto: str) -> str:
    texto = (texto or "").replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()

def _linha_lixo(linha: str) -> bool:
    l = re.sub(r"\s+", " ", (linha or "").strip().lower())
    if not l:
        return True
    for pad in _LINHAS_LIXO_RE:
        if re.search(pad, l, flags=re.I):
            return True
    if len(l) > 80 and any(x in l for x in [
        "homem de terno", "mulher de ", "fundo desfocado", "aparece em foto",
        "camisa azul", "gravata", "fala em microfone", "imagem mostra",
    ]):
        return True
    return False

def limpar_texto_fonte_v81(texto: str) -> str:
    try:
        from ururau.coleta.source_clean_v101 import limpar_texto_artigo_v101
        texto = limpar_texto_artigo_v101(texto or "")
    except Exception:
        pass
    texto = normalizar_espacos(texto)
    if not texto:
        return ""
    linhas = []
    for raw in texto.splitlines():
        linha = normalizar_espacos(raw)
        if _linha_lixo(linha):
            continue
        baixo = linha.lower()
        if any(m in baixo for m in _BLOCOS_LIXO_CONTEM):
            continue
        linhas.append(linha)
    texto = "\n".join(linhas)
    texto = re.sub(r"(?is)benef[ií]cio do assinante.*?(assine|fa[cç]a login)", " ", texto)
    texto = re.sub(r"(?is)copiar link\s+salvar.*?(assine|login)", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return texto.strip()

def texto_util_chars(texto: str) -> int:
    t = limpar_texto_fonte_v81(texto)
    t = re.sub(r"https?://\S+", "", t)
    return len(t.strip())

def fonte_suficiente_para_publicar(texto: str, minimo: int = 500) -> tuple[bool, str]:
    chars = texto_util_chars(texto)
    if chars < minimo:
        return False, f"fonte_util_curta:{chars}<{minimo}"
    return True, f"fonte_util_ok:{chars}"
