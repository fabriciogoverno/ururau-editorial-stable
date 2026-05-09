"""
source_quality_v90.py
Módulo de rastreamento de qualidade e cooldown de fontes de coleta (v90).
Persiste métricas em data/source_quality_v90.json.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

def safe_get(obj, key, default=None):
    """Helper seguro para evitar AttributeError em dict.get()."""
    return obj.get(key, default) if isinstance(obj, dict) else default


def _path_arquivo() -> str:
    """Retorna o caminho absoluto do arquivo de persistência."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "source_quality_v90.json")


def _carregar_dados() -> dict:
    """Carrega os dados do arquivo JSON. Retorna dict vazio se não existir."""
    path = _path_arquivo()
    if not os.path.exists(path):
        logger.info("[v90][SOURCE_QUALITY] Arquivo nao encontrado, iniciando dados vazios: %s", path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            dados = json.load(f)
            if not isinstance(dados, dict):
                logger.warning("[v90][SOURCE_QUALITY] Arquivo JSON nao eh dict, resetando")
                return {}
            return dados
    except (json.JSONDecodeError, OSError, IOError) as e:
        logger.error("[v90][SOURCE_QUALITY] Erro ao carregar dados: %s", e)
        return {}


def _salvar_dados(dados: dict) -> None:
    """Salva os dados no arquivo JSON."""
    path = _path_arquivo()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        logger.info("[v90][SOURCE_QUALITY] Dados salvos: %s", path)
    except (OSError, IOError) as e:
        logger.error("[v90][SOURCE_QUALITY] Erro ao salvar dados: %s", e)


def _garantir_entrada(dados: dict, dominio: str) -> dict:
    """Garante que o domínio tenha uma entrada inicial no dict."""
    if dominio not in dados:
        dados[dominio] = {
            "sucessos": 0,
            "falhas": 0,
            "melhor_metodo": "",
            "rate_limit": False,
            "ultima_falha": "",
            "cooldown_ate": "",
        }
    return dados[dominio]


def _agora_iso() -> str:
    """Retorna timestamp ISO atual em UTC."""
    return datetime.now(timezone.utc).isoformat()


def registrar_sucesso(dominio: str, metodo: str) -> None:
    """
    Registra um sucesso de coleta para o domínio.
    Atualiza contador de sucessos e melhor método se aplicável.
    """
    if not dominio or not isinstance(dominio, str):
        logger.warning("[v90][SOURCE_QUALITY] Dominio invalido: %r", dominio)
        return

    metodo = metodo.strip() if metodo and isinstance(metodo, str) else "desconhecido"
    dados = _carregar_dados()
    entrada = _garantir_entrada(dados, dominio)

    entrada["sucessos"] = safe_get(entrada, "sucessos", 0) + 1

    # Atualizar melhor método se tivermos >= 3 sucessos com este método
    sucessos_atual = safe_get(entrada, "sucessos", 0)
    melhor_atual = safe_get(entrada, "melhor_metodo", "")

    if sucessos_atual >= 3 and (not melhor_atual or sucessos_atual % 5 == 0):
        # Simples heurística: o último método bem-sucedido vira o melhor
        entrada["melhor_metodo"] = metodo
        logger.info("[v90][SOURCE_QUALITY] Dominio=%s melhor_metodo atualizado para '%s'",
                    dominio, metodo)

    # Limpar rate_limit se estava marcado
    if safe_get(entrada, "rate_limit", False):
        entrada["rate_limit"] = False
        logger.info("[v90][SOURCE_QUALITY] Dominio=%s rate_limit limpo apos sucesso", dominio)

    _salvar_dados(dados)
    logger.info("[v90][SOURCE_QUALITY] Sucesso registrado: dominio=%s metodo=%s total_sucessos=%d",
                dominio, metodo, sucessos_atual)


def registrar_falha(dominio: str, erro: str) -> None:
    """
    Registra uma falha de coleta para o domínio.
    Atualiza contador de falhas, última falha e ativa cooldown se necessário.
    """
    if not dominio or not isinstance(dominio, str):
        logger.warning("[v90][SOURCE_QUALITY] Dominio invalido: %r", dominio)
        return

    erro = erro.strip() if erro and isinstance(erro, str) else "erro_desconhecido"
    dados = _carregar_dados()
    entrada = _garantir_entrada(dados, dominio)

    entrada["falhas"] = safe_get(entrada, "falhas", 0) + 1
    entrada["ultima_falha"] = f"{_agora_iso()} | {erro}"

    # Se falhas consecutivas >= 5, ativar cooldown automático de 10 min
    falhas_atual = safe_get(entrada, "falhas", 0)
    if falhas_atual >= 5:
        cooldown_ate = (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat()
        entrada["cooldown_ate"] = cooldown_ate
        logger.warning("[v90][SOURCE_QUALITY] Dominio=%s atingiu %d falhas, cooldown auto 10min ate %s",
                       dominio, falhas_atual, cooldown_ate)

    _salvar_dados(dados)
    logger.info("[v90][SOURCE_QUALITY] Falha registrada: dominio=%s erro=%r total_falhas=%d",
                dominio, erro, falhas_atual)


def esta_em_cooldown(dominio: str) -> bool:
    """
    Verifica se o domínio está em cooldown.
    """
    if not dominio or not isinstance(dominio, str):
        return False

    dados = _carregar_dados()
    entrada = safe_get(dados, dominio)
    if not entrada:
        return False

    cooldown_ate_str = safe_get(entrada, "cooldown_ate", "")
    if not cooldown_ate_str:
        return False

    try:
        # Parse ISO format
        cooldown_ate = datetime.fromisoformat(cooldown_ate_str.replace("Z", "+00:00"))
        agora = datetime.now(timezone.utc)
        em_cooldown = agora < cooldown_ate
        if em_cooldown:
            restante = (cooldown_ate - agora).total_seconds()
            logger.info("[v90][SOURCE_QUALITY] Dominio=%s em cooldown, restam %.0fs",
                        dominio, restante)
        return em_cooldown
    except (ValueError, TypeError) as e:
        logger.error("[v90][SOURCE_QUALITY] Erro ao parse cooldown para %s: %s", dominio, e)
        return False


def definir_cooldown(dominio: str, segundos: int = 300) -> None:
    """
    Define manualmente um cooldown para o domínio.
    Padrão: 300 segundos (5 minutos).
    """
    if not dominio or not isinstance(dominio, str):
        logger.warning("[v90][SOURCE_QUALITY] Dominio invalido: %r", dominio)
        return

    if not isinstance(segundos, int) or segundos < 0:
        segundos = 300

    dados = _carregar_dados()
    entrada = _garantir_entrada(dados, dominio)

    cooldown_ate = (datetime.now(timezone.utc) + timedelta(seconds=segundos)).isoformat()
    entrada["cooldown_ate"] = cooldown_ate

    _salvar_dados(dados)
    logger.info("[v90][SOURCE_QUALITY] Cooldown definido: dominio=%s segundos=%d ate=%s",
                dominio, segundos, cooldown_ate)


def obter_melhor_metodo(dominio: str) -> str:
    """
    Retorna o melhor método registrado para o domínio.
    Retorna string vazia se não houver registro.
    """
    if not dominio or not isinstance(dominio, str):
        return ""

    dados = _carregar_dados()
    entrada = safe_get(dados, dominio)
    if not entrada:
        return ""

    melhor = safe_get(entrada, "melhor_metodo", "")
    logger.info("[v90][SOURCE_QUALITY] Melhor metodo para %s: %r", dominio, melhor)
    return melhor


def reduzir_prioridade(dominio: str) -> None:
    """
    Reduz a prioridade de um domínio aumentando o cooldown e marcando rate_limit.
    """
    if not dominio or not isinstance(dominio, str):
        logger.warning("[v90][SOURCE_QUALITY] Dominio invalido: %r", dominio)
        return

    dados = _carregar_dados()
    entrada = _garantir_entrada(dados, dominio)

    # Aumentar cooldown para 15 minutos
    cooldown_ate = (datetime.now(timezone.utc) + timedelta(seconds=900)).isoformat()
    entrada["cooldown_ate"] = cooldown_ate
    entrada["rate_limit"] = True

    _salvar_dados(dados)
    logger.warning("[v90][SOURCE_QUALITY] Prioridade reduzida: dominio=%s cooldown=15min rate_limit=True",
                   dominio)
