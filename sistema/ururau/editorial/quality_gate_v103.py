from __future__ import annotations

# PATCH_V47_20_DICT_ATTR_COMPAT
try:
    from ururau.editorial.compat_resultado_v47_20 import compat_obj as _v4720_compat_obj, getv as _v4720_getv, get_bool as _v4720_get_bool, get_score as _v4720_get_score
except Exception:
    def _v4720_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4720_get_bool(o,k,d=False): return bool(_v4720_getv(o,k,d))
    def _v4720_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4720_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4720_compat_obj(o): return o

# PATCH_V47_18_DICT_SCORE_COMPAT
# PATCH_V47_18_DICT_SCORE_COMPAT
try:
    from ururau.editorial.compat_resultado_v47_18 import compat_obj as _v4718_compat_obj, getv as _v4718_getv, get_score as _v4718_get_score
except Exception:
    def _v4718_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4718_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4718_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4718_compat_obj(o): return o

try:
    from ururau.editorial.compat_resultado_v47_18 import compat_obj as _v4718_compat_obj, getv as _v4718_getv, get_score as _v4718_get_score
except Exception:
    def _v4718_getv(o,k,d=None): return o.get(k,d) if isinstance(o,dict) else getattr(o,k,d)
    def _v4718_get_score(o,d=0):
        for k in ('score','score_total','score_qualidade','qualidade','seo_score','score_editorial','nota'):
            v=_v4718_getv(o,k,None)
            if v not in (None,''):
                try: return int(float(v))
                except Exception: pass
        return int(d)
    def _v4718_compat_obj(o): return o

import re
import html
import unicodedata
from difflib import SequenceMatcher
from typing import Any

try:
    from ururau.editorial.premium_v97 import min_requirements, paragraphs, fallback_body, tags_from_source
except Exception:  # pragma: no cover
    def paragraphs(text: str) -> list[str]:
        return [p.strip() for p in re.split(r"\n\s*\n+", str(text or "")) if p.strip()]
    def min_requirements(source_text: str) -> tuple[int, int]:
        n = len(str(source_text or ""))
        if n >= 4200: return 7, 2600
        if n >= 2600: return 6, 2100
        if n >= 1400: return 5, 1500
        if n >= 800: return 4, 1000
        return 3, 650
    def fallback_body(source_text: str, article_type: str = "", channel: str = "") -> str:
        return str(source_text or "").strip()
    def tags_from_source(source_text: str, title: str, channel: str) -> str:
        return channel or ""

_BAD_BODY_MARKERS = (
    "política de privacidade", "politica de privacidade", "catecontando histórias",
    "catecontando historias", "menu", "newsletter", "cookies", "todos os direitos",
    "leia também", "leia tambem", "publicidade", "continua após a publicidade",
    "continua apos a publicidade", "compartilhe", "siga-nos", "últimas notícias",
    "ultimas noticias",
)

_GENERIC_PHOTO_CREDITS = {
    "", "reprodução", "reproducao", "divulgação", "divulgacao", "arquivo", "arquivo pessoal",
    "internet", "redes sociais", "redacao", "redação", "foto", "imagem", "assessoria",
}


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", str(text or ""))
    return html.unescape(re.sub(r"\s+", " ", t)).strip()


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", _strip_html(text).lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _get(obj: Any, key: str, default: str = "") -> str:
    if isinstance(obj, dict):
        return str(obj.get(key) or default)
    return str(getattr(obj, key, default) or default)


def _set(obj: Any, key: str, value: Any) -> None:
    if isinstance(obj, dict):
        obj[key] = value
    elif hasattr(obj, key):
        setattr(obj, key, value)


def texto_fonte(pauta: dict, materia: Any | None = None) -> str:
    campos = [
        "cleaned_source_text", "_fonte_aba_texto", "fonte_aba_texto", "leitura_fonte_texto",
        "texto_fonte", "dossie", "raw_source_text", "fonte_texto", "source_text",
    ]
    for campo in campos:
        val = str((pauta or {}).get(campo) or "").strip()
        if len(val) >= 120:
            return val
    if materia is not None:
        for campo in campos:
            val = _get(materia, campo).strip()
            if len(val) >= 120:
                return val
    return ""


