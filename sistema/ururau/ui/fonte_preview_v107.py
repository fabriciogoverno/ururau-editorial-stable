"""
ururau/ui/fonte_preview_v107.py

Correções v107 para a aba Fonte:
- exibir no painel Fonte a mesma imagem usada como miniatura na fila;
- atualizar automaticamente o preview da imagem quando ela chegar depois do texto;
- formatar o texto capturado como matéria legível, com título e parágrafos.
"""
from __future__ import annotations

import re
import hashlib
from pathlib import Path
from typing import Any


def _compactar_linha(texto: str) -> str:
    return re.sub(r"[ \t]+", " ", str(texto or "").replace("\xa0", " ")).strip()


def uid_pauta(pauta: dict | None) -> str:
    return str((pauta or {}).get("uid") or (pauta or {}).get("_uid") or "").strip()


def mesma_pauta(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    au = uid_pauta(a)
    bu = uid_pauta(b)
    if au and bu and au == bu:
        return True
    al = str(a.get("link_origem") or "").strip()
    bl = str(b.get("link_origem") or "").strip()
    return bool(al and bl and al == bl)


def resolver_imagem_pauta(painel: Any, pauta: dict | None) -> str:
    """Retorna o arquivo local da imagem já obtida para a pauta.

    A fila usa imagem_caminho. A aba Fonte, até a v106, só lia o status e
    escrevia '[imagem já encontrada]'. A v107 centraliza a resolução para que
    fila e Fonte renderizem a mesma imagem.
    """
    pauta = pauta or {}
    candidatos: list[str] = []
    for k in (
        "imagem_caminho", "caminho_imagem", "caminho_final", "thumb_path",
        "thumb_local", "imagem_path", "foto_local", "foto_path",
    ):
        v = str(pauta.get(k) or "").strip()
        if v:
            candidatos.append(v)

    uid = uid_pauta(pauta)
    if uid:
        try:
            conn = painel.db._conectar()
            try:
                row = conn.execute(
                    "SELECT caminho_final FROM imagens WHERE pauta_uid=? ORDER BY id DESC LIMIT 1",
                    (uid,),
                ).fetchone()
            finally:
                conn.close()
            if row:
                try:
                    candidatos.append(str(row["caminho_final"] or ""))
                except Exception:
                    candidatos.append(str(row[0] or ""))
        except Exception:
            pass

    bases: list[Path] = [Path.cwd(), Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[3]]
    try:
        from ururau.config.settings import PASTA_IMAGENS
        bases.insert(0, Path(PASTA_IMAGENS))
    except Exception:
        bases.insert(0, Path("imagens"))

    vistos: set[str] = set()
    for raw in candidatos:
        if not raw or raw in vistos:
            continue
        vistos.add(raw)
        path = Path(raw)
        tentativas = [path]
        if not path.is_absolute():
            for b in bases:
                tentativas.append(b / raw)
                tentativas.append(b / path.name)
        else:
            for b in bases:
                tentativas.append(b / path.name)
        for tentativa in tentativas:
            try:
                if tentativa.exists() and tentativa.is_file():
                    return str(tentativa)
            except Exception:
                continue
    return ""


def _preview_cache_path(caminho: str) -> Path:
    """Caminho estável para miniatura leve de interface.

    A imagem final 900x675 continua intacta para publicação. A aba Fonte usa
    uma cópia menor para reduzir I/O, memória e custo do ImageTk em cliques
    sucessivos na fila.
    """
    src = Path(caminho)
    base = src.parent / "_preview_cache_v12910"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        base = Path("_preview_cache_v12910")
        base.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(str(src.resolve() if src.exists() else src).encode("utf-8", "ignore")).hexdigest()[:16]
    return base / f"{src.stem}_{key}_preview.jpg"


def _obter_preview_leve(caminho: str, max_size: tuple[int, int] = (320, 210)) -> str:
    """Gera/reutiliza uma miniatura leve para a interface."""
    src = Path(caminho)
    if not src.exists():
        return caminho
    dst = _preview_cache_path(caminho)
    try:
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime and dst.stat().st_size > 0:
            return str(dst)
    except Exception:
        pass
    try:
        from PIL import Image
        img = Image.open(src)
        img.thumbnail(max_size, Image.LANCZOS)
        # Garante RGB para JPEG leve, inclusive quando a imagem tiver alpha.
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(dst, "JPEG", quality=72, optimize=True, progressive=True)
        return str(dst)
    except Exception:
        return caminho


def exibir_imagem_fonte(painel: Any, pauta: dict | None, pendente: str = "[imagem pendente]") -> bool:
    """Mostra imagem leve na aba Fonte sem carregar o arquivo final pesado."""
    try:
        if not getattr(painel, "_lbl_leitura_imagem", None):
            return False
        caminho = resolver_imagem_pauta(painel, pauta)
        if not caminho:
            painel._leitura_photo_ref = None
            painel._lbl_leitura_imagem.config(image="", text=pendente, fg=getattr(painel, "COR_CINZA", "#64748b") if hasattr(painel, "COR_CINZA") else "#64748b")
            return False
        from PIL import Image, ImageTk
        caminho_preview = _obter_preview_leve(caminho)
        # Cache em memória por arquivo de preview. Evita recriar PhotoImage a cada clique.
        cache = getattr(painel, "_v12910_preview_photo_cache", None)
        if cache is None:
            cache = {}
            painel._v12910_preview_photo_cache = cache
        mtime_key = ""
        try:
            mtime_key = str(Path(caminho_preview).stat().st_mtime_ns)
        except Exception:
            pass
        cache_key = f"{caminho_preview}|{mtime_key}"
        photo = cache.get(cache_key)
        if photo is None:
            img = Image.open(caminho_preview)
            img.thumbnail((320, 210), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            cache[cache_key] = photo
            # Limita cache para evitar crescimento indefinido.
            if len(cache) > 40:
                for k in list(cache.keys())[:-25]:
                    cache.pop(k, None)
        painel._leitura_photo_ref = photo
        painel._lbl_leitura_imagem.config(image=photo, text="")
        return True
    except Exception as e:
        try:
            painel._leitura_photo_ref = None
            painel._lbl_leitura_imagem.config(image="", text=f"[imagem encontrada, erro no preview: {str(e)[:60]}]")
        except Exception:
            pass
        return False


def notificar_imagem_atualizada(painel: Any, pauta: dict) -> None:
    """Atualiza a aba Fonte se a imagem da pauta selecionada acabou de chegar."""
    try:
        atual = getattr(painel, "_pauta_sel", None)
        if not mesma_pauta(atual, pauta):
            return
        try:
            atual.update({
                k: v for k, v in (pauta or {}).items()
                if k.startswith("imagem_") or k in ("caminho_imagem", "caminho_final")
            })
        except Exception:
            pass
        painel.after(0, lambda p=dict(atual or pauta): exibir_imagem_fonte(painel, p, pendente="[imagem sendo carregada]"))
    except Exception:
        pass


def _split_sentencas(texto: str) -> list[str]:
    texto = _compactar_linha(texto)
    if not texto:
        return []
    prot = {
        "Sr.": "Sr§", "Sra.": "Sra§", "Dr.": "Dr§", "Dra.": "Dra§",
        "Prof.": "Prof§", "Dep.": "Dep§", "Gov.": "Gov§", "min.": "min§",
    }
    tmp = texto
    for a, b in prot.items():
        tmp = tmp.replace(a, b)
    partes = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9\"'“])", tmp)
    out: list[str] = []
    for parte in partes:
        for a, b in prot.items():
            parte = parte.replace(b, a)
        parte = _compactar_linha(parte)
        if parte:
            out.append(parte)
    return out


def _paragrafar_bloco(bloco: str) -> list[str]:
    sentencas = _split_sentencas(bloco)
    if not sentencas:
        return []
    paragrafos: list[str] = []
    atual = ""
    for sentenca in sentencas:
        if not atual:
            atual = sentenca
            continue
        qtd_periodos = len(re.findall(r"[.!?]", atual))
        if len(atual) + 1 + len(sentenca) > 620 or (qtd_periodos >= 2 and len(atual) > 260):
            paragrafos.append(atual.strip())
            atual = sentenca
        else:
            atual += " " + sentenca
    if atual.strip():
        paragrafos.append(atual.strip())
    return paragrafos


def formatar_texto_fonte(pauta: dict | None, texto: str, resultado: Any = None, max_chars: int = 16000) -> str:
    """Exibe a fonte como matéria legível: título + parágrafos com espaço normal.

    Não altera o conteúdo factual. Apenas reconstrói quebras quando a extração
    veio em bloco corrido ou em linhas sem espaçamento.
    """
    pauta = pauta or {}
    texto = str(texto or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not texto:
        return ""

    titulo = ""
    try:
        titulo = _compactar_linha(getattr(resultado, "titulo", "") or "")
    except Exception:
        titulo = ""
    titulo = titulo or _compactar_linha(pauta.get("titulo_origem") or pauta.get("titulo") or "")

    if "INTEL EDITORIAL:" in texto and "────────────────" in texto:
        partes = texto.split("────────────────────────────────────────────────────────────")
        if len(partes) >= 3:
            texto = partes[-1].strip()

    if titulo:
        texto = re.sub(rf"^\s*{re.escape(titulo)}\s*", "", texto, flags=re.I).strip()

    blocos = [b.strip() for b in re.split(r"\n\s*\n+", texto) if b.strip()]
    if len(blocos) <= 1:
        linhas = [_compactar_linha(x) for x in texto.splitlines() if _compactar_linha(x)]
        blocos = linhas if len(linhas) >= 2 else [_compactar_linha(texto)]

    paragrafos: list[str] = []
    buffer_curto = ""
    for bloco in blocos:
        bloco = _compactar_linha(bloco)
        if not bloco:
            continue
        if len(bloco) < 120 and not re.search(r"[.!?]$", bloco):
            buffer_curto = (buffer_curto + " " + bloco).strip()
            continue
        if buffer_curto:
            bloco = (buffer_curto + " " + bloco).strip()
            buffer_curto = ""
        if len(bloco) > 900:
            paragrafos.extend(_paragrafar_bloco(bloco))
        else:
            paragrafos.append(bloco)
    if buffer_curto:
        paragrafos.append(buffer_curto)

    saida: list[str] = []
    vistos: set[str] = set()
    for par in paragrafos:
        par = _compactar_linha(par)
        if len(par) < 25:
            continue
        key = re.sub(r"[^a-z0-9áéíóúãõâêôç]+", "", par.lower())[:220]
        if key and key in vistos:
            continue
        vistos.add(key)
        saida.append(par)

    partes: list[str] = []
    if titulo:
        partes.append(titulo)
    partes.extend(saida)
    out = "\n\n".join(partes).strip()
    if max_chars and len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0].strip()
    return out


# fix/auditoria-fila-scrapling-v136: leitor oficial para a aba Fonte.
def obter_texto_fonte_via_contrato(pauta: dict | None) -> tuple[str, int, bool]:
    """Retorna ``(texto, chars_uteis, valido)`` para a aba Fonte.

    Le sempre via ``ururau.core.source_text_contract.get_source_text`` para
    garantir que a aba Fonte nunca exiba "OK" com 0 caracteres e nunca troque
    texto valido por falha posterior. ``valido = chars_uteis >= MIN_VALID``.
    """
    try:
        from ururau.core.source_text_contract import (
            get_source_text, texto_util_chars, min_valid,
        )
        texto = get_source_text(pauta or {})
        util = int(texto_util_chars(texto))
        return texto, util, util >= min_valid()
    except Exception:
        p = pauta or {}
        texto = str(
            p.get("cleaned_source_text") or p.get("texto_fonte_v134")
            or p.get("texto_fonte") or p.get("texto_fonte_v105")
            or p.get("raw_source_text") or p.get("dossie") or ""
        )
        util = len(texto.strip())
        return texto, util, util >= 550

