"""
imaging/processamento.py — Processamento de imagens para publicação.
Download, validação, crop central e redimensionamento para formato padrão.
"""
from __future__ import annotations

import os
import uuid
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from ururau.config.settings import (
    HEADERS,
    PASTA_IMAGENS,
    QUALIDADE_JPEG_FINAL,
    MIN_LARGURA_IMAGEM_PUBLICAVEL,
    MIN_ALTURA_IMAGEM_PUBLICAVEL,
    TIMEOUT_PADRAO,
)
from ururau.core.models import ImagemDados
from ururau.imaging.busca import selecionar_melhor_imagem

# Dimensões alvo para publicação
LARGURA_ALVO = 900
ALTURA_ALVO  = 675
QUALIDADE_PROCESSAMENTO = 85  # qualidade usada no processamento interno (final usa settings)

_IMG_COOLDOWN_DOMINIO: dict[str, float] = {}
_IMG_URLS_BLOQUEADAS: set[str] = set()

def _dominio_img(url: str) -> str:
    try:
        host = urlparse(url or "").netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""

def _cooldown_ativo(url: str) -> bool:
    dominio = _dominio_img(url)
    if not dominio:
        return False
    ate = _IMG_COOLDOWN_DOMINIO.get(dominio, 0)
    return ate > time.time()

def _registrar_429(url: str) -> None:
    dominio = _dominio_img(url)
    if not dominio:
        return
    try:
        segundos = int(os.getenv("URURAU_IMG_COOLDOWN_429_SEG", "1800") or "1800")
    except Exception:
        segundos = 1800
    _IMG_COOLDOWN_DOMINIO[dominio] = time.time() + max(60, segundos)
    _IMG_URLS_BLOQUEADAS.add(url)
    print(f"[IMG][v111.4] cooldown 429 ativado para {dominio} por {segundos}s")



def _garantir_pasta(pasta: str) -> Path:
    p = Path(pasta)
    p.mkdir(parents=True, exist_ok=True)
    return p


def baixar_imagem(
    url: str,
    destino_dir: str,
    uid: str,
) -> Optional[str]:
    """
    Baixa imagem de url para destino_dir com nome baseado em uid.
    Retorna o caminho do arquivo baixado, ou None em caso de falha.
    """
    _garantir_pasta(destino_dir)

    # Determina extensão a partir da URL ou padrão
    caminho_url = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if caminho_url.endswith(ext):
            extensao = ext
            break
    else:
        extensao = ".jpg"

    nome_arquivo = f"foto_{uid}_original{extensao}"
    caminho = str(Path(destino_dir) / nome_arquivo)

    try:
        if url in _IMG_URLS_BLOQUEADAS or _cooldown_ativo(url):
            print(f"[IMG][v111.4] pulando imagem em cooldown: {url[:80]}")
            return None
        resp = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT_PADRAO,
            stream=True,
        )
        if getattr(resp, "status_code", 0) == 429:
            _registrar_429(url)
        resp.raise_for_status()

        with open(caminho, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"[IMG] Imagem baixada: {caminho}")
        return caminho
    except Exception as e:
        print(f"[IMG] Falha ao baixar imagem ({url[:80]}): {e}")
        return None