def normalizar_paragrafos_corpo(corpo: str, fonte: str = "") -> str:
    """Garante que texto longo não vá ao CMS como bloco único."""
    corpo = str(corpo or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    corpo = re.sub(r"(?i)^\s*(body\s*p|conteúdo|conteudo)\s*", "", corpo).strip()
    corpo = corpo.replace("—", ",").replace("–", "-")
    corpo = re.sub(r"\n{3,}", "\n\n", corpo)
    ps = paragraphs(corpo)
    if len(ps) >= 2:
        return "\n\n".join(p.strip() for p in ps if p.strip())

    # Se veio como parágrafo único, divide por sentenças sem inventar conteúdo.
    raw = re.sub(r"\s+", " ", _strip_html(corpo)).strip()
    if not raw:
        return ""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw) if len(s.strip()) > 20]
    if len(sents) < 3:
        return raw

    min_p, _ = min_requirements(fonte or raw)
    blocos: list[str] = []
    atual: list[str] = []
    for s in sents:
        atual.append(s)
        txt = " ".join(atual).strip()
        if len(txt) >= 260 or len(atual) >= 3:
            blocos.append(txt)
            atual = []
    if atual:
        blocos.append(" ".join(atual).strip())

    # Não cria parágrafos artificiais demais, mas evita blocão.
    if len(blocos) < min(3, min_p) and len(sents) >= 4:
        meio = max(1, len(sents) // 3)
        blocos = [" ".join(sents[:meio]), " ".join(sents[meio:2*meio]), " ".join(sents[2*meio:])]
    return "\n\n".join(b.strip() for b in blocos if b.strip())


def _repeticao_excessiva(corpo: str) -> bool:
    ps = [_norm(p) for p in paragraphs(corpo) if len(_norm(p)) > 40]
    if len(ps) < 3:
        return False
    seen = set()
    for p in ps:
        key = p[:180]
        if key in seen:
            return True
        seen.add(key)
    for i, a in enumerate(ps):
        for b in ps[i+1:]:
            if SequenceMatcher(None, a[:500], b[:500]).ratio() >= 0.88:
                return True
    return False


def validar_qualidade_materia(materia: Any, pauta: dict | None = None) -> tuple[bool, list[str]]:
    pauta = pauta or {}
    fonte = texto_fonte(pauta, materia)
    corpo = normalizar_paragrafos_corpo(_get(materia, "conteudo") or _get(materia, "corpo_materia"), fonte)
    ps = paragraphs(corpo)
    motivos: list[str] = []

    fonte_len = len(fonte.strip())
    min_p, min_c = min_requirements(fonte if fonte_len >= 500 else corpo)
    if len(corpo) < 650:
        motivos.append(f"corpo curto: {len(corpo)} caracteres")
    if fonte_len >= 800 and len(corpo) < min_c:
        motivos.append(f"corpo desproporcional à fonte: {len(corpo)} chars; mínimo {min_c}")
    if fonte_len >= 800 and len(ps) < min_p:
        motivos.append(f"poucos parágrafos: {len(ps)}; mínimo {min_p}")
    if len(ps) <= 1 and len(corpo) > 500:
        motivos.append("parágrafo único")
    low = _norm(corpo[:1200])
    if any(m in low for m in _BAD_BODY_MARKERS):
        motivos.append("lixo de página detectado no corpo")
    if _repeticao_excessiva(corpo):
        motivos.append("repetição excessiva de parágrafos ou ideias")
    if not (_get(materia, "titulo") or _get(materia, "titulo_seo")).strip():
        motivos.append("título ausente")
    if not (_get(materia, "subtitulo") or _get(materia, "subtitulo_curto")).strip():
        motivos.append("subtítulo ausente")
    try:
        from ururau.editorial.seo_premium_v47_12 import pontuar_seo_materia
        rep = pontuar_seo_materia(materia, pauta)
        _set(materia, "seo_score", rep.score)
        _set(materia, "seo_score_v47_12", rep.score)
        _set(materia, "seo_detalhes_v47_12", rep.to_dict())
        if rep.score < int(__import__("os").getenv("URURAU_SEO_SCORE_MINIMO_PUBLICAVEL", "90") or "90"):
            motivos.append(f"SEO abaixo de 90: {rep.score}/100")
    except Exception as _e_seo_v47_12:
        motivos.append(f"SEO não auditado: {_e_seo_v47_12}")
    return not motivos, motivos


def extrair_credito_foto(texto: str, fallback: str = "Reprodução") -> str:
    base = str(texto or "")[:6000]
    padroes = [
        r"(?:Foto|Crédito|Credito|Imagem|Divulgação|Divulgacao)\s*[:\-–—]\s*([^\n\r|/]{2,60}(?:/[A-Za-z0-9 ._\-ÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+)?)",
        r"Copyright\s+([^\n\r|]{2,60})",
        r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç .'-]{2,45}/[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç .'-]{2,30})",
    ]
    for pat in padroes:
        m = re.search(pat, base, flags=re.I)
        if not m:
            continue
        cred = re.sub(r"\s+", " ", m.group(1)).strip(" .,-–—|/")
        cred_norm = _norm(cred)
        if 2 <= len(cred) <= 60 and cred_norm not in _GENERIC_PHOTO_CREDITS:
            # Remove caudas típicas de HTML/texto bruto.
            cred = re.split(r"\s{2,}|\t|\r|\n|<", cred)[0].strip()
            return cred[:60].strip()
    fb = (fallback or "Reprodução").strip()[:60]
    return fb or "Reprodução"


