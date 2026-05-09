
"""
ururau/coleta/source_clean_v101.py
Limpeza v101 para impedir que menus, links internos, política de privacidade,
listas de matérias e cabeçalhos de site entrem como texto-fonte ou corpo final.
"""
from __future__ import annotations
import re, unicodedata
from difflib import SequenceMatcher

_HEADINGS = {
    "contexto", "detalhes", "efeitos praticos", "efeitos práticos", "proximos passos",
    "próximos passos", "o que se sabe", "entenda", "saiba mais", "orientacoes ao consumidor",
    "orientações ao consumidor", "servico", "serviço",
}
_JUNK_PHRASES = (
    "política de privacidade", "politica de privacidade", "termos de uso", "fale conosco",
    "quem somos", "catecontando histórias", "catecontando historias", "todos os direitos reservados",
    "copyright", "cookies", "newsletter", "publicidade", "continua após a publicidade",
    "continua apos a publicidade", "leia também", "leia tambem", "compartilhe", "menu",
    "buscar no site", "últimas notícias", "ultimas noticias", "mais lidas", "acesse sua conta",
    "benefício do assinante", "beneficio do assinante", "assine", "login", "entrar",
)

_DATE_RE = re.compile(r"\b(?:em\s+)?\d{1,2}/\d{1,2}/\d{4}\s*(?:às|as|,)?\s*\d{1,2}:\d{2}(?::\d{2})?\b", re.I)


def norm(text: str) -> str:
    t = unicodedata.normalize("NFD", str(text or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\xa0", " ")).strip()


def _similar(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b: return 0.0
    if a in b or b in a: return 1.0
    return SequenceMatcher(None, a[:180], b[:180]).ratio()


def _is_heading(line: str) -> bool:
    n = norm(line)
    if n in {norm(x) for x in _HEADINGS}: return True
    return len(line.strip()) <= 32 and not re.search(r"[.!?]$", line.strip()) and n in {norm(x) for x in _HEADINGS}


def _is_junk_line(line: str) -> bool:
    l = _compact(line)
    if not l: return True
    low = l.lower()
    if any(p in low for p in _JUNK_PHRASES): return True
    if len(l) <= 2: return True
    if re.fullmatch(r"[-–—•|/\\]+", l): return True
    if re.fullmatch(r"(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+\s*){1,4}", l) and len(l) < 35:
        return True
    # linha que é só uma coleção de chamadas separadas por hífen: típica lista de notícias
    if l.count(" - ") >= 3 and len(l) > 120:
        return True
    return False


def _cut_to_article_start(text: str, titulo: str = "") -> str:
    t = _compact(text)
    if not t: return ""
    # Se o título aparece mais de uma vez, usar a última ocorrência. Isso evita pegar
    # chamadas de menu/lista antes do artigo real.
    if titulo and len(norm(titulo)) >= 18:
        ntext = norm(t)
        nt = norm(titulo)
        positions = [m.start() for m in re.finditer(re.escape(nt), ntext)]
        if positions:
            # mapeia aproximadamente posição normalizada para texto original por busca literal frouxa
            candidates = []
            pattern = re.compile(re.escape(titulo), re.I)
            candidates = [m.start() for m in pattern.finditer(t)]
            if not candidates:
                # fallback: localiza por primeiras palavras do título
                words = [w for w in re.split(r"\s+", titulo.strip()) if len(w) > 2][:5]
                if words:
                    pattern2 = re.compile(r"\s+".join(map(re.escape, words)), re.I)
                    candidates = [m.start() for m in pattern2.finditer(t)]
            if candidates:
                pos = candidates[-1]
                # corta só se antes houver sinal de navegação/privacidade/lista ou se prefixo for longo
                prefix = t[:pos].lower()
                if len(prefix) > 40 and (any(p in prefix for p in _JUNK_PHRASES) or prefix.count(" - ") >= 2 or len(prefix) > 180):
                    t = t[pos:]
    # Se ainda começa com lixo e existe data de publicação no meio, corta até pouco antes do título/data.
    m = _DATE_RE.search(t[:1200])
    if m:
        prefix = t[:m.start()].lower()
        if any(p in prefix for p in _JUNK_PHRASES) or prefix.count(" - ") >= 2:
            # manter eventual título imediatamente antes da data
            start = max(0, t.rfind(" - ", 0, m.start()) + 3)
            if start > 0:
                t = t[start:]
    return t.strip()


def limpar_texto_artigo_v101(texto: str, titulo: str = "", max_chars: int = 16000) -> str:
    """Limpa texto-fonte bruto sem remover fatos do artigo."""
    t = str(texto or "").replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    if "\n" not in t:
        # quebra texto corrido em pontos principais para permitir filtro de linhas
        t = re.sub(r"\s+(-\s+)", "\n- ", t)
        t = re.sub(r"(?<!\d)\.\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", ".\n", t)
    t = _cut_to_article_start(t, titulo=titulo)
    lines = []
    seen = set()
    for raw in t.splitlines():
        line = _compact(raw).strip(" \t|•")
        if _is_junk_line(line):
            continue
        # remove chamadas soltas que começam com hífen e parecem lista de matérias
        if line.startswith("-") and len(line) < 180 and not _DATE_RE.search(line):
            continue
        key = norm(line)[:180]
        if key and key in seen:
            continue
        seen.add(key)
        lines.append(line)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out).strip()
    if max_chars and len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0].strip()
    return out


def limpar_corpo_publicacao_v101(corpo: str) -> str:
    """Remove intertítulos genéricos e restos internos do corpo final."""
    body = str(corpo or "").replace("\r\n", "\n").replace("\r", "\n").replace("—", ",").replace("–", "-")
    blocks = []
    for raw in re.split(r"\n\s*\n+", body):
        b = _compact(raw)
        if not b:
            continue
        # remove blocos em formato "Contexto\ntexto" ou "Detalhes\ntexto"
        if "\n" in raw:
            parts = [p.strip() for p in raw.splitlines() if p.strip()]
            if parts and _is_heading(parts[0]):
                b = _compact(" ".join(parts[1:]))
        if _is_heading(b):
            continue
        if _is_junk_line(b):
            continue
        for pat in [r"(?i)\bacende o alerta\b", r"(?i)\bvale lembrar que\b", r"(?i)\bcabe ressaltar que\b", r"(?i)\bé importante destacar que\b", r"(?i)\bnesse contexto\b"]:
            b = re.sub(pat, "", b)
        b = _compact(b)
        if b:
            blocks.append(b)
    return "\n\n".join(blocks).strip()


def score_texto_artigo_v101(texto: str, titulo: str = "") -> int:
    t = limpar_texto_artigo_v101(texto, titulo=titulo, max_chars=20000)
    n = norm(t)
    score = min(len(t), 5000)
    # penaliza lixo claro
    penalty = 0
    for p in _JUNK_PHRASES:
        if norm(p) in n:
            penalty += 450
    if t.count(" - ") >= 3:
        penalty += 500
    if titulo and _similar(titulo, t[:300]) < 0.25 and len(t) < 1500:
        penalty += 350
    # premia formato de artigo
    if _DATE_RE.search(t[:500]):
        score += 200
    if len(re.findall(r"(?<=[.!?])\s+", t)) >= 6:
        score += 500
    return score - penalty