def marcar_imagem_relacionada(caminho_final: str) -> None:
    """Marca foto de fallback relacionada com triângulo vermelho discreto."""
    if str(os.getenv("URURAU_PLUS_MARCAR_IMAGEM_RELACIONADA", "1")).lower() not in {"1", "true", "sim", "yes", "s"}:
        return
    try:
        from PIL import Image, ImageDraw
        with Image.open(caminho_final) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            draw = ImageDraw.Draw(img)
            w, h = img.size
            tam = max(32, min(w, h) // 14)
            pontos = [(w, 0), (w - tam, 0), (w, tam)]
            draw.polygon(pontos, fill=(210, 0, 0))
            img.save(caminho_final, "JPEG", quality=QUALIDADE_JPEG_FINAL, optimize=True)
    except Exception as e:
        print(f"[IMG][v111.4] falha ao marcar imagem relacionada: {e}")


def processar_imagem(
    caminho_original: str,
    uid: str,
    destino_dir: Optional[str] = None,
) -> Optional[str]:
    """
    Processa a imagem:
    - Converte para RGB (remove canal alpha se houver)
    - Crop central no aspecto 4:3 (900x675)
    - Redimensiona para 900x675
    - Salva como JPEG com qualidade configurada

    Retorna o caminho do arquivo final, ou None em caso de falha.
    """
    try:
        from PIL import Image
    except ImportError:
        print("[IMG] Pillow não instalado. Instale com: pip install Pillow")
        return None

    try:
        pasta = destino_dir or str(Path(caminho_original).parent)
        _garantir_pasta(pasta)
        caminho_final = str(Path(pasta) / f"foto_{uid}_final.jpg")

        with Image.open(caminho_original) as img:
            # Converte para RGB (trata PNG com transparência, etc.)
            if img.mode != "RGB":
                img = img.convert("RGB")

            largura_orig, altura_orig = img.size

            # Crop central para o aspecto 4:3
            aspecto_alvo = LARGURA_ALVO / ALTURA_ALVO
            aspecto_orig = largura_orig / altura_orig

            if aspecto_orig > aspecto_alvo:
                # Imagem mais larga que 4:3 → cortar nas laterais
                nova_largura = int(altura_orig * aspecto_alvo)
                left = (largura_orig - nova_largura) // 2
                img = img.crop((left, 0, left + nova_largura, altura_orig))
            elif aspecto_orig < aspecto_alvo:
                # Imagem mais alta que 4:3 → cortar em cima/baixo
                nova_altura = int(largura_orig / aspecto_alvo)
                top = (altura_orig - nova_altura) // 2
                img = img.crop((0, top, largura_orig, top + nova_altura))

            # Redimensiona para dimensões alvo
            img = img.resize((LARGURA_ALVO, ALTURA_ALVO), Image.LANCZOS)

            # Salva como JPEG
            img.save(caminho_final, "JPEG", quality=QUALIDADE_JPEG_FINAL, optimize=True)

        print(f"[IMG] Imagem processada: {caminho_final}")
        return caminho_final

    except Exception as e:
        print(f"[IMG] Falha ao processar imagem ({caminho_original}): {e}")
        return None


def validar_imagem(caminho: str) -> tuple[bool, dict]:
    """
    Valida se a imagem atende aos requisitos mínimos de publicação.

    Retorna:
        (bool: aprovada, dict: info com dimensões e motivo de rejeição)
    """
    info = {
        "largura": 0,
        "altura": 0,
        "formato": "",
        "tamanho_bytes": 0,
        "motivo_rejeicao": "",
        "aprovada": False,
    }

    try:
        from PIL import Image
    except ImportError:
        info["motivo_rejeicao"] = "Pillow não instalado"
        return False, info

    try:
        p = Path(caminho)
        if not p.exists():
            info["motivo_rejeicao"] = "Arquivo não encontrado"
            return False, info

        info["tamanho_bytes"] = p.stat().st_size

        if info["tamanho_bytes"] < 5000:
            info["motivo_rejeicao"] = f"Arquivo muito pequeno ({info['tamanho_bytes']} bytes)"
            return False, info

        with Image.open(caminho) as img:
            info["largura"], info["altura"] = img.size
            info["formato"] = img.format or ""

        if info["largura"] < MIN_LARGURA_IMAGEM_PUBLICAVEL:
            info["motivo_rejeicao"] = (
                f"Largura insuficiente: {info['largura']}px "
                f"(mínimo {MIN_LARGURA_IMAGEM_PUBLICAVEL}px)"
            )
            return False, info

        if info["altura"] < MIN_ALTURA_IMAGEM_PUBLICAVEL:
            info["motivo_rejeicao"] = (
                f"Altura insuficiente: {info['altura']}px "
                f"(mínimo {MIN_ALTURA_IMAGEM_PUBLICAVEL}px)"
            )
            return False, info

        info["aprovada"] = True
        return True, info

    except Exception as e:
        info["motivo_rejeicao"] = f"Erro ao abrir imagem: {e}"
        return False, info


def pipeline_imagem(
    url_pagina: str,
    titulo: str,
    pauta_uid: str,
    destino_dir: Optional[str] = None,
    imagem_preferencial: str = "",
    credito_preferencial: str = "",
    dossie_texto: str = "",
) -> ImagemDados:
    """
    Pipeline completo de imagem:
    1. Busca a melhor URL de imagem (og → corpo → Bing)
    2. Baixa a imagem
    3. Valida a imagem baixada
    4. Processa (crop + resize + JPEG)
    5. Valida imagem final
    6. Retorna ImagemDados populado

    Em caso de falha, retorna ImagemDados vazio.
    """
    pasta = destino_dir or PASTA_IMAGENS
    _garantir_pasta(pasta)

    # Resultado padrão (falha)
    vazio = ImagemDados(
        caminho_imagem="",
        uid=pauta_uid,
        estrategia_imagem="nenhuma",
    )

    # ── Etapa 1: Busca de URL ──────────────────────────────────────────────────
    print(f"[IMG_PIPELINE] Buscando imagem para: {titulo[:60]}")
    resultado_busca = selecionar_melhor_imagem(
        url_pagina,
        titulo,
        dossie_texto=dossie_texto,
        imagem_preferencial=imagem_preferencial,
        credito_preferencial=credito_preferencial,
    )

    candidatas = list(resultado_busca.get("candidatas") or [])
    if not candidatas and resultado_busca.get("url_imagem"):
        candidatas = [resultado_busca]

    if not candidatas:
        print("[IMG_PIPELINE] Nenhuma URL de imagem encontrada.")
        return vazio

    # V47.7: tenta múltiplas candidatas. Não reduz capacidade quando a primeira URL
    # cai, é pequena, vem em webp problemático ou está em cooldown/429.
    ultimo_motivo = ""
    max_tentativas = int(os.getenv("URURAU_IMG_MAX_CANDIDATAS", "12") or "12")
    for idx, cand in enumerate(candidatas[:max(1, max_tentativas)], start=1):
        url_imagem = cand.get("url_imagem", "")
        estrategia = cand.get("estrategia_imagem", "")
        credito    = cand.get("credito_foto", "Reprodução")
        imagem_relacionada = bool(cand.get("imagem_relacionada")) or estrategia in {"google_images_relacionada", "bing_search"}
        if not url_imagem:
            continue
        print(f"[IMG_PIPELINE] Tentativa {idx}/{min(len(candidatas), max_tentativas)}: {estrategia} | {url_imagem[:80]}")

        caminho_original = baixar_imagem(url_imagem, pasta, pauta_uid)
        if not caminho_original:
            ultimo_motivo = "download falhou"
            continue

        ok_original, info_original = validar_imagem(caminho_original)
        if not ok_original:
            ultimo_motivo = str(info_original.get('motivo_rejeicao') or 'original inválida')
            print(f"[IMG_PIPELINE] Imagem original inválida: {ultimo_motivo}")

        dimensoes_origem = f"{info_original['largura']}x{info_original['altura']}"

        caminho_final = processar_imagem(caminho_original, pauta_uid, pasta)
        if not caminho_final:
            ultimo_motivo = "processamento falhou"
            continue

        if imagem_relacionada:
            marcar_imagem_relacionada(caminho_final)

        ok_final, info_final = validar_imagem(caminho_final)
        if not ok_final:
            ultimo_motivo = str(info_final.get('motivo_rejeicao') or 'final inválida')
            print(f"[IMG_PIPELINE] Imagem final inválida: {ultimo_motivo}")
            continue

        print(f"[IMG_PIPELINE] Pipeline concluído: {caminho_final}")
        return ImagemDados(
            caminho_imagem=caminho_final,
            caminho_original=caminho_original,
            credito_foto=credito,
            url_imagem=url_imagem,
            estrategia_imagem=estrategia,
            dimensoes_origem=dimensoes_origem,
            largura_origem=info_original["largura"],
            altura_origem=info_original["altura"],
            melhor_qualidade=ok_original,
            score_imagem=float(info_final["largura"] * info_final["altura"]) / 1_000_000,
            uid=pauta_uid,
        )

    print(f"[IMG_PIPELINE] Todas as candidatas falharam. Último motivo: {ultimo_motivo}")
    return vazio