def aplicar_padrao_publicacao_robo_v103(materia: Any, pauta: dict | None = None, imagem: Any | None = None) -> Any:
    """Normaliza campos imediatamente antes do CMS/preview."""
    pauta = pauta or {}
    fonte = texto_fonte(pauta, materia)
    corpo = normalizar_paragrafos_corpo(_get(materia, "conteudo") or _get(materia, "corpo_materia"), fonte)
    if corpo:
        _set(materia, "conteudo", corpo)
        _set(materia, "corpo_materia", corpo)
        _set(materia, "texto_final", corpo)

    # Nome da fonte para o CMS, por regra editorial do usuário: sempre Redação no robô.
    _set(materia, "fonte_nome", "Redação")
    _set(materia, "nome_da_fonte", "Redação")

    # Link da fonte permanece o link original, mas o nome exibido no CMS é Redação.
    link = _get(materia, "link_origem") or str(pauta.get("link_origem") or pauta.get("url") or "")
    if link:
        _set(materia, "link_origem", link)
        _set(materia, "link_da_fonte", link)

    # Crédito de foto: tenta detectar; se não achar, fica Reprodução.
    atual = _get(materia, "creditos_da_foto") or str(pauta.get("imagem_credito") or "")
    raw = "\n".join([str(pauta.get("raw_source_text") or ""), fonte, str(pauta.get("html") or "")])
    credito = extrair_credito_foto(raw, atual or "Reprodução")
    _set(materia, "creditos_da_foto", credito)
    if imagem is not None and hasattr(imagem, "credito_foto"):
        try:
            if not getattr(imagem, "credito_foto", "") or _norm(getattr(imagem, "credito_foto", "")) in _GENERIC_PHOTO_CREDITS:
                imagem.credito_foto = credito
        except Exception:
            pass

    # Tags mínimas se vierem pobres.
    tags = _get(materia, "tags")
    if len([t for t in tags.split(",") if t.strip()]) < 6:
        novas = tags_from_source(fonte, _get(materia, "titulo"), _get(materia, "canal"))
        if novas:
            _set(materia, "tags", novas)
    try:
        from ururau.editorial.seo_premium_v47_12 import otimizar_seo_materia
        otimizar_seo_materia(materia, pauta)
    except Exception as _e_seo_v47_12:
        try:
            erros = list(getattr(materia, "auditoria_erros", []) or [])
            erros.append(f"seo_v47_12 falhou: {_e_seo_v47_12}")
            setattr(materia, "auditoria_erros", erros)
        except Exception:
            pass
    return materia


def similaridade_titulo(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def lead_norm(texto: str, chars: int = 420) -> str:
    ps = paragraphs(str(texto or ""))
    lead = ps[0] if ps else str(texto or "")[:chars]
    return _norm(lead[:chars])


def detectar_duplicidade_materia(materia: Any, publicados: list[dict] | list[str]) -> tuple[bool, str]:
    titulo = _get(materia, "titulo") or _get(materia, "titulo_seo")
    corpo = _get(materia, "conteudo") or _get(materia, "corpo_materia")
    lead = lead_norm(corpo)
    for item in publicados or []:
        if isinstance(item, dict):
            titulo_pub = str(item.get("titulo_publicado") or item.get("titulo") or item.get("titulo_origem") or "")
            corpo_pub = str(item.get("conteudo") or item.get("corpo_materia") or "")
        else:
            titulo_pub = str(item or "")
            corpo_pub = ""
        if titulo_pub and similaridade_titulo(titulo, titulo_pub) >= 0.86:
            return True, f"título similar já publicado: {titulo_pub[:90]}"
        if corpo_pub and lead and lead_norm(corpo_pub) and SequenceMatcher(None, lead, lead_norm(corpo_pub)).ratio() >= 0.82:
            return True, f"lead similar a matéria já publicada: {titulo_pub[:90]}"
    return False, ""

# PATCH_V47_13_SEO_GATE
try:
    from ururau.editorial.seo_premium_v47_12 import avaliar_seo_premium
except Exception:
    avaliar_seo_premium = None

def v4713_gate_seo_publicacao_direta(materia):
    if avaliar_seo_premium is None: return {'ok': False, 'motivo': 'seo_premium indisponível'}
    r=avaliar_seo_premium(materia or {})
    return {'ok': r.get('seo_score',0) >= 90, 'seo_score': r.get('seo_score',0), 'detalhes': r}
