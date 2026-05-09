"""Logging configuravel para o google_news_scraper."""

import logging
import sys


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Retorna um logger configurado com formato padrao.

    Formato: [%(asctime)s] [%(name)s] %(levelname)s: %(message)s
    Saida: stderr
    """
    logger = logging.getLogger(name)

    # Evita adicionar handlers duplicados
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Evita propagacao para o logger raiz
    logger.propagate = False

    return logger
