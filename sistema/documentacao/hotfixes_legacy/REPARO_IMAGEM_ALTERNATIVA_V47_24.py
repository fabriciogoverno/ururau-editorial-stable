# -*- coding: utf-8 -*-
from pathlib import Path
import shutil
import subprocess
import sys

BASE = None
cwd = Path.cwd().resolve()
for p in [cwd] + list(cwd.parents):
    if (p / "sistema").is_dir():
        BASE = p
        break

if BASE is None:
    raise SystemExit("ERRO: rode este arquivo na raiz do projeto, no mesmo nível da pasta sistema.")

S = BASE / "sistema"
print("[V47.24] Projeto:", BASE)


def backup(path: Path):
    if path.exists():
        b = path.with_suffix(path.suffix + ".bak_v47_24")
        if not b.exists():
            shutil.copy2(path, b)


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    path.write_text(content, encoding="utf-8")
    print("[OK]", path.relative_to(BASE))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


BUSCA_PY = r'''"""
imaging/busca.py — Busca e seleção de imagem para matérias.

V47.24
- amplia a coleta de candidatas na própria página (meta, json-ld, srcset, corpo);
- usa título + texto da fonte para montar consultas melhores;
- tenta múltiplas consultas externas, não apenas uma;
- preserva o contrato antigo do módulo.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ururau.config.settings import HEADERS, TIMEOUT_PADRAO, USAR_BING_IMAGEM

STOPWORDS = {
    "a","à","ao","aos","as","até","com","como","contra","da","das","de","do","dos","e","em","entre","na","nas","no","nos",
    "o","os","ou","para","pela","pelas","pelo","pelos","por","que","se","sem","sob","sobre","um","uma","uns","umas",
    "após","apos","já","mais","menos","ser","sua","seu","suas","seus","foi","são","era","sendo","ter","tem","há","vai"
}


def _criar_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    s.headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
    return s


def _url_absoluta(url: str, base: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        scheme = urlparse(base).scheme or "https"
        return f"{scheme}:{url}"
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return urljoin(base, url)


def _score_imagem_url(url: str) -> int:
    score = 0
    u = (url or "").lower()

    for ext, pts in ((".jpg", 12), (".jpeg", 12), (".webp", 10), (".png", 8)):
        if ext in u:
            score += pts

    for kw in ("foto", "photo", "image", "imagem", "picture", "media", "uploads", "wp-content", "cdn", "featured"):
        if kw in u:
            score += 5

    for kw in ("1200", "1024", "900", "800", "768", "large", "full"):
        if kw in u:
            score += 2

    for kw in ("icon", "logo", "favicon", "banner", "sprite", "pixel", "avatar", "ads", "doubleclick", "tracker", "gif"):
        if kw in u:
            score -= 15

    return score


def _texto_limpo(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "")).strip()


def _tokens_relevantes(texto: str) -> list[str]:
    texto = re.sub(r"[^\wÀ-ÿ\- ]+", " ", texto or "", flags=re.UNICODE)
    tokens = []
    for t in texto.split():
        low = t.lower().strip("-_ ")
        if len(low) < 4 or low in STOPWORDS or low.isdigit():
            continue
        tokens.append(low)

    vistos = set()
    saida = []
    for t in tokens:
        if t not in vistos:
            vistos.add(t)
            saida.append(t)
    return saida


def _extrair_entidades(texto: str) -> list[str]:
    texto = _texto_limpo(texto)
    ents = []
    padrao = re.compile(r"\b(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ-]{2,}(?:\s+|$)){1,4}")
    for m in padrao.finditer(texto):
        e = _texto_limpo(m.group(0))
        if len(e) >= 4 and e.lower() not in STOPWORDS:
            ents.append(e)

    vistos = set()
    saida = []
    for e in ents:
        k = e.lower()
        if k not in vistos:
            vistos.add(k)
            saida.append(e)
    return saida[:10]


def _montar_queries(titulo: str, dossie_texto: str = "") -> list[str]:
    titulo = _texto_limpo(titulo)
    dossie_texto = _texto_limpo(dossie_texto)
    queries = []

    def add(q: str):
        q = _texto_limpo(q)
        if q and q not in queries:
            queries.append(q[:160])

    add(titulo)
    add(re.split(r"\s+[\-|—]\s+", titulo)[0])

    toks_titulo = _tokens_relevantes(titulo)
    toks_dossie = _tokens_relevantes((titulo + " " + dossie_texto)[:1200])
    ents = _extrair_entidades((titulo + " " + dossie_texto)[:1200])

    if toks_titulo:
        add(" ".join(toks_titulo[:8]))
    if ents:
        add(" ".join(ents[:4]))
    if toks_dossie:
        add(" ".join(toks_dossie[:8]))
    if titulo and ents:
        add(f"{titulo} {' '.join(ents[:2])}")

    return queries[:6]


def _coletar_de_obj(obj, base: str, out: list[str]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in {"image", "thumbnailurl", "contenturl", "url"}:
                if isinstance(v, str) and v.startswith(("http://", "https://", "//", "/")):
                    out.append(_url_absoluta(v, base))
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and item.startswith(("http://", "https://", "//", "/")):
                            out.append(_url_absoluta(item, base))
                        elif isinstance(item, dict):
                            _coletar_de_obj(item, base, out)
                elif isinstance(v, dict):
                    _coletar_de_obj(v, base, out)
            else:
                _coletar_de_obj(v, base, out)
    elif isinstance(obj, list):
        for item in obj:
            _coletar_de_obj(item, base, out)


def _extrair_urls_jsonld(soup: BeautifulSoup, url_pagina: str) -> list[str]:
    urls = []
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        _coletar_de_obj(data, url_pagina, urls)
    return urls


def _extrair_urls_srcset(valor: str, base: str) -> list[str]:
    out = []
    for parte in (valor or "").split(","):
        url = (parte.strip().split(" ")[0] or "").strip()
        if url:
            out.append(_url_absoluta(url, base))
    return out


def _buscar_google_multi(query: str, session: requests.Session) -> list[str]:
    url_busca = f"https://www.google.com/search?tbm=isch&q={quote_plus(query[:160])}"
    urls = []
    try:
        resp = session.get(url_busca, timeout=TIMEOUT_PADRAO)
        resp.raise_for_status()
        html = resp.text or ""
        padroes = [
            re.compile(r'"ou":"(https?://[^"\\]+(?:jpg|jpeg|png|webp))"', re.I),
            re.compile(r'"(https?://[^"\\]+\.(?:jpg|jpeg|png|webp))"', re.I),
            re.compile(r'\["(https?://[^"\\]+\.(?:jpg|jpeg|png|webp))"', re.I),
        ]
        for pad in padroes:
            urls.extend(pad.findall(html))
    except Exception as e:
        print(f"[BUSCA_IMG][GOOGLE] falhou: {e}")
    return urls


def _buscar_bing_multi(query: str, session: requests.Session) -> list[str]:
    urls = []
    try:
        q = quote_plus(query[:160])
        resp = session.get(f"https://www.bing.com/images/search?q={q}&first=1&count=12", timeout=TIMEOUT_PADRAO)
        resp.raise_for_status()
        html = resp.text or ""
        urls.extend(re.findall(r'"murl":"(https?://[^"\\]+)"', html, flags=re.I))
        urls.extend(re.findall(r"mediaurl=(https?://[^&\"']+)", html, flags=re.I))
    except Exception as e:
        print(f"[BUSCA_IMG][BING] falhou: {e}")
    return urls


def buscar_imagem_og(url_pagina: str, session: Optional[requests.Session] = None) -> Optional[str]:
    sess = session or _criar_session()
    try:
        resp = sess.get(url_pagina, timeout=TIMEOUT_PADRAO, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag, attrs in [
            ("meta", {"property": "og:image"}),
            ("meta", {"property": "og:image:url"}),
            ("meta", {"name": "twitter:image"}),
            ("meta", {"name": "twitter:image:src"}),
            ("meta", {"itemprop": "image"}),
        ]:
            el = soup.find(tag, attrs=attrs)
            if el and el.get("content"):
                return _url_absoluta(el.get("content").strip(), url_pagina)
    except Exception as e:
        print(f"[BUSCA_IMG] og:image falhou ({url_pagina}): {e}")
    return None


def buscar_imagem_corpo_pagina(soup: BeautifulSoup, url_pagina: str) -> Optional[str]:
    candidatas = []
    article = soup.find("article") or soup.find(class_=re.compile(r"(content|body|materia|post|entry|single)", re.I)) or soup.body or soup
    for img in article.find_all("img", limit=40):
        urls = []
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            v = img.get(attr) or ""
            if v:
                urls.append(_url_absoluta(v.strip(), url_pagina))
        urls.extend(_extrair_urls_srcset(img.get("srcset") or "", url_pagina))
        urls.extend(_extrair_urls_srcset(img.get("data-srcset") or "", url_pagina))
        for u in urls:
            if not u or u.startswith("data:"):
                continue
            try:
                largura = int(str(img.get("width") or "0").replace("px", "") or 0)
            except Exception:
                largura = 0
            score = _score_imagem_url(u) + (largura // 100)
            candidatas.append((score, u))
    candidatas.sort(key=lambda x: x[0], reverse=True)
    return candidatas[0][1] if candidatas and candidatas[0][0] > 0 else None


def buscar_imagem_google_relacionada(titulo: str, session: Optional[requests.Session] = None) -> Optional[str]:
    sess = session or _criar_session()
    for url in _buscar_google_multi(titulo, sess):
        low = url.lower()
        if any(bad in low for bad in ("gstatic", "googleusercontent", "logo", "favicon", "sprite", "pixel", "encrypted-tbn")):
            continue
        if _score_imagem_url(url) > 0:
            return url
    return None


def buscar_imagem_bing(titulo: str, session: Optional[requests.Session] = None) -> Optional[str]:
    if not USAR_BING_IMAGEM:
        return None
    sess = session or _criar_session()
    for url in _buscar_bing_multi(titulo, sess):
        low = url.lower()
        if any(bad in low for bad in ("gstatic", "logo", "favicon", "sprite", "pixel", "avatar")):
            continue
        if _score_imagem_url(url) > 0:
            return url
    return None


def listar_candidatas_imagem(
    url_pagina: str,
    titulo: str,
    session: Optional[requests.Session] = None,
    imagem_preferencial: str = "",
    credito_preferencial: str = "",
    dossie_texto: str = "",
) -> list[dict]:
    sess = session or _criar_session()
    candidatas: list[dict] = []
    vistos: set[str] = set()

    def add(url: str, estrategia: str, credito: str = "Reprodução", relacionada: bool = False, score: int = 0):
        url = (url or "").strip()
        if not url:
            return
        if url.startswith("//"):
            base = url_pagina or "https://ururau.com.br/"
            url = _url_absoluta(url, base)
        if not url.startswith(("http://", "https://")):
            return
        key = url.split("#", 1)[0]
        if key in vistos:
            return
        vistos.add(key)
        candidatas.append({
            "url_imagem": url,
            "estrategia_imagem": estrategia,
            "credito_foto": credito or "Reprodução",
            "imagem_relacionada": bool(relacionada),
            "score": int(score or _score_imagem_url(url)),
        })

    if imagem_preferencial:
        add(imagem_preferencial, "imagem_preferencial_extracao", credito_preferencial or "Reprodução", False, 100)

    if url_pagina:
        try:
            resp = sess.get(url_pagina, timeout=TIMEOUT_PADRAO, allow_redirects=True)
            resp.raise_for_status()
            soup_cache = BeautifulSoup(resp.text, "html.parser")

            for tag, attrs in [
                ("meta", {"property": "og:image"}),
                ("meta", {"property": "og:image:url"}),
                ("meta", {"name": "twitter:image"}),
                ("meta", {"name": "twitter:image:src"}),
                ("meta", {"itemprop": "image"}),
            ]:
                el = soup_cache.find(tag, attrs=attrs)
                if el and el.get("content", "").strip():
                    url = _url_absoluta(el.get("content").strip(), url_pagina)
                    add(url, "og_image", "Reprodução", False, 95)

            for url in _extrair_urls_jsonld(soup_cache, url_pagina):
                add(url, "json_ld_image", "Reprodução", False, 90)

            article = soup_cache.find("article") or soup_cache.find(class_=re.compile(r"(content|body|materia|post|entry|single)", re.I)) or soup_cache.body or soup_cache
            candidatos_corpo = []
            for img in article.find_all("img", limit=50):
                urls = []
                for attr in ("src", "data-src", "data-lazy-src", "data-original"):
                    src = img.get(attr) or ""
                    if src:
                        urls.append(_url_absoluta(str(src).strip(), url_pagina))
                urls.extend(_extrair_urls_srcset(img.get("srcset") or "", url_pagina))
                urls.extend(_extrair_urls_srcset(img.get("data-srcset") or "", url_pagina))
                for url in urls:
                    if not url or url.startswith("data:"):
                        continue
                    score = _score_imagem_url(url)
                    try:
                        score += int(str(img.get("width") or "0").replace("px", "") or 0) // 100
                    except Exception:
                        pass
                    if score > 0:
                        candidatos_corpo.append((score, url))
            for score, url in sorted(candidatos_corpo, reverse=True)[:12]:
                add(url, "corpo_pagina", "Reprodução", False, score)

            html = resp.text or ""
            for url in re.findall(r"https?://[^\"'\s>]+\.(?:jpg|jpeg|png|webp)", html, flags=re.I):
                if _score_imagem_url(url) > 0:
                    add(url, "html_regex", "Reprodução", False, 55)

        except Exception as e:
            print(f"[BUSCA_IMG] Falha ao carregar página ({url_pagina}): {e}")

    queries = _montar_queries(titulo, dossie_texto)
    usar_google = str(os.getenv("URURAU_PLUS_GOOGLE_IMAGES_FALLBACK", "1")).lower() in {"1", "true", "sim", "yes", "s"}
    usar_bing = bool(USAR_BING_IMAGEM) or str(os.getenv("URURAU_PLUS_BING_IMAGES_FALLBACK", "1")).lower() in {"1", "true", "sim", "yes", "s"}

    for q in queries:
        if usar_google:
            for url in _buscar_google_multi(q, sess)[:8]:
                low = url.lower()
                if any(bad in low for bad in ("gstatic", "googleusercontent", "logo", "favicon", "sprite", "pixel", "encrypted-tbn", "doubleclick")):
                    continue
                if _score_imagem_url(url) > 0:
                    add(url, "google_images_relacionada", "Reprodução/Internet", True, 22)

        if usar_bing:
            for url in _buscar_bing_multi(q, sess)[:8]:
                low = url.lower()
                if any(bad in low for bad in ("gstatic", "logo", "favicon", "sprite", "pixel", "avatar")):
                    continue
                if _score_imagem_url(url) > 0:
                    add(url, "bing_search", "Reprodução/Internet", True, 18)

    candidatas.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidatas


def selecionar_melhor_imagem(
    url_pagina: str,
    titulo: str,
    dossie_texto: str = "",
    session: Optional[requests.Session] = None,
    imagem_preferencial: str = "",
    credito_preferencial: str = "",
) -> dict:
    candidatas = listar_candidatas_imagem(
        url_pagina=url_pagina,
        titulo=titulo,
        session=session,
        imagem_preferencial=imagem_preferencial,
        credito_preferencial=credito_preferencial,
        dossie_texto=dossie_texto,
    )
    if not candidatas:
        print(f"[BUSCA_IMG] Nenhuma imagem encontrada para: {titulo[:60]}")
        return {
            "url_imagem": "",
            "estrategia_imagem": "",
            "credito_foto": "Reprodução",
            "imagem_relacionada": False,
            "candidatas": [],
        }

    melhor = dict(candidatas[0])
    melhor["candidatas"] = candidatas
    print(f"[BUSCA_IMG] Melhor imagem: {melhor.get('estrategia_imagem')} | {str(melhor.get('url_imagem'))[:80]}")
    return melhor
'''

