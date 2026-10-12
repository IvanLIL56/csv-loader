"""
Модуль настройки логирования.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path


def setup_logging(level_str: str, log_dir: Path | None = None) -> Path:
    """Настраивает систему логирования."""
    if log_dir is None:
        log_dir = Path("logs")

    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"loader_{timestamp}.log"

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_level = getattr(logging, level_str.upper(), logging.INFO)
    console_handler.setLevel(console_level)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Запуск приложения")
    logger.info("Лог-файл: %s", log_file)
    logger.info("=" * 60)

    return log_file