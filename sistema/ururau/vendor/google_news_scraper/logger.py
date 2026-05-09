"""Structured logging setup for the scraper."""

from __future__ import annotations

import logging
import os

LOG_FORMAT = "[%(asctime)s] %(name)s %(levelname)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a logger with a stream handler.

    Log level is controlled by the env var ``GOOGLE_NEWS_SCRAPER_LOG_LEVEL``
    (default: ``INFO``).
    """
    logger = logging.getLogger(name)
    level_name = os.environ.get("GOOGLE_NEWS_SCRAPER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        logger.addHandler(handler)

    return logger