write_text(S / "ururau" / "imaging" / "busca.py", BUSCA_PY)

proc_path = S / "ururau" / "imaging" / "processamento.py"
proc = read_text(proc_path)
proc_new = proc

proc_new = proc_new.replace(
    'def pipeline_imagem(\n    url_pagina: str,\n    titulo: str,\n    pauta_uid: str,\n    destino_dir: Optional[str] = None,\n    imagem_preferencial: str = "",\n    credito_preferencial: str = "",\n) -> ImagemDados:',
    'def pipeline_imagem(\n    url_pagina: str,\n    titulo: str,\n    pauta_uid: str,\n    destino_dir: Optional[str] = None,\n    imagem_preferencial: str = "",\n    credito_preferencial: str = "",\n    dossie_texto: str = "",\n) -> ImagemDados:'
)

proc_new = proc_new.replace(
    '    resultado_busca = selecionar_melhor_imagem(\n        url_pagina,\n        titulo,\n        imagem_preferencial=imagem_preferencial,\n        credito_preferencial=credito_preferencial,\n    )',
    '    resultado_busca = selecionar_melhor_imagem(\n        url_pagina,\n        titulo,\n        dossie_texto=dossie_texto,\n        imagem_preferencial=imagem_preferencial,\n        credito_preferencial=credito_preferencial,\n    )'
)

