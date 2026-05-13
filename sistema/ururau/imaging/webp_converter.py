# -*- coding: utf-8 -*-
"""webp_converter — conversao oficial de imagens para WebP do Ururau.

spec_webp_upload_ururau: toda imagem enviada ao CMS DEVE estar em image/webp
com tamanho <= 80 KB, melhor qualidade possivel dentro do limite, sem corte
automatico, preservando o original.

Estrategia:
  1. Pillow (default). exif_transpose -> resize 'contain' (sem cortar) -> WEBP.
  2. cwebp (opcional, via URURAU_WEBP_USE_CWEBP=1 e CWEBP_PATH).
  3. Busca de qualidade decrescente 88->40, depois reduz dimensoes.

Log JSONL em sistema/logs/webp_converter.log.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageOps  # type: ignore
    PIL_OK = True
except Exception:
    Image = None  # type: ignore
    ImageOps = None  # type: ignore
    PIL_OK = False

# ── Defaults oficiais (overridaveis por env) ──────────────────────────────────
DEFAULT_MAX_BYTES = 81920          # 80 KB exatos (spec §4.2)
DEFAULT_TARGET_W = 900
DEFAULT_TARGET_H = 675
QUALIDADES_BUSCA = (88, 84, 80, 76, 72, 68, 64, 60, 56, 52, 48, 44, 40)
DIMENSOES_FALLBACK = (
    (900, 675), (840, 630), (780, 585), (720, 540), (660, 495),
)
DIMENSAO_MIN_SEM_ALERTA = (660, 495)
ALLOWED_OUTPUT_MIME = "image/webp"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_flag(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "sim", "yes", "s", "on"}


def _logs_dir() -> Path:
    base = Path(__file__).resolve().parents[2] / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _agora_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _log_jsonl(payload: dict) -> None:
    try:
        fp = _logs_dir() / "webp_converter.log"
        with fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def _slugify(texto: Any) -> str:
    s = unicodedata.normalize("NFKD", str(texto or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "imagem"


def gerar_nome_webp(uid_pauta: str | None = None,
                    titulo: str | None = None,
                    origem: str | None = None) -> str:
    """Gera um nome de arquivo .webp estavel/legivel."""
    pieces = []
    if titulo:
        pieces.append(_slugify(titulo)[:60])
    if uid_pauta:
        pieces.append(_slugify(uid_pauta)[:16])
    if not pieces:
        pieces.append(_slugify(origem or "imagem"))
    nome = "-".join(p for p in pieces if p) or "imagem"
    return nome[:100] + ".webp"


def _abrir_imagem(input_path: Path):
    if not PIL_OK:
        raise RuntimeError("Pillow nao instalado: pip install Pillow")
    im = Image.open(str(input_path))
    # spec §4.5: aplicar orientacao EXIF antes de remover metadados.
    im = ImageOps.exif_transpose(im)
    if im.mode in ("P",):
        im = im.convert("RGBA")
    return im


def _ajustar_dimensao(im, target_w: int, target_h: int, allow_canvas: bool):
    """Redimensiona preservando aspect. Sem corte automatico (spec §4.3).

    Se a imagem couber direto (mesma proporcao 4:3 com tolerancia), usa contain.
    Caso contrario, com allow_canvas=True desenha em canvas neutro 4:3 sem cortar.
    Com allow_canvas=False, apenas redimensiona ate caber em target_w x target_h.
    """
    if im is None:
        return im, False
    w, h = im.size
    target_ratio = target_w / target_h
    src_ratio = (w / h) if h else target_ratio

    if abs(src_ratio - target_ratio) < 0.02:
        novo = im.copy()
        novo.thumbnail((target_w, target_h), Image.LANCZOS)
        return novo, False

    if not allow_canvas:
        novo = im.copy()
        novo.thumbnail((target_w, target_h), Image.LANCZOS)
        return novo, False

    # canvas 'contain' sem cortar: pinta fundo neutro e centraliza.
    base = Image.new("RGB", (target_w, target_h), (15, 15, 18))
    proporcional = im.copy()
    proporcional.thumbnail((target_w, target_h), Image.LANCZOS)
    if proporcional.mode == "RGBA":
        base.paste(proporcional, (
            (target_w - proporcional.size[0]) // 2,
            (target_h - proporcional.size[1]) // 2,
        ), proporcional)
    else:
        base.paste(proporcional, (
            (target_w - proporcional.size[0]) // 2,
            (target_h - proporcional.size[1]) // 2,
        ))
    return base, True


def _to_rgb(im):
    if im.mode == "RGBA":
        # remove transparencia para WebP lossy (foto) preservando aparencia.
        bg = Image.new("RGB", im.size, (15, 15, 18))
        bg.paste(im, mask=im.split()[3])
        return bg
    if im.mode != "RGB":
        return im.convert("RGB")
    return im


def _salvar_webp_pillow(im, quality: int, method: int | None = None) -> bytes:
    if method is None:
        method = _env_int("URURAU_WEBP_METHOD", 4)
    method = max(0, min(6, int(method)))
    buf = BytesIO()
    im.save(buf, format="WEBP", quality=quality, method=method, lossless=False)
    return buf.getvalue()


def _tentar_cwebp(input_path: Path, quality: int) -> bytes | None:
    if not _env_flag("URURAU_WEBP_USE_CWEBP", "0"):
        return None
    binario = os.getenv("CWEBP_PATH", "").strip() or shutil.which("cwebp")
    if not binario:
        return None
    try:
        with subprocess.Popen(
            [binario, "-quiet", "-q", str(quality), "-m", "6",
             "-preset", "photo", str(input_path), "-o", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ) as p:
            out, _ = p.communicate(timeout=30)
            if p.returncode == 0 and out:
                return out
    except Exception:
        return None
    return None


def converter_buffer_para_webp_ururau(
    bytes_imagem: bytes,
    *, max_bytes: int = DEFAULT_MAX_BYTES,
    target_width: int = DEFAULT_TARGET_W,
    target_height: int = DEFAULT_TARGET_H,
    allow_canvas: bool = True,
) -> dict:
    """Converte um buffer de imagem para WebP. Devolve metadata + bytes finais."""
    if not PIL_OK:
        return {"ok": False, "erro_tipo": "SEM_BIBLIOTECA_WEBP",
                "erro": "Pillow ausente", "bytes": None}
    try:
        im = Image.open(BytesIO(bytes_imagem))
        im = ImageOps.exif_transpose(im)
    except Exception as e:
        return {"ok": False, "erro_tipo": "IMAGEM_CORROMPIDA",
                "erro": str(e), "bytes": None}

    melhor: dict[str, Any] = {}
    for dim_w, dim_h in DIMENSOES_FALLBACK:
        if dim_w > target_width or dim_h > target_height:
            continue
        ajustada, canvas_used = _ajustar_dimensao(im, dim_w, dim_h, allow_canvas)
        if ajustada is None:
            continue
        rgb = _to_rgb(ajustada)
        for q in QUALIDADES_BUSCA:
            try:
                buf = _salvar_webp_pillow(rgb, q)
            except Exception:
                continue
            size = len(buf)
            if size <= max_bytes:
                return {
                    "ok": True,
                    "bytes": buf,
                    "size_bytes": size,
                    "width": rgb.size[0],
                    "height": rgb.size[1],
                    "quality": q,
                    "method": "pillow",
                    "resized": True,
                    "canvas_used": canvas_used,
                    "abaixo_dim_min_alerta": (rgb.size[0] < DIMENSAO_MIN_SEM_ALERTA[0]),
                    "erro": None,
                }
            if not melhor or size < melhor.get("size_bytes", 10**12):
                melhor = {
                    "bytes": buf, "size_bytes": size,
                    "width": rgb.size[0], "height": rgb.size[1],
                    "quality": q,
                }
    return {
        "ok": False,
        "erro_tipo": "WEBP_FALHOU_LIMITE_80KB",
        "erro": f"Nao foi possivel ficar abaixo de {max_bytes} bytes. Melhor tentativa: {melhor.get('size_bytes')} bytes a quality={melhor.get('quality')}.",
        "tentativa_melhor": melhor,
        "bytes": None,
    }


def converter_para_webp_ururau(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    max_bytes: int | None = None,
    target_width: int = DEFAULT_TARGET_W,
    target_height: int = DEFAULT_TARGET_H,
    allow_canvas: bool = True,
    preserve_original: bool = True,
    nome_saida: str | None = None,
    pauta_uid: str | None = None,
) -> dict:
    """Converte ``input_path`` para WebP <= max_bytes. Preserva original.

    Sempre escreve em arquivo .webp dentro de ``output_dir`` (default: mesma
    pasta da imagem original). NUNCA apaga a original (spec §3.1).
    """
    inp = Path(str(input_path)).expanduser()
    out_dir = Path(str(output_dir)).expanduser() if output_dir else inp.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = int(max_bytes or _env_int("URURAU_WEBP_MAX_BYTES", DEFAULT_MAX_BYTES))
    log_payload: dict[str, Any] = {
        "timestamp": _agora_iso(),
        "pauta_uid": pauta_uid or "",
        "input": str(inp),
        "max_bytes": max_bytes,
    }

    if not inp.exists() or not inp.is_file():
        out = {"ok": False, "erro_tipo": "ARQUIVO_NAO_ENCONTRADO",
               "erro": f"Arquivo nao existe: {inp}", "input_path": str(inp),
               "output_path": None}
        _log_jsonl({**log_payload, **out, "ok": False})
        return out

    if not PIL_OK:
        out = {"ok": False, "erro_tipo": "SEM_BIBLIOTECA_WEBP",
               "erro": "Pillow nao instalado (pip install Pillow)",
               "input_path": str(inp), "output_path": None}
        _log_jsonl({**log_payload, **out, "ok": False})
        return out

    # Caso especial: se ja for webp e couber, copia sem reprocessar.
    if inp.suffix.lower() == ".webp" and inp.stat().st_size <= max_bytes:
        try:
            with Image.open(str(inp)) as im_chk:
                im_chk.verify()
            with Image.open(str(inp)) as im_dim:
                w, h = im_dim.size
        except Exception as e:
            out = {"ok": False, "erro_tipo": "IMAGEM_CORROMPIDA",
                   "erro": str(e), "input_path": str(inp), "output_path": None}
            _log_jsonl({**log_payload, **out, "ok": False})
            return out
        # gera nome de saida se solicitado
        if nome_saida:
            destino = out_dir / nome_saida
            if str(destino) != str(inp):
                shutil.copy2(str(inp), str(destino))
        else:
            destino = inp
        out = {
            "ok": True, "input_path": str(inp), "output_path": str(destino),
            "format": "webp", "mime": ALLOWED_OUTPUT_MIME,
            "size_bytes": destino.stat().st_size,
            "width": w, "height": h,
            "quality": None, "method": "pillow_passthrough",
            "resized": False, "canvas_used": False,
            "original_preserved": preserve_original, "erro": None,
            "abaixo_dim_min_alerta": w < DIMENSAO_MIN_SEM_ALERTA[0],
        }
        _log_jsonl({**log_payload, **{k: out[k] for k in ("ok","output_path","size_bytes","width","height","quality","method")}, "cms_ready": True})
        return out

    # Le bytes da imagem.
    try:
        bytes_imagem = inp.read_bytes()
    except Exception as e:
        out = {"ok": False, "erro_tipo": "FORMATO_NAO_SUPORTADO",
               "erro": str(e), "input_path": str(inp), "output_path": None}
        _log_jsonl({**log_payload, **out, "ok": False})
        return out

    res = converter_buffer_para_webp_ururau(
        bytes_imagem,
        max_bytes=max_bytes,
        target_width=target_width,
        target_height=target_height,
        allow_canvas=allow_canvas,
    )

    if not res.get("ok"):
        out = {
            "ok": False,
            "erro_tipo": res.get("erro_tipo") or "WEBP_FALHOU_LIMITE_80KB",
            "erro": res.get("erro") or "Conversao falhou.",
            "input_path": str(inp),
            "output_path": None,
            "tentativa_melhor": res.get("tentativa_melhor"),
        }
        _log_jsonl({**log_payload, **{k: out[k] for k in ("ok","erro_tipo","erro")}})
        return out

    nome = nome_saida or gerar_nome_webp(
        uid_pauta=pauta_uid, titulo=inp.stem, origem=inp.suffix.lstrip(".")
    )
    destino = out_dir / nome
    destino.write_bytes(res["bytes"])

    if preserve_original and inp.exists():
        # arquivo original NUNCA e apagado.
        pass

    out = {
        "ok": True,
        "input_path": str(inp),
        "output_path": str(destino),
        "format": "webp",
        "mime": ALLOWED_OUTPUT_MIME,
        "size_bytes": res["size_bytes"],
        "width": res["width"],
        "height": res["height"],
        "quality": res["quality"],
        "method": res["method"],
        "resized": res["resized"],
        "canvas_used": res["canvas_used"],
        "original_preserved": preserve_original,
        "abaixo_dim_min_alerta": res["abaixo_dim_min_alerta"],
        "erro": None,
    }
    _log_jsonl({**log_payload,
                **{k: out[k] for k in ("ok","output_path","size_bytes","width","height","quality","method")},
                "cms_ready": True})
    return out


def validar_webp_ururau(path: str | Path, max_bytes: int | None = None) -> dict:
    """Valida que o arquivo e WebP valido, <= max_bytes, nao corrompido."""
    p = Path(str(path))
    max_b = int(max_bytes or _env_int("URURAU_WEBP_MAX_BYTES", DEFAULT_MAX_BYTES))
    if not p.exists() or not p.is_file():
        return {"ok": False, "erro": "arquivo_nao_existe", "path": str(p)}
    if p.suffix.lower() != ".webp":
        return {"ok": False, "erro": "extensao_nao_e_webp",
                "extensao": p.suffix, "path": str(p)}
    size = p.stat().st_size
    if size > max_b:
        return {"ok": False, "erro": "tamanho_excede_limite",
                "size_bytes": size, "max_bytes": max_b, "path": str(p)}
    if not PIL_OK:
        # Fallback: confia na extensao + magic number.
        header = p.read_bytes()[:12]
        if not (header.startswith(b"RIFF") and header[8:12] == b"WEBP"):
            return {"ok": False, "erro": "magic_number_nao_e_webp",
                    "path": str(p)}
        return {"ok": True, "size_bytes": size, "mime": ALLOWED_OUTPUT_MIME,
                "width": None, "height": None, "path": str(p)}
    try:
        with Image.open(str(p)) as im:
            im.verify()
        with Image.open(str(p)) as im2:
            fmt = (im2.format or "").lower()
            w, h = im2.size
    except Exception as e:
        return {"ok": False, "erro": f"imagem_corrompida:{e}", "path": str(p)}
    if fmt != "webp":
        return {"ok": False, "erro": f"formato_invalido:{fmt}", "path": str(p)}
    return {"ok": True, "size_bytes": size, "mime": ALLOWED_OUTPUT_MIME,
            "width": w, "height": h, "path": str(p)}


def baixar_e_converter_imagem_url(url: str, output_dir: str | Path,
                                  *, pauta_uid: str | None = None,
                                  **kwargs) -> dict:
    """Baixa uma URL para arquivo temporario e converte para WebP."""
    import tempfile
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = r.read()
    except Exception as e:
        return {"ok": False, "erro_tipo": "DOWNLOAD_FALHOU",
                "erro": str(e), "input_path": url, "output_path": None}
    fd, tmp = tempfile.mkstemp(suffix=Path(url.split("?")[0]).suffix or ".bin")
    os.close(fd)
    try:
        Path(tmp).write_bytes(data)
        return converter_para_webp_ururau(
            tmp, output_dir, pauta_uid=pauta_uid, **kwargs
        )
    finally:
        try:
            Path(tmp).unlink()
        except Exception:
            pass


__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TARGET_W",
    "DEFAULT_TARGET_H",
    "QUALIDADES_BUSCA",
    "DIMENSOES_FALLBACK",
    "ALLOWED_OUTPUT_MIME",
    "converter_para_webp_ururau",
    "converter_buffer_para_webp_ururau",
    "validar_webp_ururau",
    "baixar_e_converter_imagem_url",
    "gerar_nome_webp",
]