proc_new = proc_new.replace(
    'int(os.getenv("URURAU_IMG_MAX_CANDIDATAS", "6") or "6")',
    'int(os.getenv("URURAU_IMG_MAX_CANDIDATAS", "12") or "12")'
)

if proc_new == proc:
    print("[AVISO] processamento.py não precisou/aceitou patch automático. Verifique se a versão já mudou.")
else:
    write_text(proc_path, proc_new)

wf_path = S / "ururau" / "publisher" / "workflow.py"
wf = read_text(wf_path)

old = '''            imagem = pipeline_imagem(
                url_pagina=pauta.get("link_origem", ""),
                titulo=pauta.get("titulo_origem", ""),
                pauta_uid=uid,
                imagem_preferencial=(pauta.get("imagem_url") or pauta.get("imagem_url_extracao") or pauta.get("imagem") or ""),
                credito_preferencial=(pauta.get("imagem_credito") or pauta.get("credito_foto") or ""),
            )'''

new = '''            imagem = pipeline_imagem(
                url_pagina=pauta.get("link_origem", ""),
                titulo=pauta.get("titulo_origem", ""),
                pauta_uid=uid,
                imagem_preferencial=(pauta.get("imagem_url") or pauta.get("imagem_url_extracao") or pauta.get("imagem") or ""),
                credito_preferencial=(pauta.get("imagem_credito") or pauta.get("credito_foto") or ""),
                dossie_texto=(pauta.get("texto_fonte") or pauta.get("cleaned_source_text") or pauta.get("resumo_origem") or ""),
            )'''

wf_new = wf.replace(old, new)

if wf_new == wf:
    print("[AVISO] workflow.py não casou no trecho esperado. Verifique etapa_imagem manualmente.")
else:
    write_text(wf_path, wf_new)

bat = BASE / "24_VALIDAR_IMAGEM_ALTERNATIVA_V47_24.bat"
bat.write_text(
    '@echo off\r\n'
    'cd /d "%~dp0sistema"\r\n'
    'python -m py_compile ururau\\imaging\\busca.py\r\n'
    'python -m py_compile ururau\\imaging\\processamento.py\r\n'
    'python -m py_compile ururau\\publisher\\workflow.py\r\n'
    'echo VALIDACAO IMAGEM ALTERNATIVA V47.24 OK\r\n'
    'pause\r\n',
    encoding="utf-8"
)
print("[OK]", bat.relative_to(BASE))

for target in [
    S / "ururau" / "imaging" / "busca.py",
    proc_path,
    wf_path,
]:
    subprocess.run([sys.executable, "-m", "py_compile", str(target)], check=True)

print("\n[V47.24] reparo aplicado com sucesso.")
print("Rode agora: .\\24_VALIDAR_IMAGEM_ALTERNATIVA_V47_24.bat")
print("Depois: .\\02_ABRIR_PAINEL.bat")
